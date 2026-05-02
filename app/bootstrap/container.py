from dataclasses import dataclass
from pathlib import Path
import shutil

import requests

from app.application.services.dashboardSnapshotService import DashboardSnapshotService
from app.application.services.modelStatsService import ModelStatsService
from app.application.useCases.getGitDiffUseCase import GetGitDiffUseCase
from app.application.useCases.getGitStatusUseCase import GetGitStatusUseCase
from app.application.useCases.getLogsUseCase import GetLogsUseCase
from app.application.useCases.getRunDetailsUseCase import GetRunDetailsUseCase
from app.application.useCases.getRunListUseCase import GetRunListUseCase
from app.application.useCases.createTelegramUserUseCase import CreateTelegramUserUseCase
from app.application.useCases.handleIncomingTelegramMessageUseCase import (
    HandleIncomingTelegramMessageUseCase,
)
from app.application.useCases.runAgentUseCase import RunAgentUseCase
from app.common.contouringRequestsPolicy import ContouringRequestsPolicy
from app.common.memoryPrincipal import formatTelegramUserMemoryPrincipal
from app.common.memoryPrincipal import parseTelegramUserIdFromMemoryPrincipal
from app.common.structuredLogger import createAppLogger
from app.common.structuredLogger import writeJsonlEvent
from app.config.settingsLoader import loadSettings
from app.config.settingsModels import SettingsModel
from app.domain.policies.memoryPolicy import MemoryPolicy
from app.domain.policies.stopPolicy import StopPolicy
from app.domain.protocols.loggerProtocol import LoggerProtocol
from app.integrations.git.gitService import GitService
from app.integrations.telegram.telegramMessageChunker import splitTelegramMessage
from app.integrations.telegram.schedulerTelegramFormatter import formatReminderTelegramMessage
from app.integrations.telegram.schedulerTelegramFormatter import formatSchedulerTelegramMessage
from app.integrations.telegram.telegramPollingRunner import TelegramPollingRunner
from app.integrations.telegram.telegramUpdateHandler import TelegramUpdateHandler
from app.integrations.telegram.telegramFileDownloader import TelegramFileDownloader
from app.memory.services.memoryService import MemoryService
from app.memory.stores.markdownMemoryStore import MarkdownMemoryStore
from app.models.providers.openRouterClient import OpenRouterClient
from app.models.services.llmService import LlmService
from app.observability.stores.jsonRunRepository import JsonRunRepository
from app.reminders.reminderConfigStore import ReminderConfigStore
from app.runtime.agentLoop import AgentLoop
from app.runtime.llmRoutingPlanResolver import LlmRoutingPlanResolver
from app.runtime.outputParser import OutputParser
from app.runtime.promptBuilder import PromptBuilder
from app.runtime.routePlanParser import RoutePlanParser
from app.runtime.toolExecutionCoordinator import ToolExecutionCoordinator
from app.scheduler.schedulerRunner import SchedulerRunner
from app.integrations.speech.fasterWhisperTranscriber import FasterWhisperTranscriber
from app.skills.services.skillSelectorRules import SkillSelectorRules
from app.skills.services.skillService import SkillService
from app.skills.stores.markdownSkillStore import MarkdownSkillStore
from app.tools.registry.toolMetadataRenderer import ToolMetadataRenderer
from app.tools.registry.toolRegistry import ToolRegistry
from app.tools.services.toolFactory import buildToolRegistry
from app.users.telegramUserRegistryStore import TelegramUserRegistryStore


@dataclass
class ApplicationContainer:
    settings: SettingsModel
    logger: LoggerProtocol
    toolRegistry: ToolRegistry
    toolExecutionCoordinator: ToolExecutionCoordinator
    contouringHttpPolicy: ContouringRequestsPolicy
    runAgentUseCase: RunAgentUseCase
    schedulerRunner: SchedulerRunner | None
    telegramPollingRunner: TelegramPollingRunner
    telegramUpdateHandler: TelegramUpdateHandler
    getLogsUseCase: GetLogsUseCase
    getRunListUseCase: GetRunListUseCase
    getRunDetailsUseCase: GetRunDetailsUseCase
    getGitStatusUseCase: GetGitStatusUseCase
    getGitDiffUseCase: GetGitDiffUseCase
    skillStore: MarkdownSkillStore
    dashboardSnapshotService: DashboardSnapshotService
    modelStatsService: ModelStatsService
    telegramUserRegistryStore: TelegramUserRegistryStore
    createTelegramUserUseCase: CreateTelegramUserUseCase


