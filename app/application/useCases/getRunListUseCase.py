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

    def execute(self, in_limit: int, in_offset: int = 0) -> list[dict[str, Any]]:
        ret = self._runRepository.listRuns(
            in_limit=in_limit,
            in_offset=in_offset,
            in_session_id=self._allowedSessionId,
        )
        return ret
