from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from app.config.settingsModels import ReminderModel


@dataclass
class ReminderService:
    in_defaultTimeZoneName: str = "UTC"

    def _resolveTimeZone(self, in_timeZoneName: str) -> ZoneInfo:
        ret: ZoneInfo
        resolvedZone: ZoneInfo
        zoneName = str(in_timeZoneName or "").strip()
        if zoneName == "":
            zoneName = str(self.in_defaultTimeZoneName or "UTC").strip()
        try:
            resolvedZone = ZoneInfo(zoneName)
        except Exception:
            resolvedZone = ZoneInfo("UTC")
        ret = resolvedZone
        return ret

    def _parseTimeLocal(self, in_timeLocal: str) -> tuple[int, int]:
        ret: tuple[int, int]
        hoursValue = 9
        minutesValue = 0
        rawValue = str(in_timeLocal or "").strip()
        parts = rawValue.split(":")
        isValid = len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit()
        if isValid is True:
            parsedHours = int(parts[0])
            parsedMinutes = int(parts[1])
            if 0 <= parsedHours <= 23 and 0 <= parsedMinutes <= 59:
                hoursValue = parsedHours
                minutesValue = parsedMinutes
        ret = (hoursValue, minutesValue)
        return ret

    def _resolveRemainingRuns(
        self,
        in_configRemainingRuns: int | None,
        in_stateRemainingRuns: Any,
    ) -> int | None:
        ret: int | None
        resolvedRemaining: int | None
        if isinstance(in_stateRemainingRuns, int):
            resolvedRemaining = int(in_stateRemainingRuns)
            if resolvedRemaining < 0:
                resolvedRemaining = 0
        else:
            resolvedRemaining = in_configRemainingRuns
        ret = resolvedRemaining
        return ret

    def _resolveEnabledFlag(self, in_configEnabled: bool, in_stateEnabled: Any) -> bool:
        ret: bool
        runtimeEnabled = in_configEnabled
        if isinstance(in_stateEnabled, bool):
            runtimeEnabled = runtimeEnabled and in_stateEnabled
        ret = runtimeEnabled
        return ret

    def _isWeekdayAllowed(self, in_kind: str, in_weekdays: list[int], in_weekday: int) -> bool:
        ret: bool
        kindValue = str(in_kind or "").strip().lower()
        normalizedWeekdays = sorted(set(x for x in in_weekdays if 0 <= int(x) <= 6))
        isAllowed = True
        if kindValue == "weekly":
            isAllowed = in_weekday in normalizedWeekdays
        ret = isAllowed
        return ret

    def _buildNextFireAtUnixTs(
        self,
        in_reminder: ReminderModel,
        in_nowUnixTs: int,
    ) -> int | None:
        ret: int | None
        timeZoneName = str(in_reminder.schedule.timeZone or "").strip()
        zoneInfo = self._resolveTimeZone(in_timeZoneName=timeZoneName)
        hoursValue, minutesValue = self._parseTimeLocal(in_timeLocal=in_reminder.schedule.timeLocal)
        nowLocal = datetime.fromtimestamp(int(in_nowUnixTs), tz=zoneInfo)
        kindValue = str(in_reminder.schedule.kind or "daily").strip().lower()
        weekdays = sorted(set(int(item) for item in in_reminder.schedule.weekdays if 0 <= int(item) <= 6))
        if kindValue not in {"daily", "weekly"}:
            kindValue = "daily"

        nextFireAt: int | None = None
        maxDaysToScan = 14
        dayOffset = 0
        while dayOffset <= maxDaysToScan:
            candidateDate = nowLocal.date() + timedelta(days=dayOffset)
            candidateLocal = datetime(
                year=candidateDate.year,
                month=candidateDate.month,
                day=candidateDate.day,
                hour=hoursValue,
                minute=minutesValue,
                tzinfo=zoneInfo,
            )
            isFuture = candidateLocal.timestamp() > int(in_nowUnixTs)
            if kindValue == "weekly":
                isWeekdayAllowed = candidateLocal.weekday() in weekdays
            else:
                isWeekdayAllowed = True
            if isFuture is True and isWeekdayAllowed is True:
                nextFireAt = int(candidateLocal.timestamp())
                break
            dayOffset += 1
        ret = nextFireAt
        return ret

    def evaluateReminder(
        self,
        in_reminder: ReminderModel,
        in_state: dict[str, Any],
        in_nowUnixTs: int,
    ) -> dict[str, Any]:
        ret: dict[str, Any]
        stateSnapshot = dict(in_state or {})
        lastFiredAtRaw = stateSnapshot.get("lastFiredAtUnixTs")
        lastFiredAtUnixTs = int(lastFiredAtRaw) if isinstance(lastFiredAtRaw, int) else None
        remainingRuns = self._resolveRemainingRuns(
            in_configRemainingRuns=in_reminder.schedule.remainingRuns,
            in_stateRemainingRuns=stateSnapshot.get("remainingRuns"),
        )
        isEnabled = self._resolveEnabledFlag(
            in_configEnabled=bool(in_reminder.enabled),
            in_stateEnabled=stateSnapshot.get("enabled"),
        )
        if isinstance(remainingRuns, int) and remainingRuns <= 0:
            isEnabled = False

        timeZoneName = str(in_reminder.schedule.timeZone or "").strip()
        zoneInfo = self._resolveTimeZone(in_timeZoneName=timeZoneName)
        hoursValue, minutesValue = self._parseTimeLocal(in_timeLocal=in_reminder.schedule.timeLocal)
        nowLocal = datetime.fromtimestamp(int(in_nowUnixTs), tz=zoneInfo)
        isTimeMatch = nowLocal.hour == hoursValue and nowLocal.minute == minutesValue
        isWeekdayAllowed = self._isWeekdayAllowed(
            in_kind=in_reminder.schedule.kind,
            in_weekdays=in_reminder.schedule.weekdays,
            in_weekday=nowLocal.weekday(),
        )
        currentSlotUnixTs = int(in_nowUnixTs) - (int(in_nowUnixTs) % 60)
        if isinstance(lastFiredAtUnixTs, int):
            lastSlotUnixTs = int(lastFiredAtUnixTs) - (int(lastFiredAtUnixTs) % 60)
        else:
            lastSlotUnixTs = -1
        isDuplicateInSameMinute = lastSlotUnixTs == currentSlotUnixTs
        isDue = (
            isEnabled is True
            and isTimeMatch is True
            and isWeekdayAllowed is True
            and isDuplicateInSameMinute is False
        )
        nextFireAtUnixTs = self._buildNextFireAtUnixTs(
            in_reminder=in_reminder,
            in_nowUnixTs=int(in_nowUnixTs),
        )
        ret = {
            "isDue": isDue,
            "isEnabled": isEnabled,
            "remainingRuns": remainingRuns,
            "nextFireAtUnixTs": nextFireAtUnixTs,
            "lastFiredAtUnixTs": lastFiredAtUnixTs,
        }
        return ret

    def markReminderSent(
        self,
        in_reminder: ReminderModel,
        in_state: dict[str, Any],
        in_nowUnixTs: int,
    ) -> dict[str, Any]:
        ret: dict[str, Any]
        stateSnapshot = dict(in_state or {})
        remainingRuns = self._resolveRemainingRuns(
            in_configRemainingRuns=in_reminder.schedule.remainingRuns,
            in_stateRemainingRuns=stateSnapshot.get("remainingRuns"),
        )
        if isinstance(remainingRuns, int):
            remainingRuns = max(0, remainingRuns - 1)
        if isinstance(remainingRuns, int):
            enabledValue = remainingRuns > 0
        else:
            enabledValue = self._resolveEnabledFlag(
                in_configEnabled=bool(in_reminder.enabled),
                in_stateEnabled=stateSnapshot.get("enabled"),
            )
        nextFireAtUnixTs = self._buildNextFireAtUnixTs(
            in_reminder=in_reminder,
            in_nowUnixTs=int(in_nowUnixTs),
        )
        ret = {
            **stateSnapshot,
            "lastFiredAtUnixTs": int(in_nowUnixTs),
            "nextFireAtUnixTs": nextFireAtUnixTs,
            "remainingRuns": remainingRuns,
            "enabled": enabledValue,
        }
        return ret

