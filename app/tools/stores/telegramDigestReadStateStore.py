import json
import os
from pathlib import Path
from threading import Lock

_STATE_LOCK = Lock()


class TelegramDigestReadStateStore:
    """Persists last-seen Telegram public post ids per channel for unread-style digests."""

    def __init__(self, in_stateFilePath: Path) -> None:
        self._stateFilePath = in_stateFilePath.resolve()

    def readChannelLastSeenMap(self) -> dict[str, int]:
        ret: dict[str, int]
        with _STATE_LOCK:
            ret = self._readChannelLastSeenMapUnlocked()
        return ret

    def mergeChannelLastSeenMap(self, in_updates: dict[str, int]) -> None:
        with _STATE_LOCK:
            existingMap = self._readChannelLastSeenMapUnlocked()
            for channelName, messageIdValue in in_updates.items():
                normalizedChannel = str(channelName or "").strip().lower()
                if normalizedChannel == "":
                    continue
                previousValue = int(existingMap.get(normalizedChannel, 0))
                nextValue = int(messageIdValue)
                if nextValue > previousValue:
                    existingMap[normalizedChannel] = nextValue
            self._writeChannelLastSeenMapUnlocked(in_channelMap=existingMap)

    def _readChannelLastSeenMapUnlocked(self) -> dict[str, int]:
        ret: dict[str, int]
        resultMap: dict[str, int] = {}
        if self._stateFilePath.exists() is False:
            ret = resultMap
            return ret
        try:
            rawText = self._stateFilePath.read_text(encoding="utf-8")
            parsedValue = json.loads(rawText)
        except (OSError, json.JSONDecodeError):
            ret = resultMap
            return ret
        if isinstance(parsedValue, dict) is False:
            ret = resultMap
            return ret
        nestedMap = parsedValue.get("channelLastSeenMessageId")
        if isinstance(nestedMap, dict) is False:
            ret = resultMap
            return ret
        for channelKey, messageIdRaw in nestedMap.items():
            channelText = str(channelKey or "").strip().lower()
            if channelText == "":
                continue
            try:
                messageIdInt = int(messageIdRaw)
            except (TypeError, ValueError):
                continue
            resultMap[channelText] = messageIdInt
        ret = resultMap
        return ret

    def _writeChannelLastSeenMapUnlocked(self, in_channelMap: dict[str, int]) -> None:
        payload = {
            "version": 1,
            "channelLastSeenMessageId": dict(in_channelMap),
        }
        self._stateFilePath.parent.mkdir(parents=True, exist_ok=True)
        tempPath = self._stateFilePath.with_suffix(self._stateFilePath.suffix + ".tmp")
        textValue = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
        tempPath.write_text(textValue, encoding="utf-8")
        os.replace(tempPath, self._stateFilePath)
