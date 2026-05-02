"""Регрессии изоляции памяти и read_memory_file между tenant-ключами."""

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from app.config.settingsModels import MemorySettings
from app.memory.services.memoryService import MemoryService
from app.domain.policies.memoryPolicy import MemoryPolicy
from app.memory.stores.markdownMemoryStore import MarkdownMemoryStore
from app.tools.implementations.readMemoryFileTool import ReadMemoryFileTool


def testLongTermMemoryIsolatedBetweenPrincipals() -> None:
    with TemporaryDirectory() as tempDir:
        memorySettings = MemorySettings(
            memoryRootPath=str(Path(tempDir) / "memory"),
            longTermFileName="long_term.md",
            sessionSummaryFileName="summary.md",
            recentMessagesFileName="recent.md",
        )
        store = MarkdownMemoryStore(in_memorySettings=memorySettings)
        store.writeLongTermMemory(
            in_memoryPrincipalId="telegramUser:1",
            in_lines=["- secret-user-one"],
        )
        store.writeLongTermMemory(
            in_memoryPrincipalId="telegramUser:2",
            in_lines=["- secret-user-two"],
        )
        service = MemoryService(
            in_memoryStore=store,
            in_memoryPolicy=MemoryPolicy(),
            in_recentMessagesLimit=4,
            in_sessionSummaryMaxChars=2000,
        )
        blockOne = service.buildLongTermOnlyMemoryBlock(in_memoryPrincipalId="telegramUser:1")
        blockTwo = service.buildLongTermOnlyMemoryBlock(in_memoryPrincipalId="telegramUser:2")

    assert "secret-user-one" in blockOne
    assert "secret-user-two" not in blockOne
    assert "secret-user-two" in blockTwo
    assert "secret-user-one" not in blockTwo


def testReadMemoryFileToolDeniesForeignSessionDirectory() -> None:
    with TemporaryDirectory() as tempDir:
        memoryRoot = Path(tempDir) / "memory"
        sessionsRoot = memoryRoot / "sessions"
        ownDir = sessionsRoot / "telegramUser_1"
        foreignDir = sessionsRoot / "telegramUser_2"
        ownDir.mkdir(parents=True)
        foreignDir.mkdir(parents=True)
        targetForeign = foreignDir / "recent.md"
        targetForeign.write_text("leak", encoding="utf-8")
        tool = ReadMemoryFileTool(
            in_memoryRootPath=str(memoryRoot),
            in_allowedReadOnlyPaths=[str(memoryRoot)],
        )
        with pytest.raises(PermissionError):
            tool.execute(
                in_args={"relativePath": str(targetForeign), "maxChars": 100},
                in_memoryPrincipalId="telegramUser:1",
            )
