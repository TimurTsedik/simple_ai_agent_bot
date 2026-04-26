from dataclasses import dataclass
import json
from time import monotonic
from typing import Any

from app.config.settingsModels import ModelSettings
from app.domain.policies.stopPolicy import StopPolicy
from app.domain.protocols.llmClientProtocol import LlmClientProtocol
from app.runtime.outputParser import OutputParser
from app.runtime.promptBuilder import PromptBuilder
from app.runtime.toolExecutionCoordinator import ToolExecutionCoordinator
from app.tools.registry.toolMetadataRenderer import ToolMetadataRenderer
from app.tools.registry.toolRegistry import ToolRegistry


@dataclass(frozen=True)
class AgentLoopResultModel:
    completionReason: str
    finalAnswer: str
    stepCount: int
    toolCallCount: int
    selectedModel: str
    memoryCandidates: list[str]
    executionDurationMs: int
    stepTraces: list[dict[str, Any]]
    promptSnapshot: str


class AgentLoop:
    def __init__(
        self,
        in_llmClient: LlmClientProtocol,
        in_promptBuilder: PromptBuilder,
        in_outputParser: OutputParser,
        in_stopPolicy: StopPolicy,
        in_modelSettings: ModelSettings,
        in_toolExecutionCoordinator: ToolExecutionCoordinator,
        in_toolMetadataRenderer: ToolMetadataRenderer,
        in_toolRegistry: ToolRegistry,
    ) -> None:
        self._llmClient = in_llmClient
        self._promptBuilder = in_promptBuilder
        self._outputParser = in_outputParser
        self._stopPolicy = in_stopPolicy
        self._modelSettings = in_modelSettings
        self._toolExecutionCoordinator = in_toolExecutionCoordinator
        self._toolMetadataRenderer = in_toolMetadataRenderer
        self._toolRegistry = in_toolRegistry

    def run(
        self,
        in_userMessage: str,
        in_skillsBlock: str,
        in_memoryBlock: str,
        in_allowToolCalls: bool = True,
    ) -> AgentLoopResultModel:
        ret: AgentLoopResultModel
        startedAtMonotonicSeconds = monotonic()
        stepCount = 0
        toolCallCount = 0
        observations: list[str] = []
        finalAnswer = "Остановка: не удалось завершить запрос корректно."
        completionReason = "fatal_runtime_error"
        selectedModel = self._modelSettings.primaryModel
        isFinished = False
        memoryCandidates: list[str] = []
        toolsDescription = (
            self._toolMetadataRenderer.renderForPrompt(in_toolRegistry=self._toolRegistry)
            if in_allowToolCalls is True
            else ""
        )
        stepTraces: list[dict[str, Any]] = []
        lastPromptSnapshot = ""
        lastToolSignature = ""
        repeatedToolCallCount = 0
        lastToolName = ""
        repeatedSameToolNameCount = 0

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
                    in_toolsDescription=toolsDescription,
                    in_skillsBlock=in_skillsBlock,
                    in_memoryBlock=in_memoryBlock,
                )
                lastPromptSnapshot = promptText
                rawModelOutput = self._llmClient.complete(
                    in_modelName=selectedModel,
                    in_promptText=promptText,
                )
                parseResult = self._outputParser.parse(in_rawText=rawModelOutput)
                stepTrace: dict[str, Any] = {
                    "stepIndex": stepCount + 1,
                    "promptSnapshot": promptText,
                    "rawModelResponse": rawModelOutput,
                    "parsedModelResponse": None,
                    "toolCall": None,
                    "toolResult": None,
                    "observation": None,
                    "status": "running",
                }
                if parseResult.isValid is False or parseResult.parsedOutput is None:
                    completionReason = "stop_response"
                    finalAnswer = "Остановка: модель вернула невалидный JSON."
                    stepTrace["status"] = "parse_error"
                    stepTrace["parsedModelResponse"] = {
                        "isValid": False,
                        "errorCode": parseResult.errorCode,
                        "errorMessage": parseResult.errorMessage,
                    }
                    isFinished = True
                else:
                    parsedOutput = parseResult.parsedOutput
                    stepTrace["parsedModelResponse"] = {
                        "outputType": parsedOutput.outputType,
                        "reason": parsedOutput.reason,
                        "action": parsedOutput.action,
                        "args": parsedOutput.args,
                        "finalAnswer": parsedOutput.finalAnswer,
                        "memoryCandidates": parsedOutput.memoryCandidates,
                    }
                    if parsedOutput.outputType == "final":
                        completionReason = "final_answer"
                        finalAnswer = parsedOutput.finalAnswer or ""
                        memoryCandidates = parsedOutput.memoryCandidates or []
                        stepTrace["status"] = "final"
                        isFinished = True
                    elif parsedOutput.outputType == "stop":
                        completionReason = "stop_response"
                        finalAnswer = parsedOutput.finalAnswer or ""
                        memoryCandidates = parsedOutput.memoryCandidates or []
                        stepTrace["status"] = "stop"
                        isFinished = True
                    else:
                        if in_allowToolCalls is False:
                            blockedObservation = (
                                "Tool calls are disabled for this request. "
                                "Answer directly without using any tool."
                            )
                            observations.append(blockedObservation)
                            stepTrace["status"] = "tool_call_blocked"
                            stepTrace["toolCall"] = {
                                "toolName": parsedOutput.action or "unknown_tool",
                                "args": parsedOutput.args or {},
                            }
                            stepTrace["observation"] = blockedObservation
                            completionReason = "running"
                            finalAnswer = ""
                            isFinished = False
                            stepTraces.append(stepTrace)
                            stepCount += 1
                            continue
                        toolCallCount += 1
                        toolName = parsedOutput.action or "unknown_tool"
                        toolArgs = parsedOutput.args or {}
                        toolSignature = json.dumps(
                            {"toolName": toolName, "args": toolArgs},
                            ensure_ascii=False,
                            sort_keys=True,
                        )
                        if toolSignature == lastToolSignature:
                            repeatedToolCallCount += 1
                        else:
                            repeatedToolCallCount = 1
                            lastToolSignature = toolSignature
                        if toolName == lastToolName:
                            repeatedSameToolNameCount += 1
                        else:
                            repeatedSameToolNameCount = 1
                            lastToolName = toolName
                        if repeatedToolCallCount >= 3:
                            completionReason = "repeated_tool_call_loop"
                            finalAnswer = (
                                "Остановка: обнаружен повторяющийся вызов одного и того же инструмента."
                            )
                            stepTrace["status"] = "repeated_tool_call_loop"
                            stepTrace["toolCall"] = {
                                "toolName": toolName,
                                "args": toolArgs,
                            }
                            isFinished = True
                            stepTraces.append(stepTrace)
                            stepCount += 1
                            break
                        if repeatedSameToolNameCount >= 3:
                            completionReason = "repeated_tool_call_loop"
                            finalAnswer = (
                                "Остановка: обнаружены повторные вызовы одного инструмента."
                            )
                            stepTrace["status"] = "repeated_tool_call_loop"
                            stepTrace["toolCall"] = {
                                "toolName": toolName,
                                "args": toolArgs,
                            }
                            isFinished = True
                            stepTraces.append(stepTrace)
                            stepCount += 1
                            break
                        toolResult = self._toolExecutionCoordinator.execute(
                            in_toolName=toolName,
                            in_rawArgs=toolArgs,
                        )
                        observationText = str(toolResult)
                        observations.append(observationText)
                        stepTrace["status"] = "tool_call"
                        stepTrace["toolCall"] = {
                            "toolName": toolName,
                            "args": toolArgs,
                        }
                        stepTrace["toolResult"] = {
                            "ok": toolResult.ok,
                            "tool_name": toolResult.tool_name,
                            "data": toolResult.data,
                            "error": toolResult.error,
                            "meta": toolResult.meta,
                        }
                        stepTrace["observation"] = observationText
                        completionReason = "running"
                        finalAnswer = ""
                        isFinished = False
                stepTraces.append(stepTrace)
                stepCount += 1

        executionDurationMs = int((monotonic() - startedAtMonotonicSeconds) * 1000)
        ret = AgentLoopResultModel(
            completionReason=completionReason,
            finalAnswer=finalAnswer,
            stepCount=stepCount,
            toolCallCount=toolCallCount,
            selectedModel=selectedModel,
            memoryCandidates=memoryCandidates,
            executionDurationMs=executionDurationMs,
            stepTraces=stepTraces,
            promptSnapshot=lastPromptSnapshot,
        )
        return ret
