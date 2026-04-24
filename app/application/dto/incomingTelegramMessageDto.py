from pydantic import BaseModel


class IncomingTelegramMessageDto(BaseModel):
    updateId: int
    telegramUserId: int
    chatId: int
    text: str
