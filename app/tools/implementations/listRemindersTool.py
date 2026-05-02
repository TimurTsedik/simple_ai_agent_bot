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

    def _loadTasksState(self) -> dict[str, Any]:
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
        tasks_state = loaded.get("tasksState", {})
        if isinstance(tasks_state, dict) is False:
            tasks_state = {}
        ret = tasks_state
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
        recurring_tasks = self.in_reminderConfigStore.listInternalRunTasksForOwner(
            in_ownerMemoryPrincipalId=str(in_memoryPrincipalId or "").strip(),
        )
        tasks_state = self._loadTasksState()
        owner_seg = str(in_memoryPrincipalId or "").strip().replace(":", "_")
        mergedItems: list[dict[str, Any]] = []
        for reminderItem in reminderItems:
            composite_key = f"{owner_seg}::{reminderItem.reminderId}"
            reminderState = tasks_state.get(composite_key, {})
            if isinstance(reminderState, dict) is False:
                reminderState = {}
            mergedItems.append(
                {
                    "reminder": reminderItem.model_dump(exclude_none=True),
                    "runtimeState": reminderState,
                }
            )
        recurringMerged: list[dict[str, Any]] = []
        for task_payload in recurring_tasks:
            task_id_value = str(task_payload.get("taskId", "") or "").strip()
            composite_key = f"{owner_seg}::{task_id_value}"
            run_state = tasks_state.get(composite_key, {})
            if isinstance(run_state, dict) is False:
                run_state = {}
            recurringMerged.append(
                {
                    "task": task_payload,
                    "runtimeState": run_state,
                }
            )
        ret = {
            "ok": True,
            "count": len(mergedItems),
            "items": mergedItems,
            "recurringAgentRunCount": len(recurringMerged),
            "recurringAgentRuns": recurringMerged,
        }
        return ret

