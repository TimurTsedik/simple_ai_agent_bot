from datetime import datetime, timezone
from pathlib import Path

import yaml

from app.config.settingsModels import (
    LoggingSettings,
    SchedulerJobInternalRunAction,
    SchedulerJobSchedule,
    SchedulerJobSettings,
    SchedulerSettings,
)
from app.scheduler.schedulerRunner import SchedulerRunner


def _memory_root_with_job_yaml(
    tmp_path: Path,
    *,
    in_interval_seconds: int,
    in_allowed_hour_start: int | None = None,
    in_allowed_hour_end: int | None = None,
) -> Path:
    memory_root = tmp_path / "memory"
    session_dir = memory_root / "sessions" / "telegramUser_16739703"
    session_dir.mkdir(parents=True)
    schedule_block: dict = {
        "intervalSeconds": int(in_interval_seconds),
    }
    if in_allowed_hour_start is not None:
        schedule_block["allowedHourStart"] = in_allowed_hour_start
    if in_allowed_hour_end is not None:
        schedule_block["allowedHourEnd"] = in_allowed_hour_end
    payload = {
        "jobs": [
            {
                "jobId": "job1",
                "enabled": True,
                "schedule": schedule_block,
                "actionInternalRun": {
                    "sessionId": "scheduler:test",
                    "message": "hello",
                },
            }
        ]
    }
    (session_dir / "schedules.yaml").write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    ret = memory_root
    return ret


def testSchedulerRunsJobOnFirstTick(tmp_path: Path) -> None:
    calls: list[tuple[str, str, str]] = []

    memory_root = _memory_root_with_job_yaml(tmp_path, in_interval_seconds=3600)
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
    nowValue = 1000

    runner = SchedulerRunner(
        in_schedulerSettings=schedulerSettings,
        in_loggingSettings=loggingSettings,
        in_dataRootPath=str(tmp_path),
        in_memoryRootPath=str(memory_root),
        in_adminTelegramUserId=16739703,
        in_runInternalCallable=lambda sessionId, message, principal: (
            calls.append((sessionId, message, principal)) or "run1",
            "answer",
        ),
        in_nowUnixTsProvider=lambda: nowValue,
        in_sleepCallable=lambda _: None,
    )

    runner._tickOnce()

    assert calls == [
        ("telegramUser:16739703:scheduler:test", "hello", "telegramUser:16739703"),
    ]
    statePath = tmp_path / "scheduler" / "jobs_state.json"
    assert statePath.exists() is True


def testSchedulerRespectsInterval(tmp_path: Path) -> None:
    calls: list[str] = []
    memory_root = _memory_root_with_job_yaml(tmp_path, in_interval_seconds=60)
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
    nowValue = 1000

    runner = SchedulerRunner(
        in_schedulerSettings=schedulerSettings,
        in_loggingSettings=loggingSettings,
        in_dataRootPath=str(tmp_path),
        in_memoryRootPath=str(memory_root),
        in_adminTelegramUserId=16739703,
        in_runInternalCallable=lambda *_: (calls.append("x") or "run1", "answer"),
        in_nowUnixTsProvider=lambda: nowValue,
        in_sleepCallable=lambda _: None,
    )

    runner._tickOnce()
    runner._tickOnce()
    assert len(calls) == 1

    nowValue = 1059
    runner._tickOnce()
    assert len(calls) == 1

    nowValue = 1060
    runner._tickOnce()
    assert len(calls) == 2


def testSchedulerRespectsHourWindow(tmp_path: Path, monkeypatch) -> None:
    calls: list[str] = []
    memory_root = _memory_root_with_job_yaml(
        tmp_path,
        in_interval_seconds=3600,
        in_allowed_hour_start=8,
        in_allowed_hour_end=23,
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
    nowUnixTs = int(datetime(2026, 1, 1, 7, 0, tzinfo=timezone.utc).timestamp())

    runner = SchedulerRunner(
        in_schedulerSettings=schedulerSettings,
        in_loggingSettings=loggingSettings,
        in_dataRootPath=str(tmp_path),
        in_memoryRootPath=str(memory_root),
        in_adminTelegramUserId=16739703,
        in_runInternalCallable=lambda *_: (calls.append("x") or "run1", "answer"),
        in_nowUnixTsProvider=lambda: nowUnixTs,
        in_sleepCallable=lambda _: None,
        in_timeZoneName="UTC",
    )
    runner._tickOnce()
    assert len(calls) == 0


def testSchedulerHourWindowUsesConfiguredTimeZone(tmp_path: Path) -> None:
    calls: list[str] = []
    memory_root = _memory_root_with_job_yaml(
        tmp_path,
        in_interval_seconds=3600,
        in_allowed_hour_start=8,
        in_allowed_hour_end=23,
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
    nowUnixTs = int(datetime(2026, 4, 29, 6, 0, tzinfo=timezone.utc).timestamp())

    runner = SchedulerRunner(
        in_schedulerSettings=schedulerSettings,
        in_loggingSettings=loggingSettings,
        in_dataRootPath=str(tmp_path),
        in_memoryRootPath=str(memory_root),
        in_adminTelegramUserId=16739703,
        in_runInternalCallable=lambda *_: (calls.append("x") or "run1", "answer"),
        in_nowUnixTsProvider=lambda: nowUnixTs,
        in_sleepCallable=lambda _: None,
        in_timeZoneName="Asia/Jerusalem",
    )
    runner._tickOnce()
    assert len(calls) == 1


def testSchedulerCallsCompletionCallbackWithFinalAnswer(tmp_path: Path) -> None:
    notifications: list[tuple[str, str, str, str, str]] = []
    memory_root = _memory_root_with_job_yaml(tmp_path, in_interval_seconds=3600)
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
        in_runInternalCallable=lambda *_: ("run1", "result text"),
        in_onRunCompletedCallable=lambda jobId, sessionId, runId, finalAnswer, owner: notifications.append(
            (jobId, sessionId, runId, finalAnswer, owner)
        ),
        in_nowUnixTsProvider=lambda: 1000,
        in_sleepCallable=lambda _: None,
    )

    runner._tickOnce()

    assert notifications == [
        (
            "job1",
            "telegramUser:16739703:scheduler:test",
            "run1",
            "result text",
            "telegramUser:16739703",
        )
    ]
