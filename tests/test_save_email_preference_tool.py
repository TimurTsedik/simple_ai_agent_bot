from pathlib import Path
from tempfile import TemporaryDirectory

from app.config.settingsModels import MemorySettings
from app.memory.stores.markdownMemoryStore import MarkdownMemoryStore
from app.tools.implementations.saveEmailPreferenceTool import SaveEmailPreferenceTool


def testSaveEmailPreferenceToolRejectsEmptyPayload() -> None:
    with TemporaryDirectory() as tempDir:
        memorySettings = MemorySettings(
            memoryRootPath=str(Path(tempDir) / "memory"),
            longTermFileName="long_term.md",
            sessionSummaryFileName="summary.md",
            recentMessagesFileName="recent.md",
        )
        store = MarkdownMemoryStore(in_memorySettings=memorySettings)
        tool = SaveEmailPreferenceTool(in_memoryStore=store)
        result = tool.execute(
            in_args={
                "preferredSenders": [],
                "preferredKeywords": [],
                "userNote": "",
            }
        )
    assert result["ok"] is False


def testSaveEmailPreferenceToolWritesLongTermLine() -> None:
    with TemporaryDirectory() as tempDir:
        memorySettings = MemorySettings(
            memoryRootPath=str(Path(tempDir) / "memory"),
            longTermFileName="long_term.md",
            sessionSummaryFileName="summary.md",
            recentMessagesFileName="recent.md",
        )
        store = MarkdownMemoryStore(in_memorySettings=memorySettings)
        tool = SaveEmailPreferenceTool(in_memoryStore=store)
        result = tool.execute(
            in_args={
                "preferredSenders": ["Research@Aton.RU", "alfabank.ru"],
                "preferredKeywords": ["облигации"],
                "userNote": "корпоративные действия и аналитика",
            }
        )
        lines = store.readLongTermMemory()

    assert result["ok"] is True
    assert len(lines) == 1
    assert "email_pref_json" in lines[0]
    assert "research@aton.ru" in lines[0]
    assert "alfabank.ru" in lines[0]


def testSaveEmailPreferenceToolDeduplicatesSenders() -> None:
    with TemporaryDirectory() as tempDir:
        memorySettings = MemorySettings(
            memoryRootPath=str(Path(tempDir) / "memory"),
            longTermFileName="long_term.md",
            sessionSummaryFileName="summary.md",
            recentMessagesFileName="recent.md",
        )
        store = MarkdownMemoryStore(in_memorySettings=memorySettings)
        tool = SaveEmailPreferenceTool(in_memoryStore=store)
        result = tool.execute(
            in_args={
                "preferredSenders": ["a@x.ru", "A@X.RU", " a@x.ru "],
                "preferredKeywords": [],
                "userNote": "",
            }
        )

    assert result["ok"] is True
    sendersSaved = result["saved"]["preferredSenders"]
    assert sendersSaved == ["a@x.ru"]
