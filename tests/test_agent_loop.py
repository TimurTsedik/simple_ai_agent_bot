from app.config.settingsModels import ModelSettings, RuntimeSettings
from app.domain.entities.llmCompletionResult import LlmCompletionResultModel
from app.domain.policies.stopPolicy import StopPolicy
from app.runtime.agentLoop import AgentLoop
from app.runtime.outputParser import OutputParser
from app.runtime.promptBuilder import PromptBuilder
from app.runtime.toolExecutionCoordinator import ToolExecutionCoordinator
from app.tools.registry.toolMetadataRenderer import ToolMetadataRenderer
from app.tools.registry.toolRegistry import ToolDefinitionModel, ToolRegistry
from pydantic import BaseModel, ConfigDict
import json


class SequenceLlmClient:
    def __init__(self, in_outputs: list[str]) -> None:
        self._outputs = in_outputs
        self._index = 0

    def complete(
        self,
        in_modelName: str,
        in_promptText: str,
        *,
        in_timeoutSeconds: int | None = None,
        in_useJsonObjectResponseFormat: bool = False,
    ) -> LlmCompletionResultModel:
        ret: LlmCompletionResultModel
        _ = (in_promptText, in_timeoutSeconds, in_useJsonObjectResponseFormat)
        if self._index < len(self._outputs):
            contentValue = self._outputs[self._index]
            self._index += 1
        else:
            contentValue = self._outputs[-1]
        ret = LlmCompletionResultModel(
            content=contentValue,
            selectedModel=in_modelName,
            fallbackEvents=(),
        )
        return ret


def _makeRuntimeSettings(
    in_maxSteps: int,
    in_maxBlocked: int = 3,
    in_windowSize: int = 8,
    in_maxInWindow: int = 3,
) -> RuntimeSettings:
    ret = RuntimeSettings(
        maxSteps=in_maxSteps,
        maxToolCalls=3,
        maxExecutionSeconds=60,
        maxToolOutputChars=1000,
        maxPromptChars=3000,
        recentMessagesLimit=12,
        sessionSummaryMaxChars=2000,
        skillSelectionMaxCount=4,
        maxToolCallBlockedIterations=in_maxBlocked,
        toolCallHistoryWindowSize=in_windowSize,
        maxSameToolSignatureInWindow=in_maxInWindow,
        extraSecondsPerLlmError=0,
        maxExtraSecondsTotal=0,
    )
    return ret


def _makeModelSettings() -> ModelSettings:
    ret = ModelSettings(
        openRouterBaseUrl="https://openrouter.ai/api/v1",
        primaryModel="model-primary",
        secondaryModel="model-secondary",
        tertiaryModel="model-tertiary",
        requestTimeoutSeconds=45,
        retryCountBeforeFallback=2,
        returnToPrimaryCooldownSeconds=300,
    )
    return ret


class EmptyArgsModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SingleFieldArgsModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    k: str


class ReadEmailArgsForTestModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    maxItems: int = 10
    unreadOnly: bool = True
    sinceHours: int = 24


class DigestArgsForTestModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    maxItems: int = 10
    sinceHours: int = 24
    sinceUnixTs: int = 0
    channels: list[str] = []
    topics: list[str] = []
    keywords: list[str] = []


def _echoTool(in_args: dict) -> dict:
    ret = {"echo": in_args}
    return ret


def _makeToolExecutionCoordinator(in_maxToolOutputChars: int) -> ToolExecutionCoordinator:
    ret = ToolExecutionCoordinator(
        in_toolRegistry=ToolRegistry(
            in_toolDefinitions=[
                ToolDefinitionModel(
                    name="a",
                    description="test tool",
                    argsModel=EmptyArgsModel,
                    timeoutSeconds=1,
                    executeCallable=_echoTool,
                )
            ]
        ),
        in_maxToolOutputChars=in_maxToolOutputChars,
    )
    return ret


def testAgentLoopBlocksRepeatToolCallAfterSuccess() -> None:
    runtimeSettings = _makeRuntimeSettings(in_maxSteps=8, in_maxBlocked=2)
    toolCall = '{"type":"tool_call","reason":"x","action":"a","args":{}}'
    llmClient = SequenceLlmClient(
        in_outputs=[
            toolCall,
            toolCall,
            '{"type":"final","reason":"done","final_answer":"Ок, использовал прошлый результат"}',
        ]
    )

    callCount: dict[str, int] = {"a": 0}

    def _countingTool(in_args: dict) -> dict:
        _ = in_args
        callCount["a"] += 1
        ret = {
            "items": [
                {
                    "channel": "x",
                    "dateUnixTs": "1",
                    "summary": "s",
                    "link": "https://t.me/x/1",
                }
            ],
            "count": 1,
            "sinceUnixTsUsed": 0,
            "channelErrors": {},
        }
        return ret

    loop = AgentLoop(
        in_llmClient=llmClient,
        in_promptBuilder=PromptBuilder(in_runtimeSettings=runtimeSettings),
        in_outputParser=OutputParser(),
        in_stopPolicy=StopPolicy(in_runtimeSettings=runtimeSettings),
        in_modelSettings=_makeModelSettings(),
        in_toolExecutionCoordinator=ToolExecutionCoordinator(
            in_toolRegistry=ToolRegistry(
                in_toolDefinitions=[
                    ToolDefinitionModel(
                        name="a",
                        description="test tool",
                        argsModel=EmptyArgsModel,
                        timeoutSeconds=1,
                        executeCallable=_countingTool,
                    )
                ]
            ),
            in_maxToolOutputChars=runtimeSettings.maxToolOutputChars,
        ),
        in_toolMetadataRenderer=ToolMetadataRenderer(),
        in_toolRegistry=ToolRegistry(
            in_toolDefinitions=[
                ToolDefinitionModel(
                    name="a",
                    description="test tool",
                    argsModel=EmptyArgsModel,
                    timeoutSeconds=1,
                    executeCallable=_countingTool,
                )
            ]
        ),
    )

    result = loop.run(in_userMessage="x", in_skillsBlock="", in_memoryBlock="")

    assert result.completionReason == "final_answer"
    assert callCount["a"] == 1
    assert result.toolCallCount == 1
    blockedSteps = [s for s in result.stepTraces if s.get("status") == "tool_call_blocked"]
    assert len(blockedSteps) == 1


