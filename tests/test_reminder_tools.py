import json
from pathlib import Path

import yaml

from app.config.settingsModels import MemorySettings
from app.reminders.reminderConfigStore import ReminderConfigStore
from app.tools.implementations.deleteReminderTool import DeleteReminderTool
from app.tools.implementations.listRemindersTool import ListRemindersTool
from app.tools.implementations.scheduleRecurringAgentRunTool import ScheduleRecurringAgentRunTool
from app.tools.implementations.scheduleReminderTool import ScheduleReminderTool


def testScheduleListDeleteReminderToolsWorkAsContract(tmp_path: Path) -> None:
    memory_root = Path(tmp_path) / "memory"
    session_dir = memory_root / "sessions" / "telegramUser_99"
    session_dir.mkdir(parents=True)
    (session_dir / "schedules.yaml").write_text(
        yaml.safe_dump({"scheduledTasks": []}, sort_keys=False),
        encoding="utf-8",
    )
    memory_settings = MemorySettings(memoryRootPath=str(memory_root))
    reminderConfigStore = ReminderConfigStore(in_memorySettings=memory_settings)
    scheduleTool = ScheduleReminderTool(in_reminderConfigStore=reminderConfigStore)
    ownerPrincipal = "telegramUser:99"
    listTool = ListRemindersTool(
        in_reminderConfigStore=reminderConfigStore,
        in_dataRootPath=str(tmp_path),
        in_adminMemoryPrincipalId=ownerPrincipal,
    )
    deleteTool = DeleteReminderTool(
        in_reminderConfigStore=reminderConfigStore,
        in_dataRootPath=str(tmp_path),
        in_adminMemoryPrincipalId=ownerPrincipal,
    )

    createResult = scheduleTool.execute(
        in_args={
            "message": "Созвон",
            "scheduleType": "weekly",
            "weekdays": [1, 3],
            "timeLocal": "17:00",
            "timeZone": "UTC",
            "remainingRuns": 2,
            "enabled": True,
            "reminderId": "",
        },
        in_memoryPrincipalId=ownerPrincipal,
    )
    reminderIdValue = str(createResult["reminder"]["reminderId"])
    assert createResult["ok"] is True
    assert reminderIdValue != ""

    statePath = tmp_path / "scheduler" / "jobs_state.json"
    statePath.parent.mkdir(parents=True, exist_ok=True)
    statePath.write_text(
        json.dumps(
            {
                "tasksState": {
                    f"telegramUser_99::{reminderIdValue}": {"enabled": True},
                }
            }
        ),
        encoding="utf-8",
    )

    listResult = listTool.execute(
        in_args={},
        in_memoryPrincipalId=ownerPrincipal,
    )
    assert listResult["ok"] is True
    assert listResult["count"] == 1
    assert listResult["recurringAgentRunCount"] == 0
    assert listResult["items"][0]["reminder"]["reminderId"] == reminderIdValue
    assert listResult["items"][0]["runtimeState"]["enabled"] is True

    deleteResult = deleteTool.execute(
        in_args={"reminderId": reminderIdValue},
        in_memoryPrincipalId=ownerPrincipal,
    )
    assert deleteResult["ok"] is True
    assert deleteResult["deletedFromConfig"] is True
    assert deleteResult["deletedFromRuntimeState"] is True

    listResultAfterDelete = listTool.execute(
        in_args={},
        in_memoryPrincipalId=ownerPrincipal,
    )
    assert listResultAfterDelete["count"] == 0


def testScheduleRecurringAgentRunCreateListDelete(tmp_path: Path) -> None:
    memory_root = Path(tmp_path) / "memory"
    session_dir = memory_root / "sessions" / "telegramUser_42"
    session_dir.mkdir(parents=True)
    (session_dir / "schedules.yaml").write_text(
        yaml.safe_dump({"scheduledTasks": []}, sort_keys=False),
        encoding="utf-8",
    )
    memory_settings = MemorySettings(memoryRootPath=str(memory_root))
    reminder_config_store = ReminderConfigStore(in_memorySettings=memory_settings)
    recurring_tool = ScheduleRecurringAgentRunTool(in_reminderConfigStore=reminder_config_store)
    owner_principal = "telegramUser:42"
    list_tool = ListRemindersTool(
        in_reminderConfigStore=reminder_config_store,
        in_dataRootPath=str(tmp_path),
        in_adminMemoryPrincipalId=owner_principal,
    )
    delete_tool = DeleteReminderTool(
        in_reminderConfigStore=reminder_config_store,
        in_dataRootPath=str(tmp_path),
        in_adminMemoryPrincipalId=owner_principal,
    )
    create_result = recurring_tool.execute(
        in_args={
            "message": "Сделай дайджест новостей за час",
            "intervalSeconds": 3600,
            "allowedHourStart": 9,
            "allowedHourEnd": 21,
            "enabled": True,
            "taskId": "digest-hourly",
            "sessionSlug": "news_digest",
        },
        in_memoryPrincipalId=owner_principal,
    )
    assert create_result["ok"] is True
    task_payload = create_result["task"]
    assert task_payload["kind"] == "internal_run"
    assert task_payload["taskId"] == "digest-hourly"
    assert "telegramUser:42:scheduler:" in str(task_payload["internalRun"]["sessionId"])

    list_result = list_tool.execute(in_args={}, in_memoryPrincipalId=owner_principal)
    assert list_result["recurringAgentRunCount"] == 1
    assert list_result["recurringAgentRuns"][0]["task"]["taskId"] == "digest-hourly"

    delete_result = delete_tool.execute(
        in_args={"reminderId": "digest-hourly"},
        in_memoryPrincipalId=owner_principal,
    )
    assert delete_result["deletedFromConfig"] is True
    list_after = list_tool.execute(in_args={}, in_memoryPrincipalId=owner_principal)
    assert list_after["recurringAgentRunCount"] == 0

