import html
import os
from pathlib import Path
from threading import Lock
from time import time

import yaml
from fastapi import FastAPI
from fastapi import Form
from fastapi import HTTPException
from fastapi import Query
from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.responses import RedirectResponse
from fastapi.responses import FileResponse
from pydantic import ValidationError

from app.bootstrap.container import ApplicationContainer
from app.common.webDisplayTime import formatUnixEpochSecondsForWeb
from app.common.webDisplayTime import resolveDisplayZone
from app.config.settingsModels import EmailReaderToolSettings, TelegramNewsDigestToolSettings
from app.presentation.web.adminPages import renderGitDiffPage
from app.presentation.web.adminPages import renderGitStatusPage
from app.presentation.web.adminPages import renderIndexPage
from app.presentation.web.adminPages import renderLoginPage
from app.presentation.web.adminPages import renderLogsPage
from app.presentation.web.adminPages import renderRunDetailsPage
from app.presentation.web.adminPages import renderRunsPage
from app.presentation.web.adminPages import renderRunStepsPage
from app.presentation.web.adminPages import renderSkillEditPage
from app.presentation.web.adminPages import renderSkillsPage
from app.common.memoryPrincipal import formatTelegramUserMemoryPrincipal
from app.presentation.web.adminPages import renderLongTermMemoryPage
from app.presentation.web.adminPages import renderSchedulesConfigViewPage
from app.presentation.web.adminPages import renderToolsConfigEditPage
from app.presentation.web.adminPages import renderTelegramUsersPage
from app.presentation.web.adminPages import renderToolsPage
from app.security.webSessionAuth import createSessionCookieValue
from app.security.webSessionAuth import hashAdminToken
from app.security.webSessionAuth import parseSessionCookieValue
from app.tools.implementations.readMemoryFileTool import ReadMemoryFileTool


