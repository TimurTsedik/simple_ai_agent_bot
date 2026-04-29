import os
from pathlib import Path

import yaml
from fastapi import FastAPI
from fastapi import Form
from fastapi import HTTPException
from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.responses import RedirectResponse
from pydantic import ValidationError

from app.bootstrap.container import ApplicationContainer
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
from app.presentation.web.adminPages import renderToolsConfigEditPage
from app.presentation.web.adminPages import renderToolsPage
from app.security.webSessionAuth import createSessionCookieValue
from app.security.webSessionAuth import hashAdminToken
from app.security.webSessionAuth import parseSessionCookieValue


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
        ret = (
            isinstance(tokenHash, str) and tokenHash in in_app.state.adminTokenHashes
        )
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

    @in_app.get("/", response_class=HTMLResponse)
    def getIndex(in_request: Request):
        if isWebAuthorized(in_request=in_request) is False:
            return RedirectResponse(url="/login", status_code=303)
        stats = dashboardSnapshotService.getDashboardStatsSnapshot()
        ret = renderIndexPage(in_stats=stats)
        return ret

    @in_app.get("/login", response_class=HTMLResponse)
    def getLoginPage() -> str:
        ret = renderLoginPage()
        return ret

    @in_app.post("/login")
    def postLogin(adminToken: str = Form(...)):
        tokenHash = hashAdminToken(
            in_rawToken=adminToken,
            in_secret=settings.sessionCookieSecret,
        )
        if tokenHash not in in_app.state.adminTokenHashes:
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
        ret = renderLogsPage(in_logItems=logItems)
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
        ret = renderRunsPage(in_runItems=runItems)
        return ret

    @in_app.get("/runs/{runId}", response_class=HTMLResponse)
    def getRunDetailsPage(runId: str, in_request: Request):
        if isWebAuthorized(in_request=in_request) is False:
            return RedirectResponse(url="/login", status_code=303)
        runItem = getRunDetailsUseCase.execute(in_runId=runId)
        if runItem is None:
            raise HTTPException(status_code=404, detail="Run is not found")
        ret = renderRunDetailsPage(in_runId=runId, in_runItem=runItem)
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
