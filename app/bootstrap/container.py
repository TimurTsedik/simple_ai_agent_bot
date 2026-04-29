from dataclasses import dataclass
from pathlib import Path

import requests

from app.application.services.dashboardSnapshotService import DashboardSnapshotService
from app.application.services.modelStatsService import ModelStatsService
from app.application.useCases.getGitDiffUseCase import GetGitDiffUseCase
from app.application.useCases.getGitStatusUseCase import GetGitStatusUseCase
from app.application.useCases.getLogsUseCase import GetLogsUseCase
from app.application.useCases.getRunDetailsUseCase import GetRunDetailsUseCase
from app.application.useCases.getRunListUseCase import GetRunListUseCase
from app.application.useCases.handleIncomingTelegramMessageUseCase import (
    HandleIncomingTelegramMessageUseCase,
)
from app.application.useCases.runAgentUseCase import RunAgentUseCase
from app.common.contouringRequestsPolicy import ContouringRequestsPolicy
from app.common.structuredLogger import createAppLogger
from app.common.structuredLogger import writeJsonlEvent
from app.config.settingsLoader import loadSettings
from app.config.settingsModels import SettingsModel
from app.domain.policies.memoryPolicy import MemoryPolicy
from app.domain.policies.stopPolicy import StopPolicy
from app.domain.protocols.loggerProtocol import LoggerProtocol
from app.integrations.git.gitService import GitService
from app.integrations.telegram.telegramMessageChunker import splitTelegramMessage
from app.integrations.telegram.telegramPollingRunner import TelegramPollingRunner
from app.integrations.telegram.telegramUpdateHandler import TelegramUpdateHandler
from app.memory.services.memoryService import MemoryService
from app.memory.stores.markdownMemoryStore import MarkdownMemoryStore
from app.models.providers.openRouterClient import OpenRouterClient
from app.models.services.llmService import LlmService
from app.observability.stores.jsonRunRepository import JsonRunRepository
from app.runtime.agentLoop import AgentLoop
from app.runtime.outputParser import OutputParser
from app.runtime.promptBuilder import PromptBuilder
from app.runtime.toolExecutionCoordinator import ToolExecutionCoordinator
from app.scheduler.schedulerRunner import SchedulerRunner
from app.skills.services.skillSelectorRules import SkillSelectorRules
from app.skills.services.skillService import SkillService
from app.skills.stores.markdownSkillStore import MarkdownSkillStore
from app.tools.registry.toolMetadataRenderer import ToolMetadataRenderer
from app.tools.registry.toolRegistry import ToolRegistry
from app.tools.services.toolFactory import buildToolRegistry


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


def buildApplicationContainer(in_configPath: str) -> ApplicationContainer:
    settings = loadSettings(in_configPath=in_configPath)
    logger = createAppLogger(in_loggingSettings=settings.logging)
    promptBuilder = PromptBuilder(in_runtimeSettings=settings.runtime)
    outputParser = OutputParser()
    stopPolicy = StopPolicy(in_runtimeSettings=settings.runtime)
    memoryStore = MarkdownMemoryStore(in_memorySettings=settings.memory)
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
    runAgentUseCase = RunAgentUseCase(
        in_agentLoop=agentLoop,
        in_skillService=skillService,
        in_memoryService=memoryService,
        in_runRepository=runRepository,
        in_settings=settings,
    )

    def runInternalForScheduler(in_sessionId: str, in_message: str) -> tuple[str, str]:
        runResult = runAgentUseCase.execute(
            in_sessionId=in_sessionId,
            in_inputMessage=in_message,
        )
        finalAnswer = runResult.finalAnswer or "Пустой ответ агента."
        ret = (runResult.runId, finalAnswer)
        return ret

    def notifySchedulerResultToTelegram(
        in_jobId: str,
        in_sessionId: str,
        in_runId: str,
        in_finalAnswer: str,
    ) -> None:
        headerText = (
            f"Расписание: {in_jobId}\n"
            f"Сессия: {in_sessionId}\n"
            f"RunId: {in_runId}\n"
        )
        bodyText = str(in_finalAnswer or "").strip()
        formattedText = headerText + "\n" + bodyText if bodyText else headerText
        chunkSize = 3500
        textChunks = splitTelegramMessage(
            in_text=formattedText,
            in_maxChars=chunkSize,
            in_preferSeparator="\n---\n",
        )
        apiUrl = f"https://api.telegram.org/bot{settings.telegramBotToken}/sendMessage"
        for chatId in settings.telegram.allowedUserIds:
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

    schedulerRunner: SchedulerRunner | None
    if settings.scheduler.enabled is True:
        writeJsonlEvent(
            in_loggingSettings=settings.logging,
            in_eventType="scheduler_config_enabled",
            in_payload={
                "tickSeconds": int(settings.scheduler.tickSeconds),
                "jobCount": len(settings.scheduler.jobs),
                "schedulesConfigPath": settings.scheduler.schedulesConfigPath,
            },
        )
        schedulerRunner = SchedulerRunner(
            in_schedulerSettings=settings.scheduler,
            in_loggingSettings=settings.logging,
            in_dataRootPath=settings.app.dataRootPath,
            in_runInternalCallable=runInternalForScheduler,
            in_onRunCompletedCallable=notifySchedulerResultToTelegram,
        )
    else:
        writeJsonlEvent(
            in_loggingSettings=settings.logging,
            in_eventType="scheduler_config_disabled",
            in_payload={},
        )
        schedulerRunner = None

    handleIncomingTelegramMessageUseCase = HandleIncomingTelegramMessageUseCase(
        in_allowedUserIds=settings.telegram.allowedUserIds,
        in_denyMessageText=settings.telegram.denyMessageText,
        in_logger=logger,
        in_runAgentUseCase=runAgentUseCase,
        in_memoryService=memoryService,
        in_runtimeSettings=settings.runtime,
    )
    updateHandler = TelegramUpdateHandler(
        in_handleIncomingTelegramMessageUseCase=handleIncomingTelegramMessageUseCase
    )
    telegramPollingRunner = TelegramPollingRunner(
        in_settings=settings,
        in_logger=logger,
        in_updateHandler=updateHandler,
        in_contouringHttpPolicy=contouringHttpPolicy,
    )
    getLogsUseCase = GetLogsUseCase(in_loggingSettings=settings.logging)
    getRunListUseCase = GetRunListUseCase(in_runRepository=runRepository)
    getRunDetailsUseCase = GetRunDetailsUseCase(in_runRepository=runRepository)
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
    )
    return ret
