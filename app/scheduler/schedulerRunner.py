import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from threading import Event, Lock
from time import monotonic, time
from typing import Any, Callable

import requests
from pydantic import ValidationError
from zoneinfo import ZoneInfo

from app.common.adminTenantConfigPaths import resolveAdminTenantSchedulesYamlPath
from app.common.schedulerSessionId import normalizeScheduledInternalSessionId
from app.common.structuredLogger import writeJsonlEvent
from app.config.settingsModels import (
    LoggingSettings,
    ReminderModel,
    SchedulerJobSettings,
    SchedulerSettings,
)
from app.config.tenantSchedulesModels import (
    ScheduledTaskInternalRun,
    ScheduledTaskTelegramMessage,
)
from app.reminders.reminderService import ReminderService
from app.scheduler.tenantSchedulesLoader import (
    LoadedTenantSchedule,
    discoverTenantScheduleFiles,
    loadTenantScheduleFile,
    snapshotTenantFileMtimes,
    tenantSnapshotChanged,
)


def _atomicWriteJson(in_path: Path, in_data: dict[str, Any]) -> None:
    in_path.parent.mkdir(parents=True, exist_ok=True)
    tmpPath = in_path.with_suffix(in_path.suffix + ".tmp")
    tmpPath.write_text(json.dumps(in_data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmpPath, in_path)


def _loadJsonOrEmpty(in_path: Path) -> dict[str, Any]:
    ret: dict[str, Any]
    if in_path.exists() is False:
        ret = {}
    else:
        try:
            loaded = json.loads(in_path.read_text(encoding="utf-8"))
            ret = loaded if isinstance(loaded, dict) else {}
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            ret = {}
    return ret


@dataclass
class SchedulerRunner:
    in_schedulerSettings: SchedulerSettings
    in_loggingSettings: LoggingSettings
    in_dataRootPath: str
    in_memoryRootPath: str
    in_adminTelegramUserId: int
    in_runInternalCallable: Callable[[str, str, str], tuple[str, str]]
    in_onRunCompletedCallable: Callable[[str, str, str, str, str], None] | None = None
    in_onReminderTriggeredCallable: Callable[[str, str, str], None] | None = None
    in_onReminderCompletedCallable: Callable[[str, str], bool] | None = None
    in_timeZoneName: str = "UTC"
    in_nowUnixTsProvider: Callable[[], int] = lambda: int(time())
    in_sleepCallable: Callable[[float], None] = lambda seconds: Event().wait(seconds)

    def __post_init__(self) -> None:
        self._stopEvent = Event()
        self._lock = Lock()
        self._runningJobs: set[str] = set()
        self._statePath = Path(self.in_dataRootPath) / "scheduler" / "jobs_state.json"
        loadedState = _loadJsonOrEmpty(in_path=self._statePath)
        self._state = self._normalizeStateFromDisk(in_loadedState=loadedState)
        self._persistState()

        self._tenantFileSnapshots: dict[str, int] = {}
        self._tenantSchedules: list[LoadedTenantSchedule] = []
        self._schedulesConfigPath = resolveAdminTenantSchedulesYamlPath(
            in_memoryRootPath=self.in_memoryRootPath,
            in_adminTelegramUserId=int(self.in_adminTelegramUserId),
        ).resolve()
        try:
            self._timeZoneInfo = ZoneInfo(str(self.in_timeZoneName or "UTC"))
            self._timeZoneNameNormalized = str(self.in_timeZoneName or "UTC")
        except Exception:
            self._timeZoneInfo = ZoneInfo("UTC")
            self._timeZoneNameNormalized = "UTC"
        self._reminderService = ReminderService(
            in_defaultTimeZoneName=self._timeZoneNameNormalized
        )
        self._reloadTenantSchedulesIfChanged()
        internal_n, telegram_n = self._countTasks()
        writeJsonlEvent(
            in_loggingSettings=self.in_loggingSettings,
            in_eventType="scheduler_runner_initialized",
            in_payload={
                "statePath": str(self._statePath),
                "tickSeconds": int(self.in_schedulerSettings.tickSeconds),
                "internalRunTaskCount": internal_n,
                "telegramMessageTaskCount": telegram_n,
                "timeZoneName": self._timeZoneNameNormalized,
                "memoryRootPath": str(Path(self.in_memoryRootPath).resolve()),
                "adminTenantSchedulesYamlPath": str(self._schedulesConfigPath),
            },
        )

    def _normalizeStateFromDisk(self, in_loadedState: dict[str, Any]) -> dict[str, Any]:
        ret: dict[str, Any]
        existing_tasks = in_loadedState.get("tasksState")
        if isinstance(existing_tasks, dict) is True and len(existing_tasks) > 0:
            ret = {"tasksState": dict(existing_tasks)}
            return ret
        tasks_merged: dict[str, Any] = {}
        admin_seg = f"telegramUser_{int(self.in_adminTelegramUserId)}"
        js = in_loadedState.get("jobsState", {})
        if isinstance(js, dict) is True:
            for key, value in js.items():
                composite = f"{admin_seg}::{key}"
                tasks_merged[composite] = value if isinstance(value, dict) else {}
        rs = in_loadedState.get("remindersState", {})
        if isinstance(rs, dict) is True:
            for key, value in rs.items():
                composite = f"{admin_seg}::{key}"
                tasks_merged[composite] = value if isinstance(value, dict) else {}
        ret = {"tasksState": tasks_merged}
        return ret

    def _getTasksState(self) -> dict[str, Any]:
        ret: dict[str, Any]
        value = self._state.get("tasksState", {})
        ret = value if isinstance(value, dict) else {}
        return ret

    def _countTasks(self) -> tuple[int, int]:
        internal_n = 0
        telegram_n = 0
        for loaded in self._tenantSchedules:
            for task in loaded.document.scheduledTasks:
                if isinstance(task, ScheduledTaskInternalRun) is True:
                    internal_n += 1
                elif isinstance(task, ScheduledTaskTelegramMessage) is True:
                    telegram_n += 1
        ret = (internal_n, telegram_n)
        return ret

    def stop(self) -> None:
        self._stopEvent.set()

    def runForever(self) -> None:
        tickSeconds = int(self.in_schedulerSettings.tickSeconds)
        if tickSeconds < 1:
            tickSeconds = 1
        internal_n, telegram_n = self._countTasks()
        writeJsonlEvent(
            in_loggingSettings=self.in_loggingSettings,
            in_eventType="scheduler_started",
            in_payload={
                "internalRunTaskCount": internal_n,
                "telegramMessageTaskCount": telegram_n,
                "tickSeconds": tickSeconds,
                "statePath": str(self._statePath),
            },
        )
        try:
            while self._stopEvent.is_set() is False:
                startedAt = monotonic()
                self._tickOnce()
                elapsed = monotonic() - startedAt
                sleepFor = float(tickSeconds) - elapsed
                if sleepFor < 0.05:
                    sleepFor = 0.05
                self.in_sleepCallable(sleepFor)
        finally:
            writeJsonlEvent(
                in_loggingSettings=self.in_loggingSettings,
                in_eventType="scheduler_stopped",
                in_payload={},
            )

    def _tickOnce(self) -> None:
        self._reloadTenantSchedulesIfChanged()
        nowTs = int(self.in_nowUnixTsProvider())
        for loaded in list(self._tenantSchedules):
            for raw_task in list(loaded.document.scheduledTasks):
                if isinstance(raw_task, ScheduledTaskInternalRun) is False:
                    continue
                if raw_task.enabled is not True:
                    continue
                job_model = SchedulerJobSettings(
                    jobId=raw_task.taskId,
                    enabled=raw_task.enabled,
                    schedule=raw_task.schedule,
                    actionInternalRun=raw_task.internalRun,
                )
                state_key = f"{loaded.ownerSanitizedSegment}::{raw_task.taskId}"
                run_lock_key = state_key
                dueInfo = self._buildDueInfo(
                    in_job=job_model,
                    in_nowUnixTs=nowTs,
                    in_state_key=state_key,
                )
                if dueInfo["isDue"] is False:
                    if str(dueInfo["reason"]) == "hour_window_blocked":
                        hourWindow = dueInfo.get("hourWindow", {})
                        if (
                            isinstance(hourWindow, dict) is True
                            and str(hourWindow.get("reason")) == "window_misconfigured"
                        ):
                            writeJsonlEvent(
                                in_loggingSettings=self.in_loggingSettings,
                                in_eventType="scheduler_job_skipped",
                                in_payload={
                                    "jobId": raw_task.taskId,
                                    "reason": "window_misconfigured",
                                    "details": dueInfo,
                                },
                            )
                    continue
                writeJsonlEvent(
                    in_loggingSettings=self.in_loggingSettings,
                    in_eventType="scheduler_job_due",
                    in_payload={
                        "jobId": raw_task.taskId,
                        "tenant": loaded.ownerSanitizedSegment,
                        "details": dueInfo,
                    },
                )
                self._runJobIfNotRunning(
                    in_job=job_model,
                    in_state_key=state_key,
                    in_run_lock_key=run_lock_key,
                    in_owner_memory_principal_id=loaded.ownerMemoryPrincipalId,
                    in_scope_telegram_user_id=int(loaded.telegramUserId),
                    in_now_unix_ts=nowTs,
                )
        self._processReminders(in_now_unix_ts=nowTs)

    def _reloadTenantSchedulesIfChanged(self) -> None:
        paths = discoverTenantScheduleFiles(in_memoryRootPath=self.in_memoryRootPath)
        snapshot = snapshotTenantFileMtimes(in_paths=paths)
        if tenantSnapshotChanged(
            in_previous=self._tenantFileSnapshots,
            in_current=snapshot,
        ) is False:
            return
        self._tenantFileSnapshots = snapshot
        loaded_list: list[LoadedTenantSchedule] = []
        for path in paths:
            item = loadTenantScheduleFile(in_path=path)
            if item is not None:
                loaded_list.append(item)
        self._tenantSchedules = loaded_list
        internal_n, telegram_n = self._countTasks()
        writeJsonlEvent(
            in_loggingSettings=self.in_loggingSettings,
            in_eventType="scheduler_tenant_schedules_reloaded",
            in_payload={
                "tenantFileCount": len(paths),
                "internalRunTaskCount": internal_n,
                "telegramMessageTaskCount": telegram_n,
            },
        )

    def _persistState(self) -> None:
        _atomicWriteJson(in_path=self._statePath, in_data=self._state)

    def _buildDueInfo(
        self,
        in_job: SchedulerJobSettings,
        in_nowUnixTs: int,
        in_state_key: str,
    ) -> dict[str, Any]:
        ret: dict[str, Any]
        allowedInfo = self._buildHourWindowInfo(in_job=in_job, in_nowUnixTs=in_nowUnixTs)
        if allowedInfo["isAllowed"] is False:
            ret = {
                "isDue": False,
                "reason": "hour_window_blocked",
                "hourWindow": allowedInfo,
            }
            return ret
        intervalSeconds = int(in_job.schedule.intervalSeconds)
        if intervalSeconds < 5:
            intervalSeconds = 5
        tasks_state = self._getTasksState()
        lastRunAt = int(tasks_state.get(in_state_key, {}).get("lastRunAtUnixTs", 0))
        sinceLastRun = in_nowUnixTs - lastRunAt if lastRunAt > 0 else -1
        secondsRemaining = (
            intervalSeconds - sinceLastRun if lastRunAt > 0 and sinceLastRun < intervalSeconds else 0
        )
        if lastRunAt <= 0:
            ret = {
                "isDue": True,
                "reason": "first_run",
                "intervalSeconds": intervalSeconds,
                "lastRunAtUnixTs": lastRunAt,
                "sinceLastRunSeconds": sinceLastRun,
                "secondsRemaining": 0,
            }
        elif sinceLastRun >= intervalSeconds:
            ret = {
                "isDue": True,
                "reason": "interval_elapsed",
                "intervalSeconds": intervalSeconds,
                "lastRunAtUnixTs": lastRunAt,
                "sinceLastRunSeconds": sinceLastRun,
                "secondsRemaining": 0,
            }
        else:
            ret = {
                "isDue": False,
                "reason": "interval_not_elapsed",
                "intervalSeconds": intervalSeconds,
                "lastRunAtUnixTs": lastRunAt,
                "sinceLastRunSeconds": sinceLastRun,
                "secondsRemaining": secondsRemaining,
            }
        return ret

    def _buildHourWindowInfo(self, in_job: SchedulerJobSettings, in_nowUnixTs: int) -> dict[str, Any]:
        ret: dict[str, Any]
        startHour = in_job.schedule.allowedHourStart
        endHour = in_job.schedule.allowedHourEnd
        currentHour = int(datetime.fromtimestamp(in_nowUnixTs, tz=self._timeZoneInfo).hour)
        if startHour is None and endHour is None:
            ret = {
                "isAllowed": True,
                "reason": "no_window",
                "currentHour": currentHour,
                "allowedHourStart": startHour,
                "allowedHourEnd": endHour,
                "timeZoneName": self._timeZoneNameNormalized,
            }
            return ret
        if startHour is None or endHour is None:
            ret = {
                "isAllowed": False,
                "reason": "window_misconfigured",
                "currentHour": currentHour,
                "allowedHourStart": startHour,
                "allowedHourEnd": endHour,
                "timeZoneName": self._timeZoneNameNormalized,
            }
            return ret
        if startHour <= endHour:
            isAllowed = startHour <= currentHour <= endHour
        else:
            isAllowed = currentHour >= startHour or currentHour <= endHour
        ret = {
            "isAllowed": isAllowed,
            "reason": "inside_window" if isAllowed is True else "outside_window",
            "currentHour": currentHour,
            "allowedHourStart": startHour,
            "allowedHourEnd": endHour,
            "timeZoneName": self._timeZoneNameNormalized,
        }
        return ret

    def _runJobIfNotRunning(
        self,
        in_job: SchedulerJobSettings,
        in_state_key: str,
        in_run_lock_key: str,
        in_owner_memory_principal_id: str,
        in_scope_telegram_user_id: int,
        in_now_unix_ts: int,
    ) -> None:
        with self._lock:
            if in_run_lock_key in self._runningJobs:
                writeJsonlEvent(
                    in_loggingSettings=self.in_loggingSettings,
                    in_eventType="scheduler_job_skipped",
                    in_payload={
                        "jobId": in_job.jobId,
                        "reason": "already_running",
                    },
                )
                return
            self._runningJobs.add(in_run_lock_key)
        try:
            self._runJob(
                in_job=in_job,
                in_state_key=in_state_key,
                in_owner_memory_principal_id=in_owner_memory_principal_id,
                in_scope_telegram_user_id=in_scope_telegram_user_id,
                in_now_unix_ts=in_now_unix_ts,
            )
        finally:
            with self._lock:
                self._runningJobs.discard(in_run_lock_key)

    def _runJob(
        self,
        in_job: SchedulerJobSettings,
        in_state_key: str,
        in_owner_memory_principal_id: str,
        in_scope_telegram_user_id: int,
        in_now_unix_ts: int,
    ) -> None:
        tasks_state = self._getTasksState()
        prev = tasks_state.get(in_state_key, {}) if isinstance(tasks_state.get(in_state_key), dict) else {}
        startedAtUnixTs = int(in_now_unix_ts)
        tasks_state[in_state_key] = {**prev, "lastStartedAtUnixTs": startedAtUnixTs}
        self._state["tasksState"] = tasks_state
        self._persistState()

        sessionId = normalizeScheduledInternalSessionId(
            in_sessionId=str(in_job.actionInternalRun.sessionId),
            in_scopeTelegramUserId=int(in_scope_telegram_user_id),
        )
        message = str(in_job.actionInternalRun.message)
        writeJsonlEvent(
            in_loggingSettings=self.in_loggingSettings,
            in_eventType="scheduler_job_started",
            in_payload={
                "jobId": in_job.jobId,
                "sessionId": sessionId,
                "messageChars": len(message),
                "startedAtUnixTs": startedAtUnixTs,
            },
        )
        statusValue = "ok"
        errorText = ""
        runId = ""
        finalAnswer = ""
        try:
            runId, finalAnswer = self.in_runInternalCallable(
                sessionId,
                message,
                str(in_owner_memory_principal_id or ""),
            )
            runId = str(runId)
            finalAnswer = str(finalAnswer)
            writeJsonlEvent(
                in_loggingSettings=self.in_loggingSettings,
                in_eventType="scheduler_job_internal_run_dispatched",
                in_payload={
                    "jobId": in_job.jobId,
                    "sessionId": sessionId,
                    "runId": runId,
                    "finalAnswerChars": len(finalAnswer),
                },
            )
            if self.in_onRunCompletedCallable is not None:
                self.in_onRunCompletedCallable(
                    in_job.jobId,
                    sessionId,
                    runId,
                    finalAnswer,
                    str(in_owner_memory_principal_id or ""),
                )
                writeJsonlEvent(
                    in_loggingSettings=self.in_loggingSettings,
                    in_eventType="scheduler_job_notification_dispatched",
                    in_payload={
                        "jobId": in_job.jobId,
                        "sessionId": sessionId,
                        "runId": runId,
                    },
                )
        except (ValidationError, OSError, json.JSONDecodeError, requests.RequestException) as in_exc:
            statusValue = "error"
            errorText = str(in_exc)
            writeJsonlEvent(
                in_loggingSettings=self.in_loggingSettings,
                in_eventType="scheduler_job_internal_run_error",
                in_payload={
                    "jobId": in_job.jobId,
                    "sessionId": sessionId,
                    "error": errorText,
                    "errorType": type(in_exc).__name__,
                },
            )
        except Exception as in_exc:
            statusValue = "error"
            errorText = f"{type(in_exc).__name__}: {in_exc}"
            writeJsonlEvent(
                in_loggingSettings=self.in_loggingSettings,
                in_eventType="scheduler_job_internal_run_error",
                in_payload={
                    "jobId": in_job.jobId,
                    "sessionId": sessionId,
                    "error": errorText,
                    "errorType": type(in_exc).__name__,
                },
            )
        finishedAtUnixTs = int(self.in_nowUnixTsProvider())
        tasks_state = self._getTasksState()
        tasks_state[in_state_key] = {
            **(tasks_state.get(in_state_key, {}) if isinstance(tasks_state.get(in_state_key), dict) else {}),
            "lastRunAtUnixTs": finishedAtUnixTs,
            "lastFinishedAtUnixTs": finishedAtUnixTs,
            "lastStatus": statusValue,
            "lastError": errorText,
            "lastRunId": runId,
        }
        self._state["tasksState"] = tasks_state
        self._persistState()
        writeJsonlEvent(
            in_loggingSettings=self.in_loggingSettings,
            in_eventType="scheduler_job_finished",
            in_payload={
                "jobId": in_job.jobId,
                "status": statusValue,
                "runId": runId,
                "error": errorText,
            },
        )

    def _processReminders(self, in_now_unix_ts: int) -> None:
        reminders_state = self._getTasksState()
        did_state_change = False
        for loaded in list(self._tenantSchedules):
            for task in list(loaded.document.scheduledTasks):
                if isinstance(task, ScheduledTaskTelegramMessage) is False:
                    continue
                if task.enabled is not True:
                    continue
                reminder_id_value = str(task.taskId or "").strip()
                if reminder_id_value == "":
                    continue
                composite_key = f"{loaded.ownerSanitizedSegment}::{reminder_id_value}"
                reminder_item = ReminderModel(
                    reminderId=reminder_id_value,
                    enabled=task.enabled,
                    message=task.message,
                    ownerMemoryPrincipalId=loaded.ownerMemoryPrincipalId,
                    schedule=task.schedule,
                    createdAtUnixTs=task.createdAtUnixTs,
                    lastFiredAtUnixTs=task.lastFiredAtUnixTs,
                    nextFireAtUnixTs=task.nextFireAtUnixTs,
                )
                one_state_raw = reminders_state.get(composite_key, {})
                one_state = one_state_raw if isinstance(one_state_raw, dict) else {}
                evaluation = self._reminderService.evaluateReminder(
                    in_reminder=reminder_item,
                    in_state=one_state,
                    in_nowUnixTs=int(in_now_unix_ts),
                )
                merged_state = {
                    **one_state,
                    "nextFireAtUnixTs": evaluation.get("nextFireAtUnixTs"),
                    "remainingRuns": evaluation.get("remainingRuns"),
                    "enabled": evaluation.get("isEnabled"),
                }
                if merged_state != one_state:
                    reminders_state[composite_key] = merged_state
                    did_state_change = True
                if evaluation.get("isDue") is not True:
                    continue
                if self.in_onReminderTriggeredCallable is None:
                    continue
                try:
                    self.in_onReminderTriggeredCallable(
                        reminder_id_value,
                        str(task.message or ""),
                        str(loaded.ownerMemoryPrincipalId or ""),
                    )
                    updated_state = self._reminderService.markReminderSent(
                        in_reminder=reminder_item,
                        in_state=reminders_state.get(composite_key, {}),
                        in_nowUnixTs=int(in_now_unix_ts),
                    )
                    reminders_state[composite_key] = updated_state
                    did_state_change = True
                    writeJsonlEvent(
                        in_loggingSettings=self.in_loggingSettings,
                        in_eventType="scheduler_reminder_triggered",
                        in_payload={
                            "reminderId": reminder_id_value,
                            "nextFireAtUnixTs": updated_state.get("nextFireAtUnixTs"),
                            "remainingRuns": updated_state.get("remainingRuns"),
                            "enabled": updated_state.get("enabled"),
                        },
                    )
                    should_remove = (
                        isinstance(updated_state.get("remainingRuns"), int) is True
                        and int(updated_state.get("remainingRuns")) == 0
                        and bool(updated_state.get("enabled")) is False
                    )
                    if should_remove is True and self.in_onReminderCompletedCallable is not None:
                        was_deleted = self.in_onReminderCompletedCallable(
                            reminder_id_value,
                            str(loaded.ownerMemoryPrincipalId or ""),
                        )
                        if was_deleted is True:
                            if composite_key in reminders_state:
                                del reminders_state[composite_key]
                                did_state_change = True
                            writeJsonlEvent(
                                in_loggingSettings=self.in_loggingSettings,
                                in_eventType="scheduler_reminder_removed",
                                in_payload={
                                    "reminderId": reminder_id_value,
                                    "reason": "remaining_runs_exhausted",
                                },
                            )
                        else:
                            writeJsonlEvent(
                                in_loggingSettings=self.in_loggingSettings,
                                in_eventType="scheduler_reminder_remove_error",
                                in_payload={
                                    "reminderId": reminder_id_value,
                                    "reason": "reminder_not_found_in_config",
                                },
                            )
                except requests.RequestException as in_exc:
                    writeJsonlEvent(
                        in_loggingSettings=self.in_loggingSettings,
                        in_eventType="scheduler_reminder_delivery_error",
                        in_payload={
                            "reminderId": reminder_id_value,
                            "error": str(in_exc),
                            "errorType": type(in_exc).__name__,
                        },
                    )
                except Exception as in_exc:
                    writeJsonlEvent(
                        in_loggingSettings=self.in_loggingSettings,
                        in_eventType="scheduler_reminder_delivery_error",
                        in_payload={
                            "reminderId": reminder_id_value,
                            "error": str(in_exc),
                            "errorType": type(in_exc).__name__,
                        },
                    )
        if did_state_change is True:
            self._state["tasksState"] = reminders_state
            self._persistState()
