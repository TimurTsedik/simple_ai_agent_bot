import os
from pathlib import Path
from tempfile import TemporaryDirectory

from app.config.settingsLoader import SettingsLoadError, loadSettings


def _writeConfigFile(in_path: Path) -> None:
    in_path.write_text(
        "\n".join(
            [
                "app:",
                "  appName: test-app",
                "  environment: test",
                "  dataRootPath: ./data",
                "telegram:",
                "  pollingTimeoutSeconds: 10",
                "  allowedUserIds: [1, 2]",
                "  denyMessageText: denied",
                "  digestChannelUsernames: [channel_one]",
                "models:",
                "  openRouterBaseUrl: https://openrouter.ai/api/v1",
                "  primaryModel: model-primary",
                "  secondaryModel: model-secondary",
                "  tertiaryModel: model-tertiary",
                "  requestTimeoutSeconds: 45",
                "  retryCountBeforeFallback: 2",
                "  returnToPrimaryCooldownSeconds: 300",
                "runtime:",
                "  maxSteps: 5",
                "  maxToolCalls: 5",
                "  maxExecutionSeconds: 30",
                "  maxToolOutputChars: 1000",
                "  maxPromptChars: 5000",
                "  recentMessagesLimit: 12",
                "  sessionSummaryMaxChars: 2000",
                "  skillSelectionMaxCount: 4",
                "  extraSecondsPerLlmError: 0",
                "  maxExtraSecondsTotal: 0",
                "security:",
                "  webSessionCookieTtlSeconds: 3600",
                "  maxAdminTokens: 3",
                "  allowedReadOnlyPaths: [./data]",
                "logging:",
                "  logsDirPath: ./data/logs",
                "  runLogsFileName: run.jsonl",
                "  appLogsFileName: app.log",
                "  maxBytes: 10485760",
                "  backupCount: 5",
            ]
        ),
        encoding="utf-8",
    )


def _writeEnvFile(
    in_path: Path,
    in_token: str,
    in_apiKey: str,
    in_cookieSecret: str,
    in_adminRawTokens: str = "token-one-12345678",
) -> None:
    in_path.write_text(
        "\n".join(
            [
                f"TELEGRAM_BOT_TOKEN={in_token}",
                f"OPENROUTER_API_KEY={in_apiKey}",
                f"SESSION_COOKIE_SECRET={in_cookieSecret}",
                f"ADMIN_RAW_TOKENS={in_adminRawTokens}",
            ]
        ),
        encoding="utf-8",
    )


def testLoadSettingsSuccess() -> None:
    previousTelegramToken = os.environ.get("TELEGRAM_BOT_TOKEN")
    previousOpenRouterKey = os.environ.get("OPENROUTER_API_KEY")
    previousCookieSecret = os.environ.get("SESSION_COOKIE_SECRET")
    with TemporaryDirectory() as tempDir:
        configPath = Path(tempDir) / "config.yaml"
        envPath = Path(tempDir) / ".env"
        _writeConfigFile(in_path=configPath)
        _writeEnvFile(
            in_path=envPath,
            in_token="tg-token-dotenv",
            in_apiKey="or-key-dotenv",
            in_cookieSecret="cookie-secret-dotenv-0123456789abcdef",
        )
        settings = loadSettings(
            in_configPath=str(configPath),
            in_envPath=str(envPath),
        )

    if previousTelegramToken is None:
        os.environ.pop("TELEGRAM_BOT_TOKEN", None)
    else:
        os.environ["TELEGRAM_BOT_TOKEN"] = previousTelegramToken
    if previousOpenRouterKey is None:
        os.environ.pop("OPENROUTER_API_KEY", None)
    else:
        os.environ["OPENROUTER_API_KEY"] = previousOpenRouterKey
    if previousCookieSecret is None:
        os.environ.pop("SESSION_COOKIE_SECRET", None)
    else:
        os.environ["SESSION_COOKIE_SECRET"] = previousCookieSecret

    assert settings.app.appName == "test-app"
    assert settings.telegramBotToken == "tg-token-dotenv"
    assert settings.openRouterApiKey == "or-key-dotenv"
    assert settings.adminRawTokens == ["token-one-12345678"]


