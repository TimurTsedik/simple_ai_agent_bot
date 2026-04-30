import json

from app.common.timeProvider import getUtcNowIso
from app.common.truncation import truncateText
from app.domain.policies.memoryPolicy import MemoryPolicy
from app.memory.stores.markdownMemoryStore import MarkdownMemoryStore


class MemoryService:
    def __init__(
        self,
        in_memoryStore: MarkdownMemoryStore,
        in_memoryPolicy: MemoryPolicy,
        in_recentMessagesLimit: int,
        in_sessionSummaryMaxChars: int,
    ) -> None:
        self._memoryStore = in_memoryStore
        self._memoryPolicy = in_memoryPolicy
        self._recentMessagesLimit = in_recentMessagesLimit
        self._sessionSummaryMaxChars = in_sessionSummaryMaxChars

    def buildMemoryBlock(self, in_sessionId: str) -> str:
        ret: str
        recentLines = self._memoryStore.readSessionRecentMessages(in_sessionId=in_sessionId)
        summaryText = self._memoryStore.readSessionSummary(in_sessionId=in_sessionId)
        longTermLines = self._memoryStore.readLongTermMemory()
        ret = (
            "## Session Summary\n"
            + summaryText
            + "\n\n## Recent Messages\n"
            + "\n".join(recentLines)
            + "\n\n"
            + self._buildLongTermBlock(in_longTermLines=longTermLines)
        )
        return ret

    def buildLongTermOnlyMemoryBlock(self) -> str:
        ret: str
        longTermLines = self._memoryStore.readLongTermMemory()
        ret = self._buildLongTermBlock(in_longTermLines=longTermLines)
        return ret

    def _buildLongTermBlock(self, in_longTermLines: list[str]) -> str:
        ret: str
        digestHintsBlock = self._buildDigestPreferenceHintsBlock(
            in_longTermLines=in_longTermLines
        )
        ret = "## Long-Term Memory\n" + "\n".join(in_longTermLines)
        if digestHintsBlock.strip() != "":
            ret += (
                "\n\n## Digest preference hints (soft guidance)\n"
                "Use only when the user did not explicitly override topics/channels/keywords. "
                "Prefer matching these hints in digest_telegram_news args.\n"
                + digestHintsBlock
            )
        return ret

    def _buildDigestPreferenceHintsBlock(self, in_longTermLines: list[str]) -> str:
        ret: str
        renderedLines: list[str] = []
        prefixText = "- digest_pref_json:"
        for lineText in in_longTermLines:
            strippedLine = lineText.strip()
            if strippedLine.startswith(prefixText) is False:
                continue
            jsonPart = strippedLine[len(prefixText) :].strip()
            try:
                payload = json.loads(jsonPart)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict) is False:
                continue
            if str(payload.get("kind", "")) != "digest_user_preference":
                continue
            topicsValue = payload.get("likedTopics", [])
            channelsValue = payload.get("likedChannels", [])
            keywordsValue = payload.get("likedKeywords", [])
            noteValue = str(payload.get("userNote", "") or "")
            savedAtValue = str(payload.get("savedAt", "") or "")
            topicsText = ", ".join(str(t) for t in topicsValue) if isinstance(topicsValue, list) else ""
            channelsText = ", ".join(str(c) for c in channelsValue) if isinstance(channelsValue, list) else ""
            keywordsText = ", ".join(str(k) for k in keywordsValue) if isinstance(keywordsValue, list) else ""
            renderedLines.append(
                f"- savedAt={savedAtValue}; topics=[{topicsText}]; channels=[{channelsText}]; "
                f"keywords=[{keywordsText}]; note={noteValue}"
            )
        keptLines = renderedLines[-12:]
        ret = "\n".join(keptLines)
        return ret

    def updateAfterRun(
        self,
        in_sessionId: str,
        in_userMessage: str,
        in_finalAnswer: str,
        in_memoryCandidates: list[str],
    ) -> None:
        self._updateRecentMessages(
            in_sessionId=in_sessionId,
            in_userMessage=in_userMessage,
            in_finalAnswer=in_finalAnswer,
        )
        self._updateSessionSummary(
            in_sessionId=in_sessionId,
            in_userMessage=in_userMessage,
            in_finalAnswer=in_finalAnswer,
        )
        self._updateLongTermMemory(in_memoryCandidates=in_memoryCandidates)

    def resetSession(self, in_sessionId: str) -> None:
        self._memoryStore.clearSessionMemory(in_sessionId=in_sessionId)

    def _updateRecentMessages(
        self,
        in_sessionId: str,
        in_userMessage: str,
        in_finalAnswer: str,
    ) -> None:
        recentLines = self._memoryStore.readSessionRecentMessages(in_sessionId=in_sessionId)
        recentLines.append(f"- user: {in_userMessage}")
        isServiceAnswer = self._isServiceAssistantAnswer(in_finalAnswer=in_finalAnswer)
        if isServiceAnswer is False:
            recentLines.append(f"- assistant: {in_finalAnswer}")
        keptLines = recentLines[-self._recentMessagesLimit :]
        self._memoryStore.writeSessionRecentMessages(
            in_sessionId=in_sessionId,
            in_lines=keptLines,
        )

    def _updateSessionSummary(
        self,
        in_sessionId: str,
        in_userMessage: str,
        in_finalAnswer: str,
    ) -> None:
        isServiceAnswer = self._isServiceAssistantAnswer(in_finalAnswer=in_finalAnswer)
        if isServiceAnswer is False:
            previousSummary = self._memoryStore.readSessionSummary(
                in_sessionId=in_sessionId
            )
            timestampText = getUtcNowIso()
            newEntry = (
                f"### {timestampText}\n"
                f"Пользователь: {in_userMessage}\n"
                f"Ассистент: {in_finalAnswer}\n\n"
            )
            combinedSummary = newEntry
            if previousSummary.strip():
                combinedSummary = newEntry + previousSummary.strip()
            truncatedSummary, _isTruncated = truncateText(
                in_text=combinedSummary,
                in_maxChars=self._sessionSummaryMaxChars,
            )
            self._memoryStore.writeSessionSummary(
                in_sessionId=in_sessionId,
                in_text=truncatedSummary,
            )

    def _updateLongTermMemory(self, in_memoryCandidates: list[str]) -> None:
        existingLines = self._memoryStore.readLongTermMemory()
        acceptedCandidates = self._memoryPolicy.filterLongTermCandidates(
            in_candidates=in_memoryCandidates
        )
        mergedLines = list(existingLines)
        for candidateText in acceptedCandidates:
            bulletLine = f"- {candidateText}"
            if bulletLine not in mergedLines:
                mergedLines.append(bulletLine)
        self._memoryStore.writeLongTermMemory(in_lines=mergedLines)

    def _isServiceAssistantAnswer(self, in_finalAnswer: str) -> bool:
        ret: bool
        loweredAnswer = in_finalAnswer.lower()
        serviceMarkers = [
            "остановка:",
            "достигнут лимит",
            "лимит вызовов инструментов",
            "limit reached",
            "tool limit",
            "max_tool_calls",
            "max_steps",
            "max execution",
            "невалидный json",
            "tool_call_blocked",
            "отключённых tool",
            "access_denied",
            "web search access denied",
            "не удалось выполнить поиск в интернете",
        ]
        ret = any(item in loweredAnswer for item in serviceMarkers)
        return ret
