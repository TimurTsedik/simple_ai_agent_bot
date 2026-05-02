from dataclasses import dataclass
from time import time

from app.config.settingsModels import MemorySettings
from app.users.provisionTelegramUserWorkspace import provisionTelegramUserWorkspaceIfNeeded
from app.users.telegramUserRegistryStore import TelegramUserRegistryStore


@dataclass(frozen=True)
class CreateTelegramUserResult:
    ok: bool
    messageText: str
    telegramUserId: int


class CreateTelegramUserUseCase:
    def __init__(
        self,
        in_registry_store: TelegramUserRegistryStore,
        in_memorySettings: MemorySettings,
    ) -> None:
        self._registry = in_registry_store
        self._memorySettings = in_memorySettings

    def execute(
        self,
        in_telegramUserId: int,
        in_displayName: str = "",
        in_note: str = "",
    ) -> CreateTelegramUserResult:
        ret: CreateTelegramUserResult
        telegramUserIdValue = int(in_telegramUserId)
        if telegramUserIdValue < 1:
            ret = CreateTelegramUserResult(
                ok=False,
                messageText="Некорректный telegram user id.",
                telegramUserId=telegramUserIdValue,
            )
        else:
            createdAtUnixTs = int(time())
            _record, wasNew = self._registry.addOrTouchUser(
                in_telegramUserId=telegramUserIdValue,
                in_displayName=in_displayName,
                in_note=in_note,
                in_createdAtUnixTs=createdAtUnixTs,
            )
            provisionTelegramUserWorkspaceIfNeeded(
                in_telegramUserId=telegramUserIdValue,
                in_memorySettings=self._memorySettings,
            )
            if wasNew is True:
                msg = (
                    "Пользователь создан: добавлен в реестр, рабочая область памяти и файлы настроек подготовлены."
                )
            else:
                msg = "Пользователь уже был в реестре; рабочая область проверена и при необходимости дополнена."
            ret = CreateTelegramUserResult(
                ok=True,
                messageText=msg,
                telegramUserId=telegramUserIdValue,
            )
        return ret
