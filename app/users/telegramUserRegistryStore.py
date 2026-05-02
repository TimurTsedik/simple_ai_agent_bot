import os
from pathlib import Path
from threading import Lock
from typing import Any

import yaml
from pydantic import ValidationError

from app.users.telegramUserRegistryModels import TelegramUserRegistryRecord
from app.users.telegramUserRegistryModels import TelegramUsersRegistryDocument

_REGISTRY_FILE_LOCK = Lock()


class TelegramUserRegistryStore:
    def __init__(self, in_registryFilePath: str) -> None:
        self._registryPath = Path(in_registryFilePath).resolve()

    def _readRaw(self) -> dict[str, Any]:
        ret: dict[str, Any]
        if self._registryPath.exists() is False or self._registryPath.is_file() is False:
            ret = {"version": 1, "users": []}
            return ret
        loaded = yaml.safe_load(self._registryPath.read_text(encoding="utf-8"))
        if isinstance(loaded, dict) is False:
            ret = {"version": 1, "users": []}
            return ret
        ret = loaded
        return ret

    def _writeDocument(self, in_document: TelegramUsersRegistryDocument) -> None:
        self._registryPath.parent.mkdir(parents=True, exist_ok=True)
        dumpData = in_document.model_dump(mode="python")
        textValue = yaml.safe_dump(dumpData, allow_unicode=True, sort_keys=False)
        tempPath = self._registryPath.with_suffix(self._registryPath.suffix + ".tmp")
        try:
            tempPath.write_text(textValue, encoding="utf-8")
            os.replace(tempPath, self._registryPath)
        except PermissionError:
            self._registryPath.write_text(textValue, encoding="utf-8")

    def listUsers(self) -> list[TelegramUserRegistryRecord]:
        ret: list[TelegramUserRegistryRecord]
        with _REGISTRY_FILE_LOCK:
            rawData = self._readRaw()
        try:
            document = TelegramUsersRegistryDocument.model_validate(rawData)
        except ValidationError:
            document = TelegramUsersRegistryDocument()
        ret = list(document.users)
        return ret

    def listRegisteredTelegramUserIds(self) -> set[int]:
        ret: set[int]
        ids: set[int] = set()
        for item in self.listUsers():
            ids.add(int(item.telegramUserId))
        ret = ids
        return ret

    def addOrTouchUser(
        self,
        in_telegramUserId: int,
        in_displayName: str,
        in_note: str,
        in_createdAtUnixTs: int,
    ) -> tuple[TelegramUserRegistryRecord, bool]:
        """Возвращает (запись, wasNewUser)."""

        telegramUserId = int(in_telegramUserId)
        displayNameTrimmed = str(in_displayName or "").strip()
        noteTrimmed = str(in_note or "").strip()
        with _REGISTRY_FILE_LOCK:
            rawData = self._readRaw()
            try:
                document = TelegramUsersRegistryDocument.model_validate(rawData)
            except ValidationError:
                document = TelegramUsersRegistryDocument()
            usersList = list(document.users)
            wasNew = True
            updatedList: list[TelegramUserRegistryRecord] = []
            targetRecord: TelegramUserRegistryRecord | None = None
            for item in usersList:
                if int(item.telegramUserId) == telegramUserId:
                    wasNew = False
                    targetRecord = TelegramUserRegistryRecord(
                        telegramUserId=int(item.telegramUserId),
                        createdAtUnixTs=int(item.createdAtUnixTs or in_createdAtUnixTs),
                        displayName=str(displayNameTrimmed or item.displayName or ""),
                        note=str(noteTrimmed or item.note or ""),
                    )
                    updatedList.append(targetRecord)
                else:
                    updatedList.append(item)
            if wasNew is True:
                targetRecord = TelegramUserRegistryRecord(
                    telegramUserId=telegramUserId,
                    createdAtUnixTs=in_createdAtUnixTs,
                    displayName=displayNameTrimmed,
                    note=noteTrimmed,
                )
                updatedList.append(targetRecord)
            newDoc = TelegramUsersRegistryDocument(users=updatedList)
            self._writeDocument(in_document=newDoc)
        retTuple = (
            targetRecord
            if targetRecord is not None
            else TelegramUserRegistryRecord(
                telegramUserId=telegramUserId,
                createdAtUnixTs=in_createdAtUnixTs,
                displayName=displayNameTrimmed,
                note=noteTrimmed,
            ),
            wasNew,
        )
        return retTuple
