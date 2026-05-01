import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.memory.stores.markdownMemoryStore import MarkdownMemoryStore
from app.tools.implementations.digestTelegramNewsTool import DigestTelegramNewsTool
from app.tools.stores.telegramDigestReadStateStore import TelegramDigestReadStateStore
from app.tools.telegramUsernameNormalize import normalizeTelegramChannelUsername

_CONFIG_LINE_PREFIX = "- digest_topic_config_json:"
_KIND_DIGEST_TOPIC_CONFIG = "digest_topic_config"
_MAX_KEYWORD_PHRASES = 48
_MAX_POSTS_PER_CHANNEL = 20


def normalizeUserDigestTopicKey(in_topicLabel: str) -> str:
    ret: str
    collapsedWhitespace = re.sub(r"\s+", " ", str(in_topicLabel or "").strip())
    ret = collapsedWhitespace.lower()
    return ret


@dataclass
class UserTopicDigestTool:
    in_memoryStore: MarkdownMemoryStore
    in_dataRootPath: str
    in_fetchEngine: DigestTelegramNewsTool

    def execute(self, in_args: dict[str, Any]) -> dict[str, Any]:
        ret: dict[str, Any]
        topicLabel = str(in_args.get("topic", "") or "").strip()
        topicKey = normalizeUserDigestTopicKey(in_topicLabel=topicLabel)
        deleteTopicFlag = bool(in_args.get("deleteTopic", False))
        fetchUnreadFlag = bool(in_args.get("fetchUnread", False))
        channelsArgRaw = [c for c in in_args.get("channels", []) if isinstance(c, str)]
        keywordsArgRaw = [k for k in in_args.get("keywords", []) if isinstance(k, str)]

        if deleteTopicFlag is True:
            deletedFlag = self._deleteTopicConfigLines(in_topicKey=topicKey)
            ret = {
                "ok": True,
                "status": "deleted" if deletedFlag else "not_found",
                "topicKey": topicKey,
                "topicLabel": topicLabel,
            }
        elif fetchUnreadFlag is True:
            ret = self._executeFetchUnreadBranch(
                in_topicKey=topicKey,
                in_topicLabel=topicLabel,
            )
        else:
            ret = self._executeConfigureBranch(
                in_topicKey=topicKey,
                in_topicLabel=topicLabel,
                in_channelsArgRaw=channelsArgRaw,
                in_keywordsArgRaw=keywordsArgRaw,
            )
        return ret

    def _executeConfigureBranch(
        self,
        in_topicKey: str,
        in_topicLabel: str,
        in_channelsArgRaw: list[str],
        in_keywordsArgRaw: list[str],
    ) -> dict[str, Any]:
        ret: dict[str, Any]
        existingConfig = self._loadTopicConfig(in_topicKey=in_topicKey)
        mergedChannels = self._mergeChannelLists(
            in_existing=list(existingConfig.get("channels", []))
            if isinstance(existingConfig, dict)
            else [],
            in_newRaw=in_channelsArgRaw,
        )
        mergedKeywords = self._mergeKeywordLists(
            in_existing=list(existingConfig.get("keywords", []))
            if isinstance(existingConfig, dict)
            else [],
            in_newRaw=in_keywordsArgRaw,
        )
        baseLabel = in_topicLabel
        if isinstance(existingConfig, dict):
            previousLabel = str(existingConfig.get("topicLabel", "") or "").strip()
            if previousLabel != "":
                baseLabel = previousLabel
        if len(mergedChannels) > 0 or len(mergedKeywords) > 0:
            payloadConfig = {
                "kind": _KIND_DIGEST_TOPIC_CONFIG,
                "topicKey": in_topicKey,
                "topicLabel": baseLabel,
                "channels": mergedChannels,
                "keywords": mergedKeywords,
                "updatedAt": datetime.now(UTC).isoformat(),
            }
            self._upsertTopicConfigLine(in_payload=payloadConfig)
        refreshedConfig = self._loadTopicConfig(in_topicKey=in_topicKey)
        if refreshedConfig is None:
            ret = {
                "ok": True,
                "status": "needs_channels",
                "topicKey": in_topicKey,
                "topicLabel": baseLabel,
                "savedConfig": None,
                "hint": "Тема ещё не настроена: спроси у пользователя список публичных username каналов.",
            }
        else:
            channelsList = list(refreshedConfig.get("channels", []))
            keywordsList = list(refreshConfigKeywords(in_config=refreshedConfig))
            if len(channelsList) == 0:
                ret = {
                    "ok": True,
                    "status": "needs_channels",
                    "topicKey": in_topicKey,
                    "topicLabel": str(refreshedConfig.get("topicLabel", "") or baseLabel),
                    "savedConfig": refreshedConfig,
                    "hint": "Нужен список публичных Telegram-каналов (@name или t.me/name).",
                }
            elif len(keywordsList) == 0:
                ret = {
                    "ok": True,
                    "status": "needs_keywords",
                    "topicKey": in_topicKey,
                    "topicLabel": str(refreshedConfig.get("topicLabel", "") or baseLabel),
                    "savedConfig": refreshedConfig,
                    "hint": "Нужен список ключевых слов/фраз для фильтрации постов.",
                }
            else:
                ret = {
                    "ok": True,
                    "status": "ready",
                    "topicKey": in_topicKey,
                    "topicLabel": str(refreshedConfig.get("topicLabel", "") or baseLabel),
                    "savedConfig": refreshedConfig,
                    "hint": "Конфигурация темы готова. Вызови снова с fetchUnread=true для загрузки непрочитанных постов.",
                }
        return ret

    def _executeFetchUnreadBranch(
        self,
        in_topicKey: str,
        in_topicLabel: str,
    ) -> dict[str, Any]:
        ret: dict[str, Any]
        topicConfig = self._loadTopicConfig(in_topicKey=in_topicKey)
        if topicConfig is None:
            ret = {
                "ok": False,
                "status": "needs_setup",
                "topicKey": in_topicKey,
                "topicLabel": in_topicLabel,
                "message": "Тема не найдена в памяти. Сначала собери каналы и ключевые слова (fetchUnread=false).",
            }
        else:
            channelsList = [
                str(item).strip().lower()
                for item in list(topicConfig.get("channels", []))
                if str(item).strip() != ""
            ]
            keywordsList = list(refreshConfigKeywords(in_config=topicConfig))
            if len(channelsList) == 0 or len(keywordsList) == 0:
                ret = {
                    "ok": False,
                    "status": "incomplete_config",
                    "topicKey": in_topicKey,
                    "topicLabel": str(topicConfig.get("topicLabel", "") or in_topicLabel),
                    "savedConfig": topicConfig,
                    "message": "В конфигурации темы отсутствуют каналы или ключевые слова.",
                }
            else:
                keywordTerms = self._normalizeKeywordTerms(in_keywords=keywordsList)
                stateStore = self._buildReadStateStore()
                lastSeenMap = stateStore.readChannelLastSeenMap()
                channelErrors: dict[str, str] = {}
                resultItems: list[dict[str, str]] = []
                lastSeenUpdates: dict[str, int] = {}
                diagnosticsChannels: list[dict[str, Any]] = []
                for channelName in sorted(set(channelsList)):
                    channelDiagnostics = self._collectUnreadForOneChannel(
                        in_channelName=channelName,
                        in_keywordTerms=keywordTerms,
                        in_lastSeenMessageId=int(lastSeenMap.get(channelName, 0)),
                        io_channelErrors=channelErrors,
                        io_lastSeenUpdates=lastSeenUpdates,
                        io_resultItems=resultItems,
                    )
                    diagnosticsChannels.append(channelDiagnostics)
                stateStore.mergeChannelLastSeenMap(in_updates=lastSeenUpdates)
                ret = {
                    "ok": True,
                    "status": "fetched",
                    "topicKey": in_topicKey,
                    "topicLabel": str(topicConfig.get("topicLabel", "") or in_topicLabel),
                    "items": resultItems,
                    "count": len(resultItems),
                    "channelErrors": channelErrors,
                    "resolvedChannels": sorted(set(channelsList)),
                    "keywordsApplied": keywordTerms,
                    "diagnostics": {
                        "perChannel": diagnosticsChannels,
                        "maxPostsPerChannel": _MAX_POSTS_PER_CHANNEL,
                    },
                }
        return ret

    def _collectUnreadForOneChannel(
        self,
        in_channelName: str,
        in_keywordTerms: list[str],
        io_channelErrors: dict[str, str],
        io_lastSeenUpdates: dict[str, int],
        io_resultItems: list[dict[str, str]],
        in_lastSeenMessageId: int,
    ) -> dict[str, Any]:
        ret: dict[str, Any]
        rawPosts = self.in_fetchEngine.fetchRawPostsForChannels(
            in_channels=[in_channelName],
            io_channelErrors=io_channelErrors,
        )
        maxParsedMessageId = self._maxParsedMessageId(in_posts=rawPosts)
        if maxParsedMessageId > 0:
            existingPeak = int(io_lastSeenUpdates.get(in_channelName, 0))
            if maxParsedMessageId > existingPeak:
                io_lastSeenUpdates[in_channelName] = maxParsedMessageId
        unreadPosts = []
        for onePost in rawPosts:
            messageIdValue = self._extractMessageIdFromPost(in_post=onePost)
            if messageIdValue is None:
                continue
            if messageIdValue <= in_lastSeenMessageId:
                continue
            postText = onePost.get("text")
            if not isinstance(postText, str):
                continue
            loweredText = postText.lower()
            if not any(term in loweredText for term in in_keywordTerms):
                continue
            unreadPosts.append(onePost)
        unreadPosts.sort(key=self._postSortKey, reverse=True)
        selectedPosts = unreadPosts[:_MAX_POSTS_PER_CHANNEL]
        addedCount = 0
        for selectedPost in selectedPosts:
            formattedItem = self._formatPostItem(in_post=selectedPost)
            if formattedItem is not None:
                io_resultItems.append(formattedItem)
                addedCount += 1
        ret = {
            "channel": in_channelName,
            "parsedPosts": len(rawPosts),
            "unreadKeywordMatched": len(unreadPosts),
            "returnedForDigest": addedCount,
            "lastSeenBefore": in_lastSeenMessageId,
            "pageMaxMessageId": maxParsedMessageId,
        }
        return ret

    def _maxParsedMessageId(self, in_posts: list[dict[str, Any]]) -> int:
        ret: int
        peakValue = 0
        for onePost in in_posts:
            messageIdValue = self._extractMessageIdFromPost(in_post=onePost)
            if messageIdValue is None:
                continue
            if messageIdValue > peakValue:
                peakValue = messageIdValue
        ret = peakValue
        return ret

    def _postSortKey(self, in_post: dict[str, Any]) -> int:
        ret: int
        dateValue = in_post.get("date")
        if isinstance(dateValue, int):
            ret = dateValue
        else:
            ret = 0
        return ret

    def _extractMessageIdFromPost(self, in_post: dict[str, Any]) -> int | None:
        ret: int | None
        rawValue = in_post.get("message_id")
        if isinstance(rawValue, int):
            ret = rawValue
        elif isinstance(rawValue, str) and rawValue.isdigit():
            ret = int(rawValue)
        else:
            ret = None
        return ret

    def _formatPostItem(self, in_post: dict[str, Any]) -> dict[str, str] | None:
        ret: dict[str, str] | None
        chatData = in_post.get("chat")
        postDate = in_post.get("date")
        postText = in_post.get("text")
        messageIdRaw = in_post.get("message_id")
        if not isinstance(chatData, dict):
            ret = None
            return ret
        username = chatData.get("username")
        if not isinstance(username, str):
            ret = None
            return ret
        if not isinstance(postDate, int) or not isinstance(postText, str):
            ret = None
            return ret
        oneLineText = postText.replace("\n", " ").strip()
        if isinstance(messageIdRaw, int | str):
            messageIdStr = str(messageIdRaw)
            if messageIdStr.isdigit():
                linkValue = f"https://t.me/{username}/{messageIdStr}"
            else:
                linkValue = f"https://t.me/{username}"
        else:
            linkValue = f"https://t.me/{username}"
        ret = {
            "channel": username,
            "dateUnixTs": str(postDate),
            "summary": oneLineText[:300],
            "link": linkValue,
        }
        return ret

    def _normalizeKeywordTerms(self, in_keywords: list[str]) -> list[str]:
        ret: list[str]
        normalizedTerms: list[str] = []
        seenTerms: set[str] = set()
        for keywordText in in_keywords:
            strippedText = str(keywordText or "").strip()
            if strippedText == "":
                continue
            loweredKey = strippedText.lower()
            if loweredKey in seenTerms:
                continue
            seenTerms.add(loweredKey)
            normalizedTerms.append(loweredKey)
            if len(normalizedTerms) >= _MAX_KEYWORD_PHRASES:
                break
        ret = normalizedTerms
        return ret

    def _mergeChannelLists(
        self,
        in_existing: list[Any],
        in_newRaw: list[str],
    ) -> list[str]:
        ret: list[str]
        mergedList: list[str] = []
        seenKeys: set[str] = set()
        for item in in_existing:
            if isinstance(item, str):
                normalizedValue = normalizeTelegramChannelUsername(in_raw=item)
                if normalizedValue is not None and normalizedValue not in seenKeys:
                    seenKeys.add(normalizedValue)
                    mergedList.append(normalizedValue)
        for rawChannel in in_newRaw:
            normalizedValue = normalizeTelegramChannelUsername(in_raw=rawChannel)
            if normalizedValue is not None and normalizedValue not in seenKeys:
                seenKeys.add(normalizedValue)
                mergedList.append(normalizedValue)
        ret = mergedList
        return ret

    def _mergeKeywordLists(
        self,
        in_existing: list[Any],
        in_newRaw: list[str],
    ) -> list[str]:
        ret: list[str]
        mergedList: list[str] = []
        seenKeys: set[str] = set()
        for item in in_existing:
            if isinstance(item, str):
                strippedText = item.strip()
                if strippedText != "":
                    loweredKey = strippedText.lower()
                    if loweredKey not in seenKeys:
                        seenKeys.add(loweredKey)
                        mergedList.append(strippedText)
        for keywordText in in_newRaw:
            strippedText = keywordText.strip()
            if strippedText != "":
                loweredKey = strippedText.lower()
                if loweredKey not in seenKeys:
                    seenKeys.add(loweredKey)
                    mergedList.append(strippedText)
            if len(mergedList) >= _MAX_KEYWORD_PHRASES:
                break
        ret = mergedList[:_MAX_KEYWORD_PHRASES]
        return ret

    def _loadTopicConfig(self, in_topicKey: str) -> dict[str, Any] | None:
        ret: dict[str, Any] | None
        memoryLines = self.in_memoryStore.readLongTermMemory()
        foundPayload: dict[str, Any] | None = None
        for lineText in memoryLines:
            strippedLine = lineText.strip()
            if strippedLine.startswith(_CONFIG_LINE_PREFIX) is False:
                continue
            jsonPart = strippedLine[len(_CONFIG_LINE_PREFIX) :].strip()
            try:
                payload = json.loads(jsonPart)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict) is False:
                continue
            if str(payload.get("kind", "")) != _KIND_DIGEST_TOPIC_CONFIG:
                continue
            if str(payload.get("topicKey", "")).strip().lower() != in_topicKey.strip().lower():
                continue
            foundPayload = payload
            break
        ret = foundPayload
        return ret

    def _upsertTopicConfigLine(self, in_payload: dict[str, Any]) -> None:
        memoryLines = self.in_memoryStore.readLongTermMemory()
        replacedLines: list[str] = []
        topicKeyValue = str(in_payload.get("topicKey", "") or "").strip().lower()
        didReplace = False
        for lineText in memoryLines:
            strippedLine = lineText.strip()
            if strippedLine.startswith(_CONFIG_LINE_PREFIX) is False:
                replacedLines.append(lineText)
                continue
            jsonPart = strippedLine[len(_CONFIG_LINE_PREFIX) :].strip()
            try:
                payload = json.loads(jsonPart)
            except json.JSONDecodeError:
                replacedLines.append(lineText)
                continue
            if isinstance(payload, dict) is False:
                replacedLines.append(lineText)
                continue
            if str(payload.get("kind", "")) != _KIND_DIGEST_TOPIC_CONFIG:
                replacedLines.append(lineText)
                continue
            existingKey = str(payload.get("topicKey", "") or "").strip().lower()
            if existingKey == topicKeyValue:
                replacedLines.append(_CONFIG_LINE_PREFIX + " " + json.dumps(in_payload, ensure_ascii=False, sort_keys=True))
                didReplace = True
            else:
                replacedLines.append(lineText)
        if didReplace is False:
            replacedLines.append(_CONFIG_LINE_PREFIX + " " + json.dumps(in_payload, ensure_ascii=False, sort_keys=True))
        self.in_memoryStore.writeLongTermMemory(in_lines=replacedLines)

    def _deleteTopicConfigLines(self, in_topicKey: str) -> bool:
        ret: bool
        memoryLines = self.in_memoryStore.readLongTermMemory()
        filteredLines: list[str] = []
        removedCount = 0
        targetKey = in_topicKey.strip().lower()
        for lineText in memoryLines:
            strippedLine = lineText.strip()
            if strippedLine.startswith(_CONFIG_LINE_PREFIX) is False:
                filteredLines.append(lineText)
                continue
            jsonPart = strippedLine[len(_CONFIG_LINE_PREFIX) :].strip()
            try:
                payload = json.loads(jsonPart)
            except json.JSONDecodeError:
                filteredLines.append(lineText)
                continue
            if isinstance(payload, dict) is False:
                filteredLines.append(lineText)
                continue
            if str(payload.get("kind", "")) != _KIND_DIGEST_TOPIC_CONFIG:
                filteredLines.append(lineText)
                continue
            existingKey = str(payload.get("topicKey", "") or "").strip().lower()
            if existingKey == targetKey:
                removedCount += 1
            else:
                filteredLines.append(lineText)
        self.in_memoryStore.writeLongTermMemory(in_lines=filteredLines)
        ret = removedCount > 0
        return ret

    def _buildReadStateStore(self) -> TelegramDigestReadStateStore:
        ret: TelegramDigestReadStateStore
        rootPath = Path(self.in_dataRootPath).resolve()
        statePath = rootPath / "state" / "telegram_digest_read_state.json"
        ret = TelegramDigestReadStateStore(in_stateFilePath=statePath)
        return ret


def refreshConfigKeywords(in_config: dict[str, Any]) -> list[str]:
    ret: list[str]
    rawKeywords = in_config.get("keywords", [])
    resultKeywords: list[str] = []
    if isinstance(rawKeywords, list):
        for item in rawKeywords:
            if isinstance(item, str) and item.strip() != "":
                resultKeywords.append(item.strip())
    ret = resultKeywords
    return ret
