from datetime import datetime, timezone
from pathlib import Path

import yaml

from app.config.settingsModels import LoggingSettings, MemorySettings, SchedulerSettings
from app.reminders.reminderConfigStore import ReminderConfigStore
from app.scheduler.schedulerRunner import SchedulerRunner


def testSchedulerReminderFiresOncePerMinuteAndDecrementsRemainingRuns(tmp_path: Path) -> None:
    sentItems: list[tuple[str, str]] = []
    nowUnixTs = int(datetime(2026, 1, 1, 10, 15, tzinfo=timezone.utc).timestamp())
    memory_root = tmp_path / "memory"
    session_dir = memory_root / "sessions" / "telegramUser_16739703"
    session_dir.mkdir(parents=True)
    schedulesPath = session_dir / "schedules.yaml"
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
        in_memoryRootPath=str(memory_root),
        in_adminTelegramUserId=16739703,
        in_runInternalCallable=lambda *_: ("", ""),
        in_onReminderTriggeredCallable=lambda reminderId, text, _owner: sentItems.append(
            (reminderId, text)
        ),
        in_onReminderCompletedCallable=lambda reminderId, owner: ReminderConfigStore(
            in_memorySettings=MemorySettings(memoryRootPath=str(memory_root)),
        ).deleteReminderForTenant(
            in_reminderId=reminderId,
            in_ownerMemoryPrincipalId=owner,
        ),
        in_nowUnixTsProvider=lambda: nowUnixTs,
        in_sleepCallable=lambda _: None,
        in_timeZoneName="UTC",
    )

    runner._tickOnce()
    runner._tickOnce()

    assert sentItems == [("reminder-1", "Пора сделать паузу")]
    loaded_schedules = yaml.safe_load(schedulesPath.read_text(encoding="utf-8")) or {}
    st = loaded_schedules.get("scheduledTasks", [])
    assert isinstance(st, list) is True
    assert len(st) == 0


def testSchedulerReminderHotReloadsFromSchedulesFile(tmp_path: Path) -> None:
    sentItems: list[tuple[str, str]] = []
    nowUnixTs = int(datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc).timestamp())
    memory_root = tmp_path / "memory"
    session_dir = memory_root / "sessions" / "telegramUser_16739703"
    session_dir.mkdir(parents=True)
    schedulesPath = session_dir / "schedules.yaml"
    schedulesPath.write_text(
        yaml.safe_dump({"jobs": [], "reminders": []}, sort_keys=False),
        encoding="utf-8",
    )
    schedulerSettings = SchedulerSettings(
        enabled=True,
        tickSeconds=1,
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
        in_memoryRootPath=str(memory_root),
        in_adminTelegramUserId=16739703,
        in_runInternalCallable=lambda *_: ("", ""),
        in_onReminderTriggeredCallable=lambda reminderId, text, _owner: sentItems.append(
            (reminderId, text)
        ),
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
                        "message": "reload",
                        "schedule": {
                            "kind": "daily",
                            "timeLocal": "12:00",
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

    runner._tickOnce()

    assert len(sentItems) == 1
    assert sentItems[0][0] == "reload-rem"