def testAgentLoopAllowsSecondReadEmailCallWhenInsufficientItems() -> None:
    runtimeSettings = _makeRuntimeSettings(in_maxSteps=8, in_maxBlocked=2)
    llmClient = SequenceLlmClient(
        in_outputs=[
            '{"type":"tool_call","reason":"x","action":"read_email","args":{"maxItems":5}}',
            '{"type":"tool_call","reason":"x","action":"read_email","args":{"maxItems":5,"unreadOnly":false,"sinceHours":168}}',
            '{"type":"final","reason":"done","final_answer":"ok"}',
        ]
    )

    callCount: dict[str, int] = {"read_email": 0}

    def _readEmailTool(in_args: dict) -> dict:
        callCount["read_email"] += 1
        unreadOnly = bool(in_args.get("unreadOnly", True)) is True
        countValue = 1 if unreadOnly is True else 5
        ret = {"count": countValue, "sinceUnixTsUsed": 0, "items": [{"uid": "1"} for _ in range(countValue)]}
        return ret

    toolReg = ToolRegistry(
        in_toolDefinitions=[
            ToolDefinitionModel(
                name="read_email",
                description="email",
                argsModel=ReadEmailArgsForTestModel,
                timeoutSeconds=1,
                executeCallable=_readEmailTool,
            )
        ]
    )
    loop = AgentLoop(
        in_llmClient=llmClient,
        in_promptBuilder=PromptBuilder(in_runtimeSettings=runtimeSettings),
        in_outputParser=OutputParser(),
        in_stopPolicy=StopPolicy(in_runtimeSettings=runtimeSettings),
        in_modelSettings=_makeModelSettings(),
        in_toolExecutionCoordinator=ToolExecutionCoordinator(
            in_toolRegistry=toolReg,
            in_maxToolOutputChars=runtimeSettings.maxToolOutputChars,
        ),
        in_toolMetadataRenderer=ToolMetadataRenderer(),
        in_toolRegistry=toolReg,
    )

    result = loop.run(in_userMessage="x", in_skillsBlock="", in_memoryBlock="")
    assert result.completionReason == "final_answer"
    assert callCount["read_email"] == 2
    blockedSteps = [s for s in result.stepTraces if s.get("status") == "tool_call_blocked"]
    assert len(blockedSteps) == 0


def testAgentLoopAllowsSecondDigestCallWhenFirstWindowTooNarrow() -> None:
    runtimeSettings = _makeRuntimeSettings(in_maxSteps=8, in_maxBlocked=2)
    llmClient = SequenceLlmClient(
        in_outputs=[
            '{"type":"tool_call","reason":"x","action":"digest_telegram_news","args":{"channels":["how2ai"],"topics":["ai"],"sinceHours":24,"maxItems":10}}',
            '{"type":"tool_call","reason":"x","action":"digest_telegram_news","args":{"channels":["how2ai"],"topics":["ai"],"sinceHours":168,"maxItems":10}}',
            '{"type":"final","reason":"done","final_answer":"ok"}',
        ]
    )

    callCount: dict[str, int] = {"digest_telegram_news": 0}

    def _digestTool(in_args: dict) -> dict:
        callCount["digest_telegram_news"] += 1
        if int(in_args.get("sinceHours", 24)) <= 24:
            ret = {
                "items": [],
                "count": 0,
                "sinceUnixTsUsed": 1777366869,
                "channelErrors": {},
                "resolvedChannels": ["how2ai"],
                "resolvedTopics": ["ai"],
                "diagnostics": {"filteredOutByTime": 5},
            }
        else:
            ret = {
                "items": [
                    {
                        "channel": "how2ai",
                        "dateUnixTs": "1777369999",
                        "summary": "AI news",
                        "link": "https://t.me/how2ai/1",
                    }
                ],
                "count": 1,
                "sinceUnixTsUsed": 1777360000,
                "channelErrors": {},
                "resolvedChannels": ["how2ai"],
                "resolvedTopics": ["ai"],
                "diagnostics": {"filteredOutByTime": 0},
            }
        return ret

    toolReg = ToolRegistry(
        in_toolDefinitions=[
            ToolDefinitionModel(
                name="digest_telegram_news",
                description="digest",
                argsModel=DigestArgsForTestModel,
                timeoutSeconds=1,
                executeCallable=_digestTool,
            )
        ]
    )
    loop = AgentLoop(
        in_llmClient=llmClient,
        in_promptBuilder=PromptBuilder(in_runtimeSettings=runtimeSettings),
        in_outputParser=OutputParser(),
        in_stopPolicy=StopPolicy(in_runtimeSettings=runtimeSettings),
        in_modelSettings=_makeModelSettings(),
        in_toolExecutionCoordinator=ToolExecutionCoordinator(
            in_toolRegistry=toolReg,
            in_maxToolOutputChars=runtimeSettings.maxToolOutputChars,
        ),
        in_toolMetadataRenderer=ToolMetadataRenderer(),
        in_toolRegistry=toolReg,
    )

    result = loop.run(in_userMessage="x", in_skillsBlock="", in_memoryBlock="")
    assert result.completionReason == "final_answer"
    assert callCount["digest_telegram_news"] == 2
    blockedSteps = [s for s in result.stepTraces if s.get("status") == "tool_call_blocked"]
    assert len(blockedSteps) == 1


