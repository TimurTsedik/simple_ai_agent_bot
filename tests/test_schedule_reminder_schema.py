from app.tools.registry.toolSchemas import ScheduleReminderArgsModel


def testScheduleReminderSchemaNormalizesOnceToDailySingleRun() -> None:
    argsModel = ScheduleReminderArgsModel.model_validate(
        {
            "reminderId": "",
            "enabled": True,
            "message": "Выпить воды",
            "scheduleType": "once",
            "weekdays": [],
            "timeLocal": "16:43",
            "timeZone": "",
            "remainingRuns": None,
        }
    )

    assert argsModel.scheduleType == "daily"
    assert argsModel.remainingRuns == 1
    assert argsModel.weekdays == []

