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

        while isFinished is False:
            stopDecision = self._stopPolicy.evaluate(
                in_stepCount=stepCount,
                in_toolCallCount=toolCallCount,
                in_startedAtMonotonicSeconds=startedAtMonotonicSeconds,
                in_llmErrorCount=llmErrorCount,
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
                llmErrorCount = sum(
                    1
                    for item in loopFallbackEvents
                    if isinstance(item, dict) and item.get("event") == "model_error"
                )
                selectedModel = llmResult.selectedModel
                rawModelOutput = llmResult.content
                parseResult = self._outputParser.parse(in_rawText=rawModelOutput)
                repairRawOutput: str | None = None
                if parseResult.isValid is False or parseResult.parsedOutput is None:
                    repairPromptText = self._promptBuilder.buildJsonRepairPrompt(
                        in_previousRawOutput=rawModelOutput,
                        in_parseErrorCode=parseResult.errorCode,
                        in_parseErrorMessage=parseResult.errorMessage,
                    )
                    repairLlmResult = self._invokeLlm(
                        in_modelName=selectedModel,
                        in_promptText=repairPromptText,
                        io_fallbackEvents=loopFallbackEvents,
                    )
                    selectedModel = repairLlmResult.selectedModel
                    repairRawOutput = repairLlmResult.content
                    parseResult = self._outputParser.parse(in_rawText=repairRawOutput)

                stepTrace: dict[str, Any] = {
                    "stepIndex": stepCount + 1,
                    "promptSnapshot": promptText,
                    "rawModelResponse": rawModelOutput,
                    "repairRawModelResponse": repairRawOutput,
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
                    parsedFinalAnswer = parsedOutput.finalAnswer or ""
                    if (
                        repairRawOutput is not None
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
                        )
                        if toolResult.ok is True:
                            successfulToolNames.add(toolName)
                            toolNameToLastOkResult[toolName] = toolResult
                            toolNameToLastOkArgs[toolName] = dict(toolArgs)
                        self._appendToolSignatureWindow(
                            io_window=toolSignatureWindow,
                            in_signature=toolSignature,
                            in_maxSize=windowSize,
                        )
                        observationText = self._buildToolObservationText(
                            in_toolResult=toolResult
                        )
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
            fallbackEvents=tuple(loopFallbackEvents),
        )
        return ret

    def _invokeLlm(
        self,
        in_modelName: str,
        in_promptText: str,
        io_fallbackEvents: list[dict[str, Any]],
    ) -> LlmCompletionResultModel:
        ret: LlmCompletionResultModel
        llmResult = self._llmClient.complete(
            in_modelName=in_modelName,
            in_promptText=in_promptText,
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
                        "items_preview": emailPreviewItems,
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
            except Exception:
                preview["data_note"] = "non_json_tool_payload"
        ret = preview
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
        ret = "Не удалось корректно сформировать ответ. Повторите запрос."
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
