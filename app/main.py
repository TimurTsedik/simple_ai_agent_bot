from contextlib import asynccontextmanager
from threading import Thread

from fastapi import FastAPI

from app.bootstrap.container import buildApplicationContainer
from app.common.structuredLogger import writeJsonlEvent
from app.config.defaults import DEFAULT_CONFIG_PATH
from app.config.settingsLoader import SettingsLoadError
from app.observability.sentrySetup import captureSentryException
from app.observability.sentrySetup import configureSentry
from app.presentation.api.internalApiRoutes import registerInternalApiRoutes
from app.presentation.web.adminWebRoutes import registerAdminWebRoutes
from app.security.webSessionAuth import hashAdminToken


def _buildApp() -> FastAPI:
    container = buildApplicationContainer(in_configPath=DEFAULT_CONFIG_PATH)
    settings = container.settings
    configureSentry(in_settings=settings, in_logger=container.logger)

    @asynccontextmanager
    async def lifespan(in_app: FastAPI):  # noqa: ANN202
        def runTelegramPollingWorker() -> None:
            try:
                in_app.state.telegramPollingRunner.runForever()
            except Exception as in_exc:
                captureSentryException(in_exception=in_exc)
                writeJsonlEvent(
                    in_loggingSettings=settings.logging,
                    in_eventType="telegram_polling_crashed",
                    in_payload={"error": str(in_exc)},
                )
                raise

        def runSchedulerWorker() -> None:
            try:
                in_app.state.schedulerRunner.runForever()
            except Exception as in_exc:
                captureSentryException(in_exception=in_exc)
                writeJsonlEvent(
                    in_loggingSettings=settings.logging,
                    in_eventType="scheduler_thread_crashed",
                    in_payload={"error": str(in_exc)},
                )
                raise

        pollingThread = Thread(
            target=runTelegramPollingWorker,
            name="telegramPollingThread",
            daemon=True,
        )
        in_app.state.telegramPollingThread = pollingThread
        in_app.state.telegramPollingThread.start()
        writeJsonlEvent(
            in_loggingSettings=settings.logging,
            in_eventType="telegram_polling_started",
            in_payload={},
        )
        schedulerThread = None
        if in_app.state.schedulerRunner is not None:
            schedulerThread = Thread(
                target=runSchedulerWorker,
                name="schedulerThread",
                daemon=True,
            )
            in_app.state.schedulerThread = schedulerThread
            in_app.state.schedulerThread.start()
            writeJsonlEvent(
                in_loggingSettings=settings.logging,
                in_eventType="scheduler_thread_started",
                in_payload={},
            )
        try:
            yield
        finally:
            if in_app.state.schedulerRunner is not None:
                in_app.state.schedulerRunner.stop()
            currentSchedulerThread = in_app.state.schedulerThread
            if currentSchedulerThread is not None:
                currentSchedulerThread.join(timeout=2)
            if in_app.state.schedulerRunner is not None:
                writeJsonlEvent(
                    in_loggingSettings=settings.logging,
                    in_eventType="scheduler_thread_stopped",
                    in_payload={},
                )
            in_app.state.telegramPollingRunner.stop()
            currentThread = in_app.state.telegramPollingThread
            if currentThread is not None:
                currentThread.join(timeout=2)
            writeJsonlEvent(
                in_loggingSettings=settings.logging,
                in_eventType="telegram_polling_stopped",
                in_payload={},
            )
            in_app.state.toolExecutionCoordinator.shutdown(in_wait=True)

    appInstance = FastAPI(title="simple-ai-agent-bot", lifespan=lifespan)
    appInstance.state.settings = settings
    appInstance.state.logger = container.logger
    appInstance.state.telegramUpdateHandler = container.telegramUpdateHandler
    appInstance.state.runAgentUseCase = container.runAgentUseCase
    appInstance.state.getLogsUseCase = container.getLogsUseCase
    appInstance.state.getRunListUseCase = container.getRunListUseCase
    appInstance.state.getRunDetailsUseCase = container.getRunDetailsUseCase
    appInstance.state.getGitStatusUseCase = container.getGitStatusUseCase
    appInstance.state.getGitDiffUseCase = container.getGitDiffUseCase
    appInstance.state.telegramPollingRunner = container.telegramPollingRunner
    appInstance.state.telegramPollingThread = None
    appInstance.state.schedulerRunner = container.schedulerRunner
    appInstance.state.schedulerThread = None
    appInstance.state.toolExecutionCoordinator = container.toolExecutionCoordinator
    appInstance.state.webSessionCookieName = "admin_session"
    appInstance.state.adminTokenHashes = {
        hashAdminToken(
            in_rawToken=oneToken,
            in_secret=settings.sessionCookieSecret,
        )
        for oneToken in settings.adminRawTokens
    }

    registerAdminWebRoutes(in_app=appInstance, in_container=container)
    registerInternalApiRoutes(in_app=appInstance, in_container=container)

    ret = appInstance
    return ret


try:
    app = _buildApp()
except SettingsLoadError as in_exc:
    raise RuntimeError(f"Application startup failed: {in_exc}") from in_exc
