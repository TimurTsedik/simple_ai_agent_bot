from pydantic import BaseModel


class SessionContextModel(BaseModel):
    sessionId: str
    platform: str
    chatId: str
