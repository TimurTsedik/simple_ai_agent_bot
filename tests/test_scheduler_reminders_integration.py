from datetime import datetime, timezone
from pathlib import Path

import yaml

from app.config.settingsModels import LoggingSettings, ReminderModel, SchedulerSettings
from app.reminders.reminderConfigStore import ReminderConfigStore
from app.scheduler.schedulerRunner import SchedulerRunner


def testSchedulerReminderFiresOncePerMinuteAndDecrementsRemainingRuns(tmp_path: Path) -> None:
    sentItems: list[tuple[str, str]] = []
    nowUnixTs = int(datetime(2026, 1, 1, 10, 15, tzinfo=timezone.utc).timestamp())
    schedulesPath = tmp_path / "test-schedules.yaml"
    schedulesPath.write_text(
        yaml.safe_dump(
            {
                "jobs": [],
                "reminders": [
                    {
                        "reminderId": "reminder-1",
                        "enabled": True,
                        "message": "Пора сделать паузу",
                        "schedule": {
                            "kind": "daily",
                            "timeLocal": "10:15",
                            "timeZone": "UTC",
                            "remainingRuns": 1,
                        },
                    }
                ],
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    schedulerSettings = SchedulerSettings(
        enabled=True,
        tickSeconds=1,
        schedulesConfigPath=str(schedulesPath),
        jobs=[],
        reminders=[
            ReminderModel(
                reminderId="reminder-1",
                enabled=True,
                message="Пора сделать паузу",
                schedule={
                    "kind": "daily",
                    "timeLocal": "10:15",
                    "timeZone": "UTC",
                    "remainingRuns": 1,
                },
            )
        ],
    )
    loggingSettings = LoggingSettings(
        logsDirPath=str(tmp_path / "logs"),
        runLogsFileName="run.jsonl",
        appLogsFileName="app.log",
        maxBytes=1024 * 1024,
        backupCount=1,
    )
    runner = SchedulerRunner(
        in_schedulerSettings=schedulerSettings,
        in_loggingSettings=loggingSettings,
        in_dataRootPath=str(tmp_path),
        in_adminTelegramUserId=16739703,
        in_runInternalCallable=lambda *_: ("", ""),
        in_onReminderTriggeredCallable=lambda reminderId, text: sentItems.append((reminderId, text)),
        in_onReminderCompletedCallable=lambda reminderId: ReminderConfigStore(
            in_schedulesConfigPath=str(schedulesPath)
        ).deleteReminder(in_reminderId=reminderId),
        in_nowUnixTsProvider=lambda: nowUnixTs,
        in_sleepCallable=lambda _: None,
        in_timeZoneName="UTC",
    )

    runner._tickOnce()
    runner._tickOnce()

    assert sentItems == [("reminder-1", "Пора сделать паузу")]
    remindersState = runner._getRemindersState()
    assert "reminder-1" not in remindersState
    loadedSchedules = yaml.safe_load(schedulesPath.read_text(encoding="utf-8")) or {}
    assert loadedSchedules.get("reminders", []) == []


def testSchedulerReminderHotReloadsFromSchedulesFile(tmp_path: Path) -> None:
    sentItems: list[tuple[str, str]] = []
    nowUnixTs = int(datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc).timestamp())
    schedulesPath = tmp_path / "schedules.yaml"
    schedulesPath.write_text(
        yaml.safe_dump({"jobs": [], "reminders": []}, sort_keys=False),
        encoding="utf-8",
    )
    schedulerSettings = SchedulerSettings(
        enabled=True,
        tickSeconds=1,
        jobs=[],
        reminders=[],
        schedulesConfigPath=str(schedulesPath),
    )
    loggingSettings = LoggingSettings(
        logsDirPath=str(tmp_path / "logs"),
        runLogsFileName="run.jsonl",
        appLogsFileName="app.log",
        maxBytes=1024 * 1024,
        backupCount=1,
    )
    runner = SchedulerRunner(
        in_schedulerSettings=schedulerSettings,
        in_loggingSettings=loggingSettings,
        in_dataRootPath=str(tmp_path),
        in_adminTelegramUserId=16739703,
        in_runInternalCallable=lambda *_: ("", ""),
        in_onReminderTriggeredCallable=lambda reminderId, text: sentItems.append((reminderId, text)),
        in_nowUnixTsProvider=lambda: nowUnixTs,
        in_sleepCallable=lambda _: None,
        in_timeZoneName="UTC",
    )

    schedulesPath.write_text(
        yaml.safe_dump(
            {
                "jobs": [],
                "reminders": [
                    {
                        "reminderId": "reload-rem",
                        "enabled": True,
                        "message": "Обновлённый reminder",
                        "schedule": {
                            "kind": "daily",
                            "timeLocal": "12:00",
                            "timeZone": "UTC",
                        },
                    }
                ],
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    runner._tickOnce()

    assert sentItems == [("reload-rem", "Обновлённый reminder")]

