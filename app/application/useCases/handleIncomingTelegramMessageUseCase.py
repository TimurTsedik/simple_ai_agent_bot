from dataclasses import dataclass

from app.application.dto.incomingTelegramMessageDto import IncomingTelegramMessageDto
from app.application.useCases.runAgentUseCase import RunAgentUseCase
from app.domain.protocols.loggerProtocol import LoggerProtocol
from app.memory.services.memoryService import MemoryService


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
        in_runAgentUseCase: RunAgentUseCase,
        in_memoryService: MemoryService,
    ) -> None:
        self._allowedUserIds = set(in_allowedUserIds)
        self._denyMessageText = in_denyMessageText
        self._logger = in_logger
        self._runAgentUseCase = in_runAgentUseCase
        self._memoryService = in_memoryService

    def execute(
        self, in_messageDto: IncomingTelegramMessageDto
    ) -> HandleIncomingTelegramMessageResult:
        ret: HandleIncomingTelegramMessageResult
        isAuthorized = in_messageDto.telegramUserId in self._allowedUserIds
        if isAuthorized:
            self._logger.info(
                f"authorized_telegram_message user={in_messageDto.telegramUserId}"
            )
            ret = self._handleAuthorizedMessage(in_messageDto=in_messageDto)
        else:
            self._logger.info(
                f"unauthorized_telegram_message user={in_messageDto.telegramUserId}"
            )
            ret = HandleIncomingTelegramMessageResult(
                isAuthorized=False,
                outgoingText=self._denyMessageText,
            )
        return ret

    def _handleAuthorizedMessage(
        self,
        in_messageDto: IncomingTelegramMessageDto,
    ) -> HandleIncomingTelegramMessageResult:
        ret: HandleIncomingTelegramMessageResult
        normalizedText = in_messageDto.text.strip()
        loweredText = normalizedText.lower()
        sessionId = f"telegram:{in_messageDto.chatId}"
        if loweredText == "/start":
            outgoingText = (
                "Бот активен. Доступные команды: /start, /health, /reset. "
                "Можно отправлять обычные сообщения для запуска агента."
            )
        elif loweredText == "/health":
            outgoingText = "ok"
        elif loweredText == "/reset":
            self._memoryService.resetSession(in_sessionId=sessionId)
            outgoingText = "Сессия сброшена: short-term и summary очищены."
        else:
            runResult = self._runAgentUseCase.execute(
                in_sessionId=sessionId,
                in_inputMessage=normalizedText,
            )
            outgoingText = runResult.finalAnswer or "Пустой ответ агента."
        ret = HandleIncomingTelegramMessageResult(
            isAuthorized=True,
            outgoingText=outgoingText,
        )
        return ret
