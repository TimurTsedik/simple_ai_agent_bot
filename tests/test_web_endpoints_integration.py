import importlib

from fastapi.testclient import TestClient


def _buildClient(in_monkeypatch) -> TestClient:
    ret: TestClient
    in_monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tg-token-test")
    in_monkeypatch.setenv("OPENROUTER_API_KEY", "or-key-test")
    in_monkeypatch.setenv("SESSION_COOKIE_SECRET", "cookie-secret-test-0123456789abcdef")
    in_monkeypatch.setenv("ADMIN_RAW_TOKENS", "token-one-12345678")
    mainModule = importlib.import_module("app.main")
    mainModule = importlib.reload(mainModule)
    mainModule.app.state.telegramPollingRunner.runForever = lambda: None
    mainModule.app.state.telegramPollingRunner.stop = lambda: None
    ret = TestClient(mainModule.app)
    return ret


def testWebEndpointsRequireLogin(monkeypatch) -> None:
    client = _buildClient(in_monkeypatch=monkeypatch)

    response = client.get("/runs", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers.get("location") == "/login"

    internalResponse = client.get("/internal/runs", follow_redirects=False)
    assert internalResponse.status_code == 401


def testWebLoginAndGitPagesRenderSafely(monkeypatch) -> None:
    client = _buildClient(in_monkeypatch=monkeypatch)
    mainModule = importlib.import_module("app.main")

    loginResponse = client.post(
        "/login",
        data={"adminToken": "token-one-12345678"},
        follow_redirects=False,
    )
    assert loginResponse.status_code == 303
    assert loginResponse.headers.get("location") == "/"

    def fakeGitStatusExecute(in_limit: int = 200) -> dict:
        ret = {
            "isGitRepo": True,
            "branch": "main<script>alert(1)</script>",
            "isClean": False,
            "items": [" M app/main.py<script>"],
            "error": "",
        }
        _ = in_limit
        return ret

    def fakeGitDiffExecute(
        in_offset: int = 0,
        in_limit: int = 5,
        in_filePath: str = "",
        in_maxCharsPerFile: int = 30000,
    ) -> dict:
        ret = {
            "isGitRepo": True,
            "totalFiles": 1,
            "offset": in_offset,
            "limit": in_limit,
            "files": [
                {
                    "filePath": "app/main.py<script>",
                    "diff": "+line<script>",
                    "truncated": False,
                }
            ],
            "error": "",
        }
        _ = in_filePath
        _ = in_maxCharsPerFile
        return ret

    mainModule.app.state.getGitStatusUseCase.execute = fakeGitStatusExecute
    mainModule.app.state.getGitDiffUseCase.execute = fakeGitDiffExecute

    runsResponse = client.get("/runs")
    indexResponse = client.get("/")
    statusResponse = client.get("/git/status")
    diffResponse = client.get("/git/diff")

    assert runsResponse.status_code == 200
    assert indexResponse.status_code == 200
    assert "Статистика LLM (provider)" in indexResponse.text
    assert statusResponse.status_code == 200
    assert diffResponse.status_code == 200
    assert "<script>" not in statusResponse.text
    assert "<script>" not in diffResponse.text
    assert "&lt;script&gt;" in statusResponse.text
    assert "&lt;script&gt;" in diffResponse.text

    internalRuns = client.get("/internal/runs", follow_redirects=False)
    assert internalRuns.status_code == 200
    assert "items" in internalRuns.json()


def testToolsAndSkillsPagesRequireLogin(monkeypatch) -> None:
    client = _buildClient(in_monkeypatch=monkeypatch)

    toolsResponse = client.get("/tools", follow_redirects=False)
    assert toolsResponse.status_code == 303
    assert toolsResponse.headers.get("location") == "/login"

    skillsResponse = client.get("/skills", follow_redirects=False)
    assert skillsResponse.status_code == 303
    assert skillsResponse.headers.get("location") == "/login"

    toolsConfigResponse = client.get("/config/tools", follow_redirects=False)
    assert toolsConfigResponse.status_code == 303
    assert toolsConfigResponse.headers.get("location") == "/login"


def testWebLoginBruteforceBlocksAfterThreeFailures(monkeypatch) -> None:
    client = _buildClient(in_monkeypatch=monkeypatch)
    mainModule = importlib.import_module("app.main")

    now = {"t": 1000.0}
    mainModule.app.state.adminLoginNowUnixTsProvider = lambda: now["t"]

    for _ in range(3):
        resp = client.post(
            "/login",
            data={"adminToken": "wrong-token"},
            follow_redirects=False,
        )
        assert resp.status_code == 401

    blocked = client.post(
        "/login",
        data={"adminToken": "token-one-12345678"},
        follow_redirects=False,
    )
    assert blocked.status_code == 429

    now["t"] += 901.0
    ok = client.post(
        "/login",
        data={"adminToken": "token-one-12345678"},
        follow_redirects=False,
    )
    assert ok.status_code == 303
    assert ok.headers.get("location") == "/"


def testWebSessionBoundToIpRejectsDifferentIp(monkeypatch) -> None:
    client = _buildClient(in_monkeypatch=monkeypatch)
    mainModule = importlib.import_module("app.main")
    mainModule.app.state.settings.security.bindSessionToIp = True
    mainModule.app.state.settings.security.trustProxyHeaders = True
    mainModule.app.state.settings.security.trustedProxyIps = ["testclient"]

    loginResp = client.post(
        "/login",
        data={"adminToken": "token-one-12345678"},
        follow_redirects=False,
        headers={"x-forwarded-for": "1.1.1.1"},
    )
    assert loginResp.status_code == 303
    cookieValue = loginResp.cookies.get("admin_session")
    assert isinstance(cookieValue, str) and cookieValue != ""

    okSameIp = client.get(
        "/",
        cookies={"admin_session": cookieValue},
        headers={"x-forwarded-for": "1.1.1.1"},
        follow_redirects=False,
    )
    assert okSameIp.status_code == 200

    otherIpResp = client.get(
        "/",
        cookies={"admin_session": cookieValue},
        headers={"x-forwarded-for": "2.2.2.2"},
        follow_redirects=False,
    )
    assert otherIpResp.status_code == 303
    assert otherIpResp.headers.get("location") == "/login"
