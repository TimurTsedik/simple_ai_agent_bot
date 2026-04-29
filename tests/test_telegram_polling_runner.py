import time
from typing import Any

from app.common.contouringRequestsPolicy import ContouringRequestsPolicy
from app.config.settingsModels import (
    AppSettings,
    LoggingSettings,
    MemorySettings,
    ModelSettings,
    RuntimeSettings,
    SecuritySettings,
    SettingsModel,
    SkillsSettings,
    TelegramSettings,
)
from app.integrations.telegram.telegramPollingRunner import TelegramPollingRunner


class FakeLogger:
    def __init__(self) -> None:
        self.errors: list[str] = []

    def info(self, in_message: str) -> None:
        _ = in_message

    def error(self, in_message: str) -> None:
        self.errors.append(in_message)


class FakeUpdateHandler:
    def __init__(self, in_delaySeconds: float = 0.0) -> None:
        self._delaySeconds = in_delaySeconds

    def handleUpdate(self, in_updateData: dict[str, Any]) -> tuple[int | None, str | None]:
        _ = in_updateData
        time.sleep(self._delaySeconds)
        ret = (111, "done")
        return ret


def _buildSettings() -> SettingsModel:
    ret = SettingsModel(
        app=AppSettings(appName="test", environment="test", dataRootPath="./data"),
        telegram=TelegramSettings(
            pollingTimeoutSeconds=10,
            allowedUserIds=[1],
            denyMessageText="deny",
            digestChannelUsernames=["channel_one"],
        ),
        models=ModelSettings(
            openRouterBaseUrl="https://openrouter.ai/api/v1",
            primaryModel="m1",
            secondaryModel="m2",
            tertiaryModel="m3",
            requestTimeoutSeconds=45,
            retryCountBeforeFallback=2,
            returnToPrimaryCooldownSeconds=300,
        ),
        runtime=RuntimeSettings(
            maxSteps=5,
            maxToolCalls=5,
            maxExecutionSeconds=30,
            maxToolOutputChars=1000,
            maxPromptChars=5000,
            recentMessagesLimit=12,
            sessionSummaryMaxChars=2000,
            skillSelectionMaxCount=4,
            extraSecondsPerLlmError=0,
            maxExtraSecondsTotal=0,
        ),
        security=SecuritySettings(
            webSessionCookieTtlSeconds=3600,
            maxAdminTokens=3,
            allowedReadOnlyPaths=["./data"],
        ),
        logging=LoggingSettings(
            logsDirPath="./data/logs",
            runLogsFileName="run.jsonl",
            appLogsFileName="app.log",
            maxBytes=10485760,
            backupCount=5,
        ),
        skills=SkillsSettings(skillsDirPath="./app/skills/assets"),
        memory=MemorySettings(
            memoryRootPath="./data/memory",
            longTermFileName="long_term.md",
            sessionSummaryFileName="summary.md",
            recentMessagesFileName="recent.md",
        ),
        telegramBotToken="tg-token",
        openRouterApiKey="or-key",
        sessionCookieSecret="cookie-secret-0123456789abcdef-XYZ",
        adminRawTokens=["token-one-12345678"],
    )
    return ret


def _buildHttpPolicy() -> ContouringRequestsPolicy:
    ret = ContouringRequestsPolicy(
        in_maxConcurrentRequests=2,
        in_timeoutSeconds=15.0,
        in_maxRetries=0,
    )
    return ret


class _FakeResponse:
    def raise_for_status(self) -> None:
        return None


def testPollingRunnerSendsTypingForPrivateMessage(monkeypatch) -> None:
    calledUrls: list[str] = []

    def fakePost(in_url: str, json: dict[str, Any], timeout: int):  # noqa: ANN201
        _ = json
        _ = timeout
        calledUrls.append(in_url)
        return _FakeResponse()

    monkeypatch.setattr("app.common.contouringRequestsPolicy.requests.post", fakePost)
    runner = TelegramPollingRunner(
        in_settings=_buildSettings(),
        in_logger=FakeLogger(),
        in_updateHandler=FakeUpdateHandler(in_delaySeconds=0.05),
        in_contouringHttpPolicy=_buildHttpPolicy(),
        in_typingIntervalSeconds=0.2,
    )
    runner._handleUpdatesPayload(
        in_payload={
            "result": [
                {
                    "update_id": 1,
                    "message": {
                        "text": "hello",
                        "chat": {"id": 111, "type": "private"},
                    },
                }
            ]
        }
    )

    assert any("/sendChatAction" in item for item in calledUrls)
    assert any("/sendMessage" in item for item in calledUrls)


def testPollingRunnerSkipsTypingForNonPrivateMessage(monkeypatch) -> None:
    calledUrls: list[str] = []

    def fakePost(in_url: str, json: dict[str, Any], timeout: int):  # noqa: ANN201
        _ = json
        _ = timeout
        calledUrls.append(in_url)
        return _FakeResponse()

    monkeypatch.setattr("app.common.contouringRequestsPolicy.requests.post", fakePost)
    runner = TelegramPollingRunner(
        in_settings=_buildSettings(),
        in_logger=FakeLogger(),
        in_updateHandler=FakeUpdateHandler(in_delaySeconds=0.0),
        in_contouringHttpPolicy=_buildHttpPolicy(),
    )
    runner._handleUpdatesPayload(
        in_payload={
            "result": [
                {
                    "update_id": 1,
                    "message": {
                        "text": "hello",
                        "chat": {"id": -100500, "type": "group"},
                    },
                }
            ]
        }
    )

    assert all("/sendChatAction" not in item for item in calledUrls)
    assert any("/sendMessage" in item for item in calledUrls)
