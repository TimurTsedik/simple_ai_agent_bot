from app.common.ids import generateId
from app.common.timeProvider import getUtcNowIso
from app.config.settingsModels import SettingsModel
from app.domain.entities.agentRun import AgentRunModel
from app.memory.services.memoryService import MemoryService
from app.observability.stores.jsonRunRepository import JsonRunRepository
from app.runtime.agentLoop import AgentLoop
from app.skills.services.skillService import SkillService


class RunAgentUseCase:
    def __init__(
        self,
        in_agentLoop: AgentLoop,
        in_skillService: SkillService,
        in_memoryService: MemoryService,
        in_runRepository: JsonRunRepository,
        in_settings: SettingsModel,
    ) -> None:
        self._agentLoop = in_agentLoop
        self._skillService = in_skillService
        self._memoryService = in_memoryService
        self._runRepository = in_runRepository
        self._settings = in_settings

    def execute(self, in_sessionId: str, in_inputMessage: str) -> AgentRunModel:
        ret: AgentRunModel
        traceId = generateId()
        runId = generateId()
        createdAt = getUtcNowIso()
        selectionResult = self._skillService.buildSkillsSelection(
            in_userMessage=in_inputMessage
        )
        skillsBlock = selectionResult.skillsBlock
        memoryBlock = self._memoryService.buildMemoryBlock(in_sessionId=in_sessionId)
        loopResult = self._agentLoop.run(
            in_userMessage=in_inputMessage,
            in_skillsBlock=skillsBlock,
            in_memoryBlock=memoryBlock,
            in_allowToolCalls=self._skillService.isToolLikelyRequired(
                in_userMessage=in_inputMessage
            ),
            in_requiredFirstSuccessfulToolName=self._resolveRequiredFirstSuccessfulToolName(
                in_selectedSkillIds=selectionResult.selectedSkillIds
            ),
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
            "selectedSkills": selectionResult.selectedSkillIds,
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

    def _resolveRequiredFirstSuccessfulToolName(
        self,
        in_selectedSkillIds: list[str],
    ) -> str:
        ret: str
        selectedSet = set(in_selectedSkillIds)
        if (
            "compose_digest" in selectedSet
            and "read_and_analyze_email" in selectedSet
        ):
            ret = "read_email"
        elif "telegram_news_digest" in selectedSet:
            ret = "digest_telegram_news"
        else:
            ret = ""
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
        telegramSnapshot = snapshot.get("telegram")
        if isinstance(telegramSnapshot, dict):
            telegramSnapshot.pop("digestChannelUsernames", None)
            telegramSnapshot.pop("portfolioTickers", None)
            telegramSnapshot.pop("digestSemanticKeywords", None)
        if in_includeToolConfig is False:
            snapshot.pop("telegram", None)
        ret = snapshot
        return ret
