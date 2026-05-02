from app.application.useCases.getRunDetailsUseCase import GetRunDetailsUseCase
from app.application.useCases.getRunListUseCase import GetRunListUseCase


class FakeRunRepository:
    def __init__(self) -> None:
        self._items = [
            {"runId": "r2", "sessionId": "telegram:2"},
            {"runId": "r1", "sessionId": "telegram:1"},
        ]

    def listRuns(
        self,
        in_limit: int,
        in_offset: int = 0,
        in_session_id: str | None = None,
    ):  # noqa: ANN201
        items = self._items
        if in_session_id is not None:
            items = [item for item in self._items if item.get("sessionId") == in_session_id]
        ret = items[in_offset : in_offset + in_limit]
        return ret

    def getRunById(self, in_runId: str):  # noqa: ANN201
        ret = None
        for item in self._items:
            if item["runId"] == in_runId:
                ret = item
                break
        return ret


def testGetRunListUseCaseReturnsItems() -> None:
    repository = FakeRunRepository()
    useCase = GetRunListUseCase(in_runRepository=repository)  # type: ignore[arg-type]

    result = useCase.execute(in_limit=1, in_offset=0)

    assert len(result) == 1
    assert result[0]["runId"] == "r2"


def testGetRunDetailsUseCaseReturnsSingleItem() -> None:
    repository = FakeRunRepository()
    useCase = GetRunDetailsUseCase(in_runRepository=repository)  # type: ignore[arg-type]

    result = useCase.execute(in_runId="r1")

    assert result is not None
    assert result["sessionId"] == "telegram:1"
