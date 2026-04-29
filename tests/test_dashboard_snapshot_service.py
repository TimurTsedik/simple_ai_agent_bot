import time
from tempfile import TemporaryDirectory

from app.application.services.dashboardSnapshotService import DashboardSnapshotService
from app.application.services.modelStatsService import ModelStatsService
from app.application.useCases.getRunListUseCase import GetRunListUseCase
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
from app.observability.stores.jsonRunRepository import JsonRunRepository
from app.skills.stores.markdownSkillStore import MarkdownSkillStore
from app.tools.registry.toolRegistry import ToolRegistry


def _buildSettings(in_dataRoot: str) -> SettingsModel:
    ret = SettingsModel(
        app=AppSettings(appName="test", environment="test", dataRootPath=in_dataRoot),
        telegram=TelegramSettings(
            pollingTimeoutSeconds=10,
            allowedUserIds=[1],
            denyMessageText="deny",
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


def testDashboardSnapshotServiceUsesTtlCache() -> None:
    with TemporaryDirectory() as tempDir:
        settings = _buildSettings(in_dataRoot=tempDir)
        runRepository = JsonRunRepository(in_dataRootPath=tempDir)
        getRunListUseCase = GetRunListUseCase(in_runRepository=runRepository)
        skillStore = MarkdownSkillStore(in_skillsDirPath=settings.skills.skillsDirPath)
        modelStatsService = ModelStatsService(in_dataRootPath=tempDir)
        service = DashboardSnapshotService(
            in_settings=settings,
            in_getRunListUseCase=getRunListUseCase,
            in_toolRegistry=ToolRegistry(in_toolDefinitions=[]),
            in_skillStore=skillStore,
            in_modelStatsService=modelStatsService,
            in_ttlSeconds=0.5,
        )
        firstStats = service.getDashboardStatsSnapshot()
        secondStats = service.getDashboardStatsSnapshot()
        assert firstStats is secondStats
        time.sleep(0.55)
        thirdStats = service.getDashboardStatsSnapshot()
        assert thirdStats is not secondStats
