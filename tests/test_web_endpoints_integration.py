import importlib
from pathlib import Path

from fastapi.testclient import TestClient

from app.common.memoryPrincipal import formatTelegramUserMemoryPrincipal


def _buildClient(in_monkeypatch, in_tmpPath: Path) -> TestClient:
    ret: TestClient
    in_monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tg-token-test")
    in_monkeypatch.setenv("OPENROUTER_API_KEY", "or-key-test")
    in_monkeypatch.setenv("SESSION_COOKIE_SECRET", "cookie-secret-test-0123456789abcdef")
    in_monkeypatch.setenv("ADMIN_RAW_TOKENS", "token-one-12345678")

    configPath = in_tmpPath / "config.yaml"
    skillsDir = in_tmpPath / "skills"
    skillsDir.mkdir(parents=True, exist_ok=True)
    (skillsDir / "default_assistant.md").write_text("# Default\n\na", encoding="utf-8")

    dataRoot = in_tmpPath / "data"
    memoryRoot = dataRoot / "memory"
    logsRoot = dataRoot / "logs"
    runsRoot = dataRoot / "runs"
    memoryRoot.mkdir(parents=True, exist_ok=True)
    logsRoot.mkdir(parents=True, exist_ok=True)
    runsRoot.mkdir(parents=True, exist_ok=True)
    adminPrincipal = formatTelegramUserMemoryPrincipal(in_telegramUserId=16739703)
    adminSessionDir = memoryRoot / "sessions" / str(adminPrincipal).replace(":", "_")
    adminSessionDir.mkdir(parents=True, exist_ok=True)
    (adminSessionDir / "long_term.md").write_text(
        "line-one\n<script>x</script>\n",
        encoding="utf-8",
    )
    (adminSessionDir / "tools.yaml").write_text(
        "telegramNewsDigest:\n"
        "  digestChannelUsernames: [\"a\"]\n"
        "  portfolioTickers: []\n"
        "  digestSemanticKeywords: []\n",
        encoding="utf-8",
    )

    configPath.write_text(
        "app:\n"
        "  appName: \"simple-ai-agent-bot\"\n"
        "  environment: \"test\"\n"
        f"  dataRootPath: \"{dataRoot.as_posix()}\"\n"
        f"  usersRegistryPath: \"{(in_tmpPath / 'users' / 'registry.yaml').as_posix()}\"\n"
        "  displayTimeZone: \"UTC\"\n"
        "telegram:\n"
        "  pollingTimeoutSeconds: 30\n"
        "  denyMessageText: \"Доступ запрещён\"\n"
        "models:\n"
        "  openRouterBaseUrl: \"https://openrouter.ai/api/v1\"\n"
        "  primaryModel: \"model-primary\"\n"
        "  secondaryModel: \"model-secondary\"\n"
        "  tertiaryModel: \"model-tertiary\"\n"
        "  requestTimeoutSeconds: 45\n"
        "  retryCountBeforeFallback: 0\n"
        "  returnToPrimaryCooldownSeconds: 300\n"
        "runtime:\n"
        "  maxSteps: 2\n"
        "  maxToolCalls: 0\n"
        "  maxExecutionSeconds: 10\n"
        "  maxToolOutputChars: 1000\n"
        "  maxPromptChars: 3000\n"
        "  recentMessagesLimit: 12\n"
        "  sessionSummaryMaxChars: 2000\n"
        "  skillSelectionMaxCount: 4\n"
        "security:\n"
        "  webSessionCookieTtlSeconds: 43200\n"
        "  maxAdminTokens: 3\n"
        "  adminWritesEnabled: false\n"
        f"  allowedReadOnlyPaths: [\"{memoryRoot.as_posix()}\",\"{runsRoot.as_posix()}\",\"{logsRoot.as_posix()}\"]\n"
        "logging:\n"
        f"  logsDirPath: \"{logsRoot.as_posix()}\"\n"
        "  runLogsFileName: \"run.jsonl\"\n"
        "  appLogsFileName: \"app.log\"\n"
        "  maxBytes: 10485760\n"
        "  backupCount: 5\n"
        "skills:\n"
        f"  skillsDirPath: \"{skillsDir.as_posix()}\"\n"
        "memory:\n"
        f"  memoryRootPath: \"{memoryRoot.as_posix()}\"\n"
        "scheduler:\n"
        "  enabled: false\n"
        "  tickSeconds: 1\n",
        encoding="utf-8",
    )

    in_monkeypatch.setattr("app.config.defaults.DEFAULT_CONFIG_PATH", str(configPath))
    mainModule = importlib.import_module("app.main")
    mainModule = importlib.reload(mainModule)
    mainModule.app.state.telegramPollingRunner.runForever = lambda: None
    mainModule.app.state.telegramPollingRunner.stop = lambda: None
    ret = TestClient(mainModule.app)
    return ret


