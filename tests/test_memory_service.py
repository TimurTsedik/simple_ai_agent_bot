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
    assert "Есть новости по рынку РФ" in memoryBlock
    assert "Сделай дайджест" in memoryBlock


def testMemoryServiceIncludesDigestPreferenceHintsInMemoryBlock() -> None:
    with TemporaryDirectory() as tempDir:
        memorySettings = MemorySettings(
            memoryRootPath=str(Path(tempDir) / "memory"),
            longTermFileName="long_term.md",
            sessionSummaryFileName="summary.md",
            recentMessagesFileName="recent.md",
        )
        store = MarkdownMemoryStore(in_memorySettings=memorySettings)
        store.writeLongTermMemory(
            in_lines=[
                "- digest_pref_json: "
                '{"kind":"digest_user_preference","likedChannels":["ai_news"],'
                '"likedKeywords":["gpt"],"likedTopics":["ai"],"savedAt":"2026-01-01T00:00:00+00:00",'
                '"userNote":"more technical"}'
            ]
        )
        service = MemoryService(
            in_memoryStore=store,
            in_memoryPolicy=MemoryPolicy(),
            in_recentMessagesLimit=4,
            in_sessionSummaryMaxChars=2000,
        )
        memoryBlock = service.buildMemoryBlock(in_sessionId="telegram:1")

    assert "## Digest preference hints" in memoryBlock
    assert "ai_news" in memoryBlock
    assert "gpt" in memoryBlock


def testMemoryServiceIncludesEmailPreferenceHintsInMemoryBlock() -> None:
    with TemporaryDirectory() as tempDir:
        memorySettings = MemorySettings(
            memoryRootPath=str(Path(tempDir) / "memory"),
            longTermFileName="long_term.md",
            sessionSummaryFileName="summary.md",
            recentMessagesFileName="recent.md",
        )
        store = MarkdownMemoryStore(in_memorySettings=memorySettings)
        store.writeLongTermMemory(
            in_lines=[
                "- email_pref_json: "
                '{"kind":"email_user_preference",'
                '"preferredSenders":["research@aton.ru","alfabank.ru"],'
                '"preferredKeywords":["облигации"],'
                '"savedAt":"2026-01-01T00:00:00+00:00",'
                '"userNote":"corporate actions"}'
            ]
        )
        service = MemoryService(
            in_memoryStore=store,
            in_memoryPolicy=MemoryPolicy(),
            in_recentMessagesLimit=4,
            in_sessionSummaryMaxChars=2000,
        )
        memoryBlock = service.buildLongTermOnlyMemoryBlock()

    assert "## Email preference hints" in memoryBlock
    assert "research@aton.ru" in memoryBlock
    assert "alfabank.ru" in memoryBlock
    assert "облигации" in memoryBlock


def testMemoryServiceBuildsLongTermOnlyMemoryBlockForDigestFlows() -> None:
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
            in_sessionId="scheduler:email",
            in_userMessage="прочитай письма",
            in_finalAnswer="дайджест уже был выше",
            in_memoryCandidates=["Пользователь предпочитает краткий дайджест"],
        )

        memoryBlock = service.buildLongTermOnlyMemoryBlock()

    assert "## Session Summary" not in memoryBlock
    assert "## Recent Messages" not in memoryBlock
    assert "## Long-Term Memory" in memoryBlock
    assert "Пользователь предпочитает краткий дайджест" in memoryBlock


def testMemoryServiceSkipsWebSearchAccessDeniedInRecentAndSummary() -> None:
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
            in_userMessage="Поищи в интернете про кошек",
            in_finalAnswer="Не удалось выполнить поиск в интернете из-за ошибки доступа (ACCESS_DENIED).",
            in_memoryCandidates=[],
        )
        memoryBlock = service.buildMemoryBlock(in_sessionId="telegram:1")

    assert "assistant: Не удалось выполнить поиск в интернете" not in memoryBlock
