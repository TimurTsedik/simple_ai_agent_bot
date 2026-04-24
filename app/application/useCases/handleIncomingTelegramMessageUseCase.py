from dataclasses import dataclass

from app.application.dto.incomingTelegramMessageDto import IncomingTelegramMessageDto
from app.domain.protocols.loggerProtocol import LoggerProtocol


@dataclass(frozen=True)
class HandleIncomingTelegramMessageResult:
    isAuthorized: bool
    outgoingText: str


class HandleIncomingTelegramMessageUseCase:
    def __init__(
        self,
        in_allowedUserIds: list[int],
        in_denyMessageText: str,
        in_logger: LoggerProtocol,
    ) -> None:
        self._allowedUserIds = set(in_allowedUserIds)
        self._denyMessageText = in_denyMessageText
        self._logger = in_logger

    def execute(
        self, in_messageDto: IncomingTelegramMessageDto
    ) -> HandleIncomingTelegramMessageResult:
        ret: HandleIncomingTelegramMessageResult
        isAuthorized = in_messageDto.telegramUserId in self._allowedUserIds
        if isAuthorized:
            self._logger.info(
                f"authorized_telegram_message user={in_messageDto.telegramUserId}"
            )
            ret = HandleIncomingTelegramMessageResult(
                isAuthorized=True,
                outgoingText="Запрос принят. Agent run будет запущен на следующем этапе.",
            )
        else:
            self._logger.info(
                f"unauthorized_telegram_message user={in_messageDto.telegramUserId}"
            )
            ret = HandleIncomingTelegramMessageResult(
                isAuthorized=False,
                outgoingText=self._denyMessageText,
            )
        return ret
