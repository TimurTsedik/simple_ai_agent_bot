from pathlib import Path
from time import monotonic
from typing import Any

from app.application.useCases.getRunListUseCase import GetRunListUseCase
from app.config.settingsModels import SettingsModel
from app.skills.stores.markdownSkillStore import MarkdownSkillStore
from app.tools.registry.toolRegistry import ToolRegistry


class DashboardSnapshotService:
    """TTL-кэш агрегатов для главной страницы админки."""

    def __init__(
        self,
        in_settings: SettingsModel,
        in_getRunListUseCase: GetRunListUseCase,
        in_toolRegistry: ToolRegistry,
        in_skillStore: MarkdownSkillStore,
        in_ttlSeconds: float = 2.0,
    ) -> None:
        self._settings = in_settings
        self._getRunListUseCase = in_getRunListUseCase
        self._toolRegistry = in_toolRegistry
        self._skillStore = in_skillStore
        self._ttlSeconds = max(0.1, float(in_ttlSeconds))
        self._cachedAtMonotonic = 0.0
        self._cachedStats: dict[str, Any] | None = None

    def getDashboardStatsSnapshot(self) -> dict[str, Any]:
        ret: dict[str, Any]
        nowMonotonic = monotonic()
        if (
            self._cachedStats is not None
            and (nowMonotonic - self._cachedAtMonotonic) < self._ttlSeconds
        ):
            ret = self._cachedStats
            return ret
        self._cachedStats = self._buildDashboardStats()
        self._cachedAtMonotonic = nowMonotonic
        ret = self._cachedStats
        return ret

    def _buildDashboardStats(self) -> dict[str, Any]:
        recentRuns = self._getRunListUseCase.execute(in_limit=50, in_offset=0)
        lastRun = recentRuns[0] if isinstance(recentRuns, list) and len(recentRuns) > 0 else {}
        toolsYamlPath = self._resolveToolsConfigPath()
        memoryRoot = Path(self._settings.memory.memoryRootPath)
        logsRoot = Path(self._settings.logging.logsDirPath)
        lastSessionId = str(lastRun.get("sessionId", ""))
        sessionFolderName = lastSessionId.replace(":", "_") if lastSessionId else ""
        sessionMemoryRoot = (
            (memoryRoot / "sessions" / sessionFolderName)
            if sessionFolderName
            else memoryRoot
        )
        recentPath = sessionMemoryRoot / self._settings.memory.recentMessagesFileName
        summaryPath = sessionMemoryRoot / self._settings.memory.sessionSummaryFileName
        longTermPath = memoryRoot / self._settings.memory.longTermFileName

        recentSize = self._fileTextSize(in_filePath=recentPath)
        summarySize = self._fileTextSize(in_filePath=summaryPath)
        longTermSize = self._fileTextSize(in_filePath=longTermPath)
        activeContextChars = int(recentSize.get("chars", 0)) + int(summarySize.get("chars", 0))
        activeContextBytes = int(recentSize.get("bytes", 0)) + int(summarySize.get("bytes", 0))

        ret = {
            "adminWritesEnabled": self._settings.security.adminWritesEnabled,
            "toolsCount": len(self._toolRegistry.listTools()),
            "skillsCount": len(self._skillStore.loadAllSkills()),
            "runsCount": len(recentRuns),
            "maxPromptChars": self._settings.runtime.maxPromptChars,
            "maxToolOutputChars": self._settings.runtime.maxToolOutputChars,
            "maxExecutionSeconds": self._settings.runtime.maxExecutionSeconds,
            "primaryModel": self._settings.models.primaryModel,
            "secondaryModel": self._settings.models.secondaryModel,
            "tertiaryModel": self._settings.models.tertiaryModel,
            "lastRunId": str(lastRun.get("runId", "")),
            "lastRunSessionId": lastSessionId,
            "lastRunStatus": str(lastRun.get("runStatus", "—")),
            "lastRunReason": str(lastRun.get("completionReason", "—")),
            "lastRunCreatedAt": str(lastRun.get("createdAt", "—")),
            "lastRunSelectedModel": str(lastRun.get("selectedModel", "—")),
            "toolsYamlInfo": self._fileInfo(in_filePath=toolsYamlPath),
            "memoryInfo": self._dirInfo(in_dirPath=memoryRoot),
            "logsInfo": self._dirInfo(in_dirPath=logsRoot),
            "contextActive": f"{activeContextChars} chars, {self._formatBytes(in_sizeBytes=activeContextBytes)}",
            "contextRecent": f"{int(recentSize.get('chars', 0))} chars, {self._formatBytes(in_sizeBytes=int(recentSize.get('bytes', 0)))}",
            "contextSummary": f"{int(summarySize.get('chars', 0))} chars, {self._formatBytes(in_sizeBytes=int(summarySize.get('bytes', 0)))}",
            "contextLongTerm": f"{int(longTermSize.get('chars', 0))} chars, {self._formatBytes(in_sizeBytes=int(longTermSize.get('bytes', 0)))}",
        }
        return ret

    def _resolveToolsConfigPath(self) -> Path:
        ret: Path
        toolsPath = Path(self._settings.tools.toolsConfigPath)
        if toolsPath.is_absolute() is False:
            ret = toolsPath.resolve()
        else:
            ret = toolsPath
        return ret

    def _formatBytes(self, in_sizeBytes: int) -> str:
        ret: str
        sizeValue = float(max(0, in_sizeBytes))
        units = ["B", "KB", "MB", "GB"]
        unitIndex = 0
        while sizeValue >= 1024.0 and unitIndex < len(units) - 1:
            sizeValue /= 1024.0
            unitIndex += 1
        ret = f"{sizeValue:.1f} {units[unitIndex]}"
        return ret

    def _dirInfo(self, in_dirPath: Path) -> str:
        ret: str
        if in_dirPath.exists() is False:
            ret = "missing"
        else:
            fileCount = 0
            totalBytes = 0
            for filePath in in_dirPath.rglob("*"):
                if filePath.is_file():
                    fileCount += 1
                    try:
                        totalBytes += int(filePath.stat().st_size)
                    except OSError:
                        pass
            ret = f"{fileCount} files, {self._formatBytes(in_sizeBytes=totalBytes)}"
        return ret

    def _fileInfo(self, in_filePath: Path) -> str:
        ret: str
        if in_filePath.exists() is False:
            ret = "missing"
        else:
            try:
                statValue = in_filePath.stat()
                ret = f"{self._formatBytes(in_sizeBytes=int(statValue.st_size))} (mtime={statValue.st_mtime:.0f})"
            except OSError:
                ret = "unavailable"
        return ret

    def _fileTextSize(self, in_filePath: Path) -> dict[str, int]:
        ret: dict[str, int]
        if in_filePath.exists() is False:
            ret = {"chars": 0, "bytes": 0}
        else:
            try:
                textValue = in_filePath.read_text(encoding="utf-8")
                byteCount = int(in_filePath.stat().st_size)
                ret = {"chars": len(textValue), "bytes": byteCount}
            except OSError:
                ret = {"chars": 0, "bytes": 0}
        return ret
