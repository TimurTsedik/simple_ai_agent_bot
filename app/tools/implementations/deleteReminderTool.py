import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.reminders.reminderConfigStore import ReminderConfigStore


@dataclass
class DeleteReminderTool:
    in_reminderConfigStore: ReminderConfigStore
    in_dataRootPath: str
    in_adminMemoryPrincipalId: str

    def _deleteReminderState(self, in_reminderId: str, in_memoryPrincipalId: str) -> bool:
        ret: bool
        statePath = Path(self.in_dataRootPath) / "scheduler" / "jobs_state.json"
        isDeleted = False
        owner_seg = str(in_memoryPrincipalId or "").strip().replace(":", "_")
        composite_key = f"{owner_seg}::{in_reminderId}"
        if statePath.exists() is True:
            try:
                loaded = json.loads(statePath.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError, UnicodeDecodeError):
                loaded = {}
            if isinstance(loaded, dict):
                tasks_state = loaded.get("tasksState", {})
                if isinstance(tasks_state, dict) is False:
                    tasks_state = {}
                legacy_rem = loaded.get("remindersState", {})
                if isinstance(legacy_rem, dict) is True and in_reminderId in legacy_rem:
                    del legacy_rem[in_reminderId]
                    loaded["remindersState"] = legacy_rem
                    isDeleted = True
                if composite_key in tasks_state:
                    del tasks_state[composite_key]
                    loaded["tasksState"] = tasks_state
                    isDeleted = True
                if isDeleted is True:
                    statePath.parent.mkdir(parents=True, exist_ok=True)
                    tempPath = statePath.with_suffix(statePath.suffix + ".tmp")
                    tempPath.write_text(
                        json.dumps(loaded, ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )
                    tempPath.replace(statePath)
        ret = isDeleted
        return ret

    def execute(
        self,
        in_args: dict[str, Any],
        *,
        in_memoryPrincipalId: str,
    ) -> dict[str, Any]:
        ret: dict[str, Any]
        reminderIdValue = str(in_args.get("reminderId", "") or "").strip()
        isDeletedFromConfig = self.in_reminderConfigStore.deleteReminderForOwner(
            in_reminderId=reminderIdValue,
            in_ownerMemoryPrincipalId=str(in_memoryPrincipalId or "").strip(),
            in_adminMemoryPrincipalId=str(self.in_adminMemoryPrincipalId or "").strip(),
        )
        isDeletedFromState = self._deleteReminderState(
            in_reminderId=reminderIdValue,
            in_memoryPrincipalId=str(in_memoryPrincipalId or "").strip(),
        )
        ret = {
            "ok": isDeletedFromConfig or isDeletedFromState,
            "deletedFromConfig": isDeletedFromConfig,
            "deletedFromRuntimeState": isDeletedFromState,
            "reminderId": reminderIdValue,
        }
        return ret