def registerAdminWebRoutes(
    in_app: FastAPI,
    in_container: ApplicationContainer,
) -> None:
    settings = in_container.settings
    toolRegistry = in_container.toolRegistry
    skillStore = in_container.skillStore
    getLogsUseCase = in_container.getLogsUseCase
    getRunListUseCase = in_container.getRunListUseCase
    getRunDetailsUseCase = in_container.getRunDetailsUseCase
    getGitStatusUseCase = in_container.getGitStatusUseCase
    getGitDiffUseCase = in_container.getGitDiffUseCase
    dashboardSnapshotService = in_container.dashboardSnapshotService
    readMemoryFileTool = ReadMemoryFileTool(
        in_memoryRootPath=settings.memory.memoryRootPath,
        in_allowedReadOnlyPaths=settings.security.allowedReadOnlyPaths,
    )

    if hasattr(in_app.state, "adminLoginBruteforceState") is False:
        in_app.state.adminLoginBruteforceState = {}
    if hasattr(in_app.state, "adminLoginBruteforceLock") is False:
        in_app.state.adminLoginBruteforceLock = Lock()
    if hasattr(in_app.state, "adminLoginNowUnixTsProvider") is False:
        in_app.state.adminLoginNowUnixTsProvider = time

    def resolveClientIpText(in_request: Request) -> str:
        ret: str
        if settings.security.trustProxyHeaders is True:
            proxyIpText = (
                in_request.client.host.strip()
                if in_request.client is not None and isinstance(in_request.client.host, str)
                else ""
            )
            trustedProxyIps = set(str(x).strip() for x in settings.security.trustedProxyIps)
            if proxyIpText in trustedProxyIps or proxyIpText in {"127.0.0.1", "::1"}:
                forwarded = str(in_request.headers.get("x-forwarded-for", "") or "").strip()
                if forwarded != "":
                    ret = forwarded.split(",", 1)[0].strip()
                    return ret
        client = in_request.client
        if client is not None and isinstance(client.host, str) and client.host.strip() != "":
            ret = client.host.strip()
            return ret
        ret = "unknown"
        return ret

    def checkLoginLockedOrNone(in_clientIpText: str) -> str | None:
        ret: str | None
        nowUnixTs = float(in_app.state.adminLoginNowUnixTsProvider())
        with in_app.state.adminLoginBruteforceLock:
            state = in_app.state.adminLoginBruteforceState.get(in_clientIpText) or {}
            lockedUntil = float(state.get("lockedUntil", 0.0) or 0.0)
            if lockedUntil > nowUnixTs:
                secondsLeft = int(max(1.0, lockedUntil - nowUnixTs))
                ret = f"Слишком много попыток. Подожди {secondsLeft} сек."
                return ret
        ret = None
        return ret

    def recordLoginFailure(in_clientIpText: str) -> None:
        nowUnixTs = float(in_app.state.adminLoginNowUnixTsProvider())
        with in_app.state.adminLoginBruteforceLock:
            state = in_app.state.adminLoginBruteforceState.get(in_clientIpText)
            if isinstance(state, dict) is False:
                state = {}
            failures = state.get("failures")
            if isinstance(failures, list) is False:
                failures = []
            failures = [float(x) for x in failures if isinstance(x, (int, float)) and nowUnixTs - float(x) <= 900.0]
            failures.append(nowUnixTs)
            lockedUntil = float(state.get("lockedUntil", 0.0) or 0.0)
            if len(failures) >= 3:
                lockedUntil = max(lockedUntil, nowUnixTs + 900.0)
            state["failures"] = failures
            state["lockedUntil"] = lockedUntil
            in_app.state.adminLoginBruteforceState[in_clientIpText] = state

    def clearLoginFailures(in_clientIpText: str) -> None:
        with in_app.state.adminLoginBruteforceLock:
            if in_clientIpText in in_app.state.adminLoginBruteforceState:
                del in_app.state.adminLoginBruteforceState[in_clientIpText]

    def isWebAuthorized(in_request: Request) -> bool:
        ret: bool
        cookieName = in_app.state.webSessionCookieName
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
        isTokenOk = (
            isinstance(tokenHash, str) and tokenHash in in_app.state.adminTokenHashes
        )
        if isTokenOk is not True:
            ret = False
            return ret
        if settings.security.bindSessionToIp is True:
            cookieIpText = payload.get("ip")
            currentIpText = resolveClientIpText(in_request=in_request)
            ret = isinstance(cookieIpText, str) and cookieIpText == currentIpText
            return ret
        ret = True
        return ret

    def ensureWritesEnabledOr403() -> None:
        if settings.security.adminWritesEnabled is not True:
            raise HTTPException(status_code=403, detail="Admin writes are disabled")

    def resolveToolsConfigPath() -> Path:
        ret: Path
        toolsPath = Path(settings.tools.toolsConfigPath)
        if toolsPath.is_absolute() is False:
            ret = toolsPath.resolve()
        else:
            ret = toolsPath
        return ret

    def atomicWriteTextFile(in_path: Path, in_text: str) -> None:
        in_path.parent.mkdir(parents=True, exist_ok=True)
        tmpPath = in_path.with_suffix(in_path.suffix + ".tmp")
        tmpPath.write_text(in_text, encoding="utf-8")
        os.replace(tmpPath, in_path)

    def loadToolsYamlTextOrEmpty() -> str:
        ret: str
        toolsPath = resolveToolsConfigPath()
        if toolsPath.exists():
            ret = toolsPath.read_text(encoding="utf-8")
        else:
            ret = ""
        return ret

    def resolveSchedulesConfigPath() -> Path:
        ret: Path
        schedulesPath = Path(settings.scheduler.schedulesConfigPath)
        if schedulesPath.is_absolute() is False:
            ret = schedulesPath.resolve()
        else:
            ret = schedulesPath
        return ret

    def loadSchedulesYamlTextOrEmpty() -> tuple[str, str]:
        ret: tuple[str, str]
        schedulesPath = resolveSchedulesConfigPath()
        if schedulesPath.exists():
            yamlText = schedulesPath.read_text(encoding="utf-8")
        else:
            yamlText = ""
        ret = (yamlText, str(schedulesPath))
        return ret

    def validateToolsYamlOrRaise(in_yamlText: str) -> None:
        loaded = yaml.safe_load(in_yamlText) or {}
        if not isinstance(loaded, dict):
            raise ValidationError.from_exception_data("tools_yaml", [])
        _ = TelegramNewsDigestToolSettings.model_validate(
            loaded.get("telegramNewsDigest", {}) if isinstance(loaded, dict) else {}
        )
        _ = EmailReaderToolSettings.model_validate(
            loaded.get("emailReader", {}) if isinstance(loaded, dict) else {}
        )

    def composeTelegramUsersHtml(
        in_notice_ok_text: str,
        in_notice_error_text: str,
    ) -> str:
        registry_store = in_container.telegramUserRegistryStore
        display_zone = resolveDisplayZone(in_timeZoneName=settings.app.displayTimeZone)
        rows_parts: list[str] = []
        for rec in sorted(
            registry_store.listUsers(),
            key=lambda item: int(item.telegramUserId),
        ):
            created_label = formatUnixEpochSecondsForWeb(
                float(rec.createdAtUnixTs),
                display_zone,
            )
            rows_parts.append(
                "<tr>"
                f"<td>{html.escape(str(rec.telegramUserId))}</td>"
                f"<td>{html.escape(str(rec.displayName or '') or '—')}</td>"
                f"<td>{html.escape(created_label)}</td>"
                f"<td>{html.escape(str(rec.note or '') or '—')}</td>"
                "</tr>"
            )
        rows_body = "".join(rows_parts)
        registry_path_resolved = str(Path(settings.app.usersRegistryPath).resolve())
        ret = renderTelegramUsersPage(
            in_user_rows_html=rows_body
            or "<tr><td colspan='4' class='muted'>Нет пользователей в реестре</td></tr>",
            in_registry_path_text=registry_path_resolved,
            in_notice_ok_text=in_notice_ok_text,
            in_notice_error_text=in_notice_error_text,
            in_writes_enabled=settings.security.adminWritesEnabled is True,
        )
        return ret

    @in_app.get("/", response_class=HTMLResponse)
    def getIndex(in_request: Request):
        if isWebAuthorized(in_request=in_request) is False:
            return RedirectResponse(url="/login", status_code=303)
        stats = dashboardSnapshotService.getDashboardStatsSnapshot()
        displayZone = resolveDisplayZone(in_timeZoneName=settings.app.displayTimeZone)
        ret = renderIndexPage(in_stats=stats, in_displayZone=displayZone)
        return ret

    @in_app.get("/login", response_class=HTMLResponse)
    def getLoginPage() -> str:
        ret = renderLoginPage()
        return ret

    @in_app.get("/favicon.png")
    def getFaviconPng() -> FileResponse:
        ret: FileResponse
        faviconPath = (Path(__file__).resolve().parents[3] / "favicon.png").resolve()
        ret = FileResponse(
            path=str(faviconPath),
            media_type="image/png",
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )
        return ret

    @in_app.get("/favicon.ico")
    def getFaviconIco() -> FileResponse:
        ret: FileResponse
        faviconPath = (Path(__file__).resolve().parents[3] / "favicon.ico").resolve()
        ret = FileResponse(
            path=str(faviconPath),
            media_type="image/x-icon",
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )
        return ret

    @in_app.post("/login")
    def postLogin(in_request: Request, adminToken: str = Form(...)):
        clientIpText = resolveClientIpText(in_request=in_request)
        lockErrorText = checkLoginLockedOrNone(in_clientIpText=clientIpText)
        if lockErrorText is not None:
            retLocked: HTMLResponse = HTMLResponse(
                content=renderLoginPage(in_errorText=lockErrorText),
                status_code=429,
            )
            return retLocked
        tokenHash = hashAdminToken(
            in_rawToken=adminToken,
            in_secret=settings.sessionCookieSecret,
        )
        if tokenHash not in in_app.state.adminTokenHashes:
            recordLoginFailure(in_clientIpText=clientIpText)
            retError: HTMLResponse = HTMLResponse(
                content=renderLoginPage(in_errorText="Неверный токен."),
                status_code=401,
            )
            return retError
        clearLoginFailures(in_clientIpText=clientIpText)
        response = RedirectResponse(url="/", status_code=303)
        cookieValue = createSessionCookieValue(
            in_tokenHash=tokenHash,
            in_secret=settings.sessionCookieSecret,
            in_ttlSeconds=settings.security.webSessionCookieTtlSeconds,
            in_ipText=clientIpText if settings.security.bindSessionToIp is True else None,
        )
        response.set_cookie(
            key=in_app.state.webSessionCookieName,
            value=cookieValue,
            max_age=settings.security.webSessionCookieTtlSeconds,
            httponly=True,
            samesite="lax",
        )
        return response

    @in_app.post("/logout")
    def postLogout() -> RedirectResponse:
        response = RedirectResponse(url="/login", status_code=303)
        response.delete_cookie(key=in_app.state.webSessionCookieName)
        return response

    @in_app.get("/health")
    def getHealth() -> dict[str, str]:
        retHealth = {"status": "ok", "service": settings.app.appName}
        return retHealth

    @in_app.get("/logs", response_class=HTMLResponse)
    def getLogsPage(in_request: Request, limit: int = 100):
        if isWebAuthorized(in_request=in_request) is False:
            return RedirectResponse(url="/login", status_code=303)
        logItems = getLogsUseCase.execute(in_limit=limit)
        displayZone = resolveDisplayZone(in_timeZoneName=settings.app.displayTimeZone)
        ret = renderLogsPage(in_logItems=logItems, in_displayZone=displayZone)
        return ret

    @in_app.get("/tools", response_class=HTMLResponse)
    def getToolsPage(in_request: Request):
        if isWebAuthorized(in_request=in_request) is False:
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

    @in_app.get("/skills", response_class=HTMLResponse)
    def getSkillsPage(in_request: Request):
        if isWebAuthorized(in_request=in_request) is False:
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

    @in_app.get("/memory/long-term", response_class=HTMLResponse)
    def getLongTermMemoryPage(in_request: Request, maxChars: int = 50000):
        if isWebAuthorized(in_request=in_request) is False:
            return RedirectResponse(url="/login", status_code=303)
        memoryRoot = Path(settings.memory.memoryRootPath).resolve()
        principalId = formatTelegramUserMemoryPrincipal(
            in_telegramUserId=settings.adminTelegramUserId,
        )
        sanitizedPrincipal = principalId.replace(":", "_")
        longTermPath = (
            memoryRoot / "sessions" / sanitizedPrincipal / settings.memory.longTermFileName
        ).resolve()
        result = readMemoryFileTool.execute(
            in_args={"relativePath": str(longTermPath), "maxChars": int(maxChars)},
            in_memoryPrincipalId=principalId,
        )
        contentText = str(result.get("content", "") or "")
        pathText = str(result.get("path", "") or "")
        truncated = len(contentText) >= int(maxChars)
        ret = renderLongTermMemoryPage(
            in_path=pathText,
            in_contentText=contentText,
            in_maxChars=int(maxChars),
            in_truncated=truncated,
        )
        return ret

    @in_app.get("/skills/{skillId}", response_class=HTMLResponse)
    def getSkillEditPage(skillId: str, in_request: Request):
        if isWebAuthorized(in_request=in_request) is False:
            return RedirectResponse(url="/login", status_code=303)
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

    @in_app.post("/skills/{skillId}", response_class=HTMLResponse)
    def postSkillEditPage(skillId: str, in_request: Request, content: str = Form(...)):
        if isWebAuthorized(in_request=in_request) is False:
            return RedirectResponse(url="/login", status_code=303)
        ensureWritesEnabledOr403()
        skillPath = Path(settings.skills.skillsDirPath) / f"{skillId}.md"
        if skillPath.exists() is False:
            raise HTTPException(status_code=404, detail="Skill is not found")
        atomicWriteTextFile(in_path=skillPath, in_text=content)
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

    @in_app.get("/config/tools", response_class=HTMLResponse)
    def getToolsConfigPage(in_request: Request):
        if isWebAuthorized(in_request=in_request) is False:
            return RedirectResponse(url="/login", status_code=303)
        toolsText = loadToolsYamlTextOrEmpty()
        ret = renderToolsConfigEditPage(
            in_toolsYamlText=toolsText,
            in_errorText="",
            in_adminWritesEnabled=settings.security.adminWritesEnabled,
        )
        return ret

    @in_app.get("/config/schedules", response_class=HTMLResponse)
    def getSchedulesConfigPage(in_request: Request):
        if isWebAuthorized(in_request=in_request) is False:
            return RedirectResponse(url="/login", status_code=303)
        schedulesText, schedulesPathText = loadSchedulesYamlTextOrEmpty()
        ret = renderSchedulesConfigViewPage(
            in_schedulesYamlText=schedulesText,
            in_schedulesPath=schedulesPathText,
        )
        return ret

    @in_app.get("/users", response_class=HTMLResponse)
    def getTelegramUsersAdminPage(in_request: Request):
        if isWebAuthorized(in_request=in_request) is False:
            return RedirectResponse(url="/login", status_code=303)
        ret = composeTelegramUsersHtml("", "")
        return ret

    @in_app.post("/users/create", response_class=HTMLResponse)
    def postTelegramUsersCreate(
        in_request: Request,
        telegram_user_id: str = Form(...),
        display_name: str = Form(""),
        note: str = Form(""),
    ):
        if isWebAuthorized(in_request=in_request) is False:
            return RedirectResponse(url="/login", status_code=303)
        ensureWritesEnabledOr403()
        result = None
        notice_error_pre = ""
        try:
            telegram_id_parsed = int(str(telegram_user_id).strip())
        except ValueError:
            telegram_id_parsed = -1
            notice_error_pre = "Некорректный Telegram ID (ожидается целое число)."
        if notice_error_pre == "":
            result = in_container.createTelegramUserUseCase.execute(
                in_telegramUserId=int(telegram_id_parsed),
                in_displayName=display_name,
                in_note=note,
            )
        notice_ok = ""
        notice_error = notice_error_pre
        if result is not None:
            if result.ok is True:
                notice_ok = result.messageText
            else:
                notice_error = result.messageText
        ret = composeTelegramUsersHtml(notice_ok, notice_error)
        return ret

    @in_app.post("/config/tools", response_class=HTMLResponse)
    def postToolsConfigPage(in_request: Request, content: str = Form(...)):
        if isWebAuthorized(in_request=in_request) is False:
            return RedirectResponse(url="/login", status_code=303)
        ensureWritesEnabledOr403()
        errorText = ""
        try:
            validateToolsYamlOrRaise(in_yamlText=content)
            toolsPath = resolveToolsConfigPath()
            atomicWriteTextFile(in_path=toolsPath, in_text=content)
        except (ValidationError, yaml.YAMLError, OSError) as in_exc:
            errorText = str(in_exc)
        ret = renderToolsConfigEditPage(
            in_toolsYamlText=content,
            in_errorText=errorText or "Сохранено.",
            in_adminWritesEnabled=settings.security.adminWritesEnabled,
        )
        return ret

    @in_app.get("/runs", response_class=HTMLResponse)
    def getRunsPage(
        in_request: Request, limit: int = 50, offset: int = 0
    ):
        if isWebAuthorized(in_request=in_request) is False:
            return RedirectResponse(url="/login", status_code=303)
        runItems = getRunListUseCase.execute(in_limit=limit, in_offset=offset)
        displayZone = resolveDisplayZone(in_timeZoneName=settings.app.displayTimeZone)
        ret = renderRunsPage(in_runItems=runItems, in_displayZone=displayZone)
        return ret

    @in_app.get("/runs/{runId}", response_class=HTMLResponse)
    def getRunDetailsPage(
        runId: str, in_request: Request, raw: int = Query(default=0)
    ):
        if isWebAuthorized(in_request=in_request) is False:
            return RedirectResponse(url="/login", status_code=303)
        runItem = getRunDetailsUseCase.execute(in_runId=runId)
        if runItem is None:
            raise HTTPException(status_code=404, detail="Run is not found")
        displayZone = resolveDisplayZone(in_timeZoneName=settings.app.displayTimeZone)
        ret = renderRunDetailsPage(
            in_runId=runId,
            in_runItem=runItem,
            in_displayZone=displayZone,
            in_rawView=(raw != 0),
        )
        return ret

    @in_app.get("/runs/{runId}/steps", response_class=HTMLResponse)
    def getRunStepsPage(runId: str, in_request: Request):
        if isWebAuthorized(in_request=in_request) is False:
            return RedirectResponse(url="/login", status_code=303)
        runItem = getRunDetailsUseCase.execute(in_runId=runId)
        if runItem is None:
            raise HTTPException(status_code=404, detail="Run is not found")
        stepItems = runItem.get("stepTraces", [])
        if not isinstance(stepItems, list):
            stepItems = []
        ret = renderRunStepsPage(in_runId=runId, in_stepItems=stepItems)
        return ret

    @in_app.get("/git/status", response_class=HTMLResponse)
    def getGitStatusPage(in_request: Request, limit: int = 200):
        if isWebAuthorized(in_request=in_request) is False:
            return RedirectResponse(url="/login", status_code=303)
        statusResult = getGitStatusUseCase.execute(in_limit=limit)
        ret = renderGitStatusPage(in_statusResult=statusResult)
        return ret

    @in_app.get("/git/diff", response_class=HTMLResponse)
    def getGitDiffPage(
        in_request: Request,
        offset: int = 0,
        limit: int = 5,
        filePath: str = "",
        maxCharsPerFile: int = 30000,
    ):
        if isWebAuthorized(in_request=in_request) is False:
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
