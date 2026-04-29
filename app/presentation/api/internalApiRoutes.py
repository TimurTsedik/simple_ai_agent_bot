from fastapi import FastAPI
from fastapi import HTTPException
from fastapi import Request

from app.bootstrap.container import ApplicationContainer
from app.common.structuredLogger import writeJsonlEvent
from app.security.webSessionAuth import parseSessionCookieValue


def registerInternalApiRoutes(
    in_app: FastAPI,
    in_container: ApplicationContainer,
) -> None:
    settings = in_container.settings

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

    def ensureInternalApiAuthorizedOrRaise(in_request: Request) -> None:
        if isWebAuthorized(in_request=in_request) is False:
            raise HTTPException(status_code=401, detail="Unauthorized")

    @in_app.post("/internal/run")
    def runInternal(in_request: Request, in_payload: dict[str, str]) -> dict[str, str]:
        ensureInternalApiAuthorizedOrRaise(in_request=in_request)
        sessionId = in_payload.get("sessionId", "telegram:debug")
        inputMessage = in_payload.get("message", "")
        runResult = in_container.runAgentUseCase.execute(
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

    @in_app.get("/internal/logs")
    def getInternalLogs(in_request: Request, limit: int = 100) -> dict[str, object]:
        ensureInternalApiAuthorizedOrRaise(in_request=in_request)
        logItems = in_container.getLogsUseCase.execute(in_limit=limit)
        retLogs = {"count": len(logItems), "items": logItems}
        return retLogs

    @in_app.get("/internal/runs")
    def getInternalRuns(
        in_request: Request, limit: int = 50, offset: int = 0
    ) -> dict[str, object]:
        ensureInternalApiAuthorizedOrRaise(in_request=in_request)
        runItems = in_container.getRunListUseCase.execute(in_limit=limit, in_offset=offset)
        retRuns = {"count": len(runItems), "items": runItems}
        return retRuns

    @in_app.get("/internal/runs/{runId}")
    def getInternalRunDetails(runId: str, in_request: Request) -> dict[str, object]:
        ensureInternalApiAuthorizedOrRaise(in_request=in_request)
        runItem = in_container.getRunDetailsUseCase.execute(in_runId=runId)
        if runItem is None:
            raise HTTPException(status_code=404, detail="Run is not found")
        retRun = {"item": runItem}
        return retRun

    @in_app.get("/internal/runs/{runId}/steps")
    def getInternalRunSteps(runId: str, in_request: Request) -> dict[str, object]:
        ensureInternalApiAuthorizedOrRaise(in_request=in_request)
        runItem = in_container.getRunDetailsUseCase.execute(in_runId=runId)
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
