import argparse
from pathlib import Path

from app.application.useCases.handleIncomingTelegramMessageUseCase import (
    HandleIncomingTelegramMessageUseCase,
)
from app.config.settingsModels import (
    AppSettings,
    LoggingSettings,
    MemorySettings,
    ModelSettings,
    RuntimeSettings,
    SchedulerSettings,
    SecuritySettings,
    SettingsModel,
    SkillsSettings,
    TelegramSettings,
    ToolsSettings,
)
from app.integrations.telegram.telegramUpdateHandler import TelegramUpdateHandler


class FakeLogger:
    def __init__(self) -> None:
        self.infoMessages: list[str] = []
        self.errorMessages: list[str] = []

    def info(self, in_message: str) -> None:
        self.infoMessages.append(in_message)

    def error(self, in_message: str) -> None:
        self.errorMessages.append(in_message)


class FakeRunResult:
    def __init__(self, in_finalAnswer: str) -> None:
        self.finalAnswer = in_finalAnswer


class FakeRunAgentUseCase:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def execute(self, in_sessionId: str, in_inputMessage: str) -> FakeRunResult:
        self.calls.append((in_sessionId, in_inputMessage))
        ret = FakeRunResult(in_finalAnswer=f"echo:{in_inputMessage}")
        return ret


class FakeMemoryService:
    def resetSession(self, in_sessionId: str) -> None:
        _ = in_sessionId

    def buildMemoryBlock(
        self,
        in_sessionId: str,
        in_longTermPrincipalId: str | None = None,
    ) -> str:
        _ = in_sessionId
        _ = in_longTermPrincipalId
        ret = ""
        return ret


class FakeDownloader:
    def downloadTelegramFileToPath(
        self,
        *,
        in_fileId: str,
        in_outPath: str,
        in_maxBytes: int,
        in_timeoutSeconds: float,
    ) -> None:
        _ = in_fileId
        _ = in_maxBytes
        _ = in_timeoutSeconds
        Path(in_outPath).write_bytes(b"fake")


class FakeTranscriber:
    def __init__(self, in_text: str) -> None:
        self._text = in_text

    def transcribeToText(
        self,
        *,
        in_audioPath: str,
        in_language: str,
        in_maxSeconds: int,
    ) -> str:
        _ = in_audioPath
        _ = in_language
        _ = in_maxSeconds
        ret = self._text
        return ret


def _makeSettings(in_tmpDir: Path) -> SettingsModel:
    memoryRoot = in_tmpDir / "memory"
    tenantDir = memoryRoot / "sessions" / "telegramUser_16739703"
    tenantDir.mkdir(parents=True, exist_ok=True)
    toolsYamlPath = tenantDir / "tools.yaml"
    toolsYamlPath.write_text(
        "telegramNewsDigest:\n  digestChannelUsernames: []\n",
        encoding="utf-8",
    )
    ret = SettingsModel(
        app=AppSettings(
            appName="simple-ai-agent-bot",
            environment="smoke",
            dataRootPath=str(in_tmpDir),
            displayTimeZone="UTC",
        ),
        telegram=TelegramSettings(
            pollingTimeoutSeconds=30,
            denyMessageText="Доступ запрещён",
            voiceMaxSeconds=60,
            voiceMaxBytes=5_000_000,
        ),
        tools=ToolsSettings(),
        adminTenantToolsYamlPath=str(toolsYamlPath.resolve()),
        adminTenantSchedulesYamlPath=str((tenantDir / "schedules.yaml").resolve()),
        models=ModelSettings(
            openRouterBaseUrl="x",
            primaryModel="x",
            secondaryModel="x",
            tertiaryModel="x",
            requestTimeoutSeconds=45,
            formatRepairRequestTimeoutSeconds=45,
            retryCountBeforeFallback=0,
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
            extraSecondsPerFormatFailureStep=0,
            maxExtraSecondsTotal=0,
            maxFormatRepairAttempts=2,
            maxConsecutiveFormatFailureSteps=2,
        ),
        security=SecuritySettings(
            webSessionCookieTtlSeconds=3600,
            maxAdminTokens=3,
            allowedReadOnlyPaths=[str(in_tmpDir)],
            adminWritesEnabled=True,
            bindSessionToIp=False,
            trustProxyHeaders=False,
            trustedProxyIps=[],
        ),
        logging=LoggingSettings(
            logsDirPath=str(in_tmpDir / "logs"),
            runLogsFileName="run.jsonl",
            appLogsFileName="app.log",
            maxBytes=1024 * 1024,
            backupCount=1,
        ),
        skills=SkillsSettings(skillsDirPath=str(in_tmpDir / "skills")),
        memory=MemorySettings(memoryRootPath=str(in_tmpDir / "memory")),
        scheduler=SchedulerSettings(enabled=False),
        telegramBotToken="token",
        openRouterApiKey="k",
        sessionCookieSecret="x" * 40,
        emailAppPassword="",
        adminRawTokens=["a" * 20],
    )
    return ret


def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke runner for Telegram voice->text pipeline.")
    parser.add_argument(
        "--transcript",
        default="напомни через минуту выпить воды",
        help="Fake transcript produced by STT.",
    )
    parser.add_argument("--chat-id", type=int, default=222)
    parser.add_argument("--user-id", type=int, default=111)
    parser.add_argument("--update-id", type=int, default=10)
    parser.add_argument("--file-id", default="file123")
    args = parser.parse_args()

    tmpDir = (Path.cwd() / "data" / "tmp" / "smoke_voice").resolve()
    tmpDir.mkdir(parents=True, exist_ok=True)

    allowedVoiceUserId = int(args.user_id)
    settings = _makeSettings(in_tmpDir=tmpDir)
    logger = FakeLogger()
    runAgentUseCase = FakeRunAgentUseCase()
    memoryService = FakeMemoryService()
    useCase = HandleIncomingTelegramMessageUseCase(
        in_get_allowed_user_ids=lambda: {allowedVoiceUserId},
        in_denyMessageText=settings.telegram.denyMessageText,
        in_logger=logger,  # type: ignore[arg-type]
        in_runAgentUseCase=runAgentUseCase,  # type: ignore[arg-type]
        in_memoryService=memoryService,  # type: ignore[arg-type]
        in_runtimeSettings=settings.runtime,
    )
    handler = TelegramUpdateHandler(
        in_handleIncomingTelegramMessageUseCase=useCase,
        in_settings=settings,
        in_logger=logger,  # type: ignore[arg-type]
        in_telegramFileDownloader=FakeDownloader(),  # type: ignore[arg-type]
        in_voiceTranscriber=FakeTranscriber(in_text=str(args.transcript)),  # type: ignore[arg-type]
    )

    updateData = {
        "update_id": int(args.update_id),
        "message": {
            "from": {"id": int(args.user_id)},
            "chat": {"id": int(args.chat_id), "type": "private"},
            "voice": {"file_id": str(args.file_id), "duration": 3},
        },
    }

    chatId, outgoingText = handler.handleUpdate(in_updateData=updateData)
    print("chatId:", chatId)
    print("outgoingText:", outgoingText)


if __name__ == "__main__":
    main()

