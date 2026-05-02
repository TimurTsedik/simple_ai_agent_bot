from app.application.useCases.getRunDetailsUseCase import GetRunDetailsUseCase
from app.application.useCases.getRunListUseCase import GetRunListUseCase
from app.common.runSessionScope import sessionIdMatchesTenantPrincipal


class FakeRunRepository:
    def __init__(self) -> None:
        self._items = [
            {"runId": "r2", "sessionId": "telegramUser:2"},
            {"runId": "r1", "sessionId": "telegramUser:1"},
            {"runId": "r1s", "sessionId": "telegramUser:1:scheduler:email"},
        ]

    def listRuns(
        self,
        in_limit: int,
        in_offset: int = 0,
        in_session_id: str | None = None,
    ):  # noqa: ANN201
        items = self._items
        if in_session_id is not None:
            filt = str(in_session_id)
            items = [
                item
                for item in self._items
                if sessionIdMatchesTenantPrincipal(
                    in_recordSessionId=str(item.get("sessionId", "") or ""),
                    in_tenantPrincipalId=filt,
                )
                is True
            ]
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
    assert result["sessionId"] == "telegramUser:1"


def testGetRunListUseCaseScopeAllListsAllSessions() -> None:
    repository = FakeRunRepository()
    useCase = GetRunListUseCase(
        in_runRepository=repository,  # type: ignore[arg-type]
        in_allowedSessionId="telegramUser:1",
    )
    scoped = useCase.execute(in_limit=10, in_offset=0, in_runs_scope="admin")
    all_runs = useCase.execute(in_limit=10, in_offset=0, in_runs_scope="all")
    assert len(scoped) == 2
    assert {item["runId"] for item in scoped} == {"r1", "r1s"}
    assert len(all_runs) == 3


def testGetRunDetailsUseCaseAllowsSchedulerSessionForAdminTenant() -> None:
    repository = FakeRunRepository()
    useCase = GetRunDetailsUseCase(
        in_runRepository=repository,  # type: ignore[arg-type]
        in_allowedSessionId="telegramUser:1",
    )
    detail = useCase.execute(in_runId="r1s", in_runs_scope="admin")
    assert detail is not None
    assert detail["sessionId"] == "telegramUser:1:scheduler:email"


def testGetRunDetailsUseCaseScopeAllBypassesAdminSession() -> None:
    repository = FakeRunRepository()
    useCase = GetRunDetailsUseCase(
        in_runRepository=repository,  # type: ignore[arg-type]
        in_allowedSessionId="telegramUser:1",
    )
    blocked = useCase.execute(in_runId="r2", in_runs_scope="admin")
    opened = useCase.execute(in_runId="r2", in_runs_scope="all")
    assert blocked is None
    assert opened is not None
    assert opened["runId"] == "r2"
