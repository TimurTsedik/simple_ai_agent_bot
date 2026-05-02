from pathlib import Path

from app.config.settingsModels import (
    LoggingSettings,
    SchedulerJobInternalRunAction,
    SchedulerJobSchedule,
    SchedulerJobSettings,
    SchedulerSettings,
)
from app.scheduler.schedulerRunner import SchedulerRunner
from datetime import datetime, timezone


def testSchedulerRunsJobOnFirstTick(tmp_path: Path) -> None:
    calls: list[tuple[str, str]] = []

    schedulerSettings = SchedulerSettings(
        enabled=True,
        tickSeconds=1,
        schedulesConfigPath=str(tmp_path / "test-schedules.yaml"),
        jobs=[
            SchedulerJobSettings(
                jobId="job1",
                enabled=True,
                schedule=SchedulerJobSchedule(intervalSeconds=3600),
                actionInternalRun=SchedulerJobInternalRunAction(
                    sessionId="scheduler:test",
                    message="hello",
                ),
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
    nowValue = 1000

    runner = SchedulerRunner(
        in_schedulerSettings=schedulerSettings,
        in_loggingSettings=loggingSettings,
        in_dataRootPath=str(tmp_path),
        in_adminTelegramUserId=16739703,
        in_runInternalCallable=lambda sessionId, message: (
            calls.append((sessionId, message)) or "run1",
            "answer",
        ),
        in_nowUnixTsProvider=lambda: nowValue,
        in_sleepCallable=lambda _: None,
    )

    runner._tickOnce()

    assert calls == [("telegramUser:16739703:scheduler:test", "hello")]
    statePath = tmp_path / "scheduler" / "jobs_state.json"
    assert statePath.exists() is True


def testSchedulerRespectsInterval(tmp_path: Path) -> None:
    calls: list[str] = []
    schedulerSettings = SchedulerSettings(
        enabled=True,
        tickSeconds=1,
        schedulesConfigPath=str(tmp_path / "test-schedules.yaml"),
        jobs=[
            SchedulerJobSettings(
                jobId="job1",
                enabled=True,
                schedule=SchedulerJobSchedule(intervalSeconds=60),
                actionInternalRun=SchedulerJobInternalRunAction(
                    sessionId="scheduler:test",
                    message="hello",
                ),
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
    nowValue = 1000

    runner = SchedulerRunner(
        in_schedulerSettings=schedulerSettings,
        in_loggingSettings=loggingSettings,
        in_dataRootPath=str(tmp_path),
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
    schedulerSettings = SchedulerSettings(
        enabled=True,
        tickSeconds=1,
        schedulesConfigPath=str(tmp_path / "test-schedules.yaml"),
        jobs=[
            SchedulerJobSettings(
                jobId="job1",
                enabled=True,
                schedule=SchedulerJobSchedule(
                    intervalSeconds=3600,
                    allowedHourStart=8,
                    allowedHourEnd=23,
                ),
                actionInternalRun=SchedulerJobInternalRunAction(
                    sessionId="scheduler:test",
                    message="hello",
                ),
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
    nowUnixTs = int(datetime(2026, 1, 1, 7, 0, tzinfo=timezone.utc).timestamp())

    runner = SchedulerRunner(
        in_schedulerSettings=schedulerSettings,
        in_loggingSettings=loggingSettings,
        in_dataRootPath=str(tmp_path),
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
    schedulerSettings = SchedulerSettings(
        enabled=True,
        tickSeconds=1,
        schedulesConfigPath=str(tmp_path / "test-schedules.yaml"),
        jobs=[
            SchedulerJobSettings(
                jobId="job1",
                enabled=True,
                schedule=SchedulerJobSchedule(
                    intervalSeconds=3600,
                    allowedHourStart=8,
                    allowedHourEnd=23,
                ),
                actionInternalRun=SchedulerJobInternalRunAction(
                    sessionId="scheduler:test",
                    message="hello",
                ),
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
    # 06:00 UTC == 09:00 Asia/Jerusalem (DST, UTC+3) at this date.
    nowUnixTs = int(datetime(2026, 4, 29, 6, 0, tzinfo=timezone.utc).timestamp())

    runner = SchedulerRunner(
        in_schedulerSettings=schedulerSettings,
        in_loggingSettings=loggingSettings,
        in_dataRootPath=str(tmp_path),
        in_adminTelegramUserId=16739703,
        in_runInternalCallable=lambda *_: (calls.append("x") or "run1", "answer"),
        in_nowUnixTsProvider=lambda: nowUnixTs,
        in_sleepCallable=lambda _: None,
        in_timeZoneName="Asia/Jerusalem",
    )
    runner._tickOnce()
    assert len(calls) == 1


def testSchedulerCallsCompletionCallbackWithFinalAnswer(tmp_path: Path) -> None:
    notifications: list[tuple[str, str, str, str]] = []
    schedulerSettings = SchedulerSettings(
        enabled=True,
        tickSeconds=1,
        schedulesConfigPath=str(tmp_path / "test-schedules.yaml"),
        jobs=[
            SchedulerJobSettings(
                jobId="job1",
                enabled=True,
                schedule=SchedulerJobSchedule(intervalSeconds=3600),
                actionInternalRun=SchedulerJobInternalRunAction(
                    sessionId="scheduler:test",
                    message="hello",
                ),
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
        in_runInternalCallable=lambda *_: ("run1", "result text"),
        in_onRunCompletedCallable=lambda jobId, sessionId, runId, finalAnswer: notifications.append(
            (jobId, sessionId, runId, finalAnswer)
        ),
        in_nowUnixTsProvider=lambda: 1000,
        in_sleepCallable=lambda _: None,
    )

    runner._tickOnce()

    assert notifications == [
        ("job1", "telegramUser:16739703:scheduler:test", "run1", "result text")
    ]

