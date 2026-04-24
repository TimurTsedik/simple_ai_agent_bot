from app.config.settingsModels import ModelSettings, RuntimeSettings
from app.domain.policies.stopPolicy import StopPolicy
from app.runtime.agentLoop import AgentLoop
from app.runtime.outputParser import OutputParser
from app.runtime.promptBuilder import PromptBuilder
from app.runtime.toolExecutionCoordinator import ToolExecutionCoordinator
from app.tools.registry.toolMetadataRenderer import ToolMetadataRenderer
from app.tools.registry.toolRegistry import ToolDefinitionModel, ToolRegistry
from pydantic import BaseModel, ConfigDict


class SequenceLlmClient:
    def __init__(self, in_outputs: list[str]) -> None:
        self._outputs = in_outputs
        self._index = 0

    def complete(self, in_modelName: str, in_promptText: str) -> str:
        ret: str
        _ = in_modelName
        _ = in_promptText
        if self._index < len(self._outputs):
            ret = self._outputs[self._index]
            self._index += 1
        else:
            ret = self._outputs[-1]
        return ret


def _makeRuntimeSettings(in_maxSteps: int) -> RuntimeSettings:
    ret = RuntimeSettings(
        maxSteps=in_maxSteps,
        maxToolCalls=3,
        maxExecutionSeconds=60,
        maxToolOutputChars=1000,
        maxPromptChars=3000,
        recentMessagesLimit=12,
        sessionSummaryMaxChars=2000,
        skillSelectionMaxCount=4,
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


def testAgentLoopStopsOnMalformedJson() -> None:
    runtimeSettings = _makeRuntimeSettings(in_maxSteps=5)
    llmClient = SequenceLlmClient(
        in_outputs=['{"type":"final","reason":"done","final_answer":"Финал"']
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

    assert result.completionReason == "stop_response"
    assert "невалидный JSON" in result.finalAnswer


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