def testAgentLoopAutoRetriesDigestOnTimeFilteredEmptyResult() -> None:
    runtimeSettings = _makeRuntimeSettings(in_maxSteps=6, in_maxBlocked=2)
    llmClient = SequenceLlmClient(
        in_outputs=[
            '{"type":"tool_call","reason":"x","action":"digest_telegram_news","args":{"channels":["larchanka"],"topics":["ai"],"sinceHours":24,"maxItems":10}}',
            '{"type":"final","reason":"done","final_answer":"ok"}',
        ]
    )

    callArgs: list[dict] = []

    def _digestTool(in_args: dict) -> dict:
        callArgs.append(dict(in_args))
        if int(in_args.get("sinceHours", 24)) <= 24:
            ret = {
                "items": [],
                "count": 0,
                "sinceUnixTsUsed": 1777367048,
                "channelErrors": {},
                "resolvedChannels": ["larchanka"],
                "resolvedTopics": ["ai"],
                "diagnostics": {"filteredOutByTime": 9},
            }
        else:
            ret = {
                "items": [
                    {
                        "channel": "larchanka",
                        "dateUnixTs": "1777369999",
                        "summary": "AI post",
                        "link": "https://t.me/larchanka/123",
                    }
                ],
                "count": 1,
                "sinceUnixTsUsed": 1777360000,
                "channelErrors": {},
                "resolvedChannels": ["larchanka"],
                "resolvedTopics": ["ai"],
                "diagnostics": {"filteredOutByTime": 0},
            }
        return ret

    toolReg = ToolRegistry(
        in_toolDefinitions=[
            ToolDefinitionModel(
                name="digest_telegram_news",
                description="digest",
                argsModel=DigestArgsForTestModel,
                timeoutSeconds=1,
                executeCallable=_digestTool,
            )
        ]
    )
    loop = AgentLoop(
        in_llmClient=llmClient,
        in_promptBuilder=PromptBuilder(in_runtimeSettings=runtimeSettings),
        in_outputParser=OutputParser(),
        in_stopPolicy=StopPolicy(in_runtimeSettings=runtimeSettings),
        in_modelSettings=_makeModelSettings(),
        in_toolExecutionCoordinator=ToolExecutionCoordinator(
            in_toolRegistry=toolReg,
            in_maxToolOutputChars=runtimeSettings.maxToolOutputChars,
        ),
        in_toolMetadataRenderer=ToolMetadataRenderer(),
        in_toolRegistry=toolReg,
    )

    result = loop.run(in_userMessage="x", in_skillsBlock="", in_memoryBlock="")
    firstStep = result.stepTraces[0]
    preview = firstStep.get("observation", "")

    assert result.completionReason == "final_answer"
    assert result.toolCallCount == 2
    assert len(callArgs) == 2
    assert int(callArgs[0].get("sinceHours", 0)) == 24
    assert int(callArgs[1].get("sinceHours", 0)) == 72
    assert firstStep.get("digestAutoRetry", {}).get("applied") is True
    assert "filteredOutByTime" in str(preview)


def testAgentLoopReturnsFinalAnswer() -> None:
    runtimeSettings = _makeRuntimeSettings(in_maxSteps=5)
    llmClient = SequenceLlmClient(
        in_outputs=['{"type":"final","reason":"done","final_answer":"Финал"}']
    )
    loop = AgentLoop(
        in_llmClient=llmClient,
        in_promptBuilder=PromptBuilder(in_runtimeSettings=runtimeSettings),
        in_outputParser=OutputParser(),
        in_stopPolicy=StopPolicy(in_runtimeSettings=runtimeSettings),
        in_modelSettings=_makeModelSettings(),
        in_toolExecutionCoordinator=_makeToolExecutionCoordinator(
            in_maxToolOutputChars=runtimeSettings.maxToolOutputChars
        ),
        in_toolMetadataRenderer=ToolMetadataRenderer(),
        in_toolRegistry=ToolRegistry(in_toolDefinitions=[]),
    )

    result = loop.run(
        in_userMessage="Привет",
        in_skillsBlock="",
        in_memoryBlock="",
    )

    assert result.completionReason == "final_answer"
    assert result.finalAnswer == "Финал"


def testAgentLoopBlocksFinalUntilRequiredToolSucceeds() -> None:
    runtimeSettings = _makeRuntimeSettings(in_maxSteps=6)
    llmClient = SequenceLlmClient(
        in_outputs=[
            '{"type":"final","reason":"done","final_answer":"сразу финал"}',
            '{"type":"tool_call","reason":"need_email","action":"read_email","args":{"maxItems":1}}',
            '{"type":"final","reason":"done","final_answer":"итог после инструмента"}',
        ]
    )

    def _readEmailTool(_in_args: dict) -> dict:
        ret = {
            "count": 1,
            "sinceUnixTsUsed": 0,
            "items": [{"uid": "1", "subject": "s"}],
        }
        return ret

    toolReg = ToolRegistry(
        in_toolDefinitions=[
            ToolDefinitionModel(
                name="read_email",
                description="email",
                argsModel=ReadEmailArgsForTestModel,
                timeoutSeconds=1,
                executeCallable=_readEmailTool,
            )
        ]
    )
    loop = AgentLoop(
        in_llmClient=llmClient,
        in_promptBuilder=PromptBuilder(in_runtimeSettings=runtimeSettings),
        in_outputParser=OutputParser(),
        in_stopPolicy=StopPolicy(in_runtimeSettings=runtimeSettings),
        in_modelSettings=_makeModelSettings(),
        in_toolExecutionCoordinator=ToolExecutionCoordinator(
            in_toolRegistry=toolReg,
            in_maxToolOutputChars=runtimeSettings.maxToolOutputChars,
        ),
        in_toolMetadataRenderer=ToolMetadataRenderer(),
        in_toolRegistry=toolReg,
    )

    result = loop.run(
        in_userMessage="прочитай письма и дай дайджест",
        in_skillsBlock="",
        in_memoryBlock="",
        in_requiredFirstSuccessfulToolName="read_email",
    )

    assert result.completionReason == "final_answer"
    assert result.finalAnswer == "итог после инструмента"
    assert result.stepCount == 3
    assert result.toolCallCount == 1
    assert result.stepTraces[0].get("status") == "final_blocked_missing_required_tool"


