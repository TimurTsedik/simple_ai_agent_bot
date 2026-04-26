from typing import Any

from app.observability.stores.jsonRunRepository import JsonRunRepository


class GetRunListUseCase:
    def __init__(self, in_runRepository: JsonRunRepository) -> None:
        self._runRepository = in_runRepository

    def execute(self, in_limit: int, in_offset: int = 0) -> list[dict[str, Any]]:
        ret = self._runRepository.listRuns(
            in_limit=in_limit,
            in_offset=in_offset,
        )
        return ret