def testEnvironmentVariablesOverrideDotEnv() -> None:
    previousTelegramToken = os.environ.get("TELEGRAM_BOT_TOKEN")
    previousOpenRouterKey = os.environ.get("OPENROUTER_API_KEY")
    previousCookieSecret = os.environ.get("SESSION_COOKIE_SECRET")
    with TemporaryDirectory() as tempDir:
        configPath = Path(tempDir) / "config.yaml"
        envPath = Path(tempDir) / ".env"
        _writeConfigFile(in_path=configPath)
        _writeEnvFile(
            in_path=envPath,
            in_token="tg-token-dotenv",
            in_apiKey="or-key-dotenv",
            in_cookieSecret="cookie-secret-dotenv-0123456789abcdef",
        )
        os.environ["TELEGRAM_BOT_TOKEN"] = "tg-token-env"
        os.environ["OPENROUTER_API_KEY"] = "or-key-env"
        os.environ["SESSION_COOKIE_SECRET"] = "cookie-secret-env-0123456789abcdef"
        settings = loadSettings(
            in_configPath=str(configPath),
            in_envPath=str(envPath),
        )

    if previousTelegramToken is None:
        os.environ.pop("TELEGRAM_BOT_TOKEN", None)
    else:
        os.environ["TELEGRAM_BOT_TOKEN"] = previousTelegramToken
    if previousOpenRouterKey is None:
        os.environ.pop("OPENROUTER_API_KEY", None)
    else:
        os.environ["OPENROUTER_API_KEY"] = previousOpenRouterKey
    if previousCookieSecret is None:
        os.environ.pop("SESSION_COOKIE_SECRET", None)
    else:
        os.environ["SESSION_COOKIE_SECRET"] = previousCookieSecret

    assert settings.telegramBotToken == "tg-token-env"
    assert settings.openRouterApiKey == "or-key-env"


def testLoadSettingsFailFastWhenEnvMissing() -> None:
    previousTelegramToken = os.environ.get("TELEGRAM_BOT_TOKEN")
    previousOpenRouterKey = os.environ.get("OPENROUTER_API_KEY")
    previousCookieSecret = os.environ.get("SESSION_COOKIE_SECRET")
    with TemporaryDirectory() as tempDir:
        configPath = Path(tempDir) / "config.yaml"
        _writeConfigFile(in_path=configPath)
        os.environ.pop("TELEGRAM_BOT_TOKEN", None)
        os.environ.pop("OPENROUTER_API_KEY", None)
        os.environ.pop("SESSION_COOKIE_SECRET", None)
        didRaise = False
        try:
            loadSettings(
                in_configPath=str(configPath),
                in_envPath=str(Path(tempDir) / "missing.env"),
            )
        except SettingsLoadError:
            didRaise = True

    if previousTelegramToken is None:
        os.environ.pop("TELEGRAM_BOT_TOKEN", None)
    else:
        os.environ["TELEGRAM_BOT_TOKEN"] = previousTelegramToken
    if previousOpenRouterKey is None:
        os.environ.pop("OPENROUTER_API_KEY", None)
    else:
        os.environ["OPENROUTER_API_KEY"] = previousOpenRouterKey
    if previousCookieSecret is None:
        os.environ.pop("SESSION_COOKIE_SECRET", None)
    else:
        os.environ["SESSION_COOKIE_SECRET"] = previousCookieSecret

    assert didRaise is True


