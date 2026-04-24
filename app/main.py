import html
from threading import Thread

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from app.application.useCases.getLogsUseCase import GetLogsUseCase
from app.application.useCases.handleIncomingTelegramMessageUseCase import (
    HandleIncomingTelegramMessageUseCase,
)
from app.application.useCases.runAgentUseCase import RunAgentUseCase
from app.config.defaults import DEFAULT_CONFIG_PATH
from app.config.settingsLoader import SettingsLoadError, loadSettings
from app.common.structuredLogger import createAppLogger
from app.common.structuredLogger import writeJsonlEvent
from app.domain.policies.memoryPolicy import MemoryPolicy
from app.domain.policies.stopPolicy import StopPolicy
from app.integrations.telegram.telegramPollingRunner import TelegramPollingRunner
from app.integrations.telegram.telegramUpdateHandler import TelegramUpdateHandler
from app.memory.services.memoryService import MemoryService
from app.memory.stores.markdownMemoryStore import MarkdownMemoryStore
from app.models.providers.openRouterClient import OpenRouterClient
from app.models.services.llmService import LlmService
from app.runtime.agentLoop import AgentLoop
from app.runtime.outputParser import OutputParser
from app.runtime.promptBuilder import PromptBuilder
from app.runtime.toolExecutionCoordinator import ToolExecutionCoordinator
from app.skills.services.skillSelectorRules import SkillSelectorRules
from app.skills.services.skillService import SkillService
from app.skills.stores.markdownSkillStore import MarkdownSkillStore
from app.tools.registry.toolMetadataRenderer import ToolMetadataRenderer
from app.tools.services.toolFactory import buildToolRegistry