def testAgentLoopFallbackWhenFormatRepairExhaustedWithoutToolData() -> None:
    runtimeSettings = _makeRuntimeSettings(in_maxSteps=5)
    runtimeSettings.maxConsecutiveFormatFailureSteps = 1
    runtimeSettings.maxFormatRepairAttempts = 2
    badPayload = '{"type":"final","reason":"done","final_answer":"Финал"'
    llmClient = SequenceLlmClient(in_outputs=[badPayload, badPayload, badPayload])
    loop = AgentLoop(
        in_llmClient=llmClient,
        in_promptBuilder=PromptBuilder(in_runtimeSettings=runtimeSettings),
        in_outputParser=OutputParser(),
        in_stopPolicy=StopPolicy(in_runtimeSettings=runtimeSettings),
        in_modelSettings=_makeModelSettings(),
        in_toolExecutionCoordinator=_makeToolExecutionCoordinator(
            in_maxToolOutputChars=runtimeSettings.maxToolOutputChars
        ),
        in_toolMetadataRenderer=ToolMetadataRenderer(),
        in_toolRegistry=ToolRegistry(in_toolDefinitions=[]),
    )

    result = loop.run(
        in_userMessage="Привет",
        in_skillsBlock="",
        in_memoryBlock="",
    )

    assert result.completionReason == "final_answer"
    assert "не удалось получить данные" in result.finalAnswer.lower()
    assert result.stepTraces[0].get("repairRawModelResponse") is not None


def testAgentLoopRepairsInvalidJsonOnce() -> None:
    runtimeSettings = _makeRuntimeSettings(in_maxSteps=5)
    badJson = '{"type":"final","reason":"done","final_answer":"Финал"'
    goodJson = '{"type":"final","reason":"done","final_answer":"После ремонта"}'
    llmClient = SequenceLlmClient(in_outputs=[badJson, goodJson])
    loop = AgentLoop(
        in_llmClient=llmClient,
        in_promptBuilder=PromptBuilder(in_runtimeSettings=runtimeSettings),
        in_outputParser=OutputParser(),
        in_stopPolicy=StopPolicy(in_runtimeSettings=runtimeSettings),
        in_modelSettings=_makeModelSettings(),
        in_toolExecutionCoordinator=_makeToolExecutionCoordinator(
            in_maxToolOutputChars=runtimeSettings.maxToolOutputChars
        ),
        in_toolMetadataRenderer=ToolMetadataRenderer(),
        in_toolRegistry=ToolRegistry(in_toolDefinitions=[]),
    )

    result = loop.run(
        in_userMessage="Привет",
        in_skillsBlock="",
        in_memoryBlock="",
    )

    assert result.completionReason == "final_answer"
    assert result.finalAnswer == "После ремонта"


def testAgentLoopReplacesTechnicalRepairAnswerWithFallback() -> None:
    runtimeSettings = _makeRuntimeSettings(in_maxSteps=5)
    llmClient = SequenceLlmClient(
        in_outputs=[
            '{"type":"tool_call","reason":"x","action":"a","args":{}}',
            '{"type":"final","reason":"x","final_answer":"bad"}{"type":"stop","reason":"x","final_answer":"bad"}',
            '{"type":"final","reason":"completed","final_answer":"I have retrieved the requested information and processed it as needed."}',
        ]
    )

    def _failingTool(_in_args: dict) -> dict:
        raise TimeoutError("slow tool")

    toolReg = ToolRegistry(
        in_toolDefinitions=[
            ToolDefinitionModel(
                name="a",
                description="test tool",
                argsModel=EmptyArgsModel,
                timeoutSeconds=1,
                executeCallable=_failingTool,
            )
        ]
    )
    loop = AgentLoop(
        in_llmClient=llmClient,
        in_promptBuilder=PromptBuilder(in_runtimeSettings=runtimeSettings),
        in_outputParser=OutputParser(),
        in_stopPolicy=StopPolicy(in_runtimeSettings=runtimeSettings),
        in_modelSettings=_makeModelSettings(),
        in_toolExecutionCoordinator=ToolExecutionCoordinator(
            in_toolRegistry=toolReg,
            in_maxToolOutputChars=runtimeSettings.maxToolOutputChars,
        ),
        in_toolMetadataRenderer=ToolMetadataRenderer(),
        in_toolRegistry=toolReg,
    )

    result = loop.run(in_userMessage="x", in_skillsBlock="", in_memoryBlock="")
    assert result.completionReason == "final_answer"
    assert "Не удалось завершить запрос" in result.finalAnswer


def testAgentLoopStopsByMaxSteps() -> None:
    runtimeSettings = _makeRuntimeSettings(in_maxSteps=2)
    llmClient = SequenceLlmClient(
        in_outputs=[
            '{"type":"tool_call","reason":"x","action":"a","args":{}}',
            '{"type":"tool_call","reason":"x","action":"a","args":{}}',
            '{"type":"tool_call","reason":"x","action":"a","args":{}}',
        ]
    )
    loop = AgentLoop(
        in_llmClient=llmClient,
        in_promptBuilder=PromptBuilder(in_runtimeSettings=runtimeSettings),
        in_outputParser=OutputParser(),
        in_stopPolicy=StopPolicy(in_runtimeSettings=runtimeSettings),
        in_modelSettings=_makeModelSettings(),
        in_toolExecutionCoordinator=_makeToolExecutionCoordinator(
            in_maxToolOutputChars=runtimeSettings.maxToolOutputChars
        ),
        in_toolMetadataRenderer=ToolMetadataRenderer(),
        in_toolRegistry=ToolRegistry(
            in_toolDefinitions=[
                ToolDefinitionModel(
                    name="a",
                    description="test tool",
                    argsModel=EmptyArgsModel,
                    timeoutSeconds=1,
                    executeCallable=_echoTool,
                )
            ]
        ),
    )

    result = loop.run(
        in_userMessage="Привет",
        in_skillsBlock="",
        in_memoryBlock="",
    )

    assert result.completionReason == "max_steps_exceeded"
    assert result.stepCount == 2


