from dataclasses import dataclass
from time import monotonic

from app.config.settingsModels import RuntimeSettings


@dataclass(frozen=True)
class StopDecisionModel:
    shouldStop: bool
    completionReason: str | None
    finalAnswer: str | None


class StopPolicy:
    def __init__(self, in_runtimeSettings: RuntimeSettings) -> None:
        self._runtimeSettings = in_runtimeSettings

    def evaluate(
        self,
        in_stepCount: int,
        in_toolCallCount: int,
        in_startedAtMonotonicSeconds: float,
    ) -> StopDecisionModel:
        ret: StopDecisionModel
        elapsedSeconds = monotonic() - in_startedAtMonotonicSeconds
        if in_stepCount >= self._runtimeSettings.maxSteps:
            ret = StopDecisionModel(
                shouldStop=True,
                completionReason="max_steps_exceeded",
                finalAnswer="Остановка: достигнут лимит шагов.",
            )
        elif in_toolCallCount >= self._runtimeSettings.maxToolCalls:
            ret = StopDecisionModel(
                shouldStop=True,
                completionReason="max_tool_calls_exceeded",
                finalAnswer="Остановка: достигнут лимит вызовов tools.",
            )
        elif elapsedSeconds >= self._runtimeSettings.maxExecutionSeconds:
            ret = StopDecisionModel(
                shouldStop=True,
                completionReason="max_execution_time_exceeded",
                finalAnswer="Остановка: достигнут лимит времени выполнения.",
            )
        else:
            ret = StopDecisionModel(
                shouldStop=False,
                completionReason=None,
                finalAnswer=None,
            )
        return ret