def testWebEndpointsRequireLogin(monkeypatch, tmp_path) -> None:
    client = _buildClient(in_monkeypatch=monkeypatch, in_tmpPath=tmp_path)

    response = client.get("/runs", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers.get("location") == "/login"

    internalResponse = client.get("/internal/runs", follow_redirects=False)
    assert internalResponse.status_code == 401


def testWebLoginAndGitPagesRenderSafely(monkeypatch, tmp_path) -> None:
    client = _buildClient(in_monkeypatch=monkeypatch, in_tmpPath=tmp_path)
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
    schedulesResponse = client.get("/config/schedules")

    assert runsResponse.status_code == 200
    assert indexResponse.status_code == 200
    assert "Ограничение:" in runsResponse.text
    assert "Ограничение:" in indexResponse.text
    assert "Статистика LLM (provider)" in indexResponse.text
    assert statusResponse.status_code == 200
    assert diffResponse.status_code == 200
    assert schedulesResponse.status_code == 200
    assert "Scheduler settings (schedules.yaml)" in schedulesResponse.text

    usersResponse = client.get("/users")
    assert usersResponse.status_code == 200
    assert "Пользователи Telegram" in usersResponse.text
    assert "<script>" not in statusResponse.text
    assert "<script>" not in diffResponse.text
    assert "&lt;script&gt;" in statusResponse.text
    assert "&lt;script&gt;" in diffResponse.text

    internalRuns = client.get("/internal/runs", follow_redirects=False)
    assert internalRuns.status_code == 200
    assert "items" in internalRuns.json()

    memoryPage = client.get("/memory/long-term")
    assert memoryPage.status_code == 200
    assert "Long-term memory" in memoryPage.text
    assert "line-one" in memoryPage.text
    assert "<script>" not in memoryPage.text
    assert "&lt;script&gt;" in memoryPage.text

    internalMemory = client.get("/internal/memory/long-term", follow_redirects=False)
    assert internalMemory.status_code == 200
    payload = internalMemory.json()
    assert "content" in payload
    assert "line-one" in str(payload.get("content", ""))


def testToolsAndSkillsPagesRequireLogin(monkeypatch, tmp_path) -> None:
    client = _buildClient(in_monkeypatch=monkeypatch, in_tmpPath=tmp_path)

    toolsResponse = client.get("/tools", follow_redirects=False)
    assert toolsResponse.status_code == 303
    assert toolsResponse.headers.get("location") == "/login"

    skillsResponse = client.get("/skills", follow_redirects=False)
    assert skillsResponse.status_code == 303
    assert skillsResponse.headers.get("location") == "/login"

    toolsConfigResponse = client.get("/config/tools", follow_redirects=False)
    assert toolsConfigResponse.status_code == 303
    assert toolsConfigResponse.headers.get("location") == "/login"

    schedulesConfigResponse = client.get("/config/schedules", follow_redirects=False)
    assert schedulesConfigResponse.status_code == 303
    assert schedulesConfigResponse.headers.get("location") == "/login"

    longTermResponse = client.get("/memory/long-term", follow_redirects=False)
    assert longTermResponse.status_code == 303
    assert longTermResponse.headers.get("location") == "/login"

    usersPageResponse = client.get("/users", follow_redirects=False)
    assert usersPageResponse.status_code == 303
    assert usersPageResponse.headers.get("location") == "/login"


def testWebLoginBruteforceBlocksAfterThreeFailures(monkeypatch, tmp_path) -> None:
    client = _buildClient(in_monkeypatch=monkeypatch, in_tmpPath=tmp_path)
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


def testWebSessionBoundToIpRejectsDifferentIp(monkeypatch, tmp_path) -> None:
    client = _buildClient(in_monkeypatch=monkeypatch, in_tmpPath=tmp_path)
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
