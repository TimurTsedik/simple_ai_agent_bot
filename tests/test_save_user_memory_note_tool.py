from pathlib import Path
from tempfile import TemporaryDirectory

from app.config.settingsModels import MemorySettings
from app.memory.stores.markdownMemoryStore import MarkdownMemoryStore
from app.tools.implementations.saveUserMemoryNoteTool import SaveUserMemoryNoteTool


def testSaveUserMemoryNoteAppendsUserMemoryJsonLine() -> None:
    with TemporaryDirectory() as temp_dir:
        memory_settings = MemorySettings(
            memoryRootPath=str(Path(temp_dir) / "memory"),
            longTermFileName="long_term.md",
            sessionSummaryFileName="summary.md",
            recentMessagesFileName="recent.md",
        )
        store = MarkdownMemoryStore(in_memorySettings=memory_settings)
        tool = SaveUserMemoryNoteTool(in_memoryStore=store)
        principal = "telegramUser:7"
        result = tool.execute(
            in_args={"noteText": "Пользователь предпочитает утренние ответы."},
            in_memoryPrincipalId=principal,
        )
        assert result["ok"] is True
        lines = store.readLongTermMemory(in_memoryPrincipalId=principal)
        assert len(lines) == 1
        assert "user_memory_json" in lines[0]
        assert "explicit_user_note" in lines[0]
        assert "утренние" in lines[0]


def testSaveUserMemoryNoteRejectsEmptyNote() -> None:
    with TemporaryDirectory() as temp_dir:
        memory_settings = MemorySettings(
            memoryRootPath=str(Path(temp_dir) / "memory"),
            longTermFileName="long_term.md",
            sessionSummaryFileName="summary.md",
            recentMessagesFileName="recent.md",
        )
        store = MarkdownMemoryStore(in_memorySettings=memory_settings)
        tool = SaveUserMemoryNoteTool(in_memoryStore=store)
        result = tool.execute(
            in_args={"noteText": "   "},
            in_memoryPrincipalId="telegramUser:1",
        )
        assert result["ok"] is False