def testAgentLoopStopsOnRepeatedSameToolCall() -> None:
    runtimeSettings = _makeRuntimeSettings(in_maxSteps=8)
    llmClient = SequenceLlmClient(
        in_outputs=[
            '{"type":"tool_call","reason":"x","action":"a","args":{"k":"v"}}',
            '{"type":"tool_call","reason":"x","action":"a","args":{"k":"v"}}',
            '{"type":"tool_call","reason":"x","action":"a","args":{"k":"v"}}',
            '{"type":"tool_call","reason":"x","action":"a","args":{"k":"v"}}',
        ]
    )
    loop = AgentLoop(
        in_llmClient=llmClient,
        in_promptBuilder=PromptBuilder(in_runtimeSettings=runtimeSettings),
        in_outputParser=OutputParser(),
        in_stopPolicy=StopPolicy(in_runtimeSettings=runtimeSettings),
        in_modelSettings=_makeModelSettings(),
        in_toolExecutionCoordinator=_makeToolExecutionCoordinator(
            in_maxToolOutputChars=runtimeSettings.maxToolOutputChars
        ),
        in_toolMetadataRenderer=ToolMetadataRenderer(),
        in_toolRegistry=ToolRegistry(
            in_toolDefinitions=[
                ToolDefinitionModel(
                    name="a",
                    description="test tool",
                    argsModel=SingleFieldArgsModel,
                    timeoutSeconds=1,
                    executeCallable=_echoTool,
                )
            ]
        ),
    )

    result = loop.run(
        in_userMessage="Привет",
        in_skillsBlock="",
        in_memoryBlock="",
    )

    assert result.completionReason == "repeated_tool_call_loop"


def testAgentLoopStopsOnRepeatedSameToolNameWithDifferentArgs() -> None:
    runtimeSettings = _makeRuntimeSettings(in_maxSteps=8)
    llmClient = SequenceLlmClient(
        in_outputs=[
            '{"type":"tool_call","reason":"x","action":"a","args":{"k":"v1"}}',
            '{"type":"tool_call","reason":"x","action":"a","args":{"k":"v2"}}',
            '{"type":"tool_call","reason":"x","action":"a","args":{"k":"v3"}}',
            '{"type":"tool_call","reason":"x","action":"a","args":{"k":"v4"}}',
        ]
    )
    loop = AgentLoop(
        in_llmClient=llmClient,
        in_promptBuilder=PromptBuilder(in_runtimeSettings=runtimeSettings),
        in_outputParser=OutputParser(),
        in_stopPolicy=StopPolicy(in_runtimeSettings=runtimeSettings),
        in_modelSettings=_makeModelSettings(),
        in_toolExecutionCoordinator=_makeToolExecutionCoordinator(
            in_maxToolOutputChars=runtimeSettings.maxToolOutputChars
        ),
        in_toolMetadataRenderer=ToolMetadataRenderer(),
        in_toolRegistry=ToolRegistry(
            in_toolDefinitions=[
                ToolDefinitionModel(
                    name="a",
                    description="test tool",
                    argsModel=SingleFieldArgsModel,
                    timeoutSeconds=1,
                    executeCallable=_echoTool,
                )
            ]
        ),
    )

    result = loop.run(
        in_userMessage="Привет",
        in_skillsBlock="",
        in_memoryBlock="",
    )

    assert result.completionReason == "repeated_tool_call_loop"


def testAgentLoopStopsOnSameSignatureWithinSlidingWindow() -> None:
    runtimeSettings = _makeRuntimeSettings(
        in_maxSteps=12,
        in_windowSize=4,
        in_maxInWindow=3,
    )
    sameCall = '{"type":"tool_call","reason":"x","action":"a","args":{"k":"v"}}'
    otherCall = '{"type":"tool_call","reason":"x","action":"a","args":{"k":"other"}}'
    llmClient = SequenceLlmClient(
        in_outputs=[sameCall, otherCall, sameCall, sameCall, sameCall]
    )
    loop = AgentLoop(
        in_llmClient=llmClient,
        in_promptBuilder=PromptBuilder(in_runtimeSettings=runtimeSettings),
        in_outputParser=OutputParser(),
        in_stopPolicy=StopPolicy(in_runtimeSettings=runtimeSettings),
        in_modelSettings=_makeModelSettings(),
        in_toolExecutionCoordinator=_makeToolExecutionCoordinator(
            in_maxToolOutputChars=runtimeSettings.maxToolOutputChars
        ),
        in_toolMetadataRenderer=ToolMetadataRenderer(),
        in_toolRegistry=ToolRegistry(
            in_toolDefinitions=[
                ToolDefinitionModel(
                    name="a",
                    description="test tool",
                    argsModel=SingleFieldArgsModel,
                    timeoutSeconds=1,
                    executeCallable=_echoTool,
                )
            ]
        ),
    )

    result = loop.run(
        in_userMessage="Привет",
        in_skillsBlock="",
        in_memoryBlock="",
    )

    assert result.completionReason == "repeated_tool_call_loop"


