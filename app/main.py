from fastapi import FastAPI

from app.application.useCases.handleIncomingTelegramMessageUseCase import (
    HandleIncomingTelegramMessageUseCase,
)
from app.application.useCases.runAgentUseCase import RunAgentUseCase
from app.config.defaults import DEFAULT_CONFIG_PATH
from app.config.settingsLoader import SettingsLoadError, loadSettings
from app.common.structuredLogger import createAppLogger
from app.integrations.telegram.telegramUpdateHandler import TelegramUpdateHandler
from app.models.services.staticLlmClient import StaticLlmClient
from app.domain.policies.stopPolicy import StopPolicy
from app.runtime.agentLoop import AgentLoop
from app.runtime.outputParser import OutputParser
from app.runtime.promptBuilder import PromptBuilder


def _buildApp() -> FastAPI:
    ret: FastAPI
    settings = loadSettings(in_configPath=DEFAULT_CONFIG_PATH)
    logger = createAppLogger(in_loggingSettings=settings.logging)
    useCase = HandleIncomingTelegramMessageUseCase(
        in_allowedUserIds=settings.telegram.allowedUserIds,
        in_denyMessageText=settings.telegram.denyMessageText,
        in_logger=logger,
    )
    updateHandler = TelegramUpdateHandler(in_handleIncomingTelegramMessageUseCase=useCase)
    promptBuilder = PromptBuilder(in_runtimeSettings=settings.runtime)
    outputParser = OutputParser()
    stopPolicy = StopPolicy(in_runtimeSettings=settings.runtime)
    llmClient = StaticLlmClient()
    agentLoop = AgentLoop(
        in_llmClient=llmClient,
        in_promptBuilder=promptBuilder,
        in_outputParser=outputParser,
        in_stopPolicy=stopPolicy,
        in_modelSettings=settings.models,
    )
    runAgentUseCase = RunAgentUseCase(in_agentLoop=agentLoop)

    appInstance = FastAPI(title="simple-ai-agent-bot")
    appInstance.state.settings = settings
    appInstance.state.logger = logger
    appInstance.state.telegramUpdateHandler = updateHandler
    appInstance.state.runAgentUseCase = runAgentUseCase

    @appInstance.get("/health")
    def getHealth() -> dict[str, str]:
        retHealth = {"status": "ok", "service": settings.app.appName}
        return retHealth

    @appInstance.post("/internal/run")
    def runInternal(in_payload: dict[str, str]) -> dict[str, str]:
        sessionId = in_payload.get("sessionId", "telegram:debug")
        inputMessage = in_payload.get("message", "")
        runResult = runAgentUseCase.execute(
            in_sessionId=sessionId,
            in_inputMessage=inputMessage,
        )
        retRunResult = {
            "runId": runResult.runId,
            "completionReason": runResult.completionReason or "",
            "finalAnswer": runResult.finalAnswer or "",
            "selectedModel": runResult.selectedModel or "",
        }
        return retRunResult

    ret = appInstance
    return ret


try:
    app = _buildApp()
except SettingsLoadError as in_exc:
    raise RuntimeError(f"Application startup failed: {in_exc}") from in_exc
