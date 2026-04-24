from app.application.useCases.handleIncomingTelegramMessageUseCase import (
    HandleIncomingTelegramMessageUseCase,
)
from app.integrations.telegram.telegramMessageMapper import mapUpdateToDto


class TelegramUpdateHandler:
    def __init__(
        self, in_handleIncomingTelegramMessageUseCase: HandleIncomingTelegramMessageUseCase
    ) -> None:
        self._handleIncomingTelegramMessageUseCase = in_handleIncomingTelegramMessageUseCase

    def handleUpdate(self, in_updateData: dict) -> tuple[int | None, str | None]:
        ret: tuple[int | None, str | None]
        messageDto = mapUpdateToDto(in_updateData=in_updateData)
        if messageDto is None:
            ret = (None, None)
        else:
            useCaseResult = self._handleIncomingTelegramMessageUseCase.execute(
                in_messageDto=messageDto
            )
            ret = (messageDto.chatId, useCaseResult.outgoingText)
        return ret