def testAgentLoopBlocksToolCallWhenToolsDisabled() -> None:
    runtimeSettings = _makeRuntimeSettings(in_maxSteps=5)
    llmClient = SequenceLlmClient(
        in_outputs=[
            '{"type":"tool_call","reason":"x","action":"a","args":{}}',
            '{"type":"final","reason":"done","final_answer":"Прямой ответ без инструмента"}',
        ]
    )
    loop = AgentLoop(
        in_llmClient=llmClient,
        in_promptBuilder=PromptBuilder(in_runtimeSettings=runtimeSettings),
        in_outputParser=OutputParser(),
        in_stopPolicy=StopPolicy(in_runtimeSettings=runtimeSettings),
        in_modelSettings=_makeModelSettings(),
        in_toolExecutionCoordinator=_makeToolExecutionCoordinator(
            in_maxToolOutputChars=runtimeSettings.maxToolOutputChars
        ),
        in_toolMetadataRenderer=ToolMetadataRenderer(),
        in_toolRegistry=ToolRegistry(
            in_toolDefinitions=[
                ToolDefinitionModel(
                    name="a",
                    description="test tool",
                    argsModel=EmptyArgsModel,
                    timeoutSeconds=1,
                    executeCallable=_echoTool,
                )
            ]
        ),
    )

    result = loop.run(
        in_userMessage="кто ты?",
        in_skillsBlock="",
        in_memoryBlock="",
        in_allowToolCalls=False,
    )

    assert result.completionReason == "final_answer"
    assert result.finalAnswer == "Прямой ответ без инструмента"
    assert result.toolCallCount == 0


def testAgentLoopStopsAfterMaxBlockedToolCalls() -> None:
    runtimeSettings = _makeRuntimeSettings(in_maxSteps=10, in_maxBlocked=2)
    toolJson = '{"type":"tool_call","reason":"x","action":"a","args":{}}'
    llmClient = SequenceLlmClient(in_outputs=[toolJson, toolJson, toolJson])
    loop = AgentLoop(
        in_llmClient=llmClient,
        in_promptBuilder=PromptBuilder(in_runtimeSettings=runtimeSettings),
        in_outputParser=OutputParser(),
        in_stopPolicy=StopPolicy(in_runtimeSettings=runtimeSettings),
        in_modelSettings=_makeModelSettings(),
        in_toolExecutionCoordinator=_makeToolExecutionCoordinator(
            in_maxToolOutputChars=runtimeSettings.maxToolOutputChars
        ),
        in_toolMetadataRenderer=ToolMetadataRenderer(),
        in_toolRegistry=ToolRegistry(
            in_toolDefinitions=[
                ToolDefinitionModel(
                    name="a",
                    description="test tool",
                    argsModel=EmptyArgsModel,
                    timeoutSeconds=1,
                    executeCallable=_echoTool,
                )
            ]
        ),
    )

    result = loop.run(
        in_userMessage="кто ты?",
        in_skillsBlock="",
        in_memoryBlock="",
        in_allowToolCalls=False,
    )

    assert result.completionReason == "tool_call_blocked_limit"
    assert result.toolCallCount == 0


def testAgentLoopStopsAfterRepeatedToolTimeouts() -> None:
    runtimeSettings = _makeRuntimeSettings(in_maxSteps=8)
    llmClient = SequenceLlmClient(
        in_outputs=[
            '{"type":"tool_call","reason":"x","action":"a","args":{}}',
            '{"type":"tool_call","reason":"x","action":"a","args":{}}',
            '{"type":"tool_call","reason":"x","action":"a","args":{}}',
        ]
    )

    def _timeoutTool(_in_args: dict) -> dict:
        raise TimeoutError("slow tool")

    toolReg = ToolRegistry(
        in_toolDefinitions=[
            ToolDefinitionModel(
                name="a",
                description="test tool",
                argsModel=EmptyArgsModel,
                timeoutSeconds=1,
                executeCallable=_timeoutTool,
            )
        ]
    )
    loop = AgentLoop(
        in_llmClient=llmClient,
        in_promptBuilder=PromptBuilder(in_runtimeSettings=runtimeSettings),
        in_outputParser=OutputParser(),
        in_stopPolicy=StopPolicy(in_runtimeSettings=runtimeSettings),
        in_modelSettings=_makeModelSettings(),
        in_toolExecutionCoordinator=ToolExecutionCoordinator(
            in_toolRegistry=toolReg,
            in_maxToolOutputChars=runtimeSettings.maxToolOutputChars,
        ),
        in_toolMetadataRenderer=ToolMetadataRenderer(),
        in_toolRegistry=toolReg,
    )

    result = loop.run(in_userMessage="x", in_skillsBlock="", in_memoryBlock="")

    assert result.completionReason == "tool_timeout_limit"
    assert "превысил лимит времени" in result.finalAnswer
    assert result.stepCount == 2
    assert result.toolCallCount == 2
    assert result.stepTraces[-1].get("status") == "tool_timeout_limit"


def testAgentLoopToolObservationIsCompactJson() -> None:
    runtimeSettings = _makeRuntimeSettings(in_maxSteps=5)
    llmClient = SequenceLlmClient(
        in_outputs=[
            '{"type":"tool_call","reason":"x","action":"a","args":{}}',
            '{"type":"final","reason":"done","final_answer":"Готово"}',
        ]
    )
    loop = AgentLoop(
        in_llmClient=llmClient,
        in_promptBuilder=PromptBuilder(in_runtimeSettings=runtimeSettings),
        in_outputParser=OutputParser(),
        in_stopPolicy=StopPolicy(in_runtimeSettings=runtimeSettings),
        in_modelSettings=_makeModelSettings(),
        in_toolExecutionCoordinator=_makeToolExecutionCoordinator(
            in_maxToolOutputChars=runtimeSettings.maxToolOutputChars
        ),
        in_toolMetadataRenderer=ToolMetadataRenderer(),
        in_toolRegistry=ToolRegistry(
            in_toolDefinitions=[
                ToolDefinitionModel(
                    name="a",
                    description="test tool",
                    argsModel=EmptyArgsModel,
                    timeoutSeconds=1,
                    executeCallable=_echoTool,
                )
            ]
        ),
    )

    result = loop.run(
        in_userMessage="Привет",
        in_skillsBlock="",
        in_memoryBlock="",
    )

    firstStep = result.stepTraces[0]
    obsText = str(firstStep.get("observation", ""))
    assert '"kind": "tool_observation"' in obsText
    assert '"tool_name": "a"' in obsText