def testLoadSettingsFailFastWhenAdminTokensMissing() -> None:
    previousTelegramToken = os.environ.get("TELEGRAM_BOT_TOKEN")
    previousOpenRouterKey = os.environ.get("OPENROUTER_API_KEY")
    previousCookieSecret = os.environ.get("SESSION_COOKIE_SECRET")
    previousAdminTokens = os.environ.get("ADMIN_RAW_TOKENS")
    with TemporaryDirectory() as tempDir:
        configPath = Path(tempDir) / "config.yaml"
        envPath = Path(tempDir) / ".env"
        _writeConfigFile(in_path=configPath)
        os.environ.pop("TELEGRAM_BOT_TOKEN", None)
        os.environ.pop("OPENROUTER_API_KEY", None)
        os.environ.pop("SESSION_COOKIE_SECRET", None)
        os.environ.pop("ADMIN_RAW_TOKENS", None)
        envPath.write_text(
            "\n".join(
                [
                    "TELEGRAM_BOT_TOKEN=tg-token-dotenv",
                    "OPENROUTER_API_KEY=or-key-dotenv",
                    "SESSION_COOKIE_SECRET=cookie-secret-dotenv-0123456789abcdef",
                ]
            ),
            encoding="utf-8",
        )
        didRaise = False
        try:
            loadSettings(
                in_configPath=str(configPath),
                in_envPath=str(envPath),
            )
        except SettingsLoadError:
            didRaise = True

    if previousTelegramToken is None:
        os.environ.pop("TELEGRAM_BOT_TOKEN", None)
    else:
        os.environ["TELEGRAM_BOT_TOKEN"] = previousTelegramToken
    if previousOpenRouterKey is None:
        os.environ.pop("OPENROUTER_API_KEY", None)
    else:
        os.environ["OPENROUTER_API_KEY"] = previousOpenRouterKey
    if previousCookieSecret is None:
        os.environ.pop("SESSION_COOKIE_SECRET", None)
    else:
        os.environ["SESSION_COOKIE_SECRET"] = previousCookieSecret
    if previousAdminTokens is None:
        os.environ.pop("ADMIN_RAW_TOKENS", None)
    else:
        os.environ["ADMIN_RAW_TOKENS"] = previousAdminTokens

    assert didRaise is True


def testLoadSettingsFailFastWhenAdminTokensLimitExceeded() -> None:
    previousTelegramToken = os.environ.get("TELEGRAM_BOT_TOKEN")
    previousOpenRouterKey = os.environ.get("OPENROUTER_API_KEY")
    previousCookieSecret = os.environ.get("SESSION_COOKIE_SECRET")
    previousAdminTokens = os.environ.get("ADMIN_RAW_TOKENS")
    with TemporaryDirectory() as tempDir:
        configPath = Path(tempDir) / "config.yaml"
        envPath = Path(tempDir) / ".env"
        _writeConfigFile(in_path=configPath)
        os.environ.pop("TELEGRAM_BOT_TOKEN", None)
        os.environ.pop("OPENROUTER_API_KEY", None)
        os.environ.pop("SESSION_COOKIE_SECRET", None)
        os.environ.pop("ADMIN_RAW_TOKENS", None)
        _writeEnvFile(
            in_path=envPath,
            in_token="tg-token-dotenv",
            in_apiKey="or-key-dotenv",
            in_cookieSecret="cookie-secret-dotenv-0123456789abcdef",
            in_adminRawTokens=(
                "token-one-12345678,token-two-12345678,"
                "token-three-123456,token-four-1234567"
            ),
        )
        didRaise = False
        try:
            loadSettings(
                in_configPath=str(configPath),
                in_envPath=str(envPath),
            )
        except SettingsLoadError:
            didRaise = True

    if previousTelegramToken is None:
        os.environ.pop("TELEGRAM_BOT_TOKEN", None)
    else:
        os.environ["TELEGRAM_BOT_TOKEN"] = previousTelegramToken
    if previousOpenRouterKey is None:
        os.environ.pop("OPENROUTER_API_KEY", None)
    else:
        os.environ["OPENROUTER_API_KEY"] = previousOpenRouterKey
    if previousCookieSecret is None:
        os.environ.pop("SESSION_COOKIE_SECRET", None)
    else:
        os.environ["SESSION_COOKIE_SECRET"] = previousCookieSecret
    if previousAdminTokens is None:
        os.environ.pop("ADMIN_RAW_TOKENS", None)
    else:
        os.environ["ADMIN_RAW_TOKENS"] = previousAdminTokens

    assert didRaise is True


