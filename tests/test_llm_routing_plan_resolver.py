from pydantic import BaseModel, ConfigDict

from app.config.settingsModels import ModelSettings, RuntimeSettings
from app.domain.entities.llmCompletionResult import LlmCompletionResultModel
from app.runtime.llmRoutingPlanResolver import LlmRoutingPlanResolver
from app.runtime.promptBuilder import PromptBuilder
from app.runtime.routePlanParser import RoutePlanParser
from app.skills.services.skillSelectorRules import SkillSelectorRules
from app.skills.services.skillService import SkillService
from app.skills.stores.markdownSkillStore import MarkdownSkillStore
from app.tools.registry.toolRegistry import ToolDefinitionModel, ToolRegistry


class _StubEmailArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


class _StubVoidArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


class StubLlmForRoutingTests:
    def __init__(self, in_yamlResponse: str) -> None:
        self._yamlResponse = in_yamlResponse

    def complete(
        self,
        in_modelName: str,
        in_promptText: str,
        *,
        in_timeoutSeconds: int | None = None,
        in_useJsonObjectResponseFormat: bool = False,
        in_runId: str | None = None,
    ) -> LlmCompletionResultModel:
        _ = in_modelName
        _ = in_promptText
        _ = in_timeoutSeconds
        _ = in_useJsonObjectResponseFormat
        _ = in_runId
        ret = LlmCompletionResultModel(
            content=self._yamlResponse,
            selectedModel="stub",
            fallbackEvents=[],
        )
        return ret


def _buildSmallToolRegistryWithReadEmailOnly() -> ToolRegistry:
    def _dummyExec(in_args: dict) -> dict:
        _ = in_args
        return {}

    defs = [
        ToolDefinitionModel(
            name="read_email",
            description="Reads email inbox.",
            argsModel=_StubEmailArgs,
            timeoutSeconds=120,
            executeCallable=_dummyExec,
        ),
    ]
    ret = ToolRegistry(in_toolDefinitions=defs)
    return ret


def _buildToolRegistryWithTelegramDigestTools() -> ToolRegistry:
    def _dummyExec(in_args: dict) -> dict:
        _ = in_args
        return {}

    defs = [
        ToolDefinitionModel(
            name="digest_telegram_news",
            description="Digest Telegram.",
            argsModel=_StubVoidArgs,
            timeoutSeconds=60,
            executeCallable=_dummyExec,
        ),
        ToolDefinitionModel(
            name="user_topic_telegram_digest",
            description="User topic digest.",
            argsModel=_StubVoidArgs,
            timeoutSeconds=60,
            executeCallable=_dummyExec,
        ),
        ToolDefinitionModel(
            name="read_email",
            description="Reads email inbox.",
            argsModel=_StubEmailArgs,
            timeoutSeconds=120,
            executeCallable=_dummyExec,
        ),
    ]
    ret = ToolRegistry(in_toolDefinitions=defs)
    return ret


def _buildToolRegistryWithScheduleAndUserTopicDigests() -> ToolRegistry:
    def _dummyExec(in_args: dict) -> dict:
        _ = in_args
        return {}

    defs = [
        ToolDefinitionModel(
            name="digest_telegram_news",
            description="Digest Telegram.",
            argsModel=_StubVoidArgs,
            timeoutSeconds=60,
            executeCallable=_dummyExec,
        ),
        ToolDefinitionModel(
            name="user_topic_telegram_digest",
            description="User topic digest.",
            argsModel=_StubVoidArgs,
            timeoutSeconds=60,
            executeCallable=_dummyExec,
        ),
        ToolDefinitionModel(
            name="schedule_recurring_agent_run",
            description="Recurring internal run.",
            argsModel=_StubVoidArgs,
            timeoutSeconds=60,
            executeCallable=_dummyExec,
        ),
        ToolDefinitionModel(
            name="read_email",
            description="Reads email inbox.",
            argsModel=_StubEmailArgs,
            timeoutSeconds=120,
            executeCallable=_dummyExec,
        ),
    ]
    ret = ToolRegistry(in_toolDefinitions=defs)
    return ret


