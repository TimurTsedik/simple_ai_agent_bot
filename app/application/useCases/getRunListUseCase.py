from typing import Any

from app.observability.stores.jsonRunRepository import JsonRunRepository


class GetRunListUseCase:
    def __init__(
        self,
        in_runRepository: JsonRunRepository,
        in_allowedSessionId: str | None = None,
    ) -> None:
        self._runRepository = in_runRepository
        self._allowedSessionId = in_allowedSessionId

    def execute(
        self,
        in_limit: int,
        in_offset: int = 0,
        in_runs_scope: str = "admin",
    ) -> list[dict[str, Any]]:
        normalized_scope = str(in_runs_scope or "admin").strip().lower()
        session_filter: str | None
        if normalized_scope == "all":
            session_filter = None
        else:
            session_filter = self._allowedSessionId
        ret = self._runRepository.listRuns(
            in_limit=in_limit,
            in_offset=in_offset,
            in_session_id=session_filter,
        )
        return ret
