from typing import Any

from app.common.runSessionScope import sessionIdMatchesTenantPrincipal
from app.observability.stores.jsonRunRepository import JsonRunRepository


class GetRunDetailsUseCase:
    def __init__(
        self,
        in_runRepository: JsonRunRepository,
        in_allowedSessionId: str | None = None,
    ) -> None:
        self._runRepository = in_runRepository
        self._allowedSessionId = in_allowedSessionId

    def execute(
        self,
        in_runId: str,
        in_runs_scope: str = "admin",
    ) -> dict[str, Any] | None:
        ret: dict[str, Any] | None
        item = self._runRepository.getRunById(in_runId=in_runId)
        if item is None:
            ret = None
            return ret
        normalized_scope = str(in_runs_scope or "admin").strip().lower()
        allowedText = self._allowedSessionId
        if normalized_scope == "all":
            allowedText = None
        if allowedText is not None:
            record_session = str(item.get("sessionId", "") or "")
            if sessionIdMatchesTenantPrincipal(
                in_recordSessionId=record_session,
                in_tenantPrincipalId=str(allowedText),
            ) is False:
                ret = None
                return ret
        ret = item
        return ret
