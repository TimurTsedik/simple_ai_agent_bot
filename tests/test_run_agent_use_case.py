from typing import Literal

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
from app.domain.entities.routingResolution import RoutingResolutionEntity
from app.runtime.agentLoop import AgentLoopResultModel


class FakeRoutingPlanResolver:
    def __init__(self, in_entity: RoutingResolutionEntity) -> None:
        self._entity = in_entity

    def resolve(self, in_userMessage: str) -> RoutingResolutionEntity:
        _ = in_userMessage
        ret = self._entity
        return ret


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


def _baseRoutingEntity(
    *,
    skillsBlock: str,
    selectedSkillIds: list[str],
    allowToolCalls: bool,
    requiredFirstSuccessfulToolName: str,
    memoryMode: Literal["full", "long_term_only"],
) -> RoutingResolutionEntity:
    ret = RoutingResolutionEntity(
        skillsBlock=skillsBlock,
        selectedSkillIds=list(selectedSkillIds),
        allowToolCalls=allowToolCalls,
        requiredFirstSuccessfulToolName=requiredFirstSuccessfulToolName,
        memoryMode=memoryMode,
        routingSource="llm",
        routingPlanDump={
            "type": "route_plan",
            "selected_skill_ids": selectedSkillIds,
            "allow_tool_calls": allowToolCalls,
            "required_first_successful_tool_name": requiredFirstSuccessfulToolName,
            "memory_mode": memoryMode,
        },
        routingPromptSnapshot="routing snapshot",
        routingRawModelResponse=None,
        routingParseErrorCode=None,
        routingParseErrorMessage=None,
        routingFallbackReason=None,
        routingDiagnostics=(),
    )
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
    routingEntity = _baseRoutingEntity(
        skillsBlock="skill block",
        selectedSkillIds=["default_assistant"],
        allowToolCalls=True,
        requiredFirstSuccessfulToolName="",
        memoryMode="full",
    )
    useCase = RunAgentUseCase(
        in_agentLoop=FakeAgentLoop(in_result=loopResult),  # type: ignore[arg-type]
        in_routingPlanResolver=FakeRoutingPlanResolver(in_entity=routingEntity),
        in_memoryService=FakeMemoryService(),
        in_runRepository=repository,  # type: ignore[arg-type]
        in_settings=_buildSettings(),
    )

    _result = useCase.execute(in_sessionId="telegram:1", in_inputMessage="кто ты?")

    assert repository.savedRunRecord is not None
    configSnapshot = repository.savedRunRecord["effectiveConfigSnapshot"]
    assert "telegram" not in configSnapshot
    assert repository.savedRunRecord["fallbackEvents"] == []
    assert repository.savedRunRecord["routingSource"] == "llm"
    assert isinstance(repository.savedRunRecord["routingPlan"], dict)


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
    routingEntity = _baseRoutingEntity(
        skillsBlock="skill block",
        selectedSkillIds=["default_assistant"],
        allowToolCalls=True,
        requiredFirstSuccessfulToolName="",
        memoryMode="full",
    )
    useCase = RunAgentUseCase(
        in_agentLoop=FakeAgentLoop(in_result=loopResult),  # type: ignore[arg-type]
        in_routingPlanResolver=FakeRoutingPlanResolver(in_entity=routingEntity),
        in_memoryService=FakeMemoryService(),
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
    routingEntity = _baseRoutingEntity(
        skillsBlock="skill block",
        selectedSkillIds=["default_assistant", "compose_digest", "read_and_analyze_email"],
        allowToolCalls=True,
        requiredFirstSuccessfulToolName="read_email",
        memoryMode="long_term_only",
    )
    fakeMemoryService = FakeMemoryService()
    useCase = RunAgentUseCase(
        in_agentLoop=fakeAgentLoop,
        in_routingPlanResolver=FakeRoutingPlanResolver(in_entity=routingEntity),
        in_memoryService=fakeMemoryService,
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


def testRunAgentUseCaseRequiresUserTopicDigestToolForUserTopicSkill() -> None:
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
    routingEntity = _baseRoutingEntity(
        skillsBlock="skill block",
        selectedSkillIds=["default_assistant", "user_topic_telegram_digest"],
        allowToolCalls=True,
        requiredFirstSuccessfulToolName="user_topic_telegram_digest",
        memoryMode="full",
    )
    useCase = RunAgentUseCase(
        in_agentLoop=fakeAgentLoop,
        in_routingPlanResolver=FakeRoutingPlanResolver(in_entity=routingEntity),
        in_memoryService=FakeMemoryService(),
        in_runRepository=repository,  # type: ignore[arg-type]
        in_settings=_buildSettings(),
    )

    _ = useCase.execute(
        in_sessionId="telegram:topic",
        in_inputMessage="создай дайджест новостей по теме ИИ",
    )

    assert fakeAgentLoop.lastRequiredFirstToolName == "user_topic_telegram_digest"


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
    routingEntity = _baseRoutingEntity(
        skillsBlock="skill block",
        selectedSkillIds=["default_assistant", "telegram_news_digest"],
        allowToolCalls=True,
        requiredFirstSuccessfulToolName="digest_telegram_news",
        memoryMode="full",
    )
    useCase = RunAgentUseCase(
        in_agentLoop=fakeAgentLoop,
        in_routingPlanResolver=FakeRoutingPlanResolver(in_entity=routingEntity),
        in_memoryService=FakeMemoryService(),
        in_runRepository=repository,  # type: ignore[arg-type]
        in_settings=_buildSettings(),
    )

    _ = useCase.execute(
        in_sessionId="scheduler:telegram_news",
        in_inputMessage="покажи дайджест экономических новостей за последний час",
    )

    assert fakeAgentLoop.lastRequiredFirstToolName == "digest_telegram_news"


def testRunAgentUseCaseRequiresReadEmailForEmailOnlySkill() -> None:
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
    routingEntity = _baseRoutingEntity(
        skillsBlock="skill block",
        selectedSkillIds=["default_assistant", "read_and_analyze_email"],
        allowToolCalls=True,
        requiredFirstSuccessfulToolName="read_email",
        memoryMode="full",
    )
    useCase = RunAgentUseCase(
        in_agentLoop=fakeAgentLoop,
        in_routingPlanResolver=FakeRoutingPlanResolver(in_entity=routingEntity),
        in_memoryService=FakeMemoryService(),
        in_runRepository=repository,  # type: ignore[arg-type]
        in_settings=_buildSettings(),
    )

    _ = useCase.execute(
        in_sessionId="telegram:1",
        in_inputMessage="прочитай непрочитанные письма",
    )

    assert fakeAgentLoop.lastRequiredFirstToolName == "read_email"


def testRunAgentUseCaseDoesNotRequireToolForEmailPreferenceFeedbackSkill() -> None:
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
    routingEntity = _baseRoutingEntity(
        skillsBlock="skill block",
        selectedSkillIds=[
            "default_assistant",
            "email_preference_feedback",
            "read_and_analyze_email",
        ],
        allowToolCalls=True,
        requiredFirstSuccessfulToolName="",
        memoryMode="full",
    )
    useCase = RunAgentUseCase(
        in_agentLoop=fakeAgentLoop,
        in_routingPlanResolver=FakeRoutingPlanResolver(in_entity=routingEntity),
        in_memoryService=FakeMemoryService(),
        in_runRepository=repository,  # type: ignore[arg-type]
        in_settings=_buildSettings(),
    )

    _ = useCase.execute(
        in_sessionId="telegram:1",
        in_inputMessage="запомни: письма от research@aton.ru важные",
    )

    assert fakeAgentLoop.lastRequiredFirstToolName == ""


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
    routingEntity = _baseRoutingEntity(
        skillsBlock="skill block",
        selectedSkillIds=[
            "default_assistant",
            "telegram_digest_feedback",
            "telegram_news_digest",
        ],
        allowToolCalls=True,
        requiredFirstSuccessfulToolName="",
        memoryMode="full",
    )
    useCase = RunAgentUseCase(
        in_agentLoop=fakeAgentLoop,
        in_routingPlanResolver=FakeRoutingPlanResolver(in_entity=routingEntity),
        in_memoryService=FakeMemoryService(),
        in_runRepository=repository,  # type: ignore[arg-type]
        in_settings=_buildSettings(),
    )

    _ = useCase.execute(
        in_sessionId="telegram:1",
        in_inputMessage="мне понравились новости про ИИ, запомни",
    )

    assert fakeAgentLoop.lastRequiredFirstToolName == ""
