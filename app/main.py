from contextlib import asynccontextmanager
from pathlib import Path
from threading import Thread

from fastapi import FastAPI
from fastapi import Form
from fastapi import HTTPException
from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.responses import RedirectResponse

from app.application.useCases.getRunDetailsUseCase import GetRunDetailsUseCase
from app.application.useCases.getGitDiffUseCase import GetGitDiffUseCase
from app.application.useCases.getGitStatusUseCase import GetGitStatusUseCase
from app.application.useCases.getRunListUseCase import GetRunListUseCase
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
from app.integrations.git.gitService import GitService
from app.memory.services.memoryService import MemoryService
from app.memory.stores.markdownMemoryStore import MarkdownMemoryStore
from app.models.providers.openRouterClient import OpenRouterClient
from app.models.services.llmService import LlmService
from app.observability.stores.jsonRunRepository import JsonRunRepository
from app.presentation.web.adminPages import renderGitDiffPage
from app.presentation.web.adminPages import renderGitStatusPage
from app.presentation.web.adminPages import renderIndexPage
from app.presentation.web.adminPages import renderLoginPage
from app.presentation.web.adminPages import renderLogsPage
from app.presentation.web.adminPages import renderRunDetailsPage
from app.presentation.web.adminPages import renderRunsPage
from app.presentation.web.adminPages import renderRunStepsPage
from app.runtime.agentLoop import AgentLoop
from app.runtime.outputParser import OutputParser
from app.runtime.promptBuilder import PromptBuilder
from app.runtime.toolExecutionCoordinator import ToolExecutionCoordinator
from app.security.webSessionAuth import createSessionCookieValue
from app.security.webSessionAuth import hashAdminToken
from app.security.webSessionAuth import parseSessionCookieValue
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
    runRepository = JsonRunRepository(in_dataRootPath=settings.app.dataRootPath)
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
        in_runRepository=runRepository,
        in_settings=settings,
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
    getRunListUseCase = GetRunListUseCase(in_runRepository=runRepository)
    getRunDetailsUseCase = GetRunDetailsUseCase(in_runRepository=runRepository)
    gitService = GitService(in_repoRootPath=str(Path(__file__).resolve().parent.parent))
    getGitStatusUseCase = GetGitStatusUseCase(in_gitService=gitService)
    getGitDiffUseCase = GetGitDiffUseCase(in_gitService=gitService)

    @asynccontextmanager
    async def lifespan(in_app: FastAPI):  # noqa: ANN202
        pollingThread = Thread(
            target=in_app.state.telegramPollingRunner.runForever,
            name="telegramPollingThread",
            daemon=True,
        )
        in_app.state.telegramPollingThread = pollingThread
        in_app.state.telegramPollingThread.start()
        writeJsonlEvent(
            in_loggingSettings=settings.logging,
            in_eventType="telegram_polling_started",
            in_payload={},
        )
        try:
            yield
        finally:
            in_app.state.telegramPollingRunner.stop()
            currentThread = in_app.state.telegramPollingThread
            if currentThread is not None:
                currentThread.join(timeout=2)
            writeJsonlEvent(
                in_loggingSettings=settings.logging,
                in_eventType="telegram_polling_stopped",
                in_payload={},
            )

    appInstance = FastAPI(title="simple-ai-agent-bot", lifespan=lifespan)
    appInstance.state.settings = settings
    appInstance.state.logger = logger
    appInstance.state.telegramUpdateHandler = updateHandler
    appInstance.state.runAgentUseCase = runAgentUseCase
    appInstance.state.getLogsUseCase = getLogsUseCase
    appInstance.state.getRunListUseCase = getRunListUseCase
    appInstance.state.getRunDetailsUseCase = getRunDetailsUseCase
    appInstance.state.getGitStatusUseCase = getGitStatusUseCase
    appInstance.state.getGitDiffUseCase = getGitDiffUseCase
    appInstance.state.telegramPollingRunner = telegramPollingRunner
    appInstance.state.telegramPollingThread = None
    appInstance.state.webSessionCookieName = "admin_session"
    appInstance.state.adminTokenHashes = {
        hashAdminToken(
            in_rawToken=oneToken,
            in_secret=settings.sessionCookieSecret,
        )
        for oneToken in settings.adminRawTokens
    }

    def _isWebAuthorized(in_request: Request) -> bool:
        ret: bool
        cookieName = appInstance.state.webSessionCookieName
        rawCookieValue = in_request.cookies.get(cookieName, "")
        if not rawCookieValue:
            ret = False
            return ret
        payload = parseSessionCookieValue(
            in_cookieValue=rawCookieValue,
            in_secret=settings.sessionCookieSecret,
        )
        if payload is None:
            ret = False
            return ret
        tokenHash = payload.get("tokenHash")
        ret = (
            isinstance(tokenHash, str) and tokenHash in appInstance.state.adminTokenHashes
        )
        return ret

    @appInstance.get("/", response_class=HTMLResponse)
    def getIndex(in_request: Request):
        if _isWebAuthorized(in_request=in_request) is False:
            return RedirectResponse(url="/login", status_code=303)
        ret = renderIndexPage()
        return ret

    @appInstance.get("/login", response_class=HTMLResponse)
    def getLoginPage() -> str:
        ret = renderLoginPage()
        return ret

    @appInstance.post("/login")
    def postLogin(adminToken: str = Form(...)):
        tokenHash = hashAdminToken(
            in_rawToken=adminToken,
            in_secret=settings.sessionCookieSecret,
        )
        if tokenHash not in appInstance.state.adminTokenHashes:
            retError: HTMLResponse = HTMLResponse(
                content=renderLoginPage(in_errorText="Неверный токен."),
                status_code=401,
            )
            return retError
        response = RedirectResponse(url="/", status_code=303)
        cookieValue = createSessionCookieValue(
            in_tokenHash=tokenHash,
            in_secret=settings.sessionCookieSecret,
            in_ttlSeconds=settings.security.webSessionCookieTtlSeconds,
        )
        response.set_cookie(
            key=appInstance.state.webSessionCookieName,
            value=cookieValue,
            max_age=settings.security.webSessionCookieTtlSeconds,
            httponly=True,
            samesite="lax",
        )
        return response

    @appInstance.post("/logout")
    def postLogout() -> RedirectResponse:
        response = RedirectResponse(url="/login", status_code=303)
        response.delete_cookie(key=appInstance.state.webSessionCookieName)
        return response

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

    @appInstance.get("/internal/runs")
    def getInternalRuns(limit: int = 50, offset: int = 0) -> dict[str, object]:
        runItems = getRunListUseCase.execute(in_limit=limit, in_offset=offset)
        retRuns = {"count": len(runItems), "items": runItems}
        return retRuns

    @appInstance.get("/internal/runs/{runId}")
    def getInternalRunDetails(runId: str) -> dict[str, object]:
        runItem = getRunDetailsUseCase.execute(in_runId=runId)
        if runItem is None:
            raise HTTPException(status_code=404, detail="Run is not found")
        retRun = {"item": runItem}
        return retRun

    @appInstance.get("/internal/runs/{runId}/steps")
    def getInternalRunSteps(runId: str) -> dict[str, object]:
        runItem = getRunDetailsUseCase.execute(in_runId=runId)
        if runItem is None:
            raise HTTPException(status_code=404, detail="Run is not found")
        stepItems = runItem.get("stepTraces", [])
        if not isinstance(stepItems, list):
            stepItems = []
        retSteps = {"runId": runId, "count": len(stepItems), "items": stepItems}
        return retSteps

    @appInstance.get("/internal/git/status")
    def getInternalGitStatus(limit: int = 200) -> dict[str, object]:
        retStatus = getGitStatusUseCase.execute(in_limit=limit)
        return retStatus

    @appInstance.get("/internal/git/diff")
    def getInternalGitDiff(
        offset: int = 0,
        limit: int = 5,
        filePath: str = "",
        maxCharsPerFile: int = 30000,
    ) -> dict[str, object]:
        retDiff = getGitDiffUseCase.execute(
            in_offset=offset,
            in_limit=limit,
            in_filePath=filePath,
            in_maxCharsPerFile=maxCharsPerFile,
        )
        return retDiff

    @appInstance.get("/logs", response_class=HTMLResponse)
    def getLogsPage(in_request: Request, limit: int = 100):
        if _isWebAuthorized(in_request=in_request) is False:
            return RedirectResponse(url="/login", status_code=303)
        logItems = getLogsUseCase.execute(in_limit=limit)
        ret = renderLogsPage(in_logItems=logItems)
        return ret

    @appInstance.get("/runs", response_class=HTMLResponse)
    def getRunsPage(
        in_request: Request, limit: int = 50, offset: int = 0
    ):
        if _isWebAuthorized(in_request=in_request) is False:
            return RedirectResponse(url="/login", status_code=303)
        runItems = getRunListUseCase.execute(in_limit=limit, in_offset=offset)
        ret = renderRunsPage(in_runItems=runItems)
        return ret

    @appInstance.get("/runs/{runId}", response_class=HTMLResponse)
    def getRunDetailsPage(runId: str, in_request: Request):
        if _isWebAuthorized(in_request=in_request) is False:
            return RedirectResponse(url="/login", status_code=303)
        runItem = getRunDetailsUseCase.execute(in_runId=runId)
        if runItem is None:
            raise HTTPException(status_code=404, detail="Run is not found")
        ret = renderRunDetailsPage(in_runId=runId, in_runItem=runItem)
        return ret

    @appInstance.get("/runs/{runId}/steps", response_class=HTMLResponse)
    def getRunStepsPage(runId: str, in_request: Request):
        if _isWebAuthorized(in_request=in_request) is False:
            return RedirectResponse(url="/login", status_code=303)
        runItem = getRunDetailsUseCase.execute(in_runId=runId)
        if runItem is None:
            raise HTTPException(status_code=404, detail="Run is not found")
        stepItems = runItem.get("stepTraces", [])
        if not isinstance(stepItems, list):
            stepItems = []
        ret = renderRunStepsPage(in_runId=runId, in_stepItems=stepItems)
        return ret

    @appInstance.get("/git/status", response_class=HTMLResponse)
    def getGitStatusPage(in_request: Request, limit: int = 200):
        if _isWebAuthorized(in_request=in_request) is False:
            return RedirectResponse(url="/login", status_code=303)
        statusResult = getGitStatusUseCase.execute(in_limit=limit)
        ret = renderGitStatusPage(in_statusResult=statusResult)
        return ret

    @appInstance.get("/git/diff", response_class=HTMLResponse)
    def getGitDiffPage(
        in_request: Request,
        offset: int = 0,
        limit: int = 5,
        filePath: str = "",
        maxCharsPerFile: int = 30000,
    ):
        if _isWebAuthorized(in_request=in_request) is False:
            return RedirectResponse(url="/login", status_code=303)
        diffResult = getGitDiffUseCase.execute(
            in_offset=offset,
            in_limit=limit,
            in_filePath=filePath,
            in_maxCharsPerFile=maxCharsPerFile,
        )
        ret = renderGitDiffPage(
            in_diffResult=diffResult,
            in_offset=offset,
            in_limit=limit,
            in_filePath=filePath,
            in_maxCharsPerFile=maxCharsPerFile,
        )
        return ret

    ret = appInstance
    return ret


try:
    app = _buildApp()
except SettingsLoadError as in_exc:
    raise RuntimeError(f"Application startup failed: {in_exc}") from in_exc