def testLoadSettingsFailFastWhenAdminTokenTooShort() -> None:
    previousAdminTokens = os.environ.get("ADMIN_RAW_TOKENS")
    previousTelegramToken = os.environ.get("TELEGRAM_BOT_TOKEN")
    previousOpenRouterKey = os.environ.get("OPENROUTER_API_KEY")
    previousCookieSecret = os.environ.get("SESSION_COOKIE_SECRET")
    with TemporaryDirectory() as tempDir:
        configPath = Path(tempDir) / "config.yaml"
        envPath = Path(tempDir) / ".env"
        _writeConfigFile(in_path=configPath)
        os.environ.pop("TELEGRAM_BOT_TOKEN", None)
        os.environ.pop("OPENROUTER_API_KEY", None)
        os.environ.pop("SESSION_COOKIE_SECRET", None)
        os.environ.pop("ADMIN_RAW_TOKENS", None)
        _writeEnvFile(
            in_path=envPath,
            in_token="tg-token-dotenv",
            in_apiKey="or-key-dotenv",
            in_cookieSecret="cookie-secret-dotenv-0123456789abcdef",
            in_adminRawTokens="short-token",
        )
        didRaise = False
        try:
            loadSettings(
                in_configPath=str(configPath),
                in_envPath=str(envPath),
            )
        except SettingsLoadError:
            didRaise = True

    if previousTelegramToken is None:
        os.environ.pop("TELEGRAM_BOT_TOKEN", None)
    else:
        os.environ["TELEGRAM_BOT_TOKEN"] = previousTelegramToken
    if previousOpenRouterKey is None:
        os.environ.pop("OPENROUTER_API_KEY", None)
    else:
        os.environ["OPENROUTER_API_KEY"] = previousOpenRouterKey
    if previousCookieSecret is None:
        os.environ.pop("SESSION_COOKIE_SECRET", None)
    else:
        os.environ["SESSION_COOKIE_SECRET"] = previousCookieSecret
    if previousAdminTokens is None:
        os.environ.pop("ADMIN_RAW_TOKENS", None)
    else:
        os.environ["ADMIN_RAW_TOKENS"] = previousAdminTokens

    assert didRaise is True


def testLoadSettingsFailFastWhenAdminTokenHasInvalidSymbols() -> None:
    previousAdminTokens = os.environ.get("ADMIN_RAW_TOKENS")
    previousTelegramToken = os.environ.get("TELEGRAM_BOT_TOKEN")
    previousOpenRouterKey = os.environ.get("OPENROUTER_API_KEY")
    previousCookieSecret = os.environ.get("SESSION_COOKIE_SECRET")
    with TemporaryDirectory() as tempDir:
        configPath = Path(tempDir) / "config.yaml"
        envPath = Path(tempDir) / ".env"
        _writeConfigFile(in_path=configPath)
        os.environ.pop("TELEGRAM_BOT_TOKEN", None)
        os.environ.pop("OPENROUTER_API_KEY", None)
        os.environ.pop("SESSION_COOKIE_SECRET", None)
        os.environ.pop("ADMIN_RAW_TOKENS", None)
        _writeEnvFile(
            in_path=envPath,
            in_token="tg-token-dotenv",
            in_apiKey="or-key-dotenv",
            in_cookieSecret="cookie-secret-dotenv-0123456789abcdef",
            in_adminRawTokens="token-one-12345678,token*bad*1234567",
        )
        didRaise = False
        try:
            loadSettings(
                in_configPath=str(configPath),
                in_envPath=str(envPath),
            )
        except SettingsLoadError:
            didRaise = True

    if previousTelegramToken is None:
        os.environ.pop("TELEGRAM_BOT_TOKEN", None)
    else:
        os.environ["TELEGRAM_BOT_TOKEN"] = previousTelegramToken
    if previousOpenRouterKey is None:
        os.environ.pop("OPENROUTER_API_KEY", None)
    else:
        os.environ["OPENROUTER_API_KEY"] = previousOpenRouterKey
    if previousCookieSecret is None:
        os.environ.pop("SESSION_COOKIE_SECRET", None)
    else:
        os.environ["SESSION_COOKIE_SECRET"] = previousCookieSecret
    if previousAdminTokens is None:
        os.environ.pop("ADMIN_RAW_TOKENS", None)
    else:
        os.environ["ADMIN_RAW_TOKENS"] = previousAdminTokens

    assert didRaise is True


