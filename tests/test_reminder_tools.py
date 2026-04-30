import json
from pathlib import Path

import yaml

from app.reminders.reminderConfigStore import ReminderConfigStore
from app.tools.implementations.deleteReminderTool import DeleteReminderTool
from app.tools.implementations.listRemindersTool import ListRemindersTool
from app.tools.implementations.scheduleReminderTool import ScheduleReminderTool


def testScheduleListDeleteReminderToolsWorkAsContract(tmp_path: Path) -> None:
    schedulesPath = tmp_path / "schedules.yaml"
    schedulesPath.write_text(
        yaml.safe_dump({"jobs": [], "reminders": []}, sort_keys=False),
        encoding="utf-8",
    )
    reminderConfigStore = ReminderConfigStore(in_schedulesConfigPath=str(schedulesPath))
    scheduleTool = ScheduleReminderTool(in_reminderConfigStore=reminderConfigStore)
    listTool = ListRemindersTool(
        in_reminderConfigStore=reminderConfigStore,
        in_dataRootPath=str(tmp_path),
    )
    deleteTool = DeleteReminderTool(
        in_reminderConfigStore=reminderConfigStore,
        in_dataRootPath=str(tmp_path),
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
        }
    )
    reminderIdValue = str(createResult["reminder"]["reminderId"])
    assert createResult["ok"] is True
    assert reminderIdValue != ""

    statePath = tmp_path / "scheduler" / "jobs_state.json"
    statePath.parent.mkdir(parents=True, exist_ok=True)
    statePath.write_text(
        json.dumps({"remindersState": {reminderIdValue: {"enabled": True}}}),
        encoding="utf-8",
    )

    listResult = listTool.execute(in_args={})
    assert listResult["ok"] is True
    assert listResult["count"] == 1
    assert listResult["items"][0]["reminder"]["reminderId"] == reminderIdValue
    assert listResult["items"][0]["runtimeState"]["enabled"] is True

    deleteResult = deleteTool.execute(in_args={"reminderId": reminderIdValue})
    assert deleteResult["ok"] is True
    assert deleteResult["deletedFromConfig"] is True
    assert deleteResult["deletedFromRuntimeState"] is True

    listResultAfterDelete = listTool.execute(in_args={})
    assert listResultAfterDelete["count"] == 0

