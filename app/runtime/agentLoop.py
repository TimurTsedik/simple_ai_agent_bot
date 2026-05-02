import json
from dataclasses import dataclass
from time import monotonic
from typing import Any

from app.config.settingsModels import ModelSettings
from app.domain.entities.llmCompletionResult import LlmCompletionResultModel
from app.domain.policies.stopPolicy import StopPolicy
from app.domain.protocols.llmClientProtocol import LlmClientProtocol
from app.runtime.outputParser import OutputParser
from app.runtime.promptBuilder import PromptBuilder
from app.runtime.toolExecutionCoordinator import ToolExecutionCoordinator, ToolResultEnvelopeModel
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
    fallbackEvents: tuple[dict[str, Any], ...]


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
        in_memoryPrincipalId: str,
        in_allowToolCalls: bool = True,
        in_requiredFirstSuccessfulToolName: str = "",
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
        successfulToolNames: set[str] = set()
        toolNameToLastOkResult: dict[str, ToolResultEnvelopeModel] = {}
        toolNameToLastOkArgs: dict[str, dict[str, Any]] = {}
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
        toolSignatureWindow: list[str] = []
        blockedToolCallIterations = 0
        loopFallbackEvents: list[dict[str, Any]] = []
        llmErrorCount = 0
        toolTimeoutCounts: dict[str, int] = {}
        maxTimeoutsPerTool = 2
        missingRequiredToolFinalCount = 0
        requiredToolName = in_requiredFirstSuccessfulToolName.strip()
        pendingValidationRetryToolName = ""
        pendingValidationRetryCount = 0
        formatFailureStepsCount = 0
        consecutiveFormatFailures = 0
        runtimeSettings = self._stopPolicy.runtimeSettings

        while isFinished is False:
            stopDecision = self._stopPolicy.evaluate(
                in_stepCount=stepCount,
                in_toolCallCount=toolCallCount,
                in_startedAtMonotonicSeconds=startedAtMonotonicSeconds,
                in_llmErrorCount=llmErrorCount,
                in_formatFailureStepsCount=formatFailureStepsCount,
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
                llmResult = self._invokeLlm(
                    in_modelName=selectedModel,
                    in_promptText=promptText,
                    io_fallbackEvents=loopFallbackEvents,
                )
                selectedModel = llmResult.selectedModel
                rawModelOutput = llmResult.content
                parseResult = self._outputParser.parse(in_rawText=rawModelOutput)
                repairRawOutputs: list[str] = []
                maxRepairs = runtimeSettings.maxFormatRepairAttempts
                repairAttemptIndex = 0
                lastInvalidRaw = rawModelOutput
                while (
                    (parseResult.isValid is False or parseResult.parsedOutput is None)
                    and repairAttemptIndex < maxRepairs
                ):
                    repairPromptText = self._promptBuilder.buildYamlRepairPrompt(
                        in_previousRawOutput=lastInvalidRaw,
                        in_parseErrorCode=parseResult.errorCode,
                        in_parseErrorMessage=parseResult.errorMessage,
                        in_attemptIndexOneBased=repairAttemptIndex + 1,
                        in_maxAttempts=maxRepairs,
                    )
                    repairLlmResult = self._invokeLlm(
                        in_modelName=selectedModel,
                        in_promptText=repairPromptText,
                        io_fallbackEvents=loopFallbackEvents,
                        in_timeoutSeconds=self._modelSettings.formatRepairRequestTimeoutSeconds,
                    )
                    selectedModel = repairLlmResult.selectedModel
                    repairRawOutputs.append(repairLlmResult.content)
                    lastInvalidRaw = repairLlmResult.content
                    parseResult = self._outputParser.parse(in_rawText=lastInvalidRaw)
                    repairAttemptIndex += 1

                llmErrorCount = sum(
                    1
                    for item in loopFallbackEvents
                    if isinstance(item, dict) and item.get("event") == "model_error"
                )

                repairRawOutput: str | None = (
                    repairRawOutputs[-1] if len(repairRawOutputs) > 0 else None
                )

                stepTrace: dict[str, Any] = {
                    "stepIndex": stepCount + 1,
                    "promptSnapshot": promptText,
                    "rawModelResponse": rawModelOutput,
                    "repairRawModelResponse": repairRawOutput,
                    "repairRawModelResponses": repairRawOutputs,
                    "parsedModelResponse": None,
                    "toolCall": None,
                    "toolResult": None,
                    "observation": None,
                    "status": "running",
                }
                if parseResult.isValid is False or parseResult.parsedOutput is None:
                    formatFailureStepsCount += 1
                    consecutiveFormatFailures += 1
                    exhaustedObservation = json.dumps(
                        {
                            "kind": "format_repair_exhausted",
                            "reason": "runtime_yaml_parse_failed_after_repairs",
                            "parse_error_code": parseResult.errorCode,
                            "parse_error_message": parseResult.errorMessage,
                            "repair_attempts_done": len(repairRawOutputs),
                        },
                        ensure_ascii=False,
                    )
                    observations.append(exhaustedObservation)
                    stepTrace["status"] = "parse_error_recoverable"
                    stepTrace["parsedModelResponse"] = {
                        "isValid": False,
                        "errorCode": parseResult.errorCode,
                        "errorMessage": parseResult.errorMessage,
                    }
                    stepTrace["observation"] = exhaustedObservation
                    stepTraces.append(stepTrace)
                    stepCount += 1
                    if (
                        consecutiveFormatFailures
                        >= runtimeSettings.maxConsecutiveFormatFailureSteps
                    ):
                        completionReason = "final_answer"
                        finalAnswer = self._buildFallbackFinalAnswer(
                            in_observations=observations
                        )
                        isFinished = True
                    continue

                consecutiveFormatFailures = 0

                parsedOutput = parseResult.parsedOutput
                parsedFinalAnswer = parsedOutput.finalAnswer or ""
                if (
                    len(repairRawOutputs) > 0
                    and parsedOutput.outputType == "final"
                    and self._isTechnicalFinalAnswer(in_text=parsedFinalAnswer)
                ):
                    parsedFinalAnswer = self._buildFallbackFinalAnswer(
                        in_observations=observations
                    )
                stepTrace["parsedModelResponse"] = {
                    "outputType": parsedOutput.outputType,
                    "reason": parsedOutput.reason,
                    "action": parsedOutput.action,
                    "args": parsedOutput.args,
                    "finalAnswer": parsedFinalAnswer,
                    "memoryCandidates": parsedOutput.memoryCandidates,
                }
                if parsedOutput.outputType == "final":
                    if pendingValidationRetryToolName != "":
                        blockedObservation = json.dumps(
                            {
                                "kind": "final_blocked",
                                "reason": "retry_required_after_validation_error",
                                "required_tool_name": pendingValidationRetryToolName,
                                "message": (
                                    "Предыдущий вызов инструмента завершился ошибкой валидации. "
                                    f"Сначала исправь args и повтори `{pendingValidationRetryToolName}`."
                                ),
                            },
                            ensure_ascii=False,
                        )
                        observations.append(blockedObservation)
                        stepTrace["status"] = "final_blocked_validation_retry"
                        stepTrace["observation"] = blockedObservation
                        completionReason = "running"
                        finalAnswer = ""
                        isFinished = False
                        if pendingValidationRetryCount >= 2:
                            completionReason = "validation_retry_missing"
                            finalAnswer = (
                                "Не удалось завершить запрос: модель не исправила "
                                "ошибочный вызов инструмента после валидационной ошибки."
                            )
                            isFinished = True
                    elif requiredToolName and requiredToolName not in successfulToolNames:
                        missingRequiredToolFinalCount += 1
                        blockedObservation = json.dumps(
                            {
                                "kind": "final_blocked",
                                "reason": "required_tool_not_called",
                                "required_tool_name": requiredToolName,
                                "message": (
                                    f"Перед final-ответом нужен успешный вызов `{requiredToolName}`."
                                ),
                            },
                            ensure_ascii=False,
                        )
                        observations.append(blockedObservation)
                        stepTrace["status"] = "final_blocked_missing_required_tool"
                        stepTrace["observation"] = blockedObservation
                        completionReason = "running"
                        finalAnswer = ""
                        isFinished = False
                        if missingRequiredToolFinalCount >= 2:
                            completionReason = "required_tool_missing"
                            finalAnswer = (
                                f"Не удалось корректно обработать запрос: модель не вызвала "
                                f"обязательный инструмент `{requiredToolName}`."
                            )
                            isFinished = True
                    else:
                        blockedToolCallIterations = 0
                        completionReason = "final_answer"
                        finalAnswer = parsedFinalAnswer
                        memoryCandidates = parsedOutput.memoryCandidates or []
                        stepTrace["status"] = "final"
                        isFinished = True
                elif parsedOutput.outputType == "stop":
                    blockedToolCallIterations = 0
                    completionReason = "stop_response"
                    finalAnswer = parsedOutput.finalAnswer or ""
                    memoryCandidates = parsedOutput.memoryCandidates or []
                    stepTrace["status"] = "stop"
                    isFinished = True
                else:
                    if in_allowToolCalls is False:
                        blockedToolCallIterations += 1
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
                        maxBlocked = self._stopPolicy.runtimeSettings.maxToolCallBlockedIterations
                        if blockedToolCallIterations >= maxBlocked:
                            completionReason = "tool_call_blocked_limit"
                            finalAnswer = (
                                "Остановка: модель многократно запрашивала инструмент при "
                                "отключённых tool calls."
                            )
                            isFinished = True
                        continue
                    blockedToolCallIterations = 0
                    toolName = parsedOutput.action or "unknown_tool"
                    toolArgs = parsedOutput.args or {}

                    if toolName in successfulToolNames:
                        previousOkResult = toolNameToLastOkResult.get(toolName)
                        previousOkArgs = toolNameToLastOkArgs.get(toolName, {})
                        allowRepeat = False
                        if toolName == "read_email" and previousOkResult is not None:
                            try:
                                prevData = json.loads(str(previousOkResult.data or "{}"))
                                prevCount = int(prevData.get("count", 0)) if isinstance(prevData, dict) else 0
                            except Exception:
                                prevCount = 0
                            requestedMaxItems = int(toolArgs.get("maxItems", previousOkArgs.get("maxItems", 10) or 10))
                            if prevCount < requestedMaxItems:
                                prevUnreadOnly = bool(previousOkArgs.get("unreadOnly", True)) is True
                                newUnreadOnly = bool(toolArgs.get("unreadOnly", prevUnreadOnly)) is True
                                prevSinceHours = int(previousOkArgs.get("sinceHours", 24) or 24)
                                newSinceHours = int(toolArgs.get("sinceHours", prevSinceHours) or prevSinceHours)
                                isBroader = (prevUnreadOnly is True and newUnreadOnly is False) or (
                                    newSinceHours > prevSinceHours
                                )
                                if isBroader is True:
                                    allowRepeat = True
                        if toolName == "digest_telegram_news" and previousOkResult is not None:
                            prevCount = 0
                            prevFilteredOutByTime = 0
                            try:
                                prevData = json.loads(str(previousOkResult.data or "{}"))
                                if isinstance(prevData, dict):
                                    prevCount = int(prevData.get("count", 0) or 0)
                                    diagnostics = prevData.get("diagnostics", {})
                                    if isinstance(diagnostics, dict):
                                        prevFilteredOutByTime = int(
                                            diagnostics.get("filteredOutByTime", 0) or 0
                                        )
                            except Exception:
                                prevCount = 0
                                prevFilteredOutByTime = 0
                            prevSinceHours = int(previousOkArgs.get("sinceHours", 24) or 24)
                            newSinceHours = int(
                                toolArgs.get("sinceHours", prevSinceHours) or prevSinceHours
                            )
                            prevSinceUnixTs = int(previousOkArgs.get("sinceUnixTs", 0) or 0)
                            newSinceUnixTs = int(
                                toolArgs.get("sinceUnixTs", prevSinceUnixTs) or prevSinceUnixTs
                            )
                            isBroaderTimeWindow = (newSinceHours > prevSinceHours) or (
                                prevSinceUnixTs > 0
                                and (newSinceUnixTs == 0 or newSinceUnixTs < prevSinceUnixTs)
                            )
                            if (
                                prevCount == 0
                                and prevFilteredOutByTime > 0
                                and isBroaderTimeWindow is True
                            ):
                                allowRepeat = True
                        if toolName == "user_topic_telegram_digest" and previousOkResult is not None:
                            prevFetchUnreadFlag = bool(previousOkArgs.get("fetchUnread", False))
                            newFetchUnreadFlag = bool(toolArgs.get("fetchUnread", False))
                            if prevFetchUnreadFlag is False and newFetchUnreadFlag is True:
                                allowRepeat = True
                            elif prevFetchUnreadFlag is False and newFetchUnreadFlag is False:
                                prevTopicKey = str(previousOkArgs.get("topic", "") or "").strip().lower()
                                newTopicKey = str(toolArgs.get("topic", "") or "").strip().lower()
                                prevChannelsTuple = tuple(
                                    sorted(
                                        str(chItem).strip().lower()
                                        for chItem in (previousOkArgs.get("channels") or [])
                                        if str(chItem).strip() != ""
                                    )
                                )
                                newChannelsTuple = tuple(
                                    sorted(
                                        str(chItem).strip().lower()
                                        for chItem in (toolArgs.get("channels") or [])
                                        if str(chItem).strip() != ""
                                    )
                                )
                                prevKeywordsTuple = tuple(
                                    sorted(
                                        str(kwItem).strip().lower()
                                        for kwItem in (previousOkArgs.get("keywords") or [])
                                        if str(kwItem).strip() != ""
                                    )
                                )
                                newKeywordsTuple = tuple(
                                    sorted(
                                        str(kwItem).strip().lower()
                                        for kwItem in (toolArgs.get("keywords") or [])
                                        if str(kwItem).strip() != ""
                                    )
                                )
                                if prevTopicKey != newTopicKey:
                                    allowRepeat = True
                                elif prevChannelsTuple != newChannelsTuple or prevKeywordsTuple != newKeywordsTuple:
                                    allowRepeat = True
                        if allowRepeat is True:
                            blockedToolCallIterations = 0
                        else:
                            blockedToolCallIterations += 1
                            blockedPayload: dict[str, Any] = {
                                "kind": "tool_call_blocked",
                                "tool_name": toolName,
                                "reason": "tool_already_succeeded_in_this_run",
                                "message": "Инструмент уже был успешно вызван в этом run. "
                                "Сформируй final-ответ по последним данным, без повторного вызова.",
                            }
                            if previousOkResult is not None:
                                blockedPayload["previous_observation_preview"] = (
                                    self._buildToolObservationPreview(
                                        in_toolResult=previousOkResult
                                    )
                                )
                            blockedObservation = json.dumps(blockedPayload, ensure_ascii=False)
                            observations.append(blockedObservation)
                            stepTrace["status"] = "tool_call_blocked"
                            stepTrace["toolCall"] = {"toolName": toolName, "args": toolArgs}
                            stepTrace["observation"] = blockedObservation
                            completionReason = "running"
                            finalAnswer = ""
                            isFinished = False
                            stepTraces.append(stepTrace)
                            stepCount += 1
                            maxBlocked = self._stopPolicy.runtimeSettings.maxToolCallBlockedIterations
                            if blockedToolCallIterations >= maxBlocked:
                                completionReason = "tool_call_blocked_limit"
                                finalAnswer = (
                                    "Остановка: модель многократно запрашивала повтор инструмента "
                                    "после успешного результата."
                                )
                                isFinished = True
                            continue

                    blockedToolCallIterations = 0
                    toolCallCount += 1
                    toolSignature = json.dumps(
                        {"toolName": toolName, "args": toolArgs},
                        ensure_ascii=False,
                        sort_keys=True,
                    )
                    windowSize = self._stopPolicy.runtimeSettings.toolCallHistoryWindowSize
                    maxInWindow = self._stopPolicy.runtimeSettings.maxSameToolSignatureInWindow
                    signatureCountInWindow = self._countSignatureInWindow(
                        in_window=toolSignatureWindow,
                        in_signature=toolSignature,
                    )
                    if signatureCountInWindow >= maxInWindow - 1:
                        completionReason = "repeated_tool_call_loop"
                        finalAnswer = (
                            "Остановка: слишком частые повторы одного и того же вызова инструмента."
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
                        in_memoryPrincipalId=in_memoryPrincipalId,
                    )
                    digestAutoRetried = False
                    digestAutoRetryArgs: dict[str, Any] | None = None
                    if (
                        toolName == "digest_telegram_news"
                        and toolResult.ok is True
                        and toolCallCount < self._stopPolicy.runtimeSettings.maxToolCalls
                    ):
                        retryArgs = self._buildDigestAutoRetryArgs(
                            in_originalArgs=toolArgs,
                            in_toolResult=toolResult,
                        )
                        if retryArgs is not None:
                            digestAutoRetried = True
                            digestAutoRetryArgs = retryArgs
                            toolCallCount += 1
                            toolResult = self._toolExecutionCoordinator.execute(
                                in_toolName=toolName,
                                in_rawArgs=retryArgs,
                                in_memoryPrincipalId=in_memoryPrincipalId,
                            )
                            toolArgs = retryArgs
                    if (
                        toolResult.ok is False
                        and isinstance(toolResult.error, dict)
                        and str(toolResult.error.get("code", "")) == "TIMEOUT"
                    ):
                        toolTimeoutCounts[toolName] = toolTimeoutCounts.get(toolName, 0) + 1
                    else:
                        toolTimeoutCounts[toolName] = 0
                    if toolResult.ok is True:
                        successfulToolNames.add(toolName)
                        toolNameToLastOkResult[toolName] = toolResult
                        toolNameToLastOkArgs[toolName] = dict(toolArgs)
                        if requiredToolName and toolName == requiredToolName:
                            missingRequiredToolFinalCount = 0
                        if toolName == pendingValidationRetryToolName:
                            pendingValidationRetryToolName = ""
                            pendingValidationRetryCount = 0
                    elif (
                        isinstance(toolResult.error, dict)
                        and str(toolResult.error.get("code", "")) == "VALIDATION_ERROR"
                    ):
                        pendingValidationRetryToolName = toolName
                        pendingValidationRetryCount += 1
                    self._appendToolSignatureWindow(
                        io_window=toolSignatureWindow,
                        in_signature=toolSignature,
                        in_maxSize=windowSize,
                    )
                    observationText = self._buildToolObservationText(
                        in_toolResult=toolResult
                    )
                    observations.append(observationText)
                    if (
                        isinstance(toolResult.error, dict)
                        and str(toolResult.error.get("code", "")) == "VALIDATION_ERROR"
                    ):
                        validationHintObservation = json.dumps(
                            {
                                "kind": "tool_validation_error_retry_hint",
                                "tool_name": toolName,
                                "message": (
                                    "Инструмент вернул VALIDATION_ERROR. "
                                    "Сделай следующий шаг как tool_call с исправленными args. "
                                    "Не отправляй final и не задавай пользователю уточнение на этом шаге."
                                ),
                                "validation_error": toolResult.error.get("message", ""),
                            },
                            ensure_ascii=False,
                        )
                        observations.append(validationHintObservation)
                    stepTrace["status"] = "tool_call"
                    stepTrace["toolCall"] = {
                        "toolName": toolName,
                        "args": toolArgs,
                    }
                    if digestAutoRetried is True:
                        stepTrace["digestAutoRetry"] = {
                            "applied": True,
                            "reason": "empty_results_all_filtered_by_time",
                            "retryArgs": digestAutoRetryArgs,
                        }
                    stepTrace["toolResult"] = {
                        "ok": toolResult.ok,
                        "tool_name": toolResult.tool_name,
                        "data": toolResult.data,
                        "error": toolResult.error,
                        "meta": toolResult.meta,
                    }
                    stepTrace["observation"] = observationText
                    timeoutCount = toolTimeoutCounts.get(toolName, 0)
                    if timeoutCount >= maxTimeoutsPerTool:
                        completionReason = "tool_timeout_limit"
                        finalAnswer = (
                            "Не удалось завершить запрос: инструмент "
                            f"`{toolName}` несколько раз превысил лимит времени. "
                            "Попробуйте повторить запрос позже."
                        )
                        stepTrace["status"] = "tool_timeout_limit"
                        isFinished = True
                    else:
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
            fallbackEvents=tuple(loopFallbackEvents),
        )
        return ret

    def _invokeLlm(
        self,
        in_modelName: str,
        in_promptText: str,
        io_fallbackEvents: list[dict[str, Any]],
        *,
        in_timeoutSeconds: int | None = None,
        in_useJsonObjectResponseFormat: bool = False,
    ) -> LlmCompletionResultModel:
        ret: LlmCompletionResultModel
        llmResult = self._llmClient.complete(
            in_modelName=in_modelName,
            in_promptText=in_promptText,
            in_timeoutSeconds=in_timeoutSeconds,
            in_useJsonObjectResponseFormat=in_useJsonObjectResponseFormat,
        )
        io_fallbackEvents.extend(list(llmResult.fallbackEvents))
        ret = llmResult
        return ret

    def _countSignatureInWindow(self, in_window: list[str], in_signature: str) -> int:
        ret: int
        countValue = 0
        for oneSig in in_window:
            if oneSig == in_signature:
                countValue += 1
        ret = countValue
        return ret

    def _appendToolSignatureWindow(
        self,
        io_window: list[str],
        in_signature: str,
        in_maxSize: int,
    ) -> None:
        io_window.append(in_signature)
        while len(io_window) > in_maxSize:
            io_window.pop(0)

    def _buildToolObservationText(self, in_toolResult: ToolResultEnvelopeModel) -> str:
        ret: str
        payload: dict[str, Any] = {
            "kind": "tool_observation",
            "tool_name": in_toolResult.tool_name,
            "ok": in_toolResult.ok,
            "duration_ms": in_toolResult.meta.get("duration_ms"),
            "truncated": in_toolResult.meta.get("truncated"),
        }
        if in_toolResult.error is not None:
            payload["error"] = {
                "code": in_toolResult.error.get("code", ""),
                "message": in_toolResult.error.get("message", ""),
            }
        if in_toolResult.ok is True and in_toolResult.data is not None:
            dataStr = str(in_toolResult.data)
            payload["telegram_link_count"] = dataStr.count("https://t.me/")
            sampleLinks: list[str] = []
            try:
                parsedValue = json.loads(dataStr)
                if isinstance(parsedValue, dict) and isinstance(parsedValue.get("items"), list):
                    itemList = parsedValue.get("items", [])
                    for oneItem in itemList[:5]:
                        if isinstance(oneItem, dict) and isinstance(oneItem.get("link"), str):
                            sampleLinks.append(oneItem["link"])
                    payload["sample_links"] = sampleLinks
                    previewItems: list[dict[str, Any]] = []
                    for oneItem in itemList[:10]:
                        if isinstance(oneItem, dict):
                            previewItems.append(
                                {
                                    "channel": oneItem.get("channel"),
                                    "dateUnixTs": oneItem.get("dateUnixTs"),
                                    "summary": str(oneItem.get("summary", ""))[:240],
                                    "link": oneItem.get("link"),
                                }
                            )
                    payload["data_preview"] = {
                        "count": parsedValue.get("count"),
                        "sinceUnixTsUsed": parsedValue.get("sinceUnixTsUsed"),
                        "items_preview": previewItems,
                        "channelErrorsCount": (
                            len(parsedValue.get("channelErrors", {}))
                            if isinstance(parsedValue.get("channelErrors"), dict)
                            else None
                        ),
                    }
                    diagnosticsValue = parsedValue.get("diagnostics", {})
                    if isinstance(diagnosticsValue, dict):
                        payload["data_preview"]["filteredOutByTime"] = diagnosticsValue.get(
                            "filteredOutByTime"
                        )
                        payload["data_preview"]["filteredOutByKeywords"] = diagnosticsValue.get(
                            "filteredOutByKeywords"
                        )
                    if in_toolResult.tool_name == "digest_telegram_news":
                        diagnosticsDictDigest: dict[str, Any]
                        diagnosticsDictDigest = (
                            diagnosticsValue if isinstance(diagnosticsValue, dict) else {}
                        )
                        digestCountPayload = parsedValue.get("count", 0)
                        digestCountNormalized = 0
                        try:
                            digestCountNormalized = int(digestCountPayload)
                        except (TypeError, ValueError):
                            digestCountNormalized = 0
                        resolvedChanListParsed = parsedValue.get("resolvedChannels", [])
                        resolvedChannelsGuess = diagnosticsDictDigest.get("resolvedChannelsCount")
                        if isinstance(resolvedChannelsGuess, (int, float)):
                            resolvedChannelsCountNormalized = int(resolvedChannelsGuess)
                        elif isinstance(resolvedChanListParsed, list):
                            resolvedChannelsCountNormalized = len(resolvedChanListParsed)
                        else:
                            resolvedChannelsCountNormalized = 0
                        requestedChanRawDigest = diagnosticsDictDigest.get(
                            "requestedChannelsCount",
                            0,
                        )
                        if isinstance(requestedChanRawDigest, (int, float)):
                            requestedChannelsCountNormalized = int(requestedChanRawDigest)
                        else:
                            requestedChannelsCountNormalized = 0
                        filtTimeDigest = int(
                            diagnosticsDictDigest.get("filteredOutByTime", 0) or 0
                        )
                        filtKwDigest = int(
                            diagnosticsDictDigest.get("filteredOutByKeywords", 0) or 0
                        )
                        totalParsedPostsRaw = diagnosticsDictDigest.get("totalParsedPosts", 0)
                        try:
                            totalParsedPostsDigest = int(totalParsedPostsRaw or 0)
                        except (TypeError, ValueError):
                            totalParsedPostsDigest = 0
                        if digestCountNormalized == 0:
                            noChannelPipelineDigest = (
                                resolvedChannelsCountNormalized == 0
                                and filtTimeDigest == 0
                                and filtKwDigest == 0
                                and totalParsedPostsDigest == 0
                                and requestedChannelsCountNormalized == 0
                            )
                            if noChannelPipelineDigest is True:
                                payload["data_preview"]["digest_followup_hint"] = {
                                    "suggest_configure_named_topic_digest": True,
                                    "resolved_channels_count": resolvedChannelsCountNormalized,
                                    "requested_channels_count": requestedChannelsCountNormalized,
                                    "hint": (
                                        "В запросе нет каналов, действующего списка каналов по умолчанию "
                                        "тоже нет — постов не откуда взять. Чтобы тематический дайджест "
                                        "(экономика, техника…) продолжить, вызови user_topic_telegram_digest "
                                        "с fetchUnread=false и topic из формулировки пользователя, затем "
                                        "действуй по status (needs_channels/needs_keywords): задай короткий "
                                        "уточняющий вопрос; не заканчивай только фразой «новостей нет» без "
                                        "предложения настроить тему."
                                    ),
                                }
                if (
                    isinstance(parsedValue, dict)
                    and in_toolResult.tool_name == "web_search"
                ):
                    isPreview = bool(parsedValue.get("_preview", False)) is True
                    if isPreview is True and str(parsedValue.get("_tool_name", "")) == "web_search":
                        payload["web_search_preview"] = {
                            "query": parsedValue.get("query"),
                            "resultsCount": parsedValue.get("resultsCount"),
                            "fetchedPagesCount": parsedValue.get("fetchedPagesCount"),
                            "blockedUrlsCount": parsedValue.get("blockedUrlsCount"),
                            "fetchErrorsCount": parsedValue.get("fetchErrorsCount"),
                            "sampleResultUrls": parsedValue.get("sampleResultUrls", []),
                            "sampleFetchedUrls": parsedValue.get("sampleFetchedUrls", []),
                        }
                    else:
                        results = parsedValue.get("results", [])
                        fetchedPages = parsedValue.get("fetchedPages", [])
                        blockedUrls = parsedValue.get("blockedUrls", [])
                        fetchErrors = parsedValue.get("fetchErrors", [])
                        sampleResultUrls: list[str] = []
                        if isinstance(results, list):
                            for oneItem in results[:5]:
                                if isinstance(oneItem, dict) and isinstance(
                                    oneItem.get("url"), str
                                ):
                                    sampleResultUrls.append(oneItem["url"])
                        sampleFetchedUrls: list[str] = []
                        if isinstance(fetchedPages, list):
                            for oneItem in fetchedPages[:3]:
                                if isinstance(oneItem, dict) and isinstance(
                                    oneItem.get("url"), str
                                ):
                                    sampleFetchedUrls.append(oneItem["url"])
                        payload["web_search_preview"] = {
                            "query": parsedValue.get("query"),
                            "resultsCount": len(results) if isinstance(results, list) else None,
                            "fetchedPagesCount": (
                                len(fetchedPages) if isinstance(fetchedPages, list) else None
                            ),
                            "blockedUrlsCount": (
                                len(blockedUrls) if isinstance(blockedUrls, list) else None
                            ),
                            "fetchErrorsCount": (
                                len(fetchErrors) if isinstance(fetchErrors, list) else None
                            ),
                            "sampleResultUrls": sampleResultUrls,
                            "sampleFetchedUrls": sampleFetchedUrls,
                        }
                if isinstance(parsedValue, dict) and in_toolResult.tool_name == "read_email":
                    itemsValue = parsedValue.get("items", [])
                    emailPreviewItems: list[dict[str, Any]] = []
                    if isinstance(itemsValue, list):
                        for oneItem in itemsValue[:10]:
                            if isinstance(oneItem, dict):
                                emailPreviewItems.append(
                                    {
                                        "uid": str(oneItem.get("uid", ""))[:64],
                                        "from": str(oneItem.get("from", ""))[:160],
                                        "subject": str(oneItem.get("subject", ""))[:200],
                                        "date": str(oneItem.get("date", ""))[:120],
                                        "dateUnixTs": oneItem.get("dateUnixTs"),
                                        "snippet": str(oneItem.get("snippet", ""))[:120],
                                        "langHint": str(oneItem.get("langHint", ""))[:16],
                                    }
                                )
                    payload["email_preview"] = {
                        "count": parsedValue.get("count"),
                        "sinceUnixTsUsed": parsedValue.get("sinceUnixTsUsed"),
                        "filteredOutAlreadySeen": parsedValue.get("filteredOutAlreadySeen"),
                        "items_preview": emailPreviewItems,
                    }
                if (
                    isinstance(parsedValue, dict)
                    and in_toolResult.tool_name == "user_topic_telegram_digest"
                ):
                    savedConfigValue = parsedValue.get("savedConfig", {})
                    savedChannelsCount: int | None = None
                    savedKeywordsCount: int | None = None
                    if isinstance(savedConfigValue, dict):
                        channelsValue = savedConfigValue.get("channels", [])
                        keywordsValue = savedConfigValue.get("keywords", [])
                        if isinstance(channelsValue, list):
                            savedChannelsCount = len(channelsValue)
                        if isinstance(keywordsValue, list):
                            savedKeywordsCount = len(keywordsValue)
                    payload["user_topic_preview"] = {
                        "status": parsedValue.get("status"),
                        "topicKey": parsedValue.get("topicKey"),
                        "topicLabel": parsedValue.get("topicLabel"),
                        "hint": parsedValue.get("hint"),
                        "message": parsedValue.get("message"),
                        "count": parsedValue.get("count"),
                        "savedChannelsCount": savedChannelsCount,
                        "savedKeywordsCount": savedKeywordsCount,
                    }
            except json.JSONDecodeError:
                payload["data_note"] = "non_json_tool_payload"
        ret = json.dumps(payload, ensure_ascii=False)
        return ret

    def _buildToolObservationPreview(
        self,
        in_toolResult: ToolResultEnvelopeModel,
    ) -> dict[str, Any]:
        ret: dict[str, Any]
        preview: dict[str, Any] = {
            "kind": "tool_observation_preview",
            "tool_name": in_toolResult.tool_name,
            "ok": in_toolResult.ok,
            "duration_ms": in_toolResult.meta.get("duration_ms"),
        }
        if in_toolResult.ok is False:
            preview["error"] = in_toolResult.error
        if in_toolResult.ok is True and in_toolResult.data is not None:
            try:
                parsedValue = json.loads(str(in_toolResult.data))
                if isinstance(parsedValue, dict):
                    preview["count"] = parsedValue.get("count")
                    preview["sinceUnixTsUsed"] = parsedValue.get("sinceUnixTsUsed")
                    if in_toolResult.tool_name == "read_email":
                        preview["markedAsReadCount"] = parsedValue.get("markedAsReadCount")
                        preview["filteredOutAlreadySeen"] = parsedValue.get(
                            "filteredOutAlreadySeen"
                        )
                    if in_toolResult.tool_name == "digest_telegram_news":
                        diagnosticsPreview = parsedValue.get("diagnostics", {})
                        diagnosticsPreviewDict = (
                            diagnosticsPreview
                            if isinstance(diagnosticsPreview, dict)
                            else {}
                        )
                        digestCountPv = parsedValue.get("count", 0)
                        try:
                            digestCountNormPreview = int(digestCountPv)
                        except (TypeError, ValueError):
                            digestCountNormPreview = 0
                        reqChPrev = diagnosticsPreviewDict.get("requestedChannelsCount")
                        rcPrev = diagnosticsPreviewDict.get("resolvedChannelsCount")
                        reqNorm = int(reqChPrev or 0) if isinstance(reqChPrev, (int, float)) else 0
                        resolvedNormPv = (
                            int(rcPrev or 0) if isinstance(rcPrev, (int, float)) else None
                        )
                        if resolvedNormPv is None and isinstance(
                            parsedValue.get("resolvedChannels"),
                            list,
                        ):
                            resolvedNormPv = len(parsedValue["resolvedChannels"])
                        if resolvedNormPv is None:
                            resolvedNormPv = 0
                        tpPrevRaw = diagnosticsPreviewDict.get("totalParsedPosts")
                        try:
                            totalParsedPv = int(tpPrevRaw or 0)
                        except (TypeError, ValueError):
                            totalParsedPv = 0
                        if digestCountNormPreview == 0:
                            preview["digest_followup_suggested"] = (
                                resolvedNormPv == 0
                                and reqNorm == 0
                                and totalParsedPv == 0
                                and int(diagnosticsPreviewDict.get("filteredOutByTime") or 0) == 0
                                and int(diagnosticsPreviewDict.get("filteredOutByKeywords") or 0)
                                == 0
                            )
                    if in_toolResult.tool_name == "user_topic_telegram_digest":
                        preview["status"] = parsedValue.get("status")
                        preview["topicKey"] = parsedValue.get("topicKey")
                        preview["topicLabel"] = parsedValue.get("topicLabel")
                        preview["hint"] = parsedValue.get("hint")
                        preview["message"] = parsedValue.get("message")
            except Exception:
                preview["data_note"] = "non_json_tool_payload"
        ret = preview
        return ret

    def _buildDigestAutoRetryArgs(
        self,
        in_originalArgs: dict[str, Any],
        in_toolResult: ToolResultEnvelopeModel,
    ) -> dict[str, Any] | None:
        ret: dict[str, Any] | None
        ret = None
        if in_toolResult.ok is False:
            return ret
        try:
            parsedValue = json.loads(str(in_toolResult.data or "{}"))
        except Exception:
            return ret
        if not isinstance(parsedValue, dict):
            return ret
        countValue = int(parsedValue.get("count", 0) or 0)
        diagnosticsValue = parsedValue.get("diagnostics", {})
        filteredOutByTime = 0
        if isinstance(diagnosticsValue, dict):
            filteredOutByTime = int(diagnosticsValue.get("filteredOutByTime", 0) or 0)
        if countValue != 0 or filteredOutByTime <= 0:
            return ret
        originalSinceHours = int(in_originalArgs.get("sinceHours", 24) or 24)
        if originalSinceHours >= 168:
            return ret
        retrySinceHours = 72 if originalSinceHours < 72 else 168
        retryArgs = dict(in_originalArgs)
        retryArgs["sinceHours"] = retrySinceHours
        if int(retryArgs.get("sinceUnixTs", 0) or 0) > 0:
            retryArgs["sinceUnixTs"] = 0
        ret = retryArgs
        return ret

    def _isTechnicalFinalAnswer(self, in_text: str) -> bool:
        ret: bool
        loweredText = in_text.strip().lower()
        markers = [
            "valid json object",
            "corrected the output",
            "processed it as needed",
            "i have retrieved the requested information",
            "as required",
        ]
        ret = any(marker in loweredText for marker in markers)
        return ret

    def _buildFallbackFinalAnswer(self, in_observations: list[str]) -> str:
        ret: str
        ret = (
            "Не удалось корректно сформировать ответ: не удалось получить данные из инструментов. "
            "Повторите запрос."
        )
        for oneObservation in reversed(in_observations):
            try:
                payload = json.loads(oneObservation)
            except Exception:
                continue
            if not isinstance(payload, dict):
                continue
            if payload.get("kind") != "tool_observation":
                continue
            if payload.get("ok") is not True:
                continue
            toolName = str(payload.get("tool_name", ""))
            if toolName in {"digest_telegram_news", "user_topic_telegram_digest"}:
                dataPreview = payload.get("data_preview", {})
                if isinstance(dataPreview, dict):
                    itemsPreview = dataPreview.get("items_preview", [])
                    if isinstance(itemsPreview, list) and len(itemsPreview) > 0:
                        lines = ["Не удалось корректно отформатировать полный дайджест. Краткий итог:"]
                        for oneItem in itemsPreview[:5]:
                            if not isinstance(oneItem, dict):
                                continue
                            summaryText = str(oneItem.get("summary", "")).strip()
                            linkText = str(oneItem.get("link", "")).strip()
                            channelText = str(oneItem.get("channel", "")).strip()
                            if summaryText:
                                lineText = f"- {summaryText}"
                            else:
                                lineText = f"- Новость из канала {channelText or 'unknown'}"
                            if linkText:
                                lineText += f" ({linkText})"
                            lines.append(lineText)
                        ret = "\n".join(lines)
                        return ret
            if toolName == "read_email":
                emailPreview = payload.get("email_preview", {})
                if isinstance(emailPreview, dict):
                    itemsPreview = emailPreview.get("items_preview", [])
                    if isinstance(itemsPreview, list) and len(itemsPreview) > 0:
                        lines = ["Не удалось корректно отформатировать полный дайджест. Краткий итог по письмам:"]
                        for oneItem in itemsPreview[:5]:
                            if not isinstance(oneItem, dict):
                                continue
                            subjectText = str(oneItem.get("subject", "")).strip()
                            fromText = str(oneItem.get("from", "")).strip()
                            dateText = str(oneItem.get("date", "")).strip()
                            lineParts = [part for part in [subjectText, fromText, dateText] if part]
                            if len(lineParts) > 0:
                                lines.append(f"- {' | '.join(lineParts)}")
                        ret = "\n".join(lines)
                        return ret
        for oneObservation in reversed(in_observations):
            try:
                payload = json.loads(oneObservation)
            except Exception:
                continue
            if not isinstance(payload, dict):
                continue
            if payload.get("kind") != "tool_observation":
                continue
            if payload.get("ok") is not False:
                continue
            errorPayload = payload.get("error", {})
            toolName = str(payload.get("tool_name", ""))
            if isinstance(errorPayload, dict):
                errorCode = str(errorPayload.get("code", ""))
                if errorCode == "TIMEOUT" and toolName == "read_email":
                    ret = (
                        "Не удалось прочитать почту: инструмент превысил лимит времени. "
                        "Попробуйте повторить запрос через минуту."
                    )
                    break
                if errorCode == "TIMEOUT":
                    ret = (
                        "Не удалось завершить запрос: один из инструментов превысил лимит времени. "
                        "Попробуйте повторить запрос."
                    )
                    break
        return ret
