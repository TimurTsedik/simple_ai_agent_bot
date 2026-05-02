import os
from pathlib import Path
from threading import Lock
from time import time
from typing import Any

import yaml
from pydantic import ValidationError

from app.common.ids import generateId
from app.common.memoryPrincipal import (
    formatTelegramUserMemoryPrincipal,
    parseTelegramUserIdFromMemoryPrincipal,
)
from app.common.schedulerSessionId import sanitizeSchedulerSessionSlug
from app.config.settingsModels import MemorySettings
from app.config.settingsModels import ReminderModel
from app.config.settingsModels import SchedulerJobInternalRunAction
from app.config.settingsModels import SchedulerJobSchedule
from app.config.tenantSchedulesModels import (
    ScheduledTaskInternalRun,
    ScheduledTaskTelegramMessage,
    TenantSchedulesFile,
    normalizeLegacySchedulesDict,
)

_SCHEDULES_FILE_LOCK = Lock()


class ReminderConfigStore:
    """Чтение/запись только задач kind=telegram_message в tenant schedules.yaml."""

    def __init__(self, in_memorySettings: MemorySettings) -> None:
        self._memorySettings = in_memorySettings

    def _schedulesPathForPrincipal(self, in_memoryPrincipalId: str) -> Path:
        principal = str(in_memoryPrincipalId or "").strip()
        if principal == "":
            principal = formatTelegramUserMemoryPrincipal(in_telegramUserId=1)
        sanitized = principal.replace(":", "_")
        memory_root = Path(self._memorySettings.memoryRootPath)
        if memory_root.is_absolute() is False:
            memory_root = memory_root.resolve()
        ret = memory_root / "sessions" / sanitized / "schedules.yaml"
        return ret

    def _readSchedulesData(self, in_path: Path) -> dict[str, Any]:
        ret: dict[str, Any]
        rawData: Any = {}
        if in_path.exists() is True:
            loaded = yaml.safe_load(in_path.read_text(encoding="utf-8"))
            rawData = loaded if loaded is not None else {}
        if isinstance(rawData, dict) is False:
            rawData = {}
        ret = rawData
        return ret

    def _writeSchedulesData(self, in_path: Path, in_data: dict[str, Any]) -> None:
        in_path.parent.mkdir(parents=True, exist_ok=True)
        tempPath = in_path.with_suffix(in_path.suffix + ".tmp")
        textValue = yaml.safe_dump(in_data, allow_unicode=True, sort_keys=False)
        try:
            tempPath.write_text(textValue, encoding="utf-8")
            os.replace(tempPath, in_path)
        except PermissionError:
            in_path.write_text(textValue, encoding="utf-8")

    def _loadTenantDocument(self, in_path: Path) -> TenantSchedulesFile:
        ret: TenantSchedulesFile
        raw = self._readSchedulesData(in_path=in_path)
        merged = normalizeLegacySchedulesDict(in_data=raw)
        ret = TenantSchedulesFile.model_validate(merged)
        return ret

    def _dumpDocument(self, in_doc: TenantSchedulesFile) -> dict[str, Any]:
        ret: dict[str, Any]
        ret = {"scheduledTasks": [item.model_dump(exclude_none=True) for item in in_doc.scheduledTasks]}
        return ret

    def listReminders(self) -> list[ReminderModel]:
        ret: list[ReminderModel]
        ret = []
        return ret

    def listRemindersForOwner(
        self,
        in_ownerMemoryPrincipalId: str,
        in_adminMemoryPrincipalId: str,
    ) -> list[ReminderModel]:
        _ = in_adminMemoryPrincipalId
        ret: list[ReminderModel]
        path = self._schedulesPathForPrincipal(in_memoryPrincipalId=in_ownerMemoryPrincipalId)
        with _SCHEDULES_FILE_LOCK:
            try:
                doc = self._loadTenantDocument(in_path=path)
            except (ValidationError, OSError, yaml.YAMLError):
                ret = []
                return ret
        owner = str(in_ownerMemoryPrincipalId or "").strip()
        out: list[ReminderModel] = []
        for task in doc.scheduledTasks:
            if isinstance(task, ScheduledTaskTelegramMessage) is False:
                continue
            out.append(
                ReminderModel(
                    reminderId=task.taskId,
                    enabled=task.enabled,
                    message=task.message,
                    ownerMemoryPrincipalId=owner,
                    schedule=task.schedule,
                    createdAtUnixTs=task.createdAtUnixTs,
                    lastFiredAtUnixTs=task.lastFiredAtUnixTs,
                    nextFireAtUnixTs=task.nextFireAtUnixTs,
                )
            )
        ret = out
        return ret

    def listInternalRunTasksForOwner(self, in_ownerMemoryPrincipalId: str) -> list[dict[str, Any]]:
        ret: list[dict[str, Any]]
        path = self._schedulesPathForPrincipal(in_memoryPrincipalId=in_ownerMemoryPrincipalId)
        with _SCHEDULES_FILE_LOCK:
            try:
                doc = self._loadTenantDocument(in_path=path)
            except (ValidationError, OSError, yaml.YAMLError):
                ret = []
                return ret
        out: list[dict[str, Any]] = []
        for task in doc.scheduledTasks:
            if isinstance(task, ScheduledTaskInternalRun) is True:
                out.append(task.model_dump(exclude_none=True))
        ret = out
        return ret

    def addOrUpdateInternalRunTask(
        self,
        in_message: str,
        in_intervalSeconds: int,
        in_allowedHourStart: int | None,
        in_allowedHourEnd: int | None,
        in_enabled: bool,
        in_ownerMemoryPrincipalId: str,
        in_taskId: str = "",
        in_sessionSlug: str = "",
    ) -> dict[str, Any]:
        ret: dict[str, Any]
        owner = str(in_ownerMemoryPrincipalId or "").strip()
        owner_uid = parseTelegramUserIdFromMemoryPrincipal(in_memoryPrincipalId=owner)
        if owner_uid is None:
            raise ValueError("ownerMemoryPrincipalId must be telegramUser:<numeric_id>")
        task_id_value = str(in_taskId or "").strip()
        if task_id_value == "":
            task_id_value = f"recurring-job-{generateId()[:8]}"
        slug_source = str(in_sessionSlug or "").strip()
        if slug_source == "":
            slug_source = task_id_value
        slug_value = sanitizeSchedulerSessionSlug(in_raw=slug_source)
        principal_text = formatTelegramUserMemoryPrincipal(in_telegramUserId=int(owner_uid))
        session_id_value = f"{principal_text}:scheduler:{slug_value}"
        path = self._schedulesPathForPrincipal(in_memoryPrincipalId=owner)
        with _SCHEDULES_FILE_LOCK:
            doc = self._loadTenantDocument(in_path=path)
            kept_tasks: list[Any] = []
            for task in doc.scheduledTasks:
                if isinstance(task, ScheduledTaskInternalRun) is True:
                    if task.taskId == task_id_value:
                        continue
                    kept_tasks.append(task)
                elif isinstance(task, ScheduledTaskTelegramMessage) is True:
                    kept_tasks.append(task)
                else:
                    kept_tasks.append(task)
            interval_value = int(in_intervalSeconds)
            if interval_value < 60:
                interval_value = 60
            new_task = ScheduledTaskInternalRun(
                taskId=task_id_value,
                enabled=bool(in_enabled),
                schedule=SchedulerJobSchedule(
                    intervalSeconds=interval_value,
                    allowedHourStart=in_allowedHourStart,
                    allowedHourEnd=in_allowedHourEnd,
                ),
                internalRun=SchedulerJobInternalRunAction(
                    sessionId=session_id_value,
                    message=str(in_message or "").strip(),
                ),
            )
            merged_doc = TenantSchedulesFile(scheduledTasks=kept_tasks + [new_task])
            self._writeSchedulesData(in_path=path, in_data=self._dumpDocument(in_doc=merged_doc))
        ret = new_task.model_dump(exclude_none=True)
        return ret

    def addOrUpdateReminder(
        self,
        in_message: str,
        in_scheduleKind: str,
        in_timeLocal: str,
        in_timeZone: str,
        in_weekdays: list[int],
        in_remainingRuns: int | None,
        in_enabled: bool,
        in_ownerMemoryPrincipalId: str,
        in_reminderId: str = "",
    ) -> ReminderModel:
        ret: ReminderModel
        reminderIdValue = str(in_reminderId or "").strip()
        if reminderIdValue == "":
            reminderIdValue = f"reminder-{generateId()[:8]}"
        owner = str(in_ownerMemoryPrincipalId or "").strip()
        path = self._schedulesPathForPrincipal(in_memoryPrincipalId=owner)
        nowUnixTs = int(time())
        with _SCHEDULES_FILE_LOCK:
            doc = self._loadTenantDocument(in_path=path)
            kept_tasks: list[Any] = []
            previous_created: int | None = None
            for task in doc.scheduledTasks:
                if isinstance(task, ScheduledTaskTelegramMessage) is True:
                    if task.taskId == reminderIdValue:
                        previous_created = task.createdAtUnixTs
                        continue
                    kept_tasks.append(task)
                elif isinstance(task, ScheduledTaskInternalRun) is True:
                    kept_tasks.append(task)
                else:
                    kept_tasks.append(task)
            new_task = ScheduledTaskTelegramMessage(
                taskId=reminderIdValue,
                enabled=bool(in_enabled),
                message=str(in_message or "").strip(),
                schedule={
                    "kind": str(in_scheduleKind or "daily"),
                    "weekdays": [int(item) for item in in_weekdays],
                    "timeLocal": str(in_timeLocal or "").strip(),
                    "timeZone": str(in_timeZone or "").strip(),
                    "remainingRuns": in_remainingRuns,
                },
                createdAtUnixTs=previous_created or nowUnixTs,
            )
            merged_doc = TenantSchedulesFile(scheduledTasks=kept_tasks + [new_task])
            self._writeSchedulesData(in_path=path, in_data=self._dumpDocument(in_doc=merged_doc))
        ret = ReminderModel(
            reminderId=reminderIdValue,
            enabled=bool(in_enabled),
            message=str(in_message or "").strip(),
            ownerMemoryPrincipalId=owner,
            schedule={
                "kind": str(in_scheduleKind or "daily"),
                "weekdays": [int(item) for item in in_weekdays],
                "timeLocal": str(in_timeLocal or "").strip(),
                "timeZone": str(in_timeZone or "").strip(),
                "remainingRuns": in_remainingRuns,
            },
            createdAtUnixTs=nowUnixTs,
        )
        return ret

    def deleteReminderForOwner(
        self,
        in_reminderId: str,
        in_ownerMemoryPrincipalId: str,
        in_adminMemoryPrincipalId: str,
    ) -> bool:
        _ = in_adminMemoryPrincipalId
        ret: bool
        reminderIdValue = str(in_reminderId or "").strip()
        owner = str(in_ownerMemoryPrincipalId or "").strip()
        path = self._schedulesPathForPrincipal(in_memoryPrincipalId=owner)
        isDeleted = False
        with _SCHEDULES_FILE_LOCK:
            doc = self._loadTenantDocument(in_path=path)
            kept: list[Any] = []
            for task in doc.scheduledTasks:
                task_id_cmp = str(getattr(task, "taskId", "") or "").strip()
                if task_id_cmp == reminderIdValue:
                    isDeleted = True
                    continue
                kept.append(task)
            if isDeleted is True:
                merged_doc = TenantSchedulesFile(scheduledTasks=kept)
                self._writeSchedulesData(in_path=path, in_data=self._dumpDocument(in_doc=merged_doc))
        ret = isDeleted
        return ret

    def deleteReminderForTenant(
        self,
        in_reminderId: str,
        in_ownerMemoryPrincipalId: str,
    ) -> bool:
        ret: bool
        ret = self.deleteReminderForOwner(
            in_reminderId=in_reminderId,
            in_ownerMemoryPrincipalId=in_ownerMemoryPrincipalId,
            in_adminMemoryPrincipalId="",
        )
        return ret