def testToolCoordinatorSerializesDictAsJsonString() -> None:
    runtimeSettings = _makeRuntimeSettings(in_maxSteps=3)
    llmClient = SequenceLlmClient(
        in_outputs=[
            '{"type":"tool_call","reason":"x","action":"a","args":{}}',
            '{"type":"final","reason":"done","final_answer":"ok"}',
        ]
    )
    loop = AgentLoop(
        in_llmClient=llmClient,
        in_promptBuilder=PromptBuilder(in_runtimeSettings=runtimeSettings),
        in_outputParser=OutputParser(),
        in_stopPolicy=StopPolicy(in_runtimeSettings=runtimeSettings),
        in_modelSettings=_makeModelSettings(),
        in_toolExecutionCoordinator=_makeToolExecutionCoordinator(
            in_maxToolOutputChars=runtimeSettings.maxToolOutputChars
        ),
        in_toolMetadataRenderer=ToolMetadataRenderer(),
        in_toolRegistry=ToolRegistry(
            in_toolDefinitions=[
                ToolDefinitionModel(
                    name="a",
                    description="test tool",
                    argsModel=EmptyArgsModel,
                    timeoutSeconds=1,
                    executeCallable=_echoTool,
                )
            ]
        ),
    )

    result = loop.run(in_userMessage="x", in_skillsBlock="", in_memoryBlock="")
    toolResult = result.stepTraces[0].get("toolResult", {})
    dataText = str(toolResult.get("data", ""))

    assert dataText.startswith("{")
    assert '"echo"' in dataText


def testReadEmailObservationContainsUpToTenItems() -> None:
    runtimeSettings = _makeRuntimeSettings(in_maxSteps=4)
    runtimeSettings.maxToolOutputChars = 20000
    llmClient = SequenceLlmClient(
        in_outputs=[
            '{"type":"tool_call","reason":"x","action":"read_email","args":{"maxItems":10}}',
            '{"type":"final","reason":"done","final_answer":"ok"}',
        ]
    )

    def _readEmailTool(_in_args: dict) -> dict:
        items = []
        for index in range(7):
            items.append(
                {
                    "uid": str(100 + index),
                    "from": "sender@example.com",
                    "subject": f"subj-{index}",
                    "date": "Tue, 28 Apr 2026 12:00:00 +0000",
                    "dateUnixTs": 1777368000 + index,
                    "snippet": "text",
                    "langHint": "ru",
                }
            )
        ret = {
            "count": len(items),
            "sinceUnixTsUsed": 0,
            "items": items,
        }
        return ret

    toolReg = ToolRegistry(
        in_toolDefinitions=[
            ToolDefinitionModel(
                name="read_email",
                description="email",
                argsModel=ReadEmailArgsForTestModel,
                timeoutSeconds=1,
                executeCallable=_readEmailTool,
            )
        ]
    )
    loop = AgentLoop(
        in_llmClient=llmClient,
        in_promptBuilder=PromptBuilder(in_runtimeSettings=runtimeSettings),
        in_outputParser=OutputParser(),
        in_stopPolicy=StopPolicy(in_runtimeSettings=runtimeSettings),
        in_modelSettings=_makeModelSettings(),
        in_toolExecutionCoordinator=ToolExecutionCoordinator(
            in_toolRegistry=toolReg,
            in_maxToolOutputChars=runtimeSettings.maxToolOutputChars,
        ),
        in_toolMetadataRenderer=ToolMetadataRenderer(),
        in_toolRegistry=toolReg,
    )

    result = loop.run(in_userMessage="x", in_skillsBlock="", in_memoryBlock="")
    obsText = str(result.stepTraces[0].get("observation", ""))
    obsPayload = json.loads(obsText)
    emailPreview = obsPayload.get("email_preview", {})
    previewItems = emailPreview.get("items_preview", [])
    assert len(previewItems) == 7


def testDigestObservationContainsUpToTenItems() -> None:
    runtimeSettings = _makeRuntimeSettings(in_maxSteps=4)
    runtimeSettings.maxToolOutputChars = 20000
    llmClient = SequenceLlmClient(
        in_outputs=[
            '{"type":"tool_call","reason":"x","action":"digest_telegram_news","args":{"maxItems":10}}',
            '{"type":"final","reason":"done","final_answer":"ok"}',
        ]
    )

    def _digestTool(_in_args: dict) -> dict:
        items = []
        for index in range(6):
            items.append(
                {
                    "channel": "markettwits",
                    "dateUnixTs": str(1777368000 + index),
                    "summary": f"news-{index}",
                    "link": f"https://t.me/markettwits/{1000 + index}",
                }
            )
        ret = {
            "count": len(items),
            "sinceUnixTsUsed": 1777367000,
            "items": items,
            "channelErrors": {},
        }
        return ret

    toolReg = ToolRegistry(
        in_toolDefinitions=[
            ToolDefinitionModel(
                name="digest_telegram_news",
                description="digest",
                argsModel=DigestArgsForTestModel,
                timeoutSeconds=1,
                executeCallable=_digestTool,
            )
        ]
    )
    loop = AgentLoop(
        in_llmClient=llmClient,
        in_promptBuilder=PromptBuilder(in_runtimeSettings=runtimeSettings),
        in_outputParser=OutputParser(),
        in_stopPolicy=StopPolicy(in_runtimeSettings=runtimeSettings),
        in_modelSettings=_makeModelSettings(),
        in_toolExecutionCoordinator=ToolExecutionCoordinator(
            in_toolRegistry=toolReg,
            in_maxToolOutputChars=runtimeSettings.maxToolOutputChars,
        ),
        in_toolMetadataRenderer=ToolMetadataRenderer(),
        in_toolRegistry=toolReg,
    )

    result = loop.run(in_userMessage="x", in_skillsBlock="", in_memoryBlock="")
    obsText = str(result.stepTraces[0].get("observation", ""))
    obsPayload = json.loads(obsText)
    dataPreview = obsPayload.get("data_preview", {})
    previewItems = dataPreview.get("items_preview", [])
    assert len(previewItems) == 6