def _buildRuntimePromptBuilder() -> PromptBuilder:
    runtimeCfg = RuntimeSettings(
        maxSteps=10,
        maxToolCalls=5,
        maxExecutionSeconds=180,
        maxToolOutputChars=4000,
        maxPromptChars=12000,
        recentMessagesLimit=10,
        sessionSummaryMaxChars=1000,
        skillSelectionMaxCount=4,
    )
    promptBuilderInst = PromptBuilder(in_runtimeSettings=runtimeCfg)
    return promptBuilderInst


def _buildMinimalModelSettings() -> ModelSettings:
    ret = ModelSettings(
        openRouterBaseUrl="https://example.invalid",
        primaryModel="m1",
        secondaryModel="m2",
        tertiaryModel="m3",
        requestTimeoutSeconds=45,
        retryCountBeforeFallback=0,
        returnToPrimaryCooldownSeconds=3600,
    )
    return ret


def testLlmRoutingPlanResolverParsesLlMRoutePlanSuccessfully() -> None:
    yamlTextValue = """type: route_plan
selected_skill_ids:
  - read_and_analyze_email
allow_tool_calls: true
required_first_successful_tool_name: read_email
memory_mode: full
"""
    skillServiceMock = SkillService(
        in_skillStore=MarkdownSkillStore(in_skillsDirPath="./app/skills/assets"),
        in_skillSelectorRules=SkillSelectorRules(),
        in_skillSelectionMaxCount=4,
    )
    resolverUnderTest = LlmRoutingPlanResolver(
        in_llmClient=StubLlmForRoutingTests(in_yamlResponse=yamlTextValue),
        in_promptBuilder=_buildRuntimePromptBuilder(),
        in_routePlanParser=RoutePlanParser(),
        in_skillService=skillServiceMock,
        in_toolRegistry=_buildSmallToolRegistryWithReadEmailOnly(),
        in_modelSettings=_buildMinimalModelSettings(),
    )
    resolutionEntity = resolverUnderTest.resolve(
        in_userMessage="дайджест непрочитанных писем",
    )
    assert resolutionEntity.routingSource == "llm"
    assert resolutionEntity.routingFallbackReason is None
    assert "default_assistant" in resolutionEntity.selectedSkillIds
    assert "read_and_analyze_email" in resolutionEntity.selectedSkillIds
    assert resolutionEntity.requiredFirstSuccessfulToolName == "read_email"


def testLlmRoutingPlanResolverHeuristicOverridesRouterWhenOnlyChannelHandles() -> None:
    yamlTextValue = """type: route_plan
selected_skill_ids:
  - default_assistant
allow_tool_calls: false
required_first_successful_tool_name: ""
memory_mode: full
"""
    skillServiceMock = SkillService(
        in_skillStore=MarkdownSkillStore(in_skillsDirPath="./app/skills/assets"),
        in_skillSelectorRules=SkillSelectorRules(),
        in_skillSelectionMaxCount=4,
    )
    resolverUnderTest = LlmRoutingPlanResolver(
        in_llmClient=StubLlmForRoutingTests(in_yamlResponse=yamlTextValue),
        in_promptBuilder=_buildRuntimePromptBuilder(),
        in_routePlanParser=RoutePlanParser(),
        in_skillService=skillServiceMock,
        in_toolRegistry=_buildToolRegistryWithTelegramDigestTools(),
        in_modelSettings=_buildMinimalModelSettings(),
    )
    resolutionEntity = resolverUnderTest.resolve(
        in_userMessage="@larchanka, @AiExp02, @vitaly_kuliev_it",
    )
    assert resolutionEntity.routingSource == "llm"
    assert resolutionEntity.allowToolCalls is True
    assert "user_topic_telegram_digest" in resolutionEntity.selectedSkillIds
    assert resolutionEntity.requiredFirstSuccessfulToolName == "user_topic_telegram_digest"
    kinds = [d.get("kind") for d in resolutionEntity.routingDiagnostics if isinstance(d, dict)]
    assert "routing_llm_heuristic_override" in kinds


