"""Регрессия: skills.skillsDirPath на каталог из образа перенаправляется в data/skills."""

from pathlib import Path

from app.bootstrap import container as containerPackage
from app.bootstrap.container import _rewriteSkillsDirIfPointsAtBundledAssets
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
    ToolsSettings,
)


def testRewriteSkillsDirWhenConfigPointsAtBundledAssets() -> None:
    bundledResolved = (
        Path(containerPackage.__file__).resolve().parents[1] / "skills" / "assets"
    ).resolve()
    settings = SettingsModel(
        app=AppSettings(
            appName="t",
            environment="test",
            dataRootPath="./data",
            displayTimeZone="UTC",
        ),
        telegramBotToken="x",
        openRouterApiKey="y",
        sessionCookieSecret="0" * 32,
        telegram=TelegramSettings(pollingTimeoutSeconds=30, denyMessageText="x"),
        models=ModelSettings(
            openRouterBaseUrl="https://x",
            primaryModel="a",
            secondaryModel="b",
            tertiaryModel="c",
            requestTimeoutSeconds=45,
            retryCountBeforeFallback=0,
            returnToPrimaryCooldownSeconds=300,
        ),
        runtime=RuntimeSettings(
            maxSteps=2,
            maxToolCalls=0,
            maxExecutionSeconds=10,
            maxToolOutputChars=1000,
            maxPromptChars=3000,
            recentMessagesLimit=4,
            sessionSummaryMaxChars=2000,
            skillSelectionMaxCount=4,
        ),
        security=SecuritySettings(
            webSessionCookieTtlSeconds=3600,
            maxAdminTokens=2,
            allowedReadOnlyPaths=[],
        ),
        logging=LoggingSettings(
            logsDirPath="./data/logs",
            runLogsFileName="run.jsonl",
            appLogsFileName="app.log",
            maxBytes=10485760,
            backupCount=3,
        ),
        skills=SkillsSettings(skillsDirPath=str(bundledResolved)),
        memory=MemorySettings(),
        tools=ToolsSettings(),
    )
    did = _rewriteSkillsDirIfPointsAtBundledAssets(in_settings=settings)
    assert did is True
    assert "data" in settings.skills.skillsDirPath.replace("\\", "/")
    assert settings.skills.skillsDirPath.endswith("skills")


def testNoRewriteWhenSkillsDirIsData() -> None:
    settings = SettingsModel(
        app=AppSettings(
            appName="t",
            environment="test",
            dataRootPath="./data",
            displayTimeZone="UTC",
        ),
        telegramBotToken="x",
        openRouterApiKey="y",
        sessionCookieSecret="0" * 32,
        telegram=TelegramSettings(pollingTimeoutSeconds=30, denyMessageText="x"),
        models=ModelSettings(
            openRouterBaseUrl="https://x",
            primaryModel="a",
            secondaryModel="b",
            tertiaryModel="c",
            requestTimeoutSeconds=45,
            retryCountBeforeFallback=0,
            returnToPrimaryCooldownSeconds=300,
        ),
        runtime=RuntimeSettings(
            maxSteps=2,
            maxToolCalls=0,
            maxExecutionSeconds=10,
            maxToolOutputChars=1000,
            maxPromptChars=3000,
            recentMessagesLimit=4,
            sessionSummaryMaxChars=2000,
            skillSelectionMaxCount=4,
        ),
        security=SecuritySettings(
            webSessionCookieTtlSeconds=3600,
            maxAdminTokens=2,
            allowedReadOnlyPaths=[],
        ),
        logging=LoggingSettings(
            logsDirPath="./data/logs",
            runLogsFileName="run.jsonl",
            appLogsFileName="app.log",
            maxBytes=10485760,
            backupCount=3,
        ),
        skills=SkillsSettings(skillsDirPath="./data/skills"),
        memory=MemorySettings(),
        tools=ToolsSettings(),
    )
    pathBefore = settings.skills.skillsDirPath
    did = _rewriteSkillsDirIfPointsAtBundledAssets(in_settings=settings)
    assert did is False
    assert settings.skills.skillsDirPath == pathBefore
