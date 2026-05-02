from pathlib import Path
from tempfile import TemporaryDirectory

from app.config.settingsModels import MemorySettings
from app.memory.stores.markdownMemoryStore import MarkdownMemoryStore
from app.tools.implementations.saveDigestPreferenceTool import SaveDigestPreferenceTool


def testSaveDigestPreferenceToolRejectsEmptyPayload() -> None:
    with TemporaryDirectory() as tempDir:
        memorySettings = MemorySettings(
            memoryRootPath=str(Path(tempDir) / "memory"),
            longTermFileName="long_term.md",
            sessionSummaryFileName="summary.md",
            recentMessagesFileName="recent.md",
        )
        store = MarkdownMemoryStore(in_memorySettings=memorySettings)
        tool = SaveDigestPreferenceTool(in_memoryStore=store)
        result = tool.execute(
            in_args={
                "likedTopics": [],
                "likedChannels": [],
                "likedKeywords": [],
                "userNote": "",
            },
            in_memoryPrincipalId="telegramUser:1",
        )
    assert result["ok"] is False


def testSaveDigestPreferenceToolWritesLongTermLine() -> None:
    with TemporaryDirectory() as tempDir:
        memorySettings = MemorySettings(
            memoryRootPath=str(Path(tempDir) / "memory"),
            longTermFileName="long_term.md",
            sessionSummaryFileName="summary.md",
            recentMessagesFileName="recent.md",
        )
        store = MarkdownMemoryStore(in_memorySettings=memorySettings)
        tool = SaveDigestPreferenceTool(in_memoryStore=store)
        result = tool.execute(
            in_args={
                "likedTopics": ["ai"],
                "likedChannels": ["@MyChannel"],
                "likedKeywords": ["gpt"],
                "userNote": "prefer deep dives",
            },
            in_memoryPrincipalId="telegramUser:1",
        )
        lines = store.readLongTermMemory(in_memoryPrincipalId="telegramUser:1")

    assert result["ok"] is True
    assert len(lines) == 1
    assert "digest_pref_json" in lines[0]
    assert "mychannel" in lines[0].lower()
