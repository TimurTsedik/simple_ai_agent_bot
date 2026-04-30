from app.application.useCases.runAgentUseCase import RunAgentUseCase
from app.config.settingsModels import (
    AppSettings,
    LoggingSettings,
    MemorySettings,
    ModelSettings,
    RuntimeSettings,
    SecuritySettings,
    SettingsModel,
    SkillsSettings,
    TelegramSettings,
)
from app.runtime.agentLoop import AgentLoopResultModel
from app.skills.services.skillService import SkillSelectionResultModel


class FakeSkillService:
    def __init__(self) -> None:
        self._selectionResult = SkillSelectionResultModel(
            selectedSkillIds=["default_assistant"],
            skillsBlock="skill block",
        )

    def buildSkillsSelection(self, in_userMessage: str) -> SkillSelectionResultModel:
        _ = in_userMessage
        ret = self._selectionResult
        return ret

    def isToolLikelyRequired(self, in_userMessage: str) -> bool:
        _ = in_userMessage
        ret = True
        return ret

    def setSelectedSkillIds(self, in_skillIds: list[str]) -> None:
        self._selectionResult = SkillSelectionResultModel(
            selectedSkillIds=in_skillIds,
            skillsBlock="skill block",
        )


class FakeMemoryService:
    def __init__(self) -> None:
        self.calledBuildMemoryBlock = False
        self.calledBuildLongTermOnlyMemoryBlock = False

    def buildMemoryBlock(self, in_sessionId: str) -> str:
        _ = in_sessionId
        self.calledBuildMemoryBlock = True
        ret = "memory block"
        return ret

    def buildLongTermOnlyMemoryBlock(self) -> str:
        self.calledBuildLongTermOnlyMemoryBlock = True
        ret = "long-term only memory block"
        return ret

    def updateAfterRun(
        self,
        in_sessionId: str,
        in_userMessage: str,
        in_finalAnswer: str,
        in_memoryCandidates: list[str],
    ) -> None:
        _ = in_sessionId
        _ = in_userMessage
        _ = in_finalAnswer
        _ = in_memoryCandidates


class FakeRunRepository:
    def __init__(self) -> None:
        self.savedRunRecord: dict | None = None

    def saveRun(self, in_runRecord: dict) -> None:
        self.savedRunRecord = in_runRecord


class FakeAgentLoop:
    def __init__(self, in_result: AgentLoopResultModel) -> None:
        self._result = in_result
        self.lastRequiredFirstToolName = ""
        self.lastMemoryBlock = ""

    def run(
        self,
        in_userMessage: str,
        in_skillsBlock: str,
        in_memoryBlock: str,
        in_allowToolCalls: bool = True,
        in_requiredFirstSuccessfulToolName: str = "",
    ) -> AgentLoopResultModel:
        _ = in_userMessage
        _ = in_skillsBlock
        self.lastMemoryBlock = in_memoryBlock
        _ = in_allowToolCalls
        self.lastRequiredFirstToolName = in_requiredFirstSuccessfulToolName
        ret = self._result
        return ret


def _buildSettings() -> SettingsModel:
    ret = SettingsModel(
        app=AppSettings(appName="test", environment="test", dataRootPath="./data"),
        telegram=TelegramSettings(
            pollingTimeoutSeconds=10,
            allowedUserIds=[1],
            denyMessageText="deny",
            digestChannelUsernames=["channel_one"],
            portfolioTickers=["AAA"],
            digestSemanticKeywords=["рынок"],
        ),
        models=ModelSettings(
            openRouterBaseUrl="https://openrouter.ai/api/v1",
            primaryModel="m1",
            secondaryModel="m2",
            tertiaryModel="m3",
            requestTimeoutSeconds=45,
            retryCountBeforeFallback=2,
            returnToPrimaryCooldownSeconds=300,
        ),
        runtime=RuntimeSettings(
            maxSteps=5,
            maxToolCalls=5,
            maxExecutionSeconds=30,
            maxToolOutputChars=1000,
            maxPromptChars=5000,
            recentMessagesLimit=12,
            sessionSummaryMaxChars=2000,
            skillSelectionMaxCount=4,
            extraSecondsPerLlmError=0,
            maxExtraSecondsTotal=0,
        ),
        security=SecuritySettings(
            webSessionCookieTtlSeconds=3600,
            maxAdminTokens=3,
            allowedReadOnlyPaths=["./data"],
        ),
        logging=LoggingSettings(
            logsDirPath="./data/logs",
            runLogsFileName="run.jsonl",
            appLogsFileName="app.log",
            maxBytes=10485760,
            backupCount=5,
        ),
        skills=SkillsSettings(skillsDirPath="./app/skills/assets"),
        memory=MemorySettings(
            memoryRootPath="./data/memory",
            longTermFileName="long_term.md",
            sessionSummaryFileName="summary.md",
            recentMessagesFileName="recent.md",
        ),
        telegramBotToken="tg-token",
        openRouterApiKey="or-key",
        sessionCookieSecret="cookie-secret-0123456789abcdef-XYZ",
        adminRawTokens=["token-one-12345678"],
    )
    return ret


