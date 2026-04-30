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

from app.common.structuredLogger import writeJsonlEvent
from app.config.settingsModels import SchedulerJobSettings, SchedulerSettings, LoggingSettings


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
    in_runInternalCallable: Callable[[str, str], tuple[str, str]]
    in_onRunCompletedCallable: Callable[[str, str, str, str], None] | None = None
    in_timeZoneName: str = "UTC"
    in_nowUnixTsProvider: Callable[[], int] = lambda: int(time())
    in_sleepCallable: Callable[[float], None] = lambda seconds: Event().wait(seconds)

    def __post_init__(self) -> None:
        self._stopEvent = Event()
        self._lock = Lock()
        self._runningJobs: set[str] = set()
        self._statePath = Path(self.in_dataRootPath) / "scheduler" / "jobs_state.json"
        self._state = _loadJsonOrEmpty(in_path=self._statePath)
        try:
            self._timeZoneInfo = ZoneInfo(str(self.in_timeZoneName or "UTC"))
            self._timeZoneNameNormalized = str(self.in_timeZoneName or "UTC")
        except Exception:
            self._timeZoneInfo = ZoneInfo("UTC")
            self._timeZoneNameNormalized = "UTC"
        writeJsonlEvent(
            in_loggingSettings=self.in_loggingSettings,
            in_eventType="scheduler_runner_initialized",
            in_payload={
                "statePath": str(self._statePath),
                "loadedStateJobCount": len(self._state),
                "tickSeconds": int(self.in_schedulerSettings.tickSeconds),
                "jobCount": len(self.in_schedulerSettings.jobs),
                "timeZoneName": self._timeZoneNameNormalized,
            },
        )

    def stop(self) -> None:
        self._stopEvent.set()

    def runForever(self) -> None:
        tickSeconds = int(self.in_schedulerSettings.tickSeconds)
        if tickSeconds < 1:
            tickSeconds = 1
        writeJsonlEvent(
            in_loggingSettings=self.in_loggingSettings,
            in_eventType="scheduler_started",
            in_payload={
                "jobCount": len(self.in_schedulerSettings.jobs),
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
        nowTs = int(self.in_nowUnixTsProvider())
        for job in list(self.in_schedulerSettings.jobs):
            if job.enabled is not True:
                continue
            dueInfo = self._buildDueInfo(in_job=job, in_nowUnixTs=nowTs)
            if dueInfo["isDue"] is False:
                if str(dueInfo["reason"]) == "hour_window_blocked":
                    hourWindow = dueInfo.get("hourWindow", {})
                    if isinstance(hourWindow, dict) and str(hourWindow.get("reason")) == "window_misconfigured":
                        writeJsonlEvent(
                            in_loggingSettings=self.in_loggingSettings,
                            in_eventType="scheduler_job_skipped",
                            in_payload={
                                "jobId": job.jobId,
                                "reason": "window_misconfigured",
                                "details": dueInfo,
                            },
                        )
                continue
            writeJsonlEvent(
                in_loggingSettings=self.in_loggingSettings,
                in_eventType="scheduler_job_due",
                in_payload={
                    "jobId": job.jobId,
                    "details": dueInfo,
                },
            )
            self._runJobIfNotRunning(in_job=job, in_nowUnixTs=nowTs)
    def _buildDueInfo(self, in_job: SchedulerJobSettings, in_nowUnixTs: int) -> dict[str, Any]:
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
        stateKey = in_job.jobId
        lastRunAt = int(self._state.get(stateKey, {}).get("lastRunAtUnixTs", 0))
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
            # Wrap-around window, e.g. 23..2
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

    def _runJobIfNotRunning(self, in_job: SchedulerJobSettings, in_nowUnixTs: int) -> None:
        with self._lock:
            if in_job.jobId in self._runningJobs:
                writeJsonlEvent(
                    in_loggingSettings=self.in_loggingSettings,
                    in_eventType="scheduler_job_skipped",
                    in_payload={
                        "jobId": in_job.jobId,
                        "reason": "already_running",
                    },
                )
                return
            self._runningJobs.add(in_job.jobId)
        try:
            self._runJob(in_job=in_job, in_nowUnixTs=in_nowUnixTs)
        finally:
            with self._lock:
                self._runningJobs.discard(in_job.jobId)

    def _runJob(self, in_job: SchedulerJobSettings, in_nowUnixTs: int) -> None:
        stateKey = in_job.jobId
        prev = self._state.get(stateKey, {}) if isinstance(self._state.get(stateKey), dict) else {}
        startedAtUnixTs = int(in_nowUnixTs)
        self._state[stateKey] = {**prev, "lastStartedAtUnixTs": startedAtUnixTs}
        _atomicWriteJson(in_path=self._statePath, in_data=self._state)

        sessionId = str(in_job.actionInternalRun.sessionId)
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
            runId, finalAnswer = self.in_runInternalCallable(sessionId, message)
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
                self.in_onRunCompletedCallable(in_job.jobId, sessionId, runId, finalAnswer)
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
        self._state[stateKey] = {
            **(self._state.get(stateKey, {}) if isinstance(self._state.get(stateKey), dict) else {}),
            "lastRunAtUnixTs": finishedAtUnixTs,
            "lastFinishedAtUnixTs": finishedAtUnixTs,
            "lastStatus": statusValue,
            "lastError": errorText,
            "lastRunId": runId,
        }
        _atomicWriteJson(in_path=self._statePath, in_data=self._state)
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

