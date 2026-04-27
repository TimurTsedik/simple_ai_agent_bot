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

    @property
    def runtimeSettings(self) -> RuntimeSettings:
        ret: RuntimeSettings
        ret = self._runtimeSettings
        return ret

    def evaluate(
        self,
        in_stepCount: int,
        in_toolCallCount: int,
        in_startedAtMonotonicSeconds: float,
        in_llmErrorCount: int = 0,
    ) -> StopDecisionModel:
        ret: StopDecisionModel
        elapsedSeconds = monotonic() - in_startedAtMonotonicSeconds
        extraSeconds = min(
            max(0, int(in_llmErrorCount)) * self._runtimeSettings.extraSecondsPerLlmError,
            self._runtimeSettings.maxExtraSecondsTotal,
        )
        effectiveMaxSeconds = self._runtimeSettings.maxExecutionSeconds + extraSeconds
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
        elif elapsedSeconds >= effectiveMaxSeconds:
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
