from contextlib import asynccontextmanager
from pathlib import Path
from threading import Thread

from fastapi import FastAPI
from fastapi import Form
from fastapi import HTTPException
from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.responses import RedirectResponse
from pathlib import Path
import os
import yaml
from pydantic import ValidationError

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
from app.presentation.web.adminPages import renderToolsConfigEditPage
from app.presentation.web.adminPages import renderToolsPage
from app.presentation.web.adminPages import renderSkillEditPage
from app.presentation.web.adminPages import renderSkillsPage
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
from app.config.settingsModels import EmailReaderToolSettings, TelegramNewsDigestToolSettings
from app.scheduler.schedulerRunner import SchedulerRunner


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
    schedulerRunner: SchedulerRunner | None
    if settings.scheduler.enabled is True:
        schedulerRunner = SchedulerRunner(
            in_schedulerSettings=settings.scheduler,
            in_loggingSettings=settings.logging,
            in_dataRootPath=settings.app.dataRootPath,
            in_runInternalCallable=lambda sessionId, message: runAgentUseCase.execute(
                in_sessionId=sessionId,
                in_inputMessage=message,
            ).runId,
        )
    else:
        schedulerRunner = None
    handleIncomingTelegramMessageUseCase = HandleIncomingTelegramMessageUseCase(
        in_allowedUserIds=settings.telegram.allowedUserIds,
        in_denyMessageText=settings.telegram.denyMessageText,
        in_logger=logger,
        in_runAgentUseCase=runAgentUseCase,
        in_memoryService=memoryService,
        in_runtimeSettings=settings.runtime,
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
        schedulerThread = None
        if in_app.state.schedulerRunner is not None:
            schedulerThread = Thread(
                target=in_app.state.schedulerRunner.runForever,
                name="schedulerThread",
                daemon=True,
            )
            in_app.state.schedulerThread = schedulerThread
            in_app.state.schedulerThread.start()
            writeJsonlEvent(
                in_loggingSettings=settings.logging,
                in_eventType="scheduler_thread_started",
                in_payload={},
            )
        try:
            yield
        finally:
            if in_app.state.schedulerRunner is not None:
                in_app.state.schedulerRunner.stop()
            currentSchedulerThread = in_app.state.schedulerThread
            if currentSchedulerThread is not None:
                currentSchedulerThread.join(timeout=2)
            if in_app.state.schedulerRunner is not None:
                writeJsonlEvent(
                    in_loggingSettings=settings.logging,
                    in_eventType="scheduler_thread_stopped",
                    in_payload={},
                )
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
    appInstance.state.schedulerRunner = schedulerRunner
    appInstance.state.schedulerThread = None
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

    def _ensureWritesEnabledOr403() -> None:
        if settings.security.adminWritesEnabled is not True:
            raise HTTPException(status_code=403, detail="Admin writes are disabled")

    def _resolveToolsConfigPath() -> Path:
        toolsPath = Path(settings.tools.toolsConfigPath)
        if toolsPath.is_absolute() is False:
            # Resolve relative to current working directory.
            # `toolsConfigPath` often is like "./app/config/tools.yaml" and should not be joined
            # with config directory (would duplicate "app/config").
            toolsPath = toolsPath.resolve()
        return toolsPath

    def _atomicWriteTextFile(in_path: Path, in_text: str) -> None:
        in_path.parent.mkdir(parents=True, exist_ok=True)
        tmpPath = in_path.with_suffix(in_path.suffix + ".tmp")
        tmpPath.write_text(in_text, encoding="utf-8")
        os.replace(tmpPath, in_path)

    def _loadToolsYamlTextOrEmpty() -> str:
        toolsPath = _resolveToolsConfigPath()
        if toolsPath.exists():
            return toolsPath.read_text(encoding="utf-8")
        return ""

    def _validateToolsYamlOrRaise(in_yamlText: str) -> None:
        loaded = yaml.safe_load(in_yamlText) or {}
        if not isinstance(loaded, dict):
            raise ValidationError.from_exception_data("tools_yaml", [])
        _ = TelegramNewsDigestToolSettings.model_validate(
            loaded.get("telegramNewsDigest", {}) if isinstance(loaded, dict) else {}
        )
        _ = EmailReaderToolSettings.model_validate(
            loaded.get("emailReader", {}) if isinstance(loaded, dict) else {}
        )

    def _formatBytes(in_sizeBytes: int) -> str:
        ret: str
        sizeValue = float(max(0, in_sizeBytes))
        units = ["B", "KB", "MB", "GB"]
        unitIndex = 0
        while sizeValue >= 1024.0 and unitIndex < len(units) - 1:
            sizeValue /= 1024.0
            unitIndex += 1
        ret = f"{sizeValue:.1f} {units[unitIndex]}"
        return ret

    def _dirInfo(in_dirPath: Path) -> str:
        ret: str
        if in_dirPath.exists() is False:
            ret = "missing"
        else:
            fileCount = 0
            totalBytes = 0
            for filePath in in_dirPath.rglob("*"):
                if filePath.is_file():
                    fileCount += 1
                    try:
                        totalBytes += int(filePath.stat().st_size)
                    except OSError:
                        pass
            ret = f"{fileCount} files, {_formatBytes(totalBytes)}"
        return ret

    def _fileInfo(in_filePath: Path) -> str:
        ret: str
        if in_filePath.exists() is False:
            ret = "missing"
        else:
            try:
                statValue = in_filePath.stat()
                ret = f"{_formatBytes(int(statValue.st_size))} (mtime={statValue.st_mtime:.0f})"
            except OSError:
                ret = "unavailable"
        return ret

    def _fileTextSize(in_filePath: Path) -> dict[str, int]:
        ret: dict[str, int]
        if in_filePath.exists() is False:
            ret = {"chars": 0, "bytes": 0}
        else:
            try:
                textValue = in_filePath.read_text(encoding="utf-8")
                byteCount = int(in_filePath.stat().st_size)
                ret = {"chars": len(textValue), "bytes": byteCount}
            except OSError:
                ret = {"chars": 0, "bytes": 0}
        return ret

    @appInstance.get("/", response_class=HTMLResponse)
    def getIndex(in_request: Request):
        if _isWebAuthorized(in_request=in_request) is False:
            return RedirectResponse(url="/login", status_code=303)
        runs = getRunListUseCase.execute(in_limit=1, in_offset=0)
        lastRun = runs[0] if isinstance(runs, list) and len(runs) > 0 else {}
        toolsYamlPath = _resolveToolsConfigPath()
        memoryRoot = Path(settings.memory.memoryRootPath)
        logsRoot = Path(settings.logging.logsDirPath)
        lastSessionId = str(lastRun.get("sessionId", ""))
        sessionFolderName = lastSessionId.replace(":", "_") if lastSessionId else ""
        sessionMemoryRoot = (
            (memoryRoot / "sessions" / sessionFolderName)
            if sessionFolderName
            else memoryRoot
        )
        recentPath = sessionMemoryRoot / settings.memory.recentMessagesFileName
        summaryPath = sessionMemoryRoot / settings.memory.sessionSummaryFileName
        longTermPath = memoryRoot / settings.memory.longTermFileName

        recentSize = _fileTextSize(in_filePath=recentPath)
        summarySize = _fileTextSize(in_filePath=summaryPath)
        longTermSize = _fileTextSize(in_filePath=longTermPath)
        activeContextChars = int(recentSize.get("chars", 0)) + int(summarySize.get("chars", 0))
        activeContextBytes = int(recentSize.get("bytes", 0)) + int(summarySize.get("bytes", 0))

        stats = {
            "adminWritesEnabled": settings.security.adminWritesEnabled,
            "toolsCount": len(toolRegistry.listTools()),
            "skillsCount": len(skillStore.loadAllSkills()),
            "runsCount": len(getRunListUseCase.execute(in_limit=50, in_offset=0)),
            "maxPromptChars": settings.runtime.maxPromptChars,
            "maxToolOutputChars": settings.runtime.maxToolOutputChars,
            "maxExecutionSeconds": settings.runtime.maxExecutionSeconds,
            "primaryModel": settings.models.primaryModel,
            "secondaryModel": settings.models.secondaryModel,
            "tertiaryModel": settings.models.tertiaryModel,
            "lastRunId": str(lastRun.get("runId", "")),
            "lastRunSessionId": lastSessionId,
            "lastRunStatus": str(lastRun.get("runStatus", "—")),
            "lastRunReason": str(lastRun.get("completionReason", "—")),
            "lastRunCreatedAt": str(lastRun.get("createdAt", "—")),
            "lastRunSelectedModel": str(lastRun.get("selectedModel", "—")),
            "toolsYamlInfo": _fileInfo(in_filePath=toolsYamlPath),
            "memoryInfo": _dirInfo(in_dirPath=memoryRoot),
            "logsInfo": _dirInfo(in_dirPath=logsRoot),
            "contextActive": f"{activeContextChars} chars, {_formatBytes(activeContextBytes)}",
            "contextRecent": f"{int(recentSize.get('chars', 0))} chars, {_formatBytes(int(recentSize.get('bytes', 0)))}",
            "contextSummary": f"{int(summarySize.get('chars', 0))} chars, {_formatBytes(int(summarySize.get('bytes', 0)))}",
            "contextLongTerm": f"{int(longTermSize.get('chars', 0))} chars, {_formatBytes(int(longTermSize.get('bytes', 0)))}",
        }
        ret = renderIndexPage(in_stats=stats)
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
    def runInternal(in_request: Request, in_payload: dict[str, str]) -> dict[str, str]:
        if _isWebAuthorized(in_request=in_request) is False:
            return RedirectResponse(url="/login", status_code=303)
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
    def getInternalLogs(in_request: Request, limit: int = 100) -> dict[str, object]:
        if _isWebAuthorized(in_request=in_request) is False:
            return RedirectResponse(url="/login", status_code=303)
        logItems = getLogsUseCase.execute(in_limit=limit)
        retLogs = {"count": len(logItems), "items": logItems}
        return retLogs

    @appInstance.get("/internal/runs")
    def getInternalRuns(
        in_request: Request, limit: int = 50, offset: int = 0
    ) -> dict[str, object]:
        if _isWebAuthorized(in_request=in_request) is False:
            return RedirectResponse(url="/login", status_code=303)
        runItems = getRunListUseCase.execute(in_limit=limit, in_offset=offset)
        retRuns = {"count": len(runItems), "items": runItems}
        return retRuns

    @appInstance.get("/internal/runs/{runId}")
    def getInternalRunDetails(runId: str, in_request: Request) -> dict[str, object]:
        if _isWebAuthorized(in_request=in_request) is False:
            return RedirectResponse(url="/login", status_code=303)
        runItem = getRunDetailsUseCase.execute(in_runId=runId)
        if runItem is None:
            raise HTTPException(status_code=404, detail="Run is not found")
        retRun = {"item": runItem}
        return retRun

    @appInstance.get("/internal/runs/{runId}/steps")
    def getInternalRunSteps(runId: str, in_request: Request) -> dict[str, object]:
        if _isWebAuthorized(in_request=in_request) is False:
            return RedirectResponse(url="/login", status_code=303)
        runItem = getRunDetailsUseCase.execute(in_runId=runId)
        if runItem is None:
            raise HTTPException(status_code=404, detail="Run is not found")
        stepItems = runItem.get("stepTraces", [])
        if not isinstance(stepItems, list):
            stepItems = []
        retSteps = {"runId": runId, "count": len(stepItems), "items": stepItems}
        return retSteps

    @appInstance.get("/internal/git/status")
    def getInternalGitStatus(in_request: Request, limit: int = 200) -> dict[str, object]:
        if _isWebAuthorized(in_request=in_request) is False:
            return RedirectResponse(url="/login", status_code=303)
        retStatus = getGitStatusUseCase.execute(in_limit=limit)
        return retStatus

    @appInstance.get("/internal/git/diff")
    def getInternalGitDiff(
        in_request: Request,
        offset: int = 0,
        limit: int = 5,
        filePath: str = "",
        maxCharsPerFile: int = 30000,
    ) -> dict[str, object]:
        if _isWebAuthorized(in_request=in_request) is False:
            return RedirectResponse(url="/login", status_code=303)
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

    @appInstance.get("/tools", response_class=HTMLResponse)
    def getToolsPage(in_request: Request):
        if _isWebAuthorized(in_request=in_request) is False:
            return RedirectResponse(url="/login", status_code=303)
        toolItems = []
        for toolDef in toolRegistry.listTools():
            toolItems.append(
                {
                    "name": toolDef.name,
                    "description": toolDef.description,
                    "argsSchema": toolDef.argsModel.model_json_schema(),
                }
            )
        ret = renderToolsPage(in_toolItems=toolItems)
        return ret

    @appInstance.get("/skills", response_class=HTMLResponse)
    def getSkillsPage(in_request: Request):
        if _isWebAuthorized(in_request=in_request) is False:
            return RedirectResponse(url="/login", status_code=303)
        skillItems = [
            {"skillId": item.skillId, "title": item.title}
            for item in skillStore.loadAllSkills()
        ]
        ret = renderSkillsPage(
            in_skillItems=skillItems,
            in_adminWritesEnabled=settings.security.adminWritesEnabled,
        )
        return ret

    @appInstance.get("/skills/{skillId}", response_class=HTMLResponse)
    def getSkillEditPage(skillId: str, in_request: Request):
        if _isWebAuthorized(in_request=in_request) is False:
            return RedirectResponse(url="/login", status_code=303)
        # Read directly from disk to make edits immediately visible.
        skillPath = Path(settings.skills.skillsDirPath) / f"{skillId}.md"
        if skillPath.exists() is False:
            raise HTTPException(status_code=404, detail="Skill is not found")
        contentText = skillPath.read_text(encoding="utf-8")
        titleValue = skillId
        for lineText in contentText.splitlines():
            if lineText.startswith("# "):
                titleValue = lineText[2:].strip()
                break
        ret = renderSkillEditPage(
            in_skillId=skillId,
            in_title=titleValue,
            in_contentText=contentText,
            in_errorText="",
            in_adminWritesEnabled=settings.security.adminWritesEnabled,
        )
        return ret

    @appInstance.post("/skills/{skillId}", response_class=HTMLResponse)
    def postSkillEditPage(skillId: str, in_request: Request, content: str = Form(...)):
        if _isWebAuthorized(in_request=in_request) is False:
            return RedirectResponse(url="/login", status_code=303)
        _ensureWritesEnabledOr403()
        skillPath = Path(settings.skills.skillsDirPath) / f"{skillId}.md"
        if skillPath.exists() is False:
            raise HTTPException(status_code=404, detail="Skill is not found")
        _atomicWriteTextFile(in_path=skillPath, in_text=content)
        titleValue = skillId
        for lineText in content.splitlines():
            if lineText.startswith("# "):
                titleValue = lineText[2:].strip()
                break
        ret = renderSkillEditPage(
            in_skillId=skillId,
            in_title=titleValue,
            in_contentText=content,
            in_errorText="Сохранено.",
            in_adminWritesEnabled=settings.security.adminWritesEnabled,
        )
        return ret

    @appInstance.get("/config/tools", response_class=HTMLResponse)
    def getToolsConfigPage(in_request: Request):
        if _isWebAuthorized(in_request=in_request) is False:
            return RedirectResponse(url="/login", status_code=303)
        toolsText = _loadToolsYamlTextOrEmpty()
        ret = renderToolsConfigEditPage(
            in_toolsYamlText=toolsText,
            in_errorText="",
            in_adminWritesEnabled=settings.security.adminWritesEnabled,
        )
        return ret

    @appInstance.post("/config/tools", response_class=HTMLResponse)
    def postToolsConfigPage(in_request: Request, content: str = Form(...)):
        if _isWebAuthorized(in_request=in_request) is False:
            return RedirectResponse(url="/login", status_code=303)
        _ensureWritesEnabledOr403()
        errorText = ""
        try:
            _validateToolsYamlOrRaise(in_yamlText=content)
            toolsPath = _resolveToolsConfigPath()
            _atomicWriteTextFile(in_path=toolsPath, in_text=content)
        except Exception as in_exc:
            errorText = str(in_exc)
        ret = renderToolsConfigEditPage(
            in_toolsYamlText=content,
            in_errorText=errorText or "Сохранено.",
            in_adminWritesEnabled=settings.security.adminWritesEnabled,
        )
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
