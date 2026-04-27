import importlib
from pathlib import Path

from fastapi.testclient import TestClient


def _buildClient(in_monkeypatch, in_tmpPath: Path, in_adminWritesEnabled: bool) -> TestClient:
    in_monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tg-token-test")
    in_monkeypatch.setenv("OPENROUTER_API_KEY", "or-key-test")
    in_monkeypatch.setenv("SESSION_COOKIE_SECRET", "cookie-secret-test-0123456789abcdef")
    in_monkeypatch.setenv("ADMIN_RAW_TOKENS", "token-one-12345678")

    configPath = in_tmpPath / "config.yaml"
    toolsPath = in_tmpPath / "tools.yaml"
    skillsDir = in_tmpPath / "skills"
    skillsDir.mkdir(parents=True, exist_ok=True)
    (skillsDir / "default_assistant.md").write_text("# Default\n\na", encoding="utf-8")

    toolsPath.write_text(
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
        "  dataRootPath: \"./data\"\n"
        "telegram:\n"
        "  pollingTimeoutSeconds: 30\n"
        "  allowedUserIds: [16739703]\n"
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
        f"  adminWritesEnabled: {'true' if in_adminWritesEnabled else 'false'}\n"
        "  allowedReadOnlyPaths: [\"./data/memory\",\"./data/runs\",\"./data/logs\"]\n"
        "logging:\n"
        "  logsDirPath: \"./data/logs\"\n"
        "  runLogsFileName: \"run.jsonl\"\n"
        "  appLogsFileName: \"app.log\"\n"
        "  maxBytes: 10485760\n"
        "  backupCount: 5\n"
        "skills:\n"
        f"  skillsDirPath: \"{skillsDir.as_posix()}\"\n"
        "tools:\n"
        f"  toolsConfigPath: \"{toolsPath.as_posix()}\"\n",
        encoding="utf-8",
    )

    in_monkeypatch.setattr("app.config.defaults.DEFAULT_CONFIG_PATH", str(configPath))
    mainModule = importlib.import_module("app.main")
    mainModule = importlib.reload(mainModule)
    mainModule.app.state.telegramPollingRunner.runForever = lambda: None
    mainModule.app.state.telegramPollingRunner.stop = lambda: None
    ret = TestClient(mainModule.app)
    return ret


def _login(in_client: TestClient) -> None:
    loginResponse = in_client.post(
        "/login",
        data={"adminToken": "token-one-12345678"},
        follow_redirects=False,
    )
    assert loginResponse.status_code == 303


def testAdminWritesDisabledBlocksPosts(monkeypatch, tmp_path) -> None:
    client = _buildClient(
        in_monkeypatch=monkeypatch, in_tmpPath=tmp_path, in_adminWritesEnabled=False
    )
    _login(in_client=client)

    respSkill = client.post(
        "/skills/default_assistant", data={"content": "# Default\n\nchanged"}
    )
    assert respSkill.status_code == 403

    respTools = client.post(
        "/config/tools",
        data={
            "content": "telegramNewsDigest:\n  digestChannelUsernames: [\"b\"]\n",
        },
    )
    assert respTools.status_code == 403


def testAdminWritesEnabledAllowsSaving(monkeypatch, tmp_path) -> None:
    client = _buildClient(
        in_monkeypatch=monkeypatch, in_tmpPath=tmp_path, in_adminWritesEnabled=True
    )
    _login(in_client=client)

    respSkill = client.post(
        "/skills/default_assistant", data={"content": "# Default\n\nchanged"}
    )
    assert respSkill.status_code == 200
    assert "Сохранено" in respSkill.text

    respTools = client.post(
        "/config/tools",
        data={
            "content": "telegramNewsDigest:\n  digestChannelUsernames: [\"b\"]\n  portfolioTickers: []\n  digestSemanticKeywords: []\n",
        },
    )
    assert respTools.status_code == 200
    assert "Сохранено" in respTools.text
