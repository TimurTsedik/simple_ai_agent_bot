from pathlib import Path
from fastapi import FastAPI
from fastapi import HTTPException
from fastapi import Query
from fastapi import Request

from app.bootstrap.container import ApplicationContainer
from app.common.memoryPrincipal import formatTelegramUserMemoryPrincipal
from app.common.structuredLogger import writeJsonlEvent
from app.security.webSessionAuth import parseSessionCookieValue
from app.tools.implementations.readMemoryFileTool import ReadMemoryFileTool


def registerInternalApiRoutes(
    in_app: FastAPI,
    in_container: ApplicationContainer,
) -> None:
    settings = in_container.settings
    readMemoryFileTool = ReadMemoryFileTool(
        in_memoryRootPath=settings.memory.memoryRootPath,
        in_allowedReadOnlyPaths=settings.security.allowedReadOnlyPaths,
    )

    def normalizeInternalRunsScope(in_rawScope: str) -> str:
        ret = "all" if str(in_rawScope or "").strip().lower() == "all" else "admin"
        return ret

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

    def ensureInternalApiAuthorizedOrRaise(in_request: Request) -> None:
        if isWebAuthorized(in_request=in_request) is False:
            raise HTTPException(status_code=401, detail="Unauthorized")

    @in_app.post("/internal/run")
    def runInternal(in_request: Request, in_payload: dict[str, str]) -> dict[str, str]:
        ensureInternalApiAuthorizedOrRaise(in_request=in_request)
        defaultPrincipal = formatTelegramUserMemoryPrincipal(
            in_telegramUserId=settings.adminTelegramUserId,
        )
        sessionId = in_payload.get("sessionId") or defaultPrincipal
        inputMessage = in_payload.get("message", "")
        runResult = in_container.runAgentUseCase.execute(
            in_sessionId=sessionId,
            in_inputMessage=inputMessage,
            in_memoryPrincipalId=sessionId,
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

    @in_app.get("/internal/logs")
    def getInternalLogs(in_request: Request, limit: int = 100) -> dict[str, object]:
        ensureInternalApiAuthorizedOrRaise(in_request=in_request)
        logItems = in_container.getLogsUseCase.execute(in_limit=limit)
        retLogs = {"count": len(logItems), "items": logItems}
        return retLogs

    @in_app.get("/internal/runs")
    def getInternalRuns(
        in_request: Request,
        limit: int = 50,
        offset: int = 0,
        scope: str = Query(default="admin"),
    ) -> dict[str, object]:
        ensureInternalApiAuthorizedOrRaise(in_request=in_request)
        runs_scope = normalizeInternalRunsScope(in_rawScope=scope)
        runItems = in_container.getRunListUseCase.execute(
            in_limit=limit,
            in_offset=offset,
            in_runs_scope=runs_scope,
        )
        retRuns = {"count": len(runItems), "items": runItems}
        return retRuns

    @in_app.get("/internal/runs/{runId}")
    def getInternalRunDetails(
        runId: str,
        in_request: Request,
        scope: str = Query(default="admin"),
    ) -> dict[str, object]:
        ensureInternalApiAuthorizedOrRaise(in_request=in_request)
        runs_scope = normalizeInternalRunsScope(in_rawScope=scope)
        runItem = in_container.getRunDetailsUseCase.execute(
            in_runId=runId,
            in_runs_scope=runs_scope,
        )
        if runItem is None:
            raise HTTPException(status_code=404, detail="Run is not found")
        retRun = {"item": runItem}
        return retRun

    @in_app.get("/internal/runs/{runId}/steps")
    def getInternalRunSteps(
        runId: str,
        in_request: Request,
        scope: str = Query(default="admin"),
    ) -> dict[str, object]:
        ensureInternalApiAuthorizedOrRaise(in_request=in_request)
        runs_scope = normalizeInternalRunsScope(in_rawScope=scope)
        runItem = in_container.getRunDetailsUseCase.execute(
            in_runId=runId,
            in_runs_scope=runs_scope,
        )
        if runItem is None:
            raise HTTPException(status_code=404, detail="Run is not found")
        stepItems = runItem.get("stepTraces", [])
        if not isinstance(stepItems, list):
            stepItems = []
        retSteps = {"runId": runId, "count": len(stepItems), "items": stepItems}
        return retSteps

    @in_app.get("/internal/git/status")
    def getInternalGitStatus(in_request: Request, limit: int = 200) -> dict[str, object]:
        ensureInternalApiAuthorizedOrRaise(in_request=in_request)
        retStatus = in_container.getGitStatusUseCase.execute(in_limit=limit)
        return retStatus

    @in_app.get("/internal/git/diff")
    def getInternalGitDiff(
        in_request: Request,
        offset: int = 0,
        limit: int = 5,
        filePath: str = "",
        maxCharsPerFile: int = 30000,
    ) -> dict[str, object]:
        ensureInternalApiAuthorizedOrRaise(in_request=in_request)
        retDiff = in_container.getGitDiffUseCase.execute(
            in_offset=offset,
            in_limit=limit,
            in_filePath=filePath,
            in_maxCharsPerFile=maxCharsPerFile,
        )
        return retDiff

    @in_app.get("/internal/memory/long-term")
    def getInternalLongTermMemory(
        in_request: Request,
        maxChars: int = 50000,
    ) -> dict[str, object]:
        ensureInternalApiAuthorizedOrRaise(in_request=in_request)
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
        truncated = len(contentText) >= int(maxChars)
        ret = {
            "path": str(result.get("path", "") or ""),
            "maxChars": int(maxChars),
            "truncated": truncated,
            "content": contentText,
        }
        return ret
