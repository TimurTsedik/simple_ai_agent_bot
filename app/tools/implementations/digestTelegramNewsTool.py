from dataclasses import dataclass
from datetime import UTC, datetime
import html
import re
import time
from typing import Any, Callable

import requests

from app.tools.digestTopicSeeds import collectSeedKeywordsForTopics
from app.tools.telegramUsernameNormalize import normalizeTelegramChannelUsername


def _getTodayStartUnixTs() -> int:
    nowUtc = datetime.now(UTC)
    todayStartUtc = nowUtc.replace(hour=0, minute=0, second=0, microsecond=0)
    ret = int(todayStartUtc.timestamp())
    return ret


def _getNowUnixTs() -> int:
    ret: int
    ret = int(datetime.now(UTC).timestamp())
    return ret


def _floorUnixTsToHour(in_unixTs: int) -> int:
    ret: int
    if in_unixTs <= 0:
        ret = 0
    else:
        ret = in_unixTs - (in_unixTs % 3600)
    return ret


def _floorUnixTsToDayUtc(in_unixTs: int) -> int:
    ret: int
    if in_unixTs <= 0:
        ret = 0
    else:
        dt = datetime.fromtimestamp(in_unixTs, tz=UTC)
        dayStart = dt.replace(hour=0, minute=0, second=0, microsecond=0)
        ret = int(dayStart.timestamp())
    return ret


def _defaultFetchHtml(in_url: str, in_timeoutSeconds: int) -> str:
    ret: str
    response = requests.get(in_url, timeout=in_timeoutSeconds)
    response.raise_for_status()
    response.encoding = response.encoding or "utf-8"
    ret = response.text
    return ret


_MAX_DIGEST_KEYWORD_PHRASES = 48


