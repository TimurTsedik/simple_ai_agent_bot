import html
import json
from pathlib import Path
from threading import Thread
from urllib.parse import quote

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

    appInstance = FastAPI(title="simple-ai-agent-bot")
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

    def _renderWebNav() -> str:
        ret: str
        ret = (
            "<div style='margin-bottom:16px;padding:8px;background:#f5f5f5;border-radius:6px;'>"
            "<a href='/'>Главная</a> | "
            "<a href='/runs'>Runs</a> | "
            "<a href='/logs'>Logs</a> | "
            "<a href='/git/status'>Git status</a> | "
            "<a href='/git/diff'>Git diff</a>"
            "<form method='post' action='/logout' style='display:inline;margin-left:12px;'>"
            "<button type='submit'>Выйти</button>"
            "</form>"
            "</div>"
        )
        return ret

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
    def getIndex(in_request: Request):
        if _isWebAuthorized(in_request=in_request) is False:
            return RedirectResponse(url="/login", status_code=303)
        ret = (
            "<html><head><title>simple-ai-agent-bot</title></head>"
            + "<body>"
            + "<h1>simple-ai-agent-bot</h1>"
            + _renderWebNav()
            + "<p>Сервис запущен.</p>"
            + "<ul>"
            + "<li><a href='/health'>/health</a> — статус сервиса</li>"
            + "<li><a href='/docs'>/docs</a> — Swagger UI</li>"
            + "<li><a href='/runs'>/runs</a> — список запусков</li>"
            + "<li><a href='/logs'>/logs</a> — просмотр последних логов</li>"
            + "<li><a href='/git/status'>/git/status</a> — git status</li>"
            + "<li><a href='/git/diff'>/git/diff</a> — git diff</li>"
            + "</ul>"
            + "</body></html>"
        )
        return ret

    @appInstance.get("/login", response_class=HTMLResponse)
    def getLoginPage() -> str:
        ret = (
            "<html><head><title>Login</title></head><body>"
            "<h1>Admin Login</h1>"
            "<form method='post' action='/login'>"
            "<label>Admin token: <input name='adminToken' type='password' /></label>"
            "<button type='submit'>Войти</button>"
            "</form>"
            "</body></html>"
        )
        return ret

    @appInstance.post("/login")
    def postLogin(adminToken: str = Form(...)):
        tokenHash = hashAdminToken(
            in_rawToken=adminToken,
            in_secret=settings.sessionCookieSecret,
        )
        if tokenHash not in appInstance.state.adminTokenHashes:
            retError: HTMLResponse = HTMLResponse(
                content=(
                    "<html><head><title>Login</title></head><body>"
                    "<h1>Admin Login</h1>"
                    "<p>Неверный токен.</p>"
                    "<form method='post' action='/login'>"
                    "<label>Admin token: <input name='adminToken' type='password' /></label>"
                    "<button type='submit'>Войти</button>"
                    "</form>"
                    "</body></html>"
                ),
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
            + "<h1>Run Logs</h1>"
            + _renderWebNav()
            + f"<p>Показаны последние {len(logItems)} записей.</p>"
            + content
            + "</body></html>"
        )
        return ret

    @appInstance.get("/runs", response_class=HTMLResponse)
    def getRunsPage(
        in_request: Request, limit: int = 50, offset: int = 0
    ):
        if _isWebAuthorized(in_request=in_request) is False:
            return RedirectResponse(url="/login", status_code=303)
        runItems = getRunListUseCase.execute(in_limit=limit, in_offset=offset)
        rows: list[str] = []
        for runItem in runItems:
            runId = str(runItem.get("runId", "unknown"))
            sessionId = str(runItem.get("sessionId", ""))
            status = str(runItem.get("runStatus", ""))
            reason = str(runItem.get("completionReason", ""))
            createdAt = str(runItem.get("createdAt", ""))
            rows.append(
                "<tr>"
                f"<td><a href='/runs/{html.escape(runId)}'>{html.escape(runId)}</a></td>"
                f"<td>{html.escape(sessionId)}</td>"
                f"<td>{html.escape(status)}</td>"
                f"<td>{html.escape(reason)}</td>"
                f"<td>{html.escape(createdAt)}</td>"
                "</tr>"
            )
        bodyRows = "".join(rows) if rows else "<tr><td colspan='5'>Запусков пока нет.</td></tr>"
        ret = (
            "<html><head><title>Runs</title></head><body>"
            + "<h1>Runs</h1>"
            + _renderWebNav()
            + f"<p>Показаны последние {len(runItems)} запусков.</p>"
            + "<table border='1' cellspacing='0' cellpadding='6'>"
            + "<thead><tr><th>runId</th><th>sessionId</th><th>status</th>"
            + "<th>completionReason</th><th>createdAt</th></tr></thead>"
            + f"<tbody>{bodyRows}</tbody>"
            + "</table>"
            + "</body></html>"
        )
        return ret

    @appInstance.get("/runs/{runId}", response_class=HTMLResponse)
    def getRunDetailsPage(runId: str, in_request: Request):
        if _isWebAuthorized(in_request=in_request) is False:
            return RedirectResponse(url="/login", status_code=303)
        runItem = getRunDetailsUseCase.execute(in_runId=runId)
        if runItem is None:
            raise HTTPException(status_code=404, detail="Run is not found")
        prettyJson = json.dumps(runItem, ensure_ascii=False, indent=2)
        ret = (
            "<html><head><title>Run Details</title></head><body>"
            + f"<h1>Run {html.escape(runId)}</h1>"
            + _renderWebNav()
            + f"<p><a href='/runs/{html.escape(runId)}/steps'>Открыть шаги agentic loop</a></p>"
            + "<pre style='white-space:pre-wrap;background:#f7f7f7;padding:8px;border-radius:6px;'>"
            + html.escape(prettyJson)
            + "</pre>"
            + "</body></html>"
        )
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

        renderedBlocks: list[str] = []
        for stepItem in stepItems:
            if not isinstance(stepItem, dict):
                continue
            stepIndex = str(stepItem.get("stepIndex", ""))
            status = str(stepItem.get("status", ""))
            toolCallJson = json.dumps(stepItem.get("toolCall"), ensure_ascii=False, indent=2)
            toolResultJson = json.dumps(
                stepItem.get("toolResult"), ensure_ascii=False, indent=2
            )
            parsedJson = json.dumps(
                stepItem.get("parsedModelResponse"), ensure_ascii=False, indent=2
            )
            promptText = str(stepItem.get("promptSnapshot", ""))
            rawResponse = str(stepItem.get("rawModelResponse", ""))
            renderedBlocks.append(
                "<div style='border:1px solid #ddd;padding:10px;border-radius:8px;margin:12px 0;'>"
                f"<h3>Step {html.escape(stepIndex)} — {html.escape(status)}</h3>"
                "<details><summary>Prompt sent to LLM</summary>"
                "<pre style='white-space:pre-wrap;background:#f7f7f7;padding:8px;border-radius:6px;'>"
                + html.escape(promptText)
                + "</pre></details>"
                "<details><summary>Raw model response</summary>"
                "<pre style='white-space:pre-wrap;background:#f7f7f7;padding:8px;border-radius:6px;'>"
                + html.escape(rawResponse)
                + "</pre></details>"
                "<details><summary>Parsed model response</summary>"
                "<pre style='white-space:pre-wrap;background:#f7f7f7;padding:8px;border-radius:6px;'>"
                + html.escape(parsedJson)
                + "</pre></details>"
                "<details><summary>Tool call</summary>"
                "<pre style='white-space:pre-wrap;background:#f7f7f7;padding:8px;border-radius:6px;'>"
                + html.escape(toolCallJson)
                + "</pre></details>"
                "<details><summary>Tool result</summary>"
                "<pre style='white-space:pre-wrap;background:#f7f7f7;padding:8px;border-radius:6px;'>"
                + html.escape(toolResultJson)
                + "</pre></details>"
                "</div>"
            )

        content = (
            "".join(renderedBlocks)
            if renderedBlocks
            else "<p>Для этого запуска шаги не найдены.</p>"
        )
        ret = (
            "<html><head><title>Run Steps</title></head><body>"
            + f"<h1>Run {html.escape(runId)} — Agentic Loop Steps</h1>"
            + _renderWebNav()
            + f"<p><a href='/runs/{html.escape(runId)}'>Назад к полному run</a></p>"
            + content
            + "</body></html>"
        )
        return ret

    @appInstance.get("/git/status", response_class=HTMLResponse)
    def getGitStatusPage(in_request: Request, limit: int = 200):
        if _isWebAuthorized(in_request=in_request) is False:
            return RedirectResponse(url="/login", status_code=303)
        statusResult = getGitStatusUseCase.execute(in_limit=limit)
        isGitRepo = bool(statusResult.get("isGitRepo", False))
        branch = str(statusResult.get("branch", ""))
        isClean = bool(statusResult.get("isClean", True))
        itemLines = statusResult.get("items", [])
        if not isinstance(itemLines, list):
            itemLines = []
        errorText = str(statusResult.get("error", ""))
        itemsBlock = (
            "<p>Изменений нет.</p>"
            if len(itemLines) == 0
            else "<pre style='white-space:pre-wrap;background:#f7f7f7;padding:8px;border-radius:6px;'>"
            + html.escape("\n".join(str(item) for item in itemLines))
            + "</pre>"
        )
        ret = (
            "<html><head><title>Git Status</title></head><body>"
            + "<h1>Git Status</h1>"
            + _renderWebNav()
            + f"<p>Git repository: {'yes' if isGitRepo else 'no'}</p>"
            + f"<p>Branch: {html.escape(branch)}</p>"
            + f"<p>Clean: {'yes' if isClean else 'no'}</p>"
            + (
                f"<p style='color:#b00020;'>Error: {html.escape(errorText)}</p>"
                if errorText
                else ""
            )
            + itemsBlock
            + "</body></html>"
        )
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
        isGitRepo = bool(diffResult.get("isGitRepo", False))
        totalFiles = int(diffResult.get("totalFiles", 0))
        currentOffset = int(diffResult.get("offset", 0))
        currentLimit = int(diffResult.get("limit", 5))
        errorText = str(diffResult.get("error", ""))
        files = diffResult.get("files", [])
        if not isinstance(files, list):
            files = []
        renderedFiles: list[str] = []
        for oneFile in files:
            if not isinstance(oneFile, dict):
                continue
            onePath = str(oneFile.get("filePath", ""))
            oneDiff = str(oneFile.get("diff", ""))
            oneTruncated = bool(oneFile.get("truncated", False))
            renderedFiles.append(
                "<div style='border:1px solid #ddd;padding:10px;border-radius:8px;margin:12px 0;'>"
                + f"<h3>{html.escape(onePath)}</h3>"
                + "<pre style='white-space:pre-wrap;background:#f7f7f7;padding:8px;border-radius:6px;'>"
                + html.escape(oneDiff)
                + "</pre>"
                + (
                    "<p style='color:#9a6700;'>Diff truncated for safety.</p>"
                    if oneTruncated
                    else ""
                )
                + "</div>"
            )
        prevOffset = max(0, currentOffset - currentLimit)
        nextOffset = currentOffset + currentLimit
        baseLink = (
            f"/git/diff?limit={currentLimit}&maxCharsPerFile={maxCharsPerFile}"
            f"&filePath={quote(filePath)}"
        )
        ret = (
            "<html><head><title>Git Diff</title></head><body>"
            + "<h1>Git Diff</h1>"
            + _renderWebNav()
            + f"<p>Git repository: {'yes' if isGitRepo else 'no'}</p>"
            + f"<p>Total changed files: {totalFiles}</p>"
            + (
                f"<p style='color:#b00020;'>Error: {html.escape(errorText)}</p>"
                if errorText
                else ""
            )
            + f"<p><a href='{baseLink}&offset={prevOffset}'>Prev</a> | "
            + f"<a href='{baseLink}&offset={nextOffset}'>Next</a></p>"
            + (
                "".join(renderedFiles)
                if len(renderedFiles) > 0
                else "<p>Diff data is empty.</p>"
            )
            + "</body></html>"
        )
        return ret

    ret = appInstance
    return ret


try:
    app = _buildApp()
except SettingsLoadError as in_exc:
    raise RuntimeError(f"Application startup failed: {in_exc}") from in_exc
