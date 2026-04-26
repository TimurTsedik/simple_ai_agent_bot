from dataclasses import dataclass
from datetime import UTC, datetime
import html
import re
from typing import Any, Callable

import requests


def _getTodayStartUnixTs() -> int:
    nowUtc = datetime.now(UTC)
    todayStartUtc = nowUtc.replace(hour=0, minute=0, second=0, microsecond=0)
    ret = int(todayStartUtc.timestamp())
    return ret


def _defaultFetchHtml(in_url: str, in_timeoutSeconds: int) -> str:
    ret: str
    response = requests.get(in_url, timeout=in_timeoutSeconds)
    response.raise_for_status()
    response.encoding = response.encoding or "utf-8"
    ret = response.text
    return ret


@dataclass
class DigestTelegramNewsTool:
    digestChannelUsernames: list[str]
    defaultKeywords: list[str]
    todayStartUnixTsProvider: Callable[[], int] = _getTodayStartUnixTs
    fetchHtmlCallable: Callable[[str, int], str] = _defaultFetchHtml

    def execute(self, in_args: dict[str, Any]) -> dict[str, Any]:
        ret: dict[str, Any]
        requestedKeywords = [
            item for item in in_args.get("keywords", []) if isinstance(item, str)
        ]
        effectiveKeywords = self._mergeKeywords(
            in_requestedKeywords=requestedKeywords,
            in_defaultKeywords=self.defaultKeywords,
        )
        keywords = [item.lower() for item in effectiveKeywords if item.strip()]
        rawSinceUnixTs = int(in_args.get("sinceUnixTs", 0))
        sinceUnixTs = (
            rawSinceUnixTs
            if rawSinceUnixTs > 0
            else self.todayStartUnixTsProvider()
        )
        maxItems = int(in_args.get("maxItems", 10))
        channelsFilter = set(self.digestChannelUsernames)
        channelPosts = self._loadChannelPosts(in_channels=sorted(channelsFilter))
        results: list[dict[str, str]] = []
        for channelPost in reversed(channelPosts):
            postDate = channelPost.get("date")
            postText = channelPost.get("text")
            chatData = channelPost.get("chat")
            if not isinstance(postDate, int) or not isinstance(postText, str):
                continue
            if not isinstance(chatData, dict):
                continue
            username = chatData.get("username")
            if not isinstance(username, str):
                continue
            if username not in channelsFilter:
                continue
            if postDate < sinceUnixTs:
                continue
            if keywords:
                loweredText = postText.lower()
                if not any(item in loweredText for item in keywords):
                    continue
            messageId = channelPost.get("message_id")
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
        ret = {"items": results, "count": len(results), "sinceUnixTsUsed": sinceUnixTs}
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

    def _loadChannelPosts(self, in_channels: list[str]) -> list[dict[str, Any]]:
        ret: list[dict[str, Any]]
        collectedItems: list[dict[str, Any]] = []
        for channelName in in_channels:
            pageUrl = f"https://t.me/s/{channelName}"
            try:
                pageHtml = self.fetchHtmlCallable(pageUrl, 20)
            except Exception:
                continue
            collectedItems.extend(
                self._parseChannelPage(in_channelName=channelName, in_pageHtml=pageHtml)
            )
        ret = collectedItems
        return ret

    def _parseChannelPage(
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
            postPath = match.group("postPath")
            dateTimeText = match.group("dateTime")
            textHtml = match.group("textHtml")
            postDateUnixTs = self._parseIsoDateToUnix(in_isoDateText=dateTimeText)
            if postDateUnixTs is None:
                continue
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