def testLoadSettingsFailFastWhenAdminTokensDuplicate() -> None:
    previousAdminTokens = os.environ.get("ADMIN_RAW_TOKENS")
    previousTelegramToken = os.environ.get("TELEGRAM_BOT_TOKEN")
    previousOpenRouterKey = os.environ.get("OPENROUTER_API_KEY")
    previousCookieSecret = os.environ.get("SESSION_COOKIE_SECRET")
    with TemporaryDirectory() as tempDir:
        configPath = Path(tempDir) / "config.yaml"
        envPath = Path(tempDir) / ".env"
        _writeConfigFile(in_path=configPath)
        os.environ.pop("TELEGRAM_BOT_TOKEN", None)
        os.environ.pop("OPENROUTER_API_KEY", None)
        os.environ.pop("SESSION_COOKIE_SECRET", None)
        os.environ.pop("ADMIN_RAW_TOKENS", None)
        _writeEnvFile(
            in_path=envPath,
            in_token="tg-token-dotenv",
            in_apiKey="or-key-dotenv",
            in_cookieSecret="cookie-secret-dotenv-0123456789abcdef",
            in_adminRawTokens="token-one-12345678,token-one-12345678",
        )
        didRaise = False
        try:
            loadSettings(
                in_configPath=str(configPath),
                in_envPath=str(envPath),
            )
        except SettingsLoadError:
            didRaise = True

    if previousTelegramToken is None:
        os.environ.pop("TELEGRAM_BOT_TOKEN", None)
    else:
        os.environ["TELEGRAM_BOT_TOKEN"] = previousTelegramToken
    if previousOpenRouterKey is None:
        os.environ.pop("OPENROUTER_API_KEY", None)
    else:
        os.environ["OPENROUTER_API_KEY"] = previousOpenRouterKey
    if previousCookieSecret is None:
        os.environ.pop("SESSION_COOKIE_SECRET", None)
    else:
        os.environ["SESSION_COOKIE_SECRET"] = previousCookieSecret
    if previousAdminTokens is None:
        os.environ.pop("ADMIN_RAW_TOKENS", None)
    else:
        os.environ["ADMIN_RAW_TOKENS"] = previousAdminTokens

    assert didRaise is True


def testLoadSettingsUsesTickSecondsFromConfigWhenSchedulerEnabled() -> None:
    previousTelegramToken = os.environ.get("TELEGRAM_BOT_TOKEN")
    previousOpenRouterKey = os.environ.get("OPENROUTER_API_KEY")
    previousCookieSecret = os.environ.get("SESSION_COOKIE_SECRET")
    previousAdminTokens = os.environ.get("ADMIN_RAW_TOKENS")
    with TemporaryDirectory() as tempDir:
        configPath = Path(tempDir) / "config.yaml"
        envPath = Path(tempDir) / ".env"
        schedulesPath = Path(tempDir) / "schedules.yaml"
        _writeConfigFile(in_path=configPath)
        configPath.write_text(
            configPath.read_text(encoding="utf-8")
            + "\n"
            + "\n".join(
                [
                    "scheduler:",
                    "  enabled: true",
                    f'  schedulesConfigPath: "{str(schedulesPath)}"',
                    "  tickSeconds: 30",
                ]
            ),
            encoding="utf-8",
        )
        schedulesPath.write_text(
            "\n".join(
                [
                    "tickSeconds: 1",
                    "jobs:",
                    "  - jobId: job1",
                    "    enabled: true",
                    "    schedule:",
                    "      intervalSeconds: 60",
                    "    actionInternalRun:",
                    "      sessionId: scheduler:test",
                    "      message: hello",
                ]
            ),
            encoding="utf-8",
        )
        _writeEnvFile(
            in_path=envPath,
            in_token="tg-token-dotenv",
            in_apiKey="or-key-dotenv",
            in_cookieSecret="cookie-secret-dotenv-0123456789abcdef",
        )
        os.environ.pop("TELEGRAM_BOT_TOKEN", None)
        os.environ.pop("OPENROUTER_API_KEY", None)
        os.environ.pop("SESSION_COOKIE_SECRET", None)
        os.environ.pop("ADMIN_RAW_TOKENS", None)

        settings = loadSettings(
            in_configPath=str(configPath),
            in_envPath=str(envPath),
        )

    if previousTelegramToken is None:
        os.environ.pop("TELEGRAM_BOT_TOKEN", None)
    else:
        os.environ["TELEGRAM_BOT_TOKEN"] = previousTelegramToken
    if previousOpenRouterKey is None:
        os.environ.pop("OPENROUTER_API_KEY", None)
    else:
        os.environ["OPENROUTER_API_KEY"] = previousOpenRouterKey
    if previousCookieSecret is None:
        os.environ.pop("SESSION_COOKIE_SECRET", None)
    else:
        os.environ["SESSION_COOKIE_SECRET"] = previousCookieSecret
    if previousAdminTokens is None:
        os.environ.pop("ADMIN_RAW_TOKENS", None)
    else:
        os.environ["ADMIN_RAW_TOKENS"] = previousAdminTokens

    assert settings.scheduler.tickSeconds == 30
    assert len(settings.scheduler.jobs) == 1