def buildApplicationContainer(in_configPath: str) -> ApplicationContainer:
    settings = loadSettings(in_configPath=in_configPath)
    logger = createAppLogger(in_loggingSettings=settings.logging)
    promptBuilder = PromptBuilder(
        in_runtimeSettings=settings.runtime,
        in_displayTimeZoneName=settings.app.displayTimeZone,
    )
    outputParser = OutputParser()
    stopPolicy = StopPolicy(in_runtimeSettings=settings.runtime)
    memoryStore = MarkdownMemoryStore(in_memorySettings=settings.memory)
    adminMemoryPrincipalId = formatTelegramUserMemoryPrincipal(
        in_telegramUserId=settings.adminTelegramUserId,
    )
    telegramUserRegistryStore = TelegramUserRegistryStore(
        in_registryFilePath=str(settings.app.usersRegistryPath),
    )
    createTelegramUserUseCase = CreateTelegramUserUseCase(
        in_registry_store=telegramUserRegistryStore,
        in_memorySettings=settings.memory,
    )
    toolRegistry = buildToolRegistry(in_settings=settings, in_memoryStore=memoryStore)
    toolMetadataRenderer = ToolMetadataRenderer()
    toolExecutionCoordinator = ToolExecutionCoordinator(
        in_toolRegistry=toolRegistry,
        in_maxToolOutputChars=settings.runtime.maxToolOutputChars,
    )
    contouringHttpPolicy = ContouringRequestsPolicy(
        in_maxConcurrentRequests=settings.telegram.outboundHttpMaxConcurrent,
        in_timeoutSeconds=float(settings.telegram.outboundHttpDefaultTimeoutSeconds),
        in_maxRetries=settings.telegram.outboundHttpMaxRetries,
    )
    openRouterClient = OpenRouterClient(
        in_baseUrl=settings.models.openRouterBaseUrl,
        in_apiKey=settings.openRouterApiKey,
        in_timeoutSeconds=settings.models.requestTimeoutSeconds,
    )
    modelStatsService = ModelStatsService(in_dataRootPath=settings.app.dataRootPath)
    llmClient = LlmService(
        in_openRouterClient=openRouterClient,
        in_modelSettings=settings.models,
        in_loggingSettings=settings.logging,
        in_modelStatsService=modelStatsService,
    )
    _ensureSkillsDirInitialized(
        in_skillsDirPath=settings.skills.skillsDirPath,
    )
    skillStore = MarkdownSkillStore(in_skillsDirPath=settings.skills.skillsDirPath)
    skillSelectorRules = SkillSelectorRules()
    skillService = SkillService(
        in_skillStore=skillStore,
        in_skillSelectorRules=skillSelectorRules,
        in_skillSelectionMaxCount=settings.runtime.skillSelectionMaxCount,
    )
    memoryPolicy = MemoryPolicy()
    memoryService = MemoryService(
        in_memoryStore=memoryStore,
        in_memoryPolicy=memoryPolicy,
        in_recentMessagesLimit=settings.runtime.recentMessagesLimit,
        in_sessionSummaryMaxChars=settings.runtime.sessionSummaryMaxChars,
    )
    runRepository = JsonRunRepository(in_dataRootPath=settings.app.dataRootPath)
    agentLoop = AgentLoop(
        in_llmClient=llmClient,
        in_promptBuilder=promptBuilder,
        in_outputParser=outputParser,
        in_stopPolicy=stopPolicy,
        in_modelSettings=settings.models,
        in_toolExecutionCoordinator=toolExecutionCoordinator,
        in_toolMetadataRenderer=toolMetadataRenderer,
        in_toolRegistry=toolRegistry,
    )
    routingPlanResolver = LlmRoutingPlanResolver(
        in_llmClient=llmClient,
        in_promptBuilder=promptBuilder,
        in_routePlanParser=RoutePlanParser(),
        in_skillService=skillService,
        in_toolRegistry=toolRegistry,
        in_modelSettings=settings.models,
    )
    runAgentUseCase = RunAgentUseCase(
        in_agentLoop=agentLoop,
        in_routingPlanResolver=routingPlanResolver,
        in_memoryService=memoryService,
        in_runRepository=runRepository,
        in_settings=settings,
    )

    def runInternalForScheduler(
        in_sessionId: str,
        in_message: str,
        in_memoryPrincipalId: str,
    ) -> tuple[str, str]:
        memory_principal = str(in_memoryPrincipalId or "").strip()
        if memory_principal == "":
            memory_principal = adminMemoryPrincipalId
        ret: tuple[str, str]
        try:
            runResult = runAgentUseCase.execute(
                in_sessionId=in_sessionId,
                in_inputMessage=in_message,
                in_memoryPrincipalId=memory_principal,
            )
            finalAnswer = runResult.finalAnswer or "Пустой ответ агента."
            ret = (runResult.runId, finalAnswer)
        finally:
            memoryService.discardScheduledInternalSessionContext(in_sessionId=in_sessionId)
        return ret

    def notifySchedulerResultToTelegram(
        in_jobId: str,
        in_sessionId: str,
        in_runId: str,
        in_finalAnswer: str,
        in_ownerMemoryPrincipalId: str,
    ) -> None:
        formattedText = formatSchedulerTelegramMessage(
            in_jobId=in_jobId,
            in_sessionId=in_sessionId,
            in_runId=in_runId,
            in_finalAnswer=in_finalAnswer,
        )
        chunkSize = 3500
        textChunks = splitTelegramMessage(
            in_text=formattedText,
            in_maxChars=chunkSize,
            in_preferSeparator="\n---\n",
        )
        apiUrl = f"https://api.telegram.org/bot{settings.telegramBotToken}/sendMessage"
        registered_ids = telegramUserRegistryStore.listRegisteredTelegramUserIds()
        owner_user_id = parseTelegramUserIdFromMemoryPrincipal(
            in_memoryPrincipalId=str(in_ownerMemoryPrincipalId or ""),
        )
        target_chat_ids: list[int]
        if owner_user_id is not None and owner_user_id in registered_ids:
            target_chat_ids = [int(owner_user_id)]
        else:
            target_chat_ids = [int(settings.adminTelegramUserId)]
        for chatId in sorted(target_chat_ids):
            for index, chunk in enumerate(textChunks, start=1):
                chunkPrefix = f"[{index}/{len(textChunks)}]\n" if len(textChunks) > 1 else ""
                try:
                    contouringHttpPolicy.post(
                        apiUrl,
                        in_json={"chat_id": int(chatId), "text": f"{chunkPrefix}{chunk}"},
                        in_timeoutSeconds=15.0,
                    ).raise_for_status()
                    writeJsonlEvent(
                        in_loggingSettings=settings.logging,
                        in_eventType="scheduler_result_sent_to_telegram",
                        in_payload={
                            "jobId": in_jobId,
                            "sessionId": in_sessionId,
                            "runId": in_runId,
                            "chatId": int(chatId),
                            "messageChars": len(chunk),
                            "chunkIndex": index,
                            "chunkTotal": len(textChunks),
                            "chunkMaxChars": chunkSize,
                        },
                    )
                except requests.RequestException as in_exc:
                    writeJsonlEvent(
                        in_loggingSettings=settings.logging,
                        in_eventType="scheduler_result_telegram_send_error",
                        in_payload={
                            "jobId": in_jobId,
                            "sessionId": in_sessionId,
                            "runId": in_runId,
                            "chatId": int(chatId),
                            "chunkIndex": index,
                            "chunkTotal": len(textChunks),
                            "error": str(in_exc),
                        },
                    )

    def notifyReminderToTelegram(
        in_reminderId: str,
        in_message: str,
        in_ownerMemoryPrincipalId: str,
    ) -> None:
        formattedText = formatReminderTelegramMessage(
            in_reminderId=in_reminderId,
            in_message=in_message,
        )
        chunkSize = 3500
        textChunks = splitTelegramMessage(
            in_text=formattedText,
            in_maxChars=chunkSize,
            in_preferSeparator="\n---\n",
        )
        apiUrl = f"https://api.telegram.org/bot{settings.telegramBotToken}/sendMessage"
        registered_ids = telegramUserRegistryStore.listRegisteredTelegramUserIds()
        owner_user_id = parseTelegramUserIdFromMemoryPrincipal(
            in_memoryPrincipalId=str(in_ownerMemoryPrincipalId or ""),
        )
        target_chat_ids: list[int]
        if owner_user_id is not None and owner_user_id in registered_ids:
            target_chat_ids = [int(owner_user_id)]
        else:
            target_chat_ids = [int(settings.adminTelegramUserId)]
        for chatId in sorted(target_chat_ids):
            for index, chunk in enumerate(textChunks, start=1):
                chunkPrefix = f"[{index}/{len(textChunks)}]\n" if len(textChunks) > 1 else ""
                contouringHttpPolicy.post(
                    apiUrl,
                    in_json={"chat_id": int(chatId), "text": f"{chunkPrefix}{chunk}"},
                    in_timeoutSeconds=15.0,
                ).raise_for_status()
                writeJsonlEvent(
                    in_loggingSettings=settings.logging,
                    in_eventType="scheduler_reminder_sent_to_telegram",
                    in_payload={
                        "reminderId": in_reminderId,
                        "chatId": int(chatId),
                        "messageChars": len(chunk),
                        "chunkIndex": index,
                        "chunkTotal": len(textChunks),
                        "chunkMaxChars": chunkSize,
                    },
                )

    reminderConfigStore = ReminderConfigStore(
        in_memorySettings=settings.memory,
    )

    def removeCompletedReminderFromConfig(
        in_reminderId: str,
        in_ownerMemoryPrincipalId: str,
    ) -> bool:
        ret: bool
        ret = reminderConfigStore.deleteReminderForTenant(
            in_reminderId=in_reminderId,
            in_ownerMemoryPrincipalId=in_ownerMemoryPrincipalId,
        )
        return ret

    schedulerRunner: SchedulerRunner | None
    if settings.scheduler.enabled is True:
        writeJsonlEvent(
            in_loggingSettings=settings.logging,
            in_eventType="scheduler_config_enabled",
            in_payload={
                "tickSeconds": int(settings.scheduler.tickSeconds),
                "adminTenantSchedulesYamlPath": settings.adminTenantSchedulesYamlPath,
                "memoryRootPath": settings.memory.memoryRootPath,
            },
        )
        schedulerRunner = SchedulerRunner(
            in_schedulerSettings=settings.scheduler,
            in_loggingSettings=settings.logging,
            in_dataRootPath=settings.app.dataRootPath,
            in_memoryRootPath=settings.memory.memoryRootPath,
            in_adminTelegramUserId=int(settings.adminTelegramUserId),
            in_runInternalCallable=runInternalForScheduler,
            in_onRunCompletedCallable=notifySchedulerResultToTelegram,
            in_onReminderTriggeredCallable=notifyReminderToTelegram,
            in_onReminderCompletedCallable=removeCompletedReminderFromConfig,
            in_timeZoneName=settings.app.displayTimeZone,
        )
    else:
        writeJsonlEvent(
            in_loggingSettings=settings.logging,
            in_eventType="scheduler_config_disabled",
            in_payload={},
        )
        schedulerRunner = None

    def getAllowedTelegramUserIds() -> set[int]:
        ret_ids = telegramUserRegistryStore.listRegisteredTelegramUserIds()
        return ret_ids

    handleIncomingTelegramMessageUseCase = HandleIncomingTelegramMessageUseCase(
        in_get_allowed_user_ids=getAllowedTelegramUserIds,
        in_denyMessageText=settings.telegram.denyMessageText,
        in_logger=logger,
        in_runAgentUseCase=runAgentUseCase,
        in_memoryService=memoryService,
        in_runtimeSettings=settings.runtime,
    )
    telegramFileDownloader = TelegramFileDownloader(
        in_telegramBotToken=settings.telegramBotToken,
        in_httpPolicy=contouringHttpPolicy,
        in_logger=logger,
    )
    transcriberDownloadRoot = str(Path(settings.app.dataRootPath).resolve() / "models")
    voiceTranscriber = FasterWhisperTranscriber(
        in_modelName=str(getattr(settings.telegram, "voiceModelName", "") or "small"),
        in_device="cpu",
        in_computeType=str(getattr(settings.telegram, "voiceComputeType", "") or "int8"),
        in_downloadRoot=transcriberDownloadRoot,
    )
    updateHandler = TelegramUpdateHandler(
        in_handleIncomingTelegramMessageUseCase=handleIncomingTelegramMessageUseCase,
        in_settings=settings,
        in_logger=logger,
        in_telegramFileDownloader=telegramFileDownloader,
        in_voiceTranscriber=voiceTranscriber,
    )
    telegramPollingRunner = TelegramPollingRunner(
        in_settings=settings,
        in_logger=logger,
        in_updateHandler=updateHandler,
        in_contouringHttpPolicy=contouringHttpPolicy,
    )
    getLogsUseCase = GetLogsUseCase(in_loggingSettings=settings.logging)
    getRunListUseCase = GetRunListUseCase(
        in_runRepository=runRepository,
        in_allowedSessionId=adminMemoryPrincipalId,
    )
    getRunDetailsUseCase = GetRunDetailsUseCase(
        in_runRepository=runRepository,
        in_allowedSessionId=adminMemoryPrincipalId,
    )
    repoRootPath = str(Path(__file__).resolve().parents[2])
    gitService = GitService(in_repoRootPath=repoRootPath)
    getGitStatusUseCase = GetGitStatusUseCase(in_gitService=gitService)
    getGitDiffUseCase = GetGitDiffUseCase(in_gitService=gitService)
    dashboardSnapshotService = DashboardSnapshotService(
        in_settings=settings,
        in_getRunListUseCase=getRunListUseCase,
        in_toolRegistry=toolRegistry,
        in_skillStore=skillStore,
        in_modelStatsService=modelStatsService,
        in_ttlSeconds=2.0,
    )
    ret = ApplicationContainer(
        settings=settings,
        logger=logger,
        toolRegistry=toolRegistry,
        toolExecutionCoordinator=toolExecutionCoordinator,
        contouringHttpPolicy=contouringHttpPolicy,
        runAgentUseCase=runAgentUseCase,
        schedulerRunner=schedulerRunner,
        telegramPollingRunner=telegramPollingRunner,
        telegramUpdateHandler=updateHandler,
        getLogsUseCase=getLogsUseCase,
        getRunListUseCase=getRunListUseCase,
        getRunDetailsUseCase=getRunDetailsUseCase,
        getGitStatusUseCase=getGitStatusUseCase,
        getGitDiffUseCase=getGitDiffUseCase,
        skillStore=skillStore,
        dashboardSnapshotService=dashboardSnapshotService,
        modelStatsService=modelStatsService,
        telegramUserRegistryStore=telegramUserRegistryStore,
        createTelegramUserUseCase=createTelegramUserUseCase,
    )
    return ret


def _ensureSkillsDirInitialized(in_skillsDirPath: str) -> None:
    targetDir = Path(in_skillsDirPath)
    if targetDir.is_absolute() is False:
        targetDir = targetDir.resolve()
    targetDir.mkdir(parents=True, exist_ok=True)

    sourceDir = (Path(__file__).resolve().parents[1] / "skills" / "assets").resolve()
    if sourceDir.exists() is False or sourceDir.is_dir() is False:
        return

    for sourcePath in sourceDir.glob("*.md"):
        if sourcePath.is_file() is False:
            continue
        targetPath = targetDir / sourcePath.name
        if targetPath.exists() is True:
            continue
        try:
            shutil.copyfile(sourcePath, targetPath)
        except OSError:
            # Best-effort initialization; service can still run without copying.
            continue
