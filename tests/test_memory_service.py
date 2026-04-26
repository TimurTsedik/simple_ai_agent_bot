from pathlib import Path
from tempfile import TemporaryDirectory

from app.config.settingsModels import MemorySettings
from app.domain.policies.memoryPolicy import MemoryPolicy
from app.memory.services.memoryService import MemoryService
from app.memory.stores.markdownMemoryStore import MarkdownMemoryStore


def testMemoryServiceUpdatesRecentSummaryAndLongTerm() -> None:
    with TemporaryDirectory() as tempDir:
        memorySettings = MemorySettings(
            memoryRootPath=str(Path(tempDir) / "memory"),
            longTermFileName="long_term.md",
            sessionSummaryFileName="summary.md",
            recentMessagesFileName="recent.md",
        )
        store = MarkdownMemoryStore(in_memorySettings=memorySettings)
        service = MemoryService(
            in_memoryStore=store,
            in_memoryPolicy=MemoryPolicy(),
            in_recentMessagesLimit=4,
            in_sessionSummaryMaxChars=2000,
        )
        service.updateAfterRun(
            in_sessionId="telegram:1",
            in_userMessage="Сделай краткий дайджест",
            in_finalAnswer="Готово",
            in_memoryCandidates=[
                "Пользователь предпочитает короткий формат",
                "Сегодня проверить временную задачу",
            ],
        )
        memoryBlock = service.buildMemoryBlock(in_sessionId="telegram:1")

    assert "user: Сделай краткий дайджест" in memoryBlock
    assert "assistant: Готово" in memoryBlock
    assert "Пользователь предпочитает короткий формат" in memoryBlock
    assert "Сегодня проверить временную задачу" not in memoryBlock


def testMemoryServiceSkipsServiceAnswersInRecentAndSummary() -> None:
    with TemporaryDirectory() as tempDir:
        memorySettings = MemorySettings(
            memoryRootPath=str(Path(tempDir) / "memory"),
            longTermFileName="long_term.md",
            sessionSummaryFileName="summary.md",
            recentMessagesFileName="recent.md",
        )
        store = MarkdownMemoryStore(in_memorySettings=memorySettings)
        service = MemoryService(
            in_memoryStore=store,
            in_memoryPolicy=MemoryPolicy(),
            in_recentMessagesLimit=10,
            in_sessionSummaryMaxChars=2000,
        )
        service.updateAfterRun(
            in_sessionId="telegram:1",
            in_userMessage="Сделай дайджест",
            in_finalAnswer="Есть новости по рынку РФ",
            in_memoryCandidates=[],
        )
        service.updateAfterRun(
            in_sessionId="telegram:1",
            in_userMessage="Сделай дайджест еще раз",
            in_finalAnswer="Извините, достигнут лимит вызовов инструментов, попробуйте позже.",
            in_memoryCandidates=[],
        )
        memoryBlock = service.buildMemoryBlock(in_sessionId="telegram:1")

    assert "assistant: Есть новости по рынку РФ" in memoryBlock
    assert "assistant: Извините, достигнут лимит вызовов инструментов" not in memoryBlock
    assert "Последний ответ ассистента: Есть новости по рынку РФ" in memoryBlock