def testLlmRoutingPlanResolverUsesFallbackRulesWhenLlMYamlInvalid() -> None:
    skillServiceMock = SkillService(
        in_skillStore=MarkdownSkillStore(in_skillsDirPath="./app/skills/assets"),
        in_skillSelectorRules=SkillSelectorRules(),
        in_skillSelectionMaxCount=4,
    )
    resolverUnderTest = LlmRoutingPlanResolver(
        in_llmClient=StubLlmForRoutingTests(in_yamlResponse="NOT_YAML_ROUTE_PLAN"),
        in_promptBuilder=_buildRuntimePromptBuilder(),
        in_routePlanParser=RoutePlanParser(),
        in_skillService=skillServiceMock,
        in_toolRegistry=_buildSmallToolRegistryWithReadEmailOnly(),
        in_modelSettings=_buildMinimalModelSettings(),
    )
    userMessagePhrase = "сделай дайджест непрочитанных писем"
    resolutionEntity = resolverUnderTest.resolve(in_userMessage=userMessagePhrase)
    assert resolutionEntity.routingSource == "fallback"
    assert resolutionEntity.routingFallbackReason is not None
    assert "default_assistant" in resolutionEntity.selectedSkillIds
    assert "read_and_analyze_email" in resolutionEntity.selectedSkillIds
    assert resolutionEntity.requiredFirstSuccessfulToolName == "read_email"


def testLlmRoutingPlanResolverOverridesFirstGateToScheduleRecurringForRecurringDigest() -> None:
    yamlTextValue = """type: route_plan
selected_skill_ids:
  - default_assistant
  - schedule_recurring_agent_run
  - user_topic_telegram_digest
allow_tool_calls: true
required_first_successful_tool_name: user_topic_telegram_digest
memory_mode: full
"""
    skillServiceMock = SkillService(
        in_skillStore=MarkdownSkillStore(in_skillsDirPath="./app/skills/assets"),
        in_skillSelectorRules=SkillSelectorRules(),
        in_skillSelectionMaxCount=4,
    )
    resolverUnderTest = LlmRoutingPlanResolver(
        in_llmClient=StubLlmForRoutingTests(in_yamlResponse=yamlTextValue),
        in_promptBuilder=_buildRuntimePromptBuilder(),
        in_routePlanParser=RoutePlanParser(),
        in_skillService=skillServiceMock,
        in_toolRegistry=_buildToolRegistryWithScheduleAndUserTopicDigests(),
        in_modelSettings=_buildMinimalModelSettings(),
    )
    resolutionEntity = resolverUnderTest.resolve(
        in_userMessage=(
            "создай повторяющееся событие - каждый день в 10 утра - "
            "дайджест постов в телеграм по теме AI"
        ),
    )
    assert resolutionEntity.routingSource == "llm"
    assert resolutionEntity.requiredFirstSuccessfulToolName == "schedule_recurring_agent_run"


def testLlmRoutingPlanResolverKeepsScheduleRecurringPriorityWithRememberSkill() -> None:
    yamlTextValue = """type: route_plan
selected_skill_ids:
  - default_assistant
  - remember_user_note
  - schedule_recurring_agent_run
  - user_topic_telegram_digest
allow_tool_calls: true
required_first_successful_tool_name: user_topic_telegram_digest
memory_mode: full
"""
    skillServiceMock = SkillService(
        in_skillStore=MarkdownSkillStore(in_skillsDirPath="./app/skills/assets"),
        in_skillSelectorRules=SkillSelectorRules(),
        in_skillSelectionMaxCount=4,
    )
    resolverUnderTest = LlmRoutingPlanResolver(
        in_llmClient=StubLlmForRoutingTests(in_yamlResponse=yamlTextValue),
        in_promptBuilder=_buildRuntimePromptBuilder(),
        in_routePlanParser=RoutePlanParser(),
        in_skillService=skillServiceMock,
        in_toolRegistry=_buildToolRegistryWithScheduleAndUserTopicDigests(),
        in_modelSettings=_buildMinimalModelSettings(),
    )
    resolutionEntity = resolverUnderTest.resolve(
        in_userMessage=(
            "запомни что мне нужен recurring дайджест: "
            "создай повторяющееся событие каждый день в 10 утра по теме AI"
        ),
    )
    assert resolutionEntity.routingSource == "llm"
    assert resolutionEntity.requiredFirstSuccessfulToolName == "schedule_recurring_agent_run"
