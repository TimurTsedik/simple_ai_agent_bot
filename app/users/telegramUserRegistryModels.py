from pydantic import BaseModel, Field


class TelegramUserRegistryRecord(BaseModel):
    telegramUserId: int = Field(ge=1)
    createdAtUnixTs: int = Field(ge=0)
    displayName: str = ""
    note: str = ""


class TelegramUsersRegistryDocument(BaseModel):
    version: int = 1
    users: list[TelegramUserRegistryRecord] = Field(default_factory=list)
