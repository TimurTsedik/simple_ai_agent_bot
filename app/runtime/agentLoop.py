from dataclasses import dataclass
from time import monotonic

from app.config.settingsModels import ModelSettings
from app.domain.policies.stopPolicy import StopPolicy
from app.domain.protocols.llmClientProtocol import LlmClientProtocol
from app.runtime.outputParser import OutputParser
from app.runtime.promptBuilder import PromptBuilder


@dataclass(frozen=True)
class AgentLoopResultModel:
    completionReason: str
    finalAnswer: str
    stepCount: int
    toolCallCount: int
    selectedModel: str


class AgentLoop:
    def __init__(
        self,
        in_llmClient: LlmClientProtocol,
        in_promptBuilder: PromptBuilder,
        in_outputParser: OutputParser,
        in_stopPolicy: StopPolicy,
        in_modelSettings: ModelSettings,
    ) -> None:
        self._llmClient = in_llmClient
        self._promptBuilder = in_promptBuilder
        self._outputParser = in_outputParser
        self._stopPolicy = in_stopPolicy
        self._modelSettings = in_modelSettings

    def run(self, in_userMessage: str) -> AgentLoopResultModel:
        ret: AgentLoopResultModel
        startedAtMonotonicSeconds = monotonic()
        stepCount = 0
        toolCallCount = 0
        observations: list[str] = []
        finalAnswer = "Остановка: не удалось завершить запрос корректно."
        completionReason = "fatal_runtime_error"
        selectedModel = self._modelSettings.primaryModel
        isFinished = False

        while isFinished is False:
            stopDecision = self._stopPolicy.evaluate(
                in_stepCount=stepCount,
                in_toolCallCount=toolCallCount,
                in_startedAtMonotonicSeconds=startedAtMonotonicSeconds,
            )
            if stopDecision.shouldStop is True:
                completionReason = stopDecision.completionReason or "fatal_runtime_error"
                finalAnswer = (
                    stopDecision.finalAnswer or "Остановка: контролируемое завершение."
                )
                isFinished = True
            else:
                promptText = self._promptBuilder.buildPrompt(
                    in_userMessage=in_userMessage,
                    in_observations=observations,
                )
                rawModelOutput = self._llmClient.complete(
                    in_modelName=selectedModel,
                    in_promptText=promptText,
                )
                parseResult = self._outputParser.parse(in_rawText=rawModelOutput)
                if parseResult.isValid is False or parseResult.parsedOutput is None:
                    completionReason = "stop_response"
                    finalAnswer = "Остановка: модель вернула невалидный JSON."
                    isFinished = True
                else:
                    parsedOutput = parseResult.parsedOutput
                    if parsedOutput.outputType == "final":
                        completionReason = "final_answer"
                        finalAnswer = parsedOutput.finalAnswer or ""
                        isFinished = True
                    elif parsedOutput.outputType == "stop":
                        completionReason = "stop_response"
                        finalAnswer = parsedOutput.finalAnswer or ""
                        isFinished = True
                    else:
                        toolCallCount += 1
                        toolName = parsedOutput.action or "unknown_tool"
                        observations.append(
                            f"Tool {toolName} временно недоступен в этом этапе."
                        )
                        completionReason = "running"
                        finalAnswer = ""
                        isFinished = False
                stepCount += 1

        ret = AgentLoopResultModel(
            completionReason=completionReason,
            finalAnswer=finalAnswer,
            stepCount=stepCount,
            toolCallCount=toolCallCount,
            selectedModel=selectedModel,
        )
        return ret
