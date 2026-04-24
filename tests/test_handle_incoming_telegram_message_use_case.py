from app.application.dto.incomingTelegramMessageDto import IncomingTelegramMessageDto
from app.application.useCases.handleIncomingTelegramMessageUseCase import (
    HandleIncomingTelegramMessageUseCase,
)


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
    def __init__(self) -> None:
        self.resetSessionIds: list[str] = []

    def resetSession(self, in_sessionId: str) -> None:
        self.resetSessionIds.append(in_sessionId)


def testAuthorizedUserGetsAcceptedMessage() -> None:
    logger = FakeLogger()
    runAgentUseCase = FakeRunAgentUseCase()
    memoryService = FakeMemoryService()
    useCase = HandleIncomingTelegramMessageUseCase(
        in_allowedUserIds=[100],
        in_denyMessageText="Доступ запрещён",
        in_logger=logger,
        in_runAgentUseCase=runAgentUseCase,  # type: ignore[arg-type]
        in_memoryService=memoryService,  # type: ignore[arg-type]
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
    assert runAgentUseCase.calls == [("telegram:200", "Привет")]


def testUnauthorizedUserGetsDeniedMessage() -> None:
    logger = FakeLogger()
    runAgentUseCase = FakeRunAgentUseCase()
    memoryService = FakeMemoryService()
    useCase = HandleIncomingTelegramMessageUseCase(
        in_allowedUserIds=[100],
        in_denyMessageText="Доступ запрещён",
        in_logger=logger,
        in_runAgentUseCase=runAgentUseCase,  # type: ignore[arg-type]
        in_memoryService=memoryService,  # type: ignore[arg-type]
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
        in_allowedUserIds=[100],
        in_denyMessageText="Доступ запрещён",
        in_logger=logger,
        in_runAgentUseCase=runAgentUseCase,  # type: ignore[arg-type]
        in_memoryService=memoryService,  # type: ignore[arg-type]
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
    assert memoryService.resetSessionIds == ["telegram:777"]
    assert runAgentUseCase.calls == []
