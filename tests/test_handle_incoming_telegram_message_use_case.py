from app.application.dto.incomingTelegramMessageDto import IncomingTelegramMessageDto
from app.application.useCases.handleIncomingTelegramMessageUseCase import (
    HandleIncomingTelegramMessageUseCase,
)
from app.config.settingsModels import RuntimeSettings


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

    def execute(
        self,
        in_sessionId: str,
        in_inputMessage: str,
        in_memoryPrincipalId: str | None = None,
    ) -> FakeRunResult:
        _ = in_memoryPrincipalId
        self.calls.append((in_sessionId, in_inputMessage))
        ret = FakeRunResult(in_finalAnswer=f"echo:{in_inputMessage}")
        return ret


class FakeMemoryService:
    def __init__(self) -> None:
        self.resetSessionIds: list[str] = []

    def resetSession(self, in_sessionId: str) -> None:
        self.resetSessionIds.append(in_sessionId)

    def buildMemoryBlock(
        self,
        in_sessionId: str,
        in_longTermPrincipalId: str | None = None,
    ) -> str:
        _ = in_sessionId
        _ = in_longTermPrincipalId
        ret = "## Session Summary\nx\n\n## Recent Messages\n- user: a\n\n## Long-Term Memory\n- b"
        return ret


def _makeRuntimeSettings() -> RuntimeSettings:
    ret = RuntimeSettings(
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
    )
    return ret


def testAuthorizedUserGetsAcceptedMessage() -> None:
    logger = FakeLogger()
    runAgentUseCase = FakeRunAgentUseCase()
    memoryService = FakeMemoryService()
    useCase = HandleIncomingTelegramMessageUseCase(
        in_get_allowed_user_ids=lambda: {100},
        in_denyMessageText="Доступ запрещён",
        in_logger=logger,
        in_runAgentUseCase=runAgentUseCase,  # type: ignore[arg-type]
        in_memoryService=memoryService,  # type: ignore[arg-type]
        in_runtimeSettings=_makeRuntimeSettings(),
    )
    dto = IncomingTelegramMessageDto(
        updateId=1,
        telegramUserId=100,
        chatId=200,
        text="Привет",
    )

    result = useCase.execute(in_messageDto=dto)

    assert result.isAuthorized is True
    assert result.outgoingText == "echo:Привет"
    assert runAgentUseCase.calls == [("telegramUser:100", "Привет")]


def testUnauthorizedUserGetsDeniedMessage() -> None:
    logger = FakeLogger()
    runAgentUseCase = FakeRunAgentUseCase()
    memoryService = FakeMemoryService()
    useCase = HandleIncomingTelegramMessageUseCase(
        in_get_allowed_user_ids=lambda: {100},
        in_denyMessageText="Доступ запрещён",
        in_logger=logger,
        in_runAgentUseCase=runAgentUseCase,  # type: ignore[arg-type]
        in_memoryService=memoryService,  # type: ignore[arg-type]
        in_runtimeSettings=_makeRuntimeSettings(),
    )
    dto = IncomingTelegramMessageDto(
        updateId=1,
        telegramUserId=999,
        chatId=200,
        text="Привет",
    )

    result = useCase.execute(in_messageDto=dto)

    assert result.isAuthorized is False
    assert result.outgoingText == "Доступ запрещён"


def testAuthorizedUserResetCommandClearsSessionMemory() -> None:
    logger = FakeLogger()
    runAgentUseCase = FakeRunAgentUseCase()
    memoryService = FakeMemoryService()
    useCase = HandleIncomingTelegramMessageUseCase(
        in_get_allowed_user_ids=lambda: {100},
        in_denyMessageText="Доступ запрещён",
        in_logger=logger,
        in_runAgentUseCase=runAgentUseCase,  # type: ignore[arg-type]
        in_memoryService=memoryService,  # type: ignore[arg-type]
        in_runtimeSettings=_makeRuntimeSettings(),
    )
    dto = IncomingTelegramMessageDto(
        updateId=1,
        telegramUserId=100,
        chatId=777,
        text="/reset",
    )

    result = useCase.execute(in_messageDto=dto)

    assert result.isAuthorized is True
    assert "Сессия сброшена" in result.outgoingText
    assert memoryService.resetSessionIds == ["telegramUser:100"]
    assert runAgentUseCase.calls == []


def testAuthorizedUserContextCommandShowsContextAndWindow() -> None:
    logger = FakeLogger()
    runAgentUseCase = FakeRunAgentUseCase()
    memoryService = FakeMemoryService()
    useCase = HandleIncomingTelegramMessageUseCase(
        in_get_allowed_user_ids=lambda: {100},
        in_denyMessageText="Доступ запрещён",
        in_logger=logger,
        in_runAgentUseCase=runAgentUseCase,  # type: ignore[arg-type]
        in_memoryService=memoryService,  # type: ignore[arg-type]
        in_runtimeSettings=_makeRuntimeSettings(),
    )
    dto = IncomingTelegramMessageDto(
        updateId=1,
        telegramUserId=100,
        chatId=777,
        text="/context",
    )

    result = useCase.execute(in_messageDto=dto)

    assert result.isAuthorized is True
    assert "session memory block" in result.outgoingText
    assert "max context window" in result.outgoingText
    assert "5000" in result.outgoingText
    assert runAgentUseCase.calls == []


def testAuthorizedUserHelpCommandReturnsTemplatesWithoutAgentRun() -> None:
    logger = FakeLogger()
    runAgentUseCase = FakeRunAgentUseCase()
    memoryService = FakeMemoryService()
    useCase = HandleIncomingTelegramMessageUseCase(
        in_get_allowed_user_ids=lambda: {100},
        in_denyMessageText="Доступ запрещён",
        in_logger=logger,
        in_runAgentUseCase=runAgentUseCase,  # type: ignore[arg-type]
        in_memoryService=memoryService,  # type: ignore[arg-type]
        in_runtimeSettings=_makeRuntimeSettings(),
    )
    dto = IncomingTelegramMessageDto(
        updateId=1,
        telegramUserId=100,
        chatId=777,
        text="/help",
    )

    result = useCase.execute(in_messageDto=dto)

    assert result.isAuthorized is True
    assert "Шаблоны запросов" in result.outgoingText
    assert "Telegram дайджест (общий)" in result.outgoingText
    assert "Telegram дайджест по теме" in result.outgoingText
    assert "Email сценарии" in result.outgoingText
    assert "Веб-поиск" in result.outgoingText
    assert "Напоминания" in result.outgoingText
    assert runAgentUseCase.calls == []


def testAuthorizedUserStartCommandMentionsHelpCommand() -> None:
    logger = FakeLogger()
    runAgentUseCase = FakeRunAgentUseCase()
    memoryService = FakeMemoryService()
    useCase = HandleIncomingTelegramMessageUseCase(
        in_get_allowed_user_ids=lambda: {100},
        in_denyMessageText="Доступ запрещён",
        in_logger=logger,
        in_runAgentUseCase=runAgentUseCase,  # type: ignore[arg-type]
        in_memoryService=memoryService,  # type: ignore[arg-type]
        in_runtimeSettings=_makeRuntimeSettings(),
    )
    dto = IncomingTelegramMessageDto(
        updateId=1,
        telegramUserId=100,
        chatId=777,
        text="/start",
    )

    result = useCase.execute(in_messageDto=dto)

    assert result.isAuthorized is True
    assert "/help" in result.outgoingText
    assert runAgentUseCase.calls == []
