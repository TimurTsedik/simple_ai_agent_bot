import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from threading import Event, Lock
from time import monotonic, time
from typing import Any, Callable

from app.common.structuredLogger import writeJsonlEvent
from app.config.settingsModels import SchedulerJobSettings, SchedulerSettings, LoggingSettings


def _atomicWriteJson(in_path: Path, in_data: dict[str, Any]) -> None:
    in_path.parent.mkdir(parents=True, exist_ok=True)
    tmpPath = in_path.with_suffix(in_path.suffix + ".tmp")
    tmpPath.write_text(json.dumps(in_data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmpPath, in_path)


def _loadJsonOrEmpty(in_path: Path) -> dict[str, Any]:
    ret: dict[str, Any]
    if in_path.exists() is False:
        ret = {}
    else:
        try:
            loaded = json.loads(in_path.read_text(encoding="utf-8"))
            ret = loaded if isinstance(loaded, dict) else {}
        except Exception:
            ret = {}
    return ret


@dataclass
class SchedulerRunner:
    in_schedulerSettings: SchedulerSettings
    in_loggingSettings: LoggingSettings
    in_dataRootPath: str
    in_runInternalCallable: Callable[[str, str], str]
    in_nowUnixTsProvider: Callable[[], int] = lambda: int(time())
    in_sleepCallable: Callable[[float], None] = lambda seconds: Event().wait(seconds)

    def __post_init__(self) -> None:
        self._stopEvent = Event()
        self._lock = Lock()
        self._runningJobs: set[str] = set()
        self._statePath = Path(self.in_dataRootPath) / "scheduler" / "jobs_state.json"
        self._state = _loadJsonOrEmpty(in_path=self._statePath)

    def stop(self) -> None:
        self._stopEvent.set()

    def runForever(self) -> None:
        tickSeconds = int(self.in_schedulerSettings.tickSeconds)
        if tickSeconds < 1:
            tickSeconds = 1
        writeJsonlEvent(
            in_loggingSettings=self.in_loggingSettings,
            in_eventType="scheduler_started",
            in_payload={"jobCount": len(self.in_schedulerSettings.jobs)},
        )
        try:
            while self._stopEvent.is_set() is False:
                startedAt = monotonic()
                self._tickOnce()
                elapsed = monotonic() - startedAt
                sleepFor = float(tickSeconds) - elapsed
                if sleepFor < 0.05:
                    sleepFor = 0.05
                self.in_sleepCallable(sleepFor)
        finally:
            writeJsonlEvent(
                in_loggingSettings=self.in_loggingSettings,
                in_eventType="scheduler_stopped",
                in_payload={},
            )

    def _tickOnce(self) -> None:
        nowTs = int(self.in_nowUnixTsProvider())
        for job in list(self.in_schedulerSettings.jobs):
            if job.enabled is not True:
                continue
            if self._isJobDue(in_job=job, in_nowUnixTs=nowTs) is False:
                continue
            self._runJobIfNotRunning(in_job=job, in_nowUnixTs=nowTs)

    def _isJobDue(self, in_job: SchedulerJobSettings, in_nowUnixTs: int) -> bool:
        ret: bool
        if self._isAllowedByHourWindow(in_job=in_job, in_nowUnixTs=in_nowUnixTs) is False:
            ret = False
            return ret
        intervalSeconds = int(in_job.schedule.intervalSeconds)
        if intervalSeconds < 5:
            intervalSeconds = 5
        stateKey = in_job.jobId
        lastRunAt = int(self._state.get(stateKey, {}).get("lastRunAtUnixTs", 0))
        if lastRunAt <= 0:
            ret = True
        else:
            ret = (in_nowUnixTs - lastRunAt) >= intervalSeconds
        return ret

    def _isAllowedByHourWindow(self, in_job: SchedulerJobSettings, in_nowUnixTs: int) -> bool:
        ret: bool
        startHour = in_job.schedule.allowedHourStart
        endHour = in_job.schedule.allowedHourEnd
        if startHour is None and endHour is None:
            ret = True
            return ret
        if startHour is None or endHour is None:
            ret = False
            return ret
        currentHour = int(datetime.fromtimestamp(in_nowUnixTs).hour)
        if startHour <= endHour:
            ret = startHour <= currentHour <= endHour
        else:
            # Wrap-around window, e.g. 23..2
            ret = currentHour >= startHour or currentHour <= endHour
        return ret

    def _runJobIfNotRunning(self, in_job: SchedulerJobSettings, in_nowUnixTs: int) -> None:
        with self._lock:
            if in_job.jobId in self._runningJobs:
                return
            self._runningJobs.add(in_job.jobId)
        try:
            self._runJob(in_job=in_job, in_nowUnixTs=in_nowUnixTs)
        finally:
            with self._lock:
                self._runningJobs.discard(in_job.jobId)

    def _runJob(self, in_job: SchedulerJobSettings, in_nowUnixTs: int) -> None:
        stateKey = in_job.jobId
        prev = self._state.get(stateKey, {}) if isinstance(self._state.get(stateKey), dict) else {}
        startedAtUnixTs = int(in_nowUnixTs)
        self._state[stateKey] = {**prev, "lastStartedAtUnixTs": startedAtUnixTs}
        _atomicWriteJson(in_path=self._statePath, in_data=self._state)

        sessionId = str(in_job.actionInternalRun.sessionId)
        message = str(in_job.actionInternalRun.message)
        writeJsonlEvent(
            in_loggingSettings=self.in_loggingSettings,
            in_eventType="scheduler_job_started",
            in_payload={"jobId": in_job.jobId, "sessionId": sessionId},
        )
        statusValue = "ok"
        errorText = ""
        runId = ""
        try:
            runId = str(self.in_runInternalCallable(sessionId, message))
        except Exception as in_exc:
            statusValue = "error"
            errorText = str(in_exc)
        finishedAtUnixTs = int(self.in_nowUnixTsProvider())
        self._state[stateKey] = {
            **(self._state.get(stateKey, {}) if isinstance(self._state.get(stateKey), dict) else {}),
            "lastRunAtUnixTs": finishedAtUnixTs,
            "lastFinishedAtUnixTs": finishedAtUnixTs,
            "lastStatus": statusValue,
            "lastError": errorText,
            "lastRunId": runId,
        }
        _atomicWriteJson(in_path=self._statePath, in_data=self._state)
        writeJsonlEvent(
            in_loggingSettings=self.in_loggingSettings,
            in_eventType="scheduler_job_finished",
            in_payload={
                "jobId": in_job.jobId,
                "status": statusValue,
                "runId": runId,
                "error": errorText,
            },
        )

