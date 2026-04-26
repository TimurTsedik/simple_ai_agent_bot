from typing import Any

from app.observability.stores.jsonRunRepository import JsonRunRepository


class GetRunDetailsUseCase:
    def __init__(self, in_runRepository: JsonRunRepository) -> None:
        self._runRepository = in_runRepository

    def execute(self, in_runId: str) -> dict[str, Any] | None:
        ret = self._runRepository.getRunById(in_runId=in_runId)
        return ret
