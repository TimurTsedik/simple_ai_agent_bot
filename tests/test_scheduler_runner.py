from pathlib import Path

from app.config.settingsModels import (
    LoggingSettings,
    SchedulerJobInternalRunAction,
    SchedulerJobSchedule,
    SchedulerJobSettings,
    SchedulerSettings,
)
from app.scheduler.schedulerRunner import SchedulerRunner


def testSchedulerRunsJobOnFirstTick(tmp_path: Path) -> None:
    calls: list[tuple[str, str]] = []

    schedulerSettings = SchedulerSettings(
        enabled=True,
        tickSeconds=1,
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
        in_runInternalCallable=lambda sessionId, message: calls.append((sessionId, message))
        or "run1",
        in_nowUnixTsProvider=lambda: nowValue,
        in_sleepCallable=lambda _: None,
    )

    runner._tickOnce()

    assert calls == [("scheduler:test", "hello")]
    statePath = tmp_path / "scheduler" / "jobs_state.json"
    assert statePath.exists() is True


def testSchedulerRespectsInterval(tmp_path: Path) -> None:
    calls: list[str] = []
    schedulerSettings = SchedulerSettings(
        enabled=True,
        tickSeconds=1,
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
        in_runInternalCallable=lambda *_: calls.append("x") or "run1",
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

    class _FakeDateTime:
        def __init__(self, hourValue: int):
            self.hour = hourValue

    def _fakeFromTimestamp(_ts: int):
        return _FakeDateTime(hourValue=7)

    monkeypatch.setattr(
        "app.scheduler.schedulerRunner.datetime",
        type("DT", (), {"fromtimestamp": staticmethod(_fakeFromTimestamp)}),
    )

    runner = SchedulerRunner(
        in_schedulerSettings=schedulerSettings,
        in_loggingSettings=loggingSettings,
        in_dataRootPath=str(tmp_path),
        in_runInternalCallable=lambda *_: calls.append("x") or "run1",
        in_nowUnixTsProvider=lambda: 1000,
        in_sleepCallable=lambda _: None,
    )
    runner._tickOnce()
    assert len(calls) == 0

