import shutil
from pathlib import Path

from app.config.settingsModels import MemorySettings


class MarkdownMemoryStore:
    def __init__(self, in_memorySettings: MemorySettings) -> None:
        self._memorySettings = in_memorySettings
        self._rootPath = Path(in_memorySettings.memoryRootPath)

    def readSessionRecentMessages(self, in_sessionId: str) -> list[str]:
        ret: list[str]
        filePath = self._buildSessionFilePath(
            in_sessionId=in_sessionId,
            in_fileName=self._memorySettings.recentMessagesFileName,
        )
        ret = self._readLines(in_filePath=filePath)
        return ret

    def writeSessionRecentMessages(self, in_sessionId: str, in_lines: list[str]) -> None:
        filePath = self._buildSessionFilePath(
            in_sessionId=in_sessionId,
            in_fileName=self._memorySettings.recentMessagesFileName,
        )
        self._writeLines(in_filePath=filePath, in_lines=in_lines)

    def readSessionSummary(self, in_sessionId: str) -> str:
        ret: str
        filePath = self._buildSessionFilePath(
            in_sessionId=in_sessionId,
            in_fileName=self._memorySettings.sessionSummaryFileName,
        )
        ret = self._readText(in_filePath=filePath)
        return ret

    def writeSessionSummary(self, in_sessionId: str, in_text: str) -> None:
        filePath = self._buildSessionFilePath(
            in_sessionId=in_sessionId,
            in_fileName=self._memorySettings.sessionSummaryFileName,
        )
        self._writeText(in_filePath=filePath, in_text=in_text)

    def readLongTermMemory(self, in_memoryPrincipalId: str) -> list[str]:
        ret: list[str]
        filePath = self._buildSessionFilePath(
            in_sessionId=in_memoryPrincipalId,
            in_fileName=self._memorySettings.longTermFileName,
        )
        ret = self._readLines(in_filePath=filePath)
        return ret

    def writeLongTermMemory(self, in_memoryPrincipalId: str, in_lines: list[str]) -> None:
        filePath = self._buildSessionFilePath(
            in_sessionId=in_memoryPrincipalId,
            in_fileName=self._memorySettings.longTermFileName,
        )
        self._writeLines(in_filePath=filePath, in_lines=in_lines)

    def clearSessionMemory(self, in_sessionId: str) -> None:
        sessionDirPath = self._buildSessionDirPath(in_sessionId=in_sessionId)
        recentPath = sessionDirPath / self._memorySettings.recentMessagesFileName
        summaryPath = sessionDirPath / self._memorySettings.sessionSummaryFileName
        if recentPath.exists():
            recentPath.unlink()
        if summaryPath.exists():
            summaryPath.unlink()

    def removeSessionWorkspaceDirectory(self, in_sessionId: str) -> None:
        """Удаляет каталог сессии целиком (без создания пути заранее)."""

        sanitizedSessionId = str(in_sessionId or "").replace(":", "_")
        sessionDirPath = self._rootPath / "sessions" / sanitizedSessionId
        if sessionDirPath.exists() is True and sessionDirPath.is_dir() is True:
            shutil.rmtree(sessionDirPath)

    def _buildSessionFilePath(self, in_sessionId: str, in_fileName: str) -> Path:
        sessionDirPath = self._buildSessionDirPath(in_sessionId=in_sessionId)
        ret = sessionDirPath / in_fileName
        return ret

    def _buildSessionDirPath(self, in_sessionId: str) -> Path:
        sanitizedSessionId = in_sessionId.replace(":", "_")
        sessionDirPath = self._rootPath / "sessions" / sanitizedSessionId
        sessionDirPath.mkdir(parents=True, exist_ok=True)
        ret = sessionDirPath
        return ret

    def _readText(self, in_filePath: Path) -> str:
        ret: str
        if in_filePath.exists():
            ret = in_filePath.read_text(encoding="utf-8")
        else:
            ret = ""
        return ret

    def _writeText(self, in_filePath: Path, in_text: str) -> None:
        in_filePath.parent.mkdir(parents=True, exist_ok=True)
        in_filePath.write_text(in_text, encoding="utf-8")

    def _readLines(self, in_filePath: Path) -> list[str]:
        ret: list[str]
        text = self._readText(in_filePath=in_filePath)
        ret = [item for item in text.splitlines() if item.strip()]
        return ret

    def _writeLines(self, in_filePath: Path, in_lines: list[str]) -> None:
        text = "\n".join(in_lines)
        self._writeText(in_filePath=in_filePath, in_text=text)