def testRunAgentUseCaseDropsToolConfigWhenNoToolCalls() -> None:
    loopResult = AgentLoopResultModel(
        completionReason="final_answer",
        finalAnswer="ok",
        stepCount=1,
        toolCallCount=0,
        selectedModel="m1",
        memoryCandidates=[],
        executionDurationMs=10,
        stepTraces=[
            {
                "rawModelResponse": '{"type":"final"}',
                "parsedModelResponse": {"outputType": "final"},
                "toolCall": None,
                "toolResult": None,
                "observation": None,
            }
        ],
        promptSnapshot="prompt",
        fallbackEvents=(),
    )
    repository = FakeRunRepository()
    useCase = RunAgentUseCase(
        in_agentLoop=FakeAgentLoop(in_result=loopResult),  # type: ignore[arg-type]
        in_skillService=FakeSkillService(),  # type: ignore[arg-type]
        in_memoryService=FakeMemoryService(),  # type: ignore[arg-type]
        in_runRepository=repository,  # type: ignore[arg-type]
        in_settings=_buildSettings(),
    )

    _result = useCase.execute(in_sessionId="telegram:1", in_inputMessage="кто ты?")

    assert repository.savedRunRecord is not None
    configSnapshot = repository.savedRunRecord["effectiveConfigSnapshot"]
    assert "telegram" not in configSnapshot
    assert repository.savedRunRecord["fallbackEvents"] == []


def testRunAgentUseCaseKeepsToolConfigWhenToolCallExists() -> None:
    loopResult = AgentLoopResultModel(
        completionReason="final_answer",
        finalAnswer="ok",
        stepCount=1,
        toolCallCount=1,
        selectedModel="m1",
        memoryCandidates=[],
        executionDurationMs=10,
        stepTraces=[
            {
                "rawModelResponse": '{"type":"tool_call"}',
                "parsedModelResponse": {"outputType": "tool_call"},
                "toolCall": {"toolName": "digest_telegram_news", "args": {}},
                "toolResult": {"ok": True},
                "observation": "obs",
            }
        ],
        promptSnapshot="prompt",
        fallbackEvents=(
            {"event": "model_error", "model": "m1", "errorCode": "TIMEOUT", "errorMessage": "x"},
        ),
    )
    repository = FakeRunRepository()
    useCase = RunAgentUseCase(
        in_agentLoop=FakeAgentLoop(in_result=loopResult),  # type: ignore[arg-type]
        in_skillService=FakeSkillService(),  # type: ignore[arg-type]
        in_memoryService=FakeMemoryService(),  # type: ignore[arg-type]
        in_runRepository=repository,  # type: ignore[arg-type]
        in_settings=_buildSettings(),
    )

    _result = useCase.execute(
        in_sessionId="telegram:1",
        in_inputMessage="сделай дайджест новостей",
    )

    assert repository.savedRunRecord is not None
    configSnapshot = repository.savedRunRecord["effectiveConfigSnapshot"]
    assert "telegram" in configSnapshot
    assert "digestChannelUsernames" not in configSnapshot["telegram"]
    assert "portfolioTickers" not in configSnapshot["telegram"]
    assert "digestSemanticKeywords" not in configSnapshot["telegram"]
    assert "telegramNewsDigest" not in configSnapshot["tools"]
    assert len(repository.savedRunRecord["fallbackEvents"]) == 1


