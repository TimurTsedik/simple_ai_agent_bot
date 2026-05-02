from typing import Any

from app.observability.stores.jsonRunRepository import (
    JsonRunRepository,
    sessionsEquivalentForAdminRunsView,
)


class GetRunDetailsUseCase:
    def __init__(
        self,
        in_runRepository: JsonRunRepository,
        in_allowedSessionId: str | None = None,
    ) -> None:
        self._runRepository = in_runRepository
        self._allowedSessionId = in_allowedSessionId

    def execute(self, in_runId: str) -> dict[str, Any] | None:
        ret: dict[str, Any] | None
        item = self._runRepository.getRunById(in_runId=in_runId)
        if item is None:
            ret = None
            return ret
        allowedText = self._allowedSessionId
        if allowedText is not None:
            record_session = str(item.get("sessionId", "") or "")
            if sessionsEquivalentForAdminRunsView(
                in_recordSessionId=record_session,
                in_allowedSessionId=str(allowedText),
            ) is False:
                ret = None
                return ret
        ret = item
        return ret