def testAgentLoopBuildsDigestFallbackFromSuccessfulObservation() -> None:
    runtimeSettings = _makeRuntimeSettings(in_maxSteps=4)
    runtimeSettings.maxToolOutputChars = 20000
    llmClient = SequenceLlmClient(
        in_outputs=[
            '{"type":"tool_call","reason":"x","action":"digest_telegram_news","args":{"maxItems":10}}',
            '{"type":"final","reason":"x","final_answer":"bad"}{"type":"stop","reason":"x","final_answer":"bad"}',
            '{"type":"final","reason":"completed","final_answer":"I’m sorry about the previous formatting issue. Here is the corrected response in a valid JSON object."}',
        ]
    )

    def _digestTool(_in_args: dict) -> dict:
        ret = {
            "count": 2,
            "sinceUnixTsUsed": 1777367000,
            "items": [
                {
                    "channel": "markettwits",
                    "dateUnixTs": "1777376989",
                    "summary": "Новость 1",
                    "link": "https://t.me/markettwits/1",
                },
                {
                    "channel": "cbrstocks",
                    "dateUnixTs": "1777376185",
                    "summary": "Новость 2",
                    "link": "https://t.me/cbrstocks/2",
                },
            ],
            "channelErrors": {},
        }
        return ret

    toolReg = ToolRegistry(
        in_toolDefinitions=[
            ToolDefinitionModel(
                name="digest_telegram_news",
                description="digest",
                argsModel=DigestArgsForTestModel,
                timeoutSeconds=1,
                executeCallable=_digestTool,
            )
        ]
    )
    loop = AgentLoop(
        in_llmClient=llmClient,
        in_promptBuilder=PromptBuilder(in_runtimeSettings=runtimeSettings),
        in_outputParser=OutputParser(),
        in_stopPolicy=StopPolicy(in_runtimeSettings=runtimeSettings),
        in_modelSettings=_makeModelSettings(),
        in_toolExecutionCoordinator=ToolExecutionCoordinator(
            in_toolRegistry=toolReg,
            in_maxToolOutputChars=runtimeSettings.maxToolOutputChars,
        ),
        in_toolMetadataRenderer=ToolMetadataRenderer(),
        in_toolRegistry=toolReg,
    )

    result = loop.run(in_userMessage="x", in_skillsBlock="", in_memoryBlock="")
    assert result.completionReason == "final_answer"
    assert "Краткий итог" in result.finalAnswer
    assert "Новость 1" in result.finalAnswer
    assert "https://t.me/markettwits/1" in result.finalAnswer


def testAgentLoopFallbackMentionsNoToolDataWhenObservationsEmpty() -> None:
    runtimeSettings = _makeRuntimeSettings(in_maxSteps=3)
    llmClient = SequenceLlmClient(
        in_outputs=[
            '{"type":"final","reason":"x","final_answer":"bad"}{"type":"stop","reason":"x","final_answer":"bad"}',
            '{"type":"final","reason":"short","final_answer":"I have corrected the output format and provided a valid JSON response."}',
        ]
    )
    loop = AgentLoop(
        in_llmClient=llmClient,
        in_promptBuilder=PromptBuilder(in_runtimeSettings=runtimeSettings),
        in_outputParser=OutputParser(),
        in_stopPolicy=StopPolicy(in_runtimeSettings=runtimeSettings),
        in_modelSettings=_makeModelSettings(),
        in_toolExecutionCoordinator=_makeToolExecutionCoordinator(
            in_maxToolOutputChars=runtimeSettings.maxToolOutputChars
        ),
        in_toolMetadataRenderer=ToolMetadataRenderer(),
        in_toolRegistry=ToolRegistry(in_toolDefinitions=[]),
    )
    result = loop.run(in_userMessage="x", in_skillsBlock="", in_memoryBlock="")
    assert result.completionReason == "final_answer"
    assert "не удалось получить данные" in result.finalAnswer.lower()


def testToolCoordinatorKeepsValidJsonWhenTruncated() -> None:
    runtimeSettings = _makeRuntimeSettings(in_maxSteps=3)

    bigValue = "x" * 5000

    def bigTool(_in_args: dict) -> dict:
        ret = {
            "query": "q",
            "results": [{"title": "t", "url": "https://example.com", "snippet": bigValue}],
            "fetchedPages": [{"url": "https://example.com", "title": "t", "text": bigValue}],
            "blockedUrls": [{"url": "http://localhost/x", "reason": "blocked"}],
            "fetchErrors": [],
        }
        return ret

    coordinator = ToolExecutionCoordinator(
        in_toolRegistry=ToolRegistry(
            in_toolDefinitions=[
                ToolDefinitionModel(
                    name="web_search",
                    description="test tool",
                    argsModel=EmptyArgsModel,
                    timeoutSeconds=1,
                    executeCallable=bigTool,
                )
            ]
        ),
        in_maxToolOutputChars=300,
    )

    result = coordinator.execute(in_toolName="web_search", in_rawArgs={})
    assert result.ok is True
    assert isinstance(result.data, str)
    # Must stay valid JSON even when truncated.
    parsed = __import__("json").loads(str(result.data))
    assert parsed.get("_preview") is True
    assert parsed.get("_tool_name") == "web_search"
