import time
from threading import Event, Thread
from typing import Any

import requests

from app.config.settingsModels import SettingsModel
from app.domain.protocols.loggerProtocol import LoggerProtocol
from app.integrations.telegram.channelPostStore import ChannelPostStore
from app.integrations.telegram.telegramUpdateHandler import TelegramUpdateHandler


class TelegramPollingRunner:
    def __init__(
        self,
        in_settings: SettingsModel,
        in_logger: LoggerProtocol,
        in_updateHandler: TelegramUpdateHandler,
        in_typingIntervalSeconds: float = 4.0,
    ) -> None:
        self._settings = in_settings
        self._logger = in_logger
        self._updateHandler = in_updateHandler
        self._typingIntervalSeconds = max(0.2, in_typingIntervalSeconds)
        self._lastUpdateId = 0
        self._stopEvent = Event()
        self._channelPostStore = ChannelPostStore(
            in_dataRootPath=in_settings.app.dataRootPath
        )

    def pollOnce(self) -> None:
        apiUrl = (
            f"https://api.telegram.org/bot{self._settings.telegramBotToken}/getUpdates"
        )
        params = {
            "timeout": self._settings.telegram.pollingTimeoutSeconds,
            "offset": self._lastUpdateId + 1,
        }
        try:
            response = requests.get(
                apiUrl,
                params=params,
                timeout=self._settings.telegram.pollingTimeoutSeconds + 5,
            )
            response.raise_for_status()
            payload = response.json()
            self._handleUpdatesPayload(in_payload=payload)
        except requests.RequestException as in_exc:
            self._logger.error(f"telegram_polling_error {in_exc}")

    def runForever(self) -> None:
        self._stopEvent.clear()
        while self._stopEvent.is_set() is False:
            self.pollOnce()
            time.sleep(0.2)

    def stop(self) -> None:
        self._stopEvent.set()

    def _handleUpdatesPayload(self, in_payload: dict[str, Any]) -> None:
        updates = in_payload.get("result", [])
        if not isinstance(updates, list):
            updates = []
        for itemData in updates:
            if not isinstance(itemData, dict):
                continue
            updateId = itemData.get("update_id", 0)
            if isinstance(updateId, int):
                self._lastUpdateId = max(self._lastUpdateId, updateId)
            self._persistChannelPostIfPresent(in_updateData=itemData)
            typingChatId = self._extractTypingChatId(in_updateData=itemData)
            if typingChatId is None:
                chatId, outgoingText = self._updateHandler.handleUpdate(
                    in_updateData=itemData
                )
            else:
                chatId, outgoingText = self._handleUpdateWithTyping(
                    in_updateData=itemData,
                    in_chatId=typingChatId,
                )
            if chatId is not None and outgoingText is not None:
                self._sendMessage(in_chatId=chatId, in_text=outgoingText)

    def _extractTypingChatId(self, in_updateData: dict[str, Any]) -> int | None:
        ret: int | None
        messageData = in_updateData.get("message")
        if not isinstance(messageData, dict):
            ret = None
        else:
            textValue = messageData.get("text")
            chatData = messageData.get("chat")
            if not isinstance(textValue, str):
                ret = None
            elif not isinstance(chatData, dict):
                ret = None
            else:
                chatId = chatData.get("id")
                chatType = chatData.get("type")
                if isinstance(chatId, int) and chatType == "private":
                    ret = chatId
                else:
                    ret = None
        return ret

    def _handleUpdateWithTyping(
        self,
        in_updateData: dict[str, Any],
        in_chatId: int,
    ) -> tuple[int | None, str | None]:
        ret: tuple[int | None, str | None]
        resultChatId: int | None = None
        resultText: str | None = None

        def runUpdate() -> None:
            nonlocal resultChatId, resultText
            resultChatId, resultText = self._updateHandler.handleUpdate(
                in_updateData=in_updateData
            )

        self._sendTypingAction(in_chatId=in_chatId)
        workerThread = Thread(
            target=runUpdate,
            name="telegramUpdateWorker",
            daemon=True,
        )
        workerThread.start()
        while workerThread.is_alive():
            workerThread.join(timeout=self._typingIntervalSeconds)
            if workerThread.is_alive():
                self._sendTypingAction(in_chatId=in_chatId)
        ret = (resultChatId, resultText)
        return ret

    def _persistChannelPostIfPresent(self, in_updateData: dict[str, Any]) -> None:
        channelPost = in_updateData.get("channel_post")
        if isinstance(channelPost, dict):
            self._channelPostStore.appendChannelPost(in_channelPostData=channelPost)

    def _sendMessage(self, in_chatId: int, in_text: str) -> None:
        apiUrl = (
            f"https://api.telegram.org/bot{self._settings.telegramBotToken}/sendMessage"
        )
        payload = {"chat_id": in_chatId, "text": in_text}
        try:
            requests.post(apiUrl, json=payload, timeout=15).raise_for_status()
        except requests.RequestException as in_exc:
            self._logger.error(f"telegram_send_error {in_exc}")

    def _sendTypingAction(self, in_chatId: int) -> None:
        apiUrl = (
            f"https://api.telegram.org/bot{self._settings.telegramBotToken}/sendChatAction"
        )
        payload = {"chat_id": in_chatId, "action": "typing"}
        try:
            requests.post(apiUrl, json=payload, timeout=10).raise_for_status()
        except requests.RequestException as in_exc:
            self._logger.error(f"telegram_typing_error {in_exc}")
