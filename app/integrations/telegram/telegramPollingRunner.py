from typing import Any

import requests

from app.config.settingsModels import SettingsModel
from app.domain.protocols.loggerProtocol import LoggerProtocol
from app.integrations.telegram.telegramUpdateHandler import TelegramUpdateHandler


class TelegramPollingRunner:
    def __init__(
        self,
        in_settings: SettingsModel,
        in_logger: LoggerProtocol,
        in_updateHandler: TelegramUpdateHandler,
    ) -> None:
        self._settings = in_settings
        self._logger = in_logger
        self._updateHandler = in_updateHandler
        self._lastUpdateId = 0

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
            chatId, outgoingText = self._updateHandler.handleUpdate(in_updateData=itemData)
            if chatId is not None and outgoingText is not None:
                self._sendMessage(in_chatId=chatId, in_text=outgoingText)

    def _sendMessage(self, in_chatId: int, in_text: str) -> None:
        apiUrl = (
            f"https://api.telegram.org/bot{self._settings.telegramBotToken}/sendMessage"
        )
        payload = {"chat_id": in_chatId, "text": in_text}
        try:
            requests.post(apiUrl, json=payload, timeout=15).raise_for_status()
        except requests.RequestException as in_exc:
            self._logger.error(f"telegram_send_error {in_exc}")