def testRunAgentUseCaseRequiresReadEmailForEmailDigestSkills() -> None:
    loopResult = AgentLoopResultModel(
        completionReason="final_answer",
        finalAnswer="ok",
        stepCount=1,
        toolCallCount=0,
        selectedModel="m1",
        memoryCandidates=[],
        executionDurationMs=10,
        stepTraces=[],
        promptSnapshot="prompt",
        fallbackEvents=(),
    )
    repository = FakeRunRepository()
    fakeAgentLoop = FakeAgentLoop(in_result=loopResult)  # type: ignore[arg-type]
    fakeSkillService = FakeSkillService()
    fakeSkillService.setSelectedSkillIds(
        ["default_assistant", "compose_digest", "read_and_analyze_email"]
    )
    fakeMemoryService = FakeMemoryService()
    useCase = RunAgentUseCase(
        in_agentLoop=fakeAgentLoop,
        in_skillService=fakeSkillService,  # type: ignore[arg-type]
        in_memoryService=fakeMemoryService,  # type: ignore[arg-type]
        in_runRepository=repository,  # type: ignore[arg-type]
        in_settings=_buildSettings(),
    )

    _ = useCase.execute(
        in_sessionId="scheduler:email",
        in_inputMessage="прочитай непрочитанные письма и сделай дайджест",
    )

    assert fakeAgentLoop.lastRequiredFirstToolName == "read_email"
    assert fakeAgentLoop.lastMemoryBlock == "long-term only memory block"
    assert fakeMemoryService.calledBuildLongTermOnlyMemoryBlock is True
    assert fakeMemoryService.calledBuildMemoryBlock is False


def testRunAgentUseCaseRequiresDigestToolForTelegramNewsSkill() -> None:
    loopResult = AgentLoopResultModel(
        completionReason="final_answer",
        finalAnswer="ok",
        stepCount=1,
        toolCallCount=0,
        selectedModel="m1",
        memoryCandidates=[],
        executionDurationMs=10,
        stepTraces=[],
        promptSnapshot="prompt",
        fallbackEvents=(),
    )
    repository = FakeRunRepository()
    fakeAgentLoop = FakeAgentLoop(in_result=loopResult)  # type: ignore[arg-type]
    fakeSkillService = FakeSkillService()
    fakeSkillService.setSelectedSkillIds(
        ["default_assistant", "telegram_news_digest"]
    )
    useCase = RunAgentUseCase(
        in_agentLoop=fakeAgentLoop,
        in_skillService=fakeSkillService,  # type: ignore[arg-type]
        in_memoryService=FakeMemoryService(),  # type: ignore[arg-type]
        in_runRepository=repository,  # type: ignore[arg-type]
        in_settings=_buildSettings(),
    )

    _ = useCase.execute(
        in_sessionId="scheduler:telegram_news",
        in_inputMessage="покажи дайджест экономических новостей за последний час",
    )

    assert fakeAgentLoop.lastRequiredFirstToolName == "digest_telegram_news"


def testRunAgentUseCaseDoesNotRequireDigestToolForFeedbackSkill() -> None:
    loopResult = AgentLoopResultModel(
        completionReason="final_answer",
        finalAnswer="ok",
        stepCount=1,
        toolCallCount=0,
        selectedModel="m1",
        memoryCandidates=[],
        executionDurationMs=10,
        stepTraces=[],
        promptSnapshot="prompt",
        fallbackEvents=(),
    )
    repository = FakeRunRepository()
    fakeAgentLoop = FakeAgentLoop(in_result=loopResult)  # type: ignore[arg-type]
    fakeSkillService = FakeSkillService()
    fakeSkillService.setSelectedSkillIds(
        ["default_assistant", "telegram_digest_feedback", "telegram_news_digest"]
    )
    useCase = RunAgentUseCase(
        in_agentLoop=fakeAgentLoop,
        in_skillService=fakeSkillService,  # type: ignore[arg-type]
        in_memoryService=FakeMemoryService(),  # type: ignore[arg-type]
        in_runRepository=repository,  # type: ignore[arg-type]
        in_settings=_buildSettings(),
    )

    _ = useCase.execute(
        in_sessionId="telegram:1",
        in_inputMessage="мне понравились новости про ИИ, запомни",
    )

    assert fakeAgentLoop.lastRequiredFirstToolName == ""