@dataclass
class DigestTelegramNewsTool:
    getDigestChannelUsernames: Callable[[], list[str]]
    getDefaultKeywords: Callable[[], list[str]]
    getTopicSeedsForTopics: Callable[[list[str]], list[str]] = collectSeedKeywordsForTopics
    todayStartUnixTsProvider: Callable[[], int] = _getTodayStartUnixTs
    nowUnixTsProvider: Callable[[], int] = _getNowUnixTs
    fetchHtmlCallable: Callable[[str, int], str] = _defaultFetchHtml
    sleepCallable: Callable[[float], None] = time.sleep
    fetchRetryDelaysSeconds: tuple[float, ...] = (0.15, 0.4, 1.0)

    def execute(self, in_args: dict[str, Any]) -> dict[str, Any]:
        ret: dict[str, Any]
        digestChannelUsernames = list(self.getDigestChannelUsernames())
        defaultKeywords = list(self.getDefaultKeywords())
        requestedKeywords = [
            item for item in in_args.get("keywords", []) if isinstance(item, str)
        ]
        topicIds = [item for item in in_args.get("topics", []) if isinstance(item, str)]
        topicSeedKeywords = list(self.getTopicSeedsForTopics(topicIds))
        afterTopicMerge = self._mergeKeywords(
            in_requestedKeywords=requestedKeywords,
            in_defaultKeywords=topicSeedKeywords,
        )
        effectiveKeywords = self._mergeKeywords(
            in_requestedKeywords=afterTopicMerge,
            in_defaultKeywords=defaultKeywords,
        )
        cappedKeywords = effectiveKeywords[:_MAX_DIGEST_KEYWORD_PHRASES]
        keywords = [item.lower() for item in cappedKeywords if item.strip()]
        requestedChannelsRaw = [
            item for item in in_args.get("channels", []) if isinstance(item, str)
        ]
        normalizedChannels: list[str] = []
        invalidChannelArgs: list[str] = []
        seenChannelKeys: set[str] = set()
        for rawChannel in requestedChannelsRaw:
            normalized = normalizeTelegramChannelUsername(in_raw=rawChannel)
            if normalized is None:
                stripped = rawChannel.strip()
                if stripped != "":
                    invalidChannelArgs.append(stripped)
                continue
            if normalized in seenChannelKeys:
                continue
            seenChannelKeys.add(normalized)
            normalizedChannels.append(normalized)
        rawSinceUnixTs = int(in_args.get("sinceUnixTs", 0))
        rawSinceHours = int(in_args.get("sinceHours", 0))
        sinceUnixTs = (
            rawSinceUnixTs
            if rawSinceUnixTs > 0
            else (
                (
                    _floorUnixTsToDayUtc(
                        max(0, self.nowUnixTsProvider() - rawSinceHours * 3600)
                    )
                    if rawSinceHours >= 24
                    else max(0, self.nowUnixTsProvider() - rawSinceHours * 3600)
                )
                if rawSinceHours > 0
                else self.todayStartUnixTsProvider()
            )
        )
        maxItems = int(in_args.get("maxItems", 10))
        if len(normalizedChannels) > 0:
            channelsFilter = set(normalizedChannels)
        else:
            channelsFilter = set(digestChannelUsernames)
        channelErrors: dict[str, str] = {}
        channelPosts = self._loadChannelPosts(
            in_channels=sorted(channelsFilter),
            io_channelErrors=channelErrors,
        )
        dedupedPosts = self._dedupePosts(in_posts=channelPosts)
        totalParsedPosts = len(channelPosts)
        totalDedupedPosts = len(dedupedPosts)
        filteredOutByInvalidShape = 0
        filteredOutByChannel = 0
        filteredOutByTime = 0
        filteredOutByKeywords = 0
        filteredOutByDuplicate = 0
        results: list[dict[str, str]] = []
        seenKeys: set[tuple[str, str]] = set()
        for channelPost in reversed(dedupedPosts):
            postDate = channelPost.get("date")
            postText = channelPost.get("text")
            chatData = channelPost.get("chat")
            if not isinstance(postDate, int) or not isinstance(postText, str):
                filteredOutByInvalidShape += 1
                continue
            if not isinstance(chatData, dict):
                filteredOutByInvalidShape += 1
                continue
            username = chatData.get("username")
            if not isinstance(username, str):
                filteredOutByInvalidShape += 1
                continue
            if username not in channelsFilter:
                filteredOutByChannel += 1
                continue
            if postDate < sinceUnixTs:
                filteredOutByTime += 1
                continue
            if keywords:
                loweredText = postText.lower()
                if not any(item in loweredText for item in keywords):
                    filteredOutByKeywords += 1
                    continue
            messageId = channelPost.get("message_id")
            messageIdStr = str(messageId) if messageId is not None else ""
            dedupKey = (username, messageIdStr)
            if dedupKey in seenKeys:
                filteredOutByDuplicate += 1
                continue
            seenKeys.add(dedupKey)
            if isinstance(messageId, int | str):
                link = f"https://t.me/{username}/{messageId}"
            else:
                link = f"https://t.me/{username}"
            oneLineText = postText.replace("\n", " ").strip()
            results.append(
                {
                    "channel": username,
                    "dateUnixTs": str(postDate),
                    "summary": oneLineText[:300],
                    "link": link,
                }
            )
            if len(results) >= maxItems:
                break
        ret = {
            "items": results,
            "count": len(results),
            "sinceUnixTsUsed": sinceUnixTs,
            "channelErrors": channelErrors,
            "resolvedChannels": sorted(channelsFilter),
            "resolvedTopics": [t.strip().lower() for t in topicIds if t.strip()],
            "diagnostics": {
                "requestedChannelsCount": len(requestedChannelsRaw),
                "invalidChannelArgsCount": len(invalidChannelArgs),
                "resolvedChannelsCount": len(channelsFilter),
                "fetchErrorChannelsCount": len(channelErrors),
                "totalParsedPosts": totalParsedPosts,
                "totalDedupedPosts": totalDedupedPosts,
                "filteredOutByInvalidShape": filteredOutByInvalidShape,
                "filteredOutByChannel": filteredOutByChannel,
                "filteredOutByTime": filteredOutByTime,
                "filteredOutByKeywords": filteredOutByKeywords,
                "filteredOutByDuplicate": filteredOutByDuplicate,
                "returnedItemsCount": len(results),
                "keywordsAppliedCount": len(keywords),
            },
        }
        if len(invalidChannelArgs) > 0:
            ret["invalidChannelArgs"] = invalidChannelArgs
        return ret

    def _mergeKeywords(
        self,
        in_requestedKeywords: list[str],
        in_defaultKeywords: list[str],
    ) -> list[str]:
        ret: list[str]
        mergedKeywords: list[str] = []
        seenKeywords: set[str] = set()
        for keywordValue in in_requestedKeywords + in_defaultKeywords:
            normalizedKeyword = keywordValue.strip()
            normalizedKey = normalizedKeyword.lower()
            if not normalizedKeyword:
                continue
            if normalizedKey in seenKeywords:
                continue
            seenKeywords.add(normalizedKey)
            mergedKeywords.append(normalizedKeyword)
        ret = mergedKeywords
        return ret

    def _loadChannelPosts(
        self,
        in_channels: list[str],
        io_channelErrors: dict[str, str],
    ) -> list[dict[str, Any]]:
        ret: list[dict[str, Any]]
        collectedItems: list[dict[str, Any]] = []
        for channelName in in_channels:
            pageUrl = f"https://t.me/s/{channelName}"
            pageHtml, fetchError = self._fetchHtmlWithRetries(in_url=pageUrl)
            if fetchError is not None:
                io_channelErrors[channelName] = fetchError
                continue
            if not pageHtml.strip():
                io_channelErrors[channelName] = "empty_response"
                continue
            collectedItems.extend(
                self._parseChannelPage(in_channelName=channelName, in_pageHtml=pageHtml)
            )
        ret = collectedItems
        return ret

    def fetchRawPostsForChannels(
        self,
        in_channels: list[str],
        io_channelErrors: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        """Loads and deduplicates parsed posts for public channels (no keyword/time filtering)."""
        ret: list[dict[str, Any]]
        errorBucket: dict[str, str]
        if io_channelErrors is None:
            errorBucket = {}
        else:
            errorBucket = io_channelErrors
        collectedPosts = self._loadChannelPosts(
            in_channels=in_channels,
            io_channelErrors=errorBucket,
        )
        ret = self._dedupePosts(in_posts=collectedPosts)
        return ret

    def _fetchHtmlWithRetries(self, in_url: str) -> tuple[str, str | None]:
        ret: tuple[str, str | None]
        lastErrorText: str | None = None
        pageHtml = ""
        delayList = list(self.fetchRetryDelaysSeconds)
        attemptCount = len(delayList) + 1
        attemptIndex = 0
        while attemptIndex < attemptCount:
            try:
                pageHtml = self.fetchHtmlCallable(in_url, 20)
                lastErrorText = None
                break
            except Exception as in_exc:
                lastErrorText = str(in_exc)
                pageHtml = ""
                if attemptIndex < len(delayList):
                    self.sleepCallable(delayList[attemptIndex])
            attemptIndex += 1
        ret = (pageHtml, lastErrorText)
        return ret

    def _dedupePosts(self, in_posts: list[dict[str, Any]]) -> list[dict[str, Any]]:
        ret: list[dict[str, Any]]
        byKey: dict[tuple[str, str], dict[str, Any]] = {}
        for onePost in in_posts:
            chatData = onePost.get("chat")
            messageId = onePost.get("message_id")
            if not isinstance(chatData, dict):
                continue
            username = chatData.get("username")
            if not isinstance(username, str):
                continue
            key = (username, str(messageId))
            existingPost = byKey.get(key)
            if existingPost is None:
                byKey[key] = onePost
            else:
                existingDate = existingPost.get("date")
                newDate = onePost.get("date")
                if isinstance(newDate, int) and isinstance(existingDate, int):
                    if newDate > existingDate:
                        byKey[key] = onePost
        ret = list(byKey.values())
        return ret

    def _parseChannelPage(
        self,
        in_channelName: str,
        in_pageHtml: str,
    ) -> list[dict[str, Any]]:
        ret: list[dict[str, Any]]
        parsedItems = self._parseWithPrimaryPattern(
            in_channelName=in_channelName,
            in_pageHtml=in_pageHtml,
        )
        if len(parsedItems) == 0:
            parsedItems = self._parseWithFallbackPattern(
                in_channelName=in_channelName,
                in_pageHtml=in_pageHtml,
            )
        ret = parsedItems
        return ret

    def _parseWithPrimaryPattern(
        self,
        in_channelName: str,
        in_pageHtml: str,
    ) -> list[dict[str, Any]]:
        ret: list[dict[str, Any]]
        parsedItems: list[dict[str, Any]] = []
        messagePattern = re.compile(
            r'data-post="(?P<postPath>[^"]+)"[\s\S]*?'
            r'<time[^>]*datetime="(?P<dateTime>[^"]+)"[\s\S]*?</time>[\s\S]*?'
            r'<div class="tgme_widget_message_text[^"]*"[^>]*>(?P<textHtml>[\s\S]*?)</div>',
            re.MULTILINE,
        )
        for match in messagePattern.finditer(in_pageHtml):
            oneItem = self._postDictFromMatch(
                in_channelName=in_channelName,
                in_match=match,
            )
            if oneItem is not None:
                parsedItems.append(oneItem)
        ret = parsedItems
        return ret

    def _parseWithFallbackPattern(
        self,
        in_channelName: str,
        in_pageHtml: str,
    ) -> list[dict[str, Any]]:
        ret: list[dict[str, Any]]
        parsedItems: list[dict[str, Any]] = []
        loosePattern = re.compile(
            r'data-post="(?P<postPath>[^"]+)"[\s\S]*?'
            r'<div class="tgme_widget_message_text[^"]*"[^>]*>(?P<textHtml>[\s\S]*?)</div>',
            re.MULTILINE,
        )
        for match in loosePattern.finditer(in_pageHtml):
            postPath = match.group("postPath")
            textHtml = match.group("textHtml")
            postDateUnixTs = self._extractUnixFromPostPathOrHtml(
                in_postPath=postPath,
                in_fullHtml=in_pageHtml,
            )
            if postDateUnixTs is None:
                postDateUnixTs = 0
            plainText = self._htmlToPlainText(in_htmlText=textHtml)
            if not plainText:
                continue
            messageId = postPath.split("/")[-1]
            parsedItems.append(
                {
                    "message_id": int(messageId) if messageId.isdigit() else messageId,
                    "date": postDateUnixTs,
                    "text": plainText,
                    "chat": {"username": in_channelName},
                }
            )
        ret = parsedItems
        return ret

    def _postDictFromMatch(
        self,
        in_channelName: str,
        in_match: re.Match[str],
    ) -> dict[str, Any] | None:
        ret: dict[str, Any] | None
        postPath = in_match.group("postPath")
        dateTimeText = in_match.group("dateTime")
        textHtml = in_match.group("textHtml")
        postDateUnixTs = self._parseIsoDateToUnix(in_isoDateText=dateTimeText)
        if postDateUnixTs is None:
            ret = None
            return ret
        plainText = self._htmlToPlainText(in_htmlText=textHtml)
        if not plainText:
            ret = None
            return ret
        messageId = postPath.split("/")[-1]
        ret = {
            "message_id": int(messageId) if messageId.isdigit() else messageId,
            "date": postDateUnixTs,
            "text": plainText,
            "chat": {"username": in_channelName},
        }
        return ret

    def _extractUnixFromPostPathOrHtml(
        self,
        in_postPath: str,
        in_fullHtml: str,
    ) -> int | None:
        ret: int | None
        snippetStart = in_fullHtml.find(in_postPath)
        if snippetStart < 0:
            ret = None
            return ret
        snippet = in_fullHtml[snippetStart : snippetStart + 800]
        timeMatch = re.search(r'datetime="([^"]+)"', snippet)
        if timeMatch is None:
            ret = None
            return ret
        ret = self._parseIsoDateToUnix(in_isoDateText=timeMatch.group(1))
        return ret

    def _parseIsoDateToUnix(self, in_isoDateText: str) -> int | None:
        ret: int | None
        try:
            dateValue = datetime.fromisoformat(in_isoDateText.replace("Z", "+00:00"))
            ret = int(dateValue.timestamp())
        except ValueError:
            ret = None
        return ret

    def _htmlToPlainText(self, in_htmlText: str) -> str:
        ret: str
        withoutTags = re.sub(r"<[^>]+>", " ", in_htmlText)
        unescaped = html.unescape(withoutTags)
        normalized = re.sub(r"\s+", " ", unescaped).strip()
        ret = normalized
        return ret
