from dataclasses import dataclass
from typing import Any

from app.reminders.reminderConfigStore import ReminderConfigStore


@dataclass
class ScheduleRecurringAgentRunTool:
    in_reminderConfigStore: ReminderConfigStore

    def execute(
        self,
        in_args: dict[str, Any],
        *,
        in_memoryPrincipalId: str,
    ) -> dict[str, Any]:
        ret: dict[str, Any]
        try:
            payload = self.in_reminderConfigStore.addOrUpdateInternalRunTask(
                in_message=str(in_args.get("message", "") or "").strip(),
                in_intervalSeconds=int(in_args.get("intervalSeconds", 3600)),
                in_allowedHourStart=in_args.get("allowedHourStart"),
                in_allowedHourEnd=in_args.get("allowedHourEnd"),
                in_enabled=bool(in_args.get("enabled", True)),
                in_ownerMemoryPrincipalId=str(in_memoryPrincipalId or "").strip(),
                in_taskId=str(in_args.get("taskId", "") or "").strip(),
                in_sessionSlug=str(in_args.get("sessionSlug", "") or "").strip(),
            )
            ret = {
                "ok": True,
                "message": "Регулярный запуск агента сохранён в schedules.yaml (kind=internal_run).",
                "task": payload,
            }
        except ValueError as in_exc:
            ret = {
                "ok": False,
                "error": str(in_exc),
                "task": None,
            }
        return ret
