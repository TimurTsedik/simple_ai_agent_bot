from dataclasses import dataclass
from typing import Any

from app.reminders.reminderConfigStore import ReminderConfigStore


@dataclass
class ScheduleReminderTool:
    in_reminderConfigStore: ReminderConfigStore

    def execute(
        self,
        in_args: dict[str, Any],
        *,
        in_memoryPrincipalId: str,
    ) -> dict[str, Any]:
        ret: dict[str, Any]
        reminderItem = self.in_reminderConfigStore.addOrUpdateReminder(
            in_message=str(in_args.get("message", "") or "").strip(),
            in_scheduleKind=str(in_args.get("scheduleType", "daily") or "daily"),
            in_timeLocal=str(in_args.get("timeLocal", "") or "").strip(),
            in_timeZone=str(in_args.get("timeZone", "") or "").strip(),
            in_weekdays=[int(item) for item in in_args.get("weekdays", [])],
            in_remainingRuns=in_args.get("remainingRuns"),
            in_enabled=bool(in_args.get("enabled", True)),
            in_ownerMemoryPrincipalId=str(in_memoryPrincipalId or "").strip(),
            in_reminderId=str(in_args.get("reminderId", "") or "").strip(),
        )
        ret = {
            "ok": True,
            "message": "Напоминание сохранено в schedules.yaml.",
            "reminder": reminderItem.model_dump(exclude_none=True),
        }
        return ret

