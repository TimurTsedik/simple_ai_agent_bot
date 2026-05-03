from typing import Literal

from app.common.ids import generateId
from app.common.timeProvider import getUtcNowIso
from app.config.settingsModels import SettingsModel
from app.domain.entities.agentRun import AgentRunModel
from app.domain.protocols.routingPlanResolverProtocol import RoutingPlanResolverProtocol
from app.memory.services.memoryService import MemoryService
from app.observability.stores.jsonRunRepository import JsonRunRepository
from app.runtime.agentLoop import AgentLoop


class RunAgentUseCase:
    def __init__(
        self,
        in_agentLoop: AgentLoop,
        in_routingPlanResolver: RoutingPlanResolverProtocol,
        in_memoryService: MemoryService,
        in_runRepository: JsonRunRepository,
        in_settings: SettingsModel,
    ) -> None:
        self._agentLoop = in_agentLoop
        self._routingPlanResolver = in_routingPlanResolver
        self._memoryService = in_memoryService
        self._runRepository = in_runRepository
        self._settings = in_settings

    def execute(
        self,
        in_sessionId: str,
        in_inputMessage: str,
        in_memoryPrincipalId: str | None = None,
    ) -> AgentRunModel:
        ret: AgentRunModel
        memoryPrincipalId = (
            in_memoryPrincipalId
            if in_memoryPrincipalId is not None
            else in_sessionId
        )
        traceId = generateId()
        runId = generateId()
        createdAt = getUtcNowIso()
        routingResolution = self._routingPlanResolver.resolve(
            in_userMessage=in_inputMessage,
            in_runId=runId,
        )
        skillsBlockText = routingResolution.skillsBlock
        memoryModeValue: Literal["full", "long_term_only"]
        memoryModeValue = routingResolution.memoryMode
        memoryBlock = self._resolveMemoryBlockFromRoutingMode(
            in_sessionId=in_sessionId,
            in_memoryPrincipalId=memoryPrincipalId,
            in_memoryMode=memoryModeValue,
        )
        loopResult = self._agentLoop.run(
            in_userMessage=in_inputMessage,
            in_skillsBlock=skillsBlockText,
            in_memoryBlock=memoryBlock,
            in_memoryPrincipalId=memoryPrincipalId,
            in_allowToolCalls=routingResolution.allowToolCalls,
            in_requiredFirstSuccessfulToolName=(
                routingResolution.requiredFirstSuccessfulToolName
            ),
            in_runId=runId,
        )
        toolCalls = [
            item.get("toolCall")
            for item in loopResult.stepTraces
            if item.get("toolCall") is not None
        ]
        toolResults = [
            item.get("toolResult")
            for item in loopResult.stepTraces
            if item.get("toolResult") is not None
        ]
        observations = [
            item.get("observation")
            for item in loopResult.stepTraces
            if item.get("observation") is not None
        ]
        self._memoryService.updateAfterRun(
            in_sessionId=in_sessionId,
            in_userMessage=in_inputMessage,
            in_finalAnswer=loopResult.finalAnswer,
            in_memoryCandidates=loopResult.memoryCandidates,
            in_memoryPrincipalId=memoryPrincipalId,
        )
        finishedAt = getUtcNowIso()
        runRecord = {
            "traceId": traceId,
            "runId": runId,
            "sessionId": in_sessionId,
            "sourceType": "telegram_or_internal",
            "inputMessage": in_inputMessage,
            "createdAt": createdAt,
            "finishedAt": finishedAt,
            "runStatus": "completed"
            if loopResult.completionReason in {"final_answer", "stop_response"}
            else "stopped",
            "completionReason": loopResult.completionReason,
            "selectedModel": loopResult.selectedModel,
            "selectedSkills": routingResolution.selectedSkillIds,
            "routingPlan": routingResolution.routingPlanDump,
            "routingSource": routingResolution.routingSource,
            "routingPromptSnapshot": routingResolution.routingPromptSnapshot,
            "routingRawModelResponse": routingResolution.routingRawModelResponse,
            "routingParseErrorCode": routingResolution.routingParseErrorCode,
            "routingParseErrorMessage": routingResolution.routingParseErrorMessage,
            "routingFallbackReason": routingResolution.routingFallbackReason,
            "routingDiagnostics": list(routingResolution.routingDiagnostics),
            "effectiveConfigSnapshot": self._buildEffectiveConfigSnapshot(
                in_includeToolConfig=len(toolCalls) > 0
            ),
            "promptSnapshot": loopResult.promptSnapshot,
            "rawModelResponses": [
                item.get("rawModelResponse")
                for item in loopResult.stepTraces
                if item.get("rawModelResponse") is not None
            ],
            "parsedResponses": [
                item.get("parsedModelResponse")
                for item in loopResult.stepTraces
                if item.get("parsedModelResponse") is not None
            ],
            "toolCalls": toolCalls,
            "toolResults": toolResults,
            "observations": observations,
            "fallbackEvents": list(loopResult.fallbackEvents),
            "finalAnswer": loopResult.finalAnswer,
            "memoryCandidates": loopResult.memoryCandidates,
            "stepTraces": loopResult.stepTraces,
            "timing": {
                "executionDurationMs": loopResult.executionDurationMs,
                "stepCount": loopResult.stepCount,
                "toolCallCount": loopResult.toolCallCount,
            },
        }
        self._runRepository.saveRun(in_runRecord=runRecord)
        ret = AgentRunModel(
            traceId=traceId,
            runId=runId,
            sessionId=in_sessionId,
            inputMessage=in_inputMessage,
            runStatus="completed",
            completionReason=loopResult.completionReason,
            finalAnswer=loopResult.finalAnswer,
            selectedModel=loopResult.selectedModel,
        )
        return ret

    def _resolveMemoryBlockFromRoutingMode(
        self,
        in_sessionId: str,
        in_memoryPrincipalId: str,
        in_memoryMode: Literal["full", "long_term_only"],
    ) -> str:
        ret: str
        if in_memoryMode == "long_term_only":
            ret = self._memoryService.buildLongTermOnlyMemoryBlock(
                in_memoryPrincipalId=in_memoryPrincipalId,
            )
        else:
            ret = self._memoryService.buildMemoryBlock(
                in_sessionId=in_sessionId,
                in_longTermPrincipalId=in_memoryPrincipalId,
            )
        return ret

    def _buildEffectiveConfigSnapshot(self, in_includeToolConfig: bool) -> dict:
        ret: dict
        snapshot = self._settings.model_dump(mode="python")
        snapshot["telegramBotToken"] = "***"
        snapshot["openRouterApiKey"] = "***"
        snapshot["sessionCookieSecret"] = "***"
        snapshot["emailAppPassword"] = "***" if self._settings.emailAppPassword else ""
        snapshot["adminRawTokens"] = ["***" for _item in self._settings.adminRawTokens]
        toolsSnapshot = snapshot.get("tools")
        if isinstance(toolsSnapshot, dict):
            toolsSnapshot.pop("telegramNewsDigest", None)
            emailReaderSnapshot = toolsSnapshot.get("emailReader")
            if isinstance(emailReaderSnapshot, dict) and "password" in emailReaderSnapshot:
                emailReaderSnapshot["password"] = "***"
        telegramSnapshot = snapshot.get("telegram")
        if isinstance(telegramSnapshot, dict):
            telegramSnapshot.pop("digestChannelUsernames", None)
            telegramSnapshot.pop("portfolioTickers", None)
            telegramSnapshot.pop("digestSemanticKeywords", None)
        if in_includeToolConfig is False:
            snapshot.pop("telegram", None)
        ret = snapshot
        return ret
