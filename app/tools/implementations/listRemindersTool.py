import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.reminders.reminderConfigStore import ReminderConfigStore


@dataclass
class ListRemindersTool:
    in_reminderConfigStore: ReminderConfigStore
    in_dataRootPath: str
    in_adminMemoryPrincipalId: str

    def _loadRemindersState(self) -> dict[str, Any]:
        ret: dict[str, Any]
        statePath = Path(self.in_dataRootPath) / "scheduler" / "jobs_state.json"
        loaded: Any = {}
        if statePath.exists() is True:
            try:
                loaded = json.loads(statePath.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError, UnicodeDecodeError):
                loaded = {}
        if isinstance(loaded, dict) is False:
            loaded = {}
        remindersState = loaded.get("remindersState", {})
        if isinstance(remindersState, dict) is False:
            remindersState = {}
        ret = remindersState
        return ret

    def execute(
        self,
        in_args: dict[str, Any],
        *,
        in_memoryPrincipalId: str,
    ) -> dict[str, Any]:
        ret: dict[str, Any]
        _ = in_args
        reminderItems = self.in_reminderConfigStore.listRemindersForOwner(
            in_ownerMemoryPrincipalId=str(in_memoryPrincipalId or "").strip(),
            in_adminMemoryPrincipalId=str(self.in_adminMemoryPrincipalId or "").strip(),
        )
        remindersState = self._loadRemindersState()
        mergedItems: list[dict[str, Any]] = []
        for reminderItem in reminderItems:
            reminderState = remindersState.get(reminderItem.reminderId, {})
            if isinstance(reminderState, dict) is False:
                reminderState = {}
            mergedItems.append(
                {
                    "reminder": reminderItem.model_dump(exclude_none=True),
                    "runtimeState": reminderState,
                }
            )
        ret = {
            "ok": True,
            "count": len(mergedItems),
            "items": mergedItems,
        }
        return ret

