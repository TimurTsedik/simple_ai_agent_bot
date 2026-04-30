import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.reminders.reminderConfigStore import ReminderConfigStore


@dataclass
class DeleteReminderTool:
    in_reminderConfigStore: ReminderConfigStore
    in_dataRootPath: str

    def _deleteReminderState(self, in_reminderId: str) -> bool:
        ret: bool
        statePath = Path(self.in_dataRootPath) / "scheduler" / "jobs_state.json"
        isDeleted = False
        if statePath.exists() is True:
            try:
                loaded = json.loads(statePath.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError, UnicodeDecodeError):
                loaded = {}
            if isinstance(loaded, dict):
                remindersState = loaded.get("remindersState", {})
                if isinstance(remindersState, dict) and in_reminderId in remindersState:
                    del remindersState[in_reminderId]
                    loaded["remindersState"] = remindersState
                    statePath.parent.mkdir(parents=True, exist_ok=True)
                    tempPath = statePath.with_suffix(statePath.suffix + ".tmp")
                    tempPath.write_text(
                        json.dumps(loaded, ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )
                    tempPath.replace(statePath)
                    isDeleted = True
        ret = isDeleted
        return ret

    def execute(self, in_args: dict[str, Any]) -> dict[str, Any]:
        ret: dict[str, Any]
        reminderIdValue = str(in_args.get("reminderId", "") or "").strip()
        isDeletedFromConfig = self.in_reminderConfigStore.deleteReminder(
            in_reminderId=reminderIdValue
        )
        isDeletedFromState = self._deleteReminderState(in_reminderId=reminderIdValue)
        ret = {
            "ok": isDeletedFromConfig or isDeletedFromState,
            "deletedFromConfig": isDeletedFromConfig,
            "deletedFromRuntimeState": isDeletedFromState,
            "reminderId": reminderIdValue,
        }
        return ret

