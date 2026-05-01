from dataclasses import dataclass

from app.application.dto.incomingTelegramMessageDto import IncomingTelegramMessageDto
from app.application.useCases.runAgentUseCase import RunAgentUseCase
from app.config.settingsModels import RuntimeSettings
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
        in_runtimeSettings: RuntimeSettings,
    ) -> None:
        self._allowedUserIds = set(in_allowedUserIds)
        self._denyMessageText = in_denyMessageText
        self._logger = in_logger
        self._runAgentUseCase = in_runAgentUseCase
        self._memoryService = in_memoryService
        self._runtimeSettings = in_runtimeSettings

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
                "Бот активен. Доступные команды: /start, /help, /health, /reset, /context. "
                "Можно отправлять обычные сообщения для запуска агента."
            )
        elif loweredText == "/help":
            outgoingText = self._buildHelpMessage()
        elif loweredText == "/health":
            outgoingText = "ok"
        elif loweredText == "/reset":
            self._memoryService.resetSession(in_sessionId=sessionId)
            outgoingText = "Сессия сброшена: short-term и summary очищены."
        elif loweredText == "/context":
            memoryBlock = self._memoryService.buildMemoryBlock(in_sessionId=sessionId)
            outgoingText = (
                "LLM context:\n"
                f"- session memory block: {len(memoryBlock)} chars\n"
                f"- max context window: {self._runtimeSettings.maxPromptChars} chars\n"
                "Примечание: prompt builder усекает prompt до maxPromptChars."
            )
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

    def _buildHelpMessage(self) -> str:
        ret: str
        ret = (
            "Шаблоны запросов для всех сценариев агента:\n\n"
            "Команды:\n"
            "- /start — показать список команд\n"
            "- /help — показать шаблоны запросов\n"
            "- /health — проверка, что бот жив\n"
            "- /reset — очистить память текущей сессии\n"
            "- /context — показать размер текущего memory block\n\n"
            "Telegram дайджест (общий):\n"
            "- создай дайджест экономических новостей\n"
            "- сделай дайджест новостей AI за час\n"
            "- дай обзор рынка из @markettwits и @headlines_for_traders\n\n"
            "Telegram дайджест по теме (с сохранением настроек):\n"
            "- создай дайджест новостей по теме ИИ\n"
            "- создай дайджест новостей техники\n"
            "- удали тему дайджеста ИИ\n\n"
            "Обратная связь по дайджесту (сохранение предпочтений):\n"
            "- запомни: мне нравятся новости из @how2ai и @larchanka\n"
            "- сохрани, что мне интересны темы ai и crypto, ключи gpt и llm\n\n"
            "Email сценарии:\n"
            "- прочитай непрочитанные письма и сделай дайджест\n"
            "- запомни, что письма от @noip.com важные\n\n"
            "Веб-поиск:\n"
            "- найди в интернете свежие источники по теме инфляции в США\n"
            "- проверь по источникам, что нового по Nvidia и datacenter\n\n"
            "Напоминания:\n"
            "- напомни завтра в 10:00 созвон с командой\n"
            "- напомни каждый понедельник в 09:30 отправить отчёт\n"
        )
        return ret
