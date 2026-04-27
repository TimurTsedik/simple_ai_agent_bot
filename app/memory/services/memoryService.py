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
            + "\n\n## Long-Term Memory\n"
            + "\n".join(longTermLines)
        )
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
