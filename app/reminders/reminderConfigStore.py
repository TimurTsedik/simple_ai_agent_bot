import os
from pathlib import Path
from threading import Lock
from time import time
from typing import Any

import yaml

from app.common.ids import generateId
from app.config.settingsModels import ReminderModel, SchedulerSettings

_SCHEDULES_FILE_LOCK = Lock()


class ReminderConfigStore:
    def __init__(self, in_schedulesConfigPath: str) -> None:
        self._schedulesConfigPath = Path(in_schedulesConfigPath).resolve()

    def _readSchedulesData(self) -> dict[str, Any]:
        ret: dict[str, Any]
        rawData: Any = {}
        if self._schedulesConfigPath.exists() is True:
            loaded = yaml.safe_load(self._schedulesConfigPath.read_text(encoding="utf-8"))
            rawData = loaded if loaded is not None else {}
        if isinstance(rawData, dict) is False:
            rawData = {}
        ret = rawData
        return ret

    def _writeSchedulesData(self, in_data: dict[str, Any]) -> None:
        self._schedulesConfigPath.parent.mkdir(parents=True, exist_ok=True)
        tempPath = self._schedulesConfigPath.with_suffix(self._schedulesConfigPath.suffix + ".tmp")
        textValue = yaml.safe_dump(in_data, allow_unicode=True, sort_keys=False)
        tempPath.write_text(textValue, encoding="utf-8")
        os.replace(tempPath, self._schedulesConfigPath)

    def _validateAndNormalize(self, in_data: dict[str, Any]) -> dict[str, Any]:
        ret: dict[str, Any]
        parsedScheduler = SchedulerSettings.model_validate({"enabled": True, **in_data})
        ret = parsedScheduler.model_dump(exclude={"enabled", "tickSeconds", "schedulesConfigPath"})
        return ret

    def listReminders(self) -> list[ReminderModel]:
        ret: list[ReminderModel]
        with _SCHEDULES_FILE_LOCK:
            schedulesData = self._readSchedulesData()
        parsedScheduler = SchedulerSettings.model_validate({"enabled": True, **schedulesData})
        ret = list(parsedScheduler.reminders)
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
        in_reminderId: str = "",
    ) -> ReminderModel:
        ret: ReminderModel
        reminderIdValue = str(in_reminderId or "").strip()
        if reminderIdValue == "":
            reminderIdValue = f"reminder-{generateId()[:8]}"

        with _SCHEDULES_FILE_LOCK:
            schedulesData = self._readSchedulesData()
            parsedScheduler = SchedulerSettings.model_validate({"enabled": True, **schedulesData})
            reminderItems = list(parsedScheduler.reminders)
            nowUnixTs = int(time())
            targetReminder = ReminderModel(
                reminderId=reminderIdValue,
                enabled=bool(in_enabled),
                message=str(in_message or "").strip(),
                schedule={
                    "kind": str(in_scheduleKind or "daily"),
                    "weekdays": [int(item) for item in in_weekdays],
                    "timeLocal": str(in_timeLocal or "").strip(),
                    "timeZone": str(in_timeZone or "").strip(),
                    "remainingRuns": in_remainingRuns,
                },
                createdAtUnixTs=nowUnixTs,
            )
            normalizedItems: list[ReminderModel] = []
            didReplace = False
            for item in reminderItems:
                if item.reminderId == reminderIdValue:
                    updatedReminder = targetReminder.model_copy(
                        update={"createdAtUnixTs": item.createdAtUnixTs or nowUnixTs}
                    )
                    normalizedItems.append(updatedReminder)
                    didReplace = True
                else:
                    normalizedItems.append(item)
            if didReplace is False:
                normalizedItems.append(targetReminder)
            schedulesData["reminders"] = [
                item.model_dump(exclude_none=True) for item in normalizedItems
            ]
            normalizedData = self._validateAndNormalize(in_data=schedulesData)
            self._writeSchedulesData(in_data=normalizedData)
            ret = next(
                item for item in normalizedItems if item.reminderId == reminderIdValue
            )
        return ret

    def deleteReminder(self, in_reminderId: str) -> bool:
        ret: bool
        reminderIdValue = str(in_reminderId or "").strip()
        isDeleted = False
        with _SCHEDULES_FILE_LOCK:
            schedulesData = self._readSchedulesData()
            parsedScheduler = SchedulerSettings.model_validate({"enabled": True, **schedulesData})
            reminderItems = list(parsedScheduler.reminders)
            filteredItems = [item for item in reminderItems if item.reminderId != reminderIdValue]
            isDeleted = len(filteredItems) != len(reminderItems)
            if isDeleted is True:
                schedulesData["reminders"] = [
                    item.model_dump(exclude_none=True) for item in filteredItems
                ]
                normalizedData = self._validateAndNormalize(in_data=schedulesData)
                self._writeSchedulesData(in_data=normalizedData)
        ret = isDeleted
        return ret

