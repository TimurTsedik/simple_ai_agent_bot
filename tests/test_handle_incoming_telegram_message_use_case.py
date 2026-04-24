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


def testAuthorizedUserGetsAcceptedMessage() -> None:
    logger = FakeLogger()
    useCase = HandleIncomingTelegramMessageUseCase(
        in_allowedUserIds=[100],
        in_denyMessageText="Доступ запрещён",
        in_logger=logger,
    )
    dto = IncomingTelegramMessageDto(
        updateId=1,
        telegramUserId=100,
        chatId=200,
        text="Привет",
    )

    result = useCase.execute(in_messageDto=dto)

    assert result.isAuthorized is True
    assert "Запрос принят" in result.outgoingText


def testUnauthorizedUserGetsDeniedMessage() -> None:
    logger = FakeLogger()
    useCase = HandleIncomingTelegramMessageUseCase(
        in_allowedUserIds=[100],
        in_denyMessageText="Доступ запрещён",
        in_logger=logger,
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