def _buildApp() -> FastAPI:
    ret: FastAPI
    settings = loadSettings(in_configPath=DEFAULT_CONFIG_PATH)
    logger = createAppLogger(in_loggingSettings=settings.logging)
    promptBuilder = PromptBuilder(in_runtimeSettings=settings.runtime)
    outputParser = OutputParser()
    stopPolicy = StopPolicy(in_runtimeSettings=settings.runtime)
    toolRegistry = buildToolRegistry(in_settings=settings)
    toolMetadataRenderer = ToolMetadataRenderer()
    toolExecutionCoordinator = ToolExecutionCoordinator(
        in_toolRegistry=toolRegistry,
        in_maxToolOutputChars=settings.runtime.maxToolOutputChars,
    )
    openRouterClient = OpenRouterClient(
        in_baseUrl=settings.models.openRouterBaseUrl,
        in_apiKey=settings.openRouterApiKey,
        in_timeoutSeconds=settings.models.requestTimeoutSeconds,
    )
    llmClient = LlmService(
        in_openRouterClient=openRouterClient,
        in_modelSettings=settings.models,
        in_loggingSettings=settings.logging,
    )
    skillStore = MarkdownSkillStore(in_skillsDirPath=settings.skills.skillsDirPath)
    skillSelectorRules = SkillSelectorRules()
    skillService = SkillService(
        in_skillStore=skillStore,
        in_skillSelectorRules=skillSelectorRules,
        in_skillSelectionMaxCount=settings.runtime.skillSelectionMaxCount,
    )
    memoryStore = MarkdownMemoryStore(in_memorySettings=settings.memory)
    memoryPolicy = MemoryPolicy()
    memoryService = MemoryService(
        in_memoryStore=memoryStore,
        in_memoryPolicy=memoryPolicy,
        in_recentMessagesLimit=settings.runtime.recentMessagesLimit,
        in_sessionSummaryMaxChars=settings.runtime.sessionSummaryMaxChars,
    )
    agentLoop = AgentLoop(
        in_llmClient=llmClient,
        in_promptBuilder=promptBuilder,
        in_outputParser=outputParser,
        in_stopPolicy=stopPolicy,
        in_modelSettings=settings.models,
        in_toolExecutionCoordinator=toolExecutionCoordinator,
        in_toolMetadataRenderer=toolMetadataRenderer,
        in_toolRegistry=toolRegistry,
    )
    runAgentUseCase = RunAgentUseCase(
        in_agentLoop=agentLoop,
        in_skillService=skillService,
        in_memoryService=memoryService,
    )
    handleIncomingTelegramMessageUseCase = HandleIncomingTelegramMessageUseCase(
        in_allowedUserIds=settings.telegram.allowedUserIds,
        in_denyMessageText=settings.telegram.denyMessageText,
        in_logger=logger,
        in_runAgentUseCase=runAgentUseCase,
        in_memoryService=memoryService,
    )
    updateHandler = TelegramUpdateHandler(
        in_handleIncomingTelegramMessageUseCase=handleIncomingTelegramMessageUseCase
    )
    telegramPollingRunner = TelegramPollingRunner(
        in_settings=settings,
        in_logger=logger,
        in_updateHandler=updateHandler,
    )
    getLogsUseCase = GetLogsUseCase(in_loggingSettings=settings.logging)

    appInstance = FastAPI(title="simple-ai-agent-bot")
    appInstance.state.settings = settings
    appInstance.state.logger = logger
    appInstance.state.telegramUpdateHandler = updateHandler
    appInstance.state.runAgentUseCase = runAgentUseCase
    appInstance.state.getLogsUseCase = getLogsUseCase
    appInstance.state.telegramPollingRunner = telegramPollingRunner
    appInstance.state.telegramPollingThread = None

    @appInstance.on_event("startup")
    def onStartup() -> None:
        pollingThread = Thread(
            target=appInstance.state.telegramPollingRunner.runForever,
            name="telegramPollingThread",
            daemon=True,
        )
        appInstance.state.telegramPollingThread = pollingThread
        appInstance.state.telegramPollingThread.start()
        writeJsonlEvent(
            in_loggingSettings=settings.logging,
            in_eventType="telegram_polling_started",
            in_payload={},
        )

    @appInstance.on_event("shutdown")
    def onShutdown() -> None:
        appInstance.state.telegramPollingRunner.stop()
        pollingThread = appInstance.state.telegramPollingThread
        if pollingThread is not None:
            pollingThread.join(timeout=2)
        writeJsonlEvent(
            in_loggingSettings=settings.logging,
            in_eventType="telegram_polling_stopped",
            in_payload={},
        )

    @appInstance.get("/", response_class=HTMLResponse)
    def getIndex() -> str:
        ret = (
            "<html><head><title>simple-ai-agent-bot</title></head>"
            "<body>"
            "<h1>simple-ai-agent-bot</h1>"
            "<p>Сервис запущен.</p>"
            "<ul>"
            "<li><a href='/health'>/health</a> — статус сервиса</li>"
            "<li><a href='/docs'>/docs</a> — Swagger UI</li>"
            "<li><a href='/logs'>/logs</a> — просмотр последних логов</li>"
            "</ul>"
            "</body></html>"
        )
        return ret

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
        writeJsonlEvent(
            in_loggingSettings=settings.logging,
            in_eventType="internal_run_result",
            in_payload={
                "runId": runResult.runId,
                "sessionId": runResult.sessionId,
                "completionReason": runResult.completionReason,
            },
        )
        retRunResult = {
            "runId": runResult.runId,
            "completionReason": runResult.completionReason or "",
            "finalAnswer": runResult.finalAnswer or "",
            "selectedModel": runResult.selectedModel or "",
        }
        return retRunResult

    @appInstance.get("/internal/logs")
    def getInternalLogs(limit: int = 100) -> dict[str, object]:
        logItems = getLogsUseCase.execute(in_limit=limit)
        retLogs = {"count": len(logItems), "items": logItems}
        return retLogs

    @appInstance.get("/logs", response_class=HTMLResponse)
    def getLogsPage(limit: int = 100) -> str:
        logItems = getLogsUseCase.execute(in_limit=limit)
        renderedItems: list[str] = []
        for oneItem in logItems:
            renderedItems.append(
                "<pre style='white-space:pre-wrap;background:#f7f7f7;padding:8px;border-radius:6px;'>"
                + html.escape(str(oneItem))
                + "</pre>"
            )
        content = "".join(renderedItems) if renderedItems else "<p>Логи пока отсутствуют.</p>"
        ret = (
            "<html><head><title>Logs</title></head><body>"
            "<h1>Run Logs</h1>"
            f"<p>Показаны последние {len(logItems)} записей.</p>"
            + content
            + "</body></html>"
        )
        return ret

    ret = appInstance
    return ret


try:
    app = _buildApp()
except SettingsLoadError as in_exc:
    raise RuntimeError(f"Application startup failed: {in_exc}") from in_exc
