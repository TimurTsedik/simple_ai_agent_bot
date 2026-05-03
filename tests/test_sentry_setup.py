import sys
import types
from typing import Any

from app.config.settingsModels import SettingsModel
from app.observability.sentrySetup import captureSentryException
from app.observability.sentrySetup import configureSentry


class _DummyLogger:
    def __init__(self) -> None:
        self.infoMessages: list[str] = []
        self.errorMessages: list[str] = []

    def info(self, in_message: str) -> None:
        self.infoMessages.append(in_message)

    def error(self, in_message: str) -> None:
        self.errorMessages.append(in_message)


def _buildSettings(in_sentryPatch: dict[str, Any]) -> SettingsModel:
    settingsData: dict[str, Any] = {
        "app": {
            "appName": "test-app",
            "environment": "test",
            "dataRootPath": "./data",
        },
        "telegram": {
            "pollingTimeoutSeconds": 10,
            "denyMessageText": "denied",
        },
        "models": {
            "openRouterBaseUrl": "https://openrouter.ai/api/v1",
            "primaryModel": "model-primary",
            "secondaryModel": "model-secondary",
            "tertiaryModel": "model-tertiary",
            "requestTimeoutSeconds": 45,
            "retryCountBeforeFallback": 2,
            "returnToPrimaryCooldownSeconds": 300,
        },
        "runtime": {
            "maxSteps": 5,
            "maxToolCalls": 5,
            "maxExecutionSeconds": 30,
            "maxToolOutputChars": 1000,
            "maxPromptChars": 5000,
            "recentMessagesLimit": 12,
            "sessionSummaryMaxChars": 2000,
            "skillSelectionMaxCount": 4,
            "toolCallHistoryWindowSize": 8,
            "maxSameToolSignatureInWindow": 3,
            "maxToolCallBlockedIterations": 3,
            "extraSecondsPerLlmError": 0,
            "maxExtraSecondsTotal": 0,
        },
        "security": {
            "webSessionCookieTtlSeconds": 3600,
            "maxAdminTokens": 3,
            "allowedReadOnlyPaths": ["./data"],
        },
        "logging": {
            "logsDirPath": "./data/logs",
            "runLogsFileName": "run.jsonl",
            "appLogsFileName": "app.log",
            "maxBytes": 10485760,
            "backupCount": 5,
        },
        "sentry": {
            "enabled": False,
            "dsn": "",
            "environment": "",
            "release": "",
            "tracesSampleRate": 0.0,
            "profilesSampleRate": 0.0,
            "sendDefaultPii": False,
        },
        "telegramBotToken": "tg-token",
        "openRouterApiKey": "or-key",
        "sessionCookieSecret": "cookie-secret-0123456789abcdef-XYZ",
        "adminRawTokens": ["token-one-12345678"],
    }
    settingsData["sentry"].update(in_sentryPatch)
    ret = SettingsModel.model_validate(settingsData)
    return ret


def testConfigureSentryInitializesSdkWhenEnabled() -> None:
    sentryModule = types.ModuleType("sentry_sdk")
    sentryModule.initCalls = []
    sentryModule.captureCalls = []

    def init(**in_kwargs: Any) -> None:
        sentryModule.initCalls.append(in_kwargs)

    def capture_exception(in_exception: Exception) -> None:
        sentryModule.captureCalls.append(in_exception)

    sentryModule.init = init
    sentryModule.capture_exception = capture_exception

    integrationsModule = types.ModuleType("sentry_sdk.integrations")
    fastApiModule = types.ModuleType("sentry_sdk.integrations.fastapi")
    loggingModule = types.ModuleType("sentry_sdk.integrations.logging")

    class FastApiIntegration:  # noqa: D401
        pass

    class LoggingIntegration:
        def __init__(self, level: int, event_level: int) -> None:
            self.level = level
            self.eventLevel = event_level

    fastApiModule.FastApiIntegration = FastApiIntegration
    loggingModule.LoggingIntegration = LoggingIntegration

    previousModules = {
        "sentry_sdk": sys.modules.get("sentry_sdk"),
        "sentry_sdk.integrations": sys.modules.get("sentry_sdk.integrations"),
        "sentry_sdk.integrations.fastapi": sys.modules.get("sentry_sdk.integrations.fastapi"),
        "sentry_sdk.integrations.logging": sys.modules.get("sentry_sdk.integrations.logging"),
    }
    sys.modules["sentry_sdk"] = sentryModule
    sys.modules["sentry_sdk.integrations"] = integrationsModule
    sys.modules["sentry_sdk.integrations.fastapi"] = fastApiModule
    sys.modules["sentry_sdk.integrations.logging"] = loggingModule

    try:
        settings = _buildSettings(
            in_sentryPatch={
                "enabled": True,
                "dsn": "https://examplePublicKey@o0.ingest.sentry.io/0",
                "environment": "production",
                "release": "v1.2.3",
                "tracesSampleRate": 0.2,
                "profilesSampleRate": 0.1,
                "sendDefaultPii": True,
            }
        )
        logger = _DummyLogger()

        didConfigure = configureSentry(in_settings=settings, in_logger=logger)
        captureSentryException(in_exception=RuntimeError("test error"))
    finally:
        for moduleName, moduleValue in previousModules.items():
            if moduleValue is None:
                sys.modules.pop(moduleName, None)
            else:
                sys.modules[moduleName] = moduleValue

    assert didConfigure is True
    assert len(sentryModule.initCalls) == 1
    initCall = sentryModule.initCalls[0]
    assert initCall["dsn"] == "https://examplePublicKey@o0.ingest.sentry.io/0"
    assert initCall["environment"] == "production"
    assert initCall["release"] == "v1.2.3"
    assert initCall["traces_sample_rate"] == 0.2
    assert initCall["profiles_sample_rate"] == 0.1
    assert initCall["send_default_pii"] is True
    assert len(sentryModule.captureCalls) == 1
    assert "Sentry successfully configured." in logger.infoMessages


def testConfigureSentrySkipsWhenDisabled() -> None:
    settings = _buildSettings(in_sentryPatch={"enabled": False})
    logger = _DummyLogger()
    didConfigure = configureSentry(in_settings=settings, in_logger=logger)
    assert didConfigure is False
    assert "Sentry is disabled by configuration." in logger.infoMessages
