import subprocess
from pathlib import Path
from typing import Any, Callable

from app.common.truncation import truncateText


CommandRunnerType = Callable[[list[str], str], tuple[int, str, str]]


def _defaultCommandRunner(in_args: list[str], in_workingDirectory: str) -> tuple[int, str, str]:
    ret: tuple[int, str, str]
    try:
        completedProcess = subprocess.run(
            in_args,
            cwd=in_workingDirectory,
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        ret = (
            int(completedProcess.returncode),
            completedProcess.stdout or "",
            completedProcess.stderr or "",
        )
    except subprocess.TimeoutExpired:
        ret = (124, "", "git command timed out")
    return ret


class GitService:
    def __init__(
        self,
        in_repoRootPath: str,
        in_commandRunner: CommandRunnerType = _defaultCommandRunner,
    ) -> None:
        self._repoRootPath = str(Path(in_repoRootPath))
        self._commandRunner = in_commandRunner

    def getStatus(self, in_limit: int = 200) -> dict[str, Any]:
        ret: dict[str, Any]
        isRepo = self._isGitRepository()
        if isRepo is False:
            ret = {
                "isGitRepo": False,
                "branch": "",
                "isClean": True,
                "items": [],
                "error": "",
            }
        else:
            exitCode, stdoutText, stderrText = self._runGitCommand(
                in_gitArgs=["status", "--short", "--branch"]
            )
            if exitCode != 0:
                ret = {
                    "isGitRepo": True,
                    "branch": "",
                    "isClean": True,
                    "items": [],
                    "error": stderrText.strip(),
                }
            else:
                lines = stdoutText.splitlines()
                branchLine = ""
                itemLines: list[str] = []
                for oneLine in lines:
                    if oneLine.startswith("## "):
                        branchLine = oneLine[3:].strip()
                    elif oneLine.strip():
                        itemLines.append(oneLine)
                boundedLimit = max(1, in_limit)
                ret = {
                    "isGitRepo": True,
                    "branch": branchLine,
                    "isClean": len(itemLines) == 0,
                    "items": itemLines[:boundedLimit],
                    "error": "",
                }
        return ret

    def getDiff(
        self,
        in_offset: int = 0,
        in_limit: int = 5,
        in_filePath: str = "",
        in_maxCharsPerFile: int = 30000,
    ) -> dict[str, Any]:
        ret: dict[str, Any]
        isRepo = self._isGitRepository()
        if isRepo is False:
            ret = {
                "isGitRepo": False,
                "totalFiles": 0,
                "offset": in_offset,
                "limit": in_limit,
                "files": [],
                "error": "",
            }
            return ret

        if in_filePath.strip():
            allFiles = [in_filePath.strip()]
        else:
            allFiles = self._listChangedFiles()

        boundedOffset = max(0, in_offset)
        boundedLimit = max(1, in_limit)
        pagedFiles = allFiles[boundedOffset : boundedOffset + boundedLimit]
        fileItems: list[dict[str, Any]] = []
        for filePath in pagedFiles:
            unstagedDiff = self._readDiffForFile(
                in_filePath=filePath,
                in_staged=False,
            )
            stagedDiff = self._readDiffForFile(
                in_filePath=filePath,
                in_staged=True,
            )
            combinedDiff = ""
            if stagedDiff:
                combinedDiff = f"## staged\n{stagedDiff}\n"
            if unstagedDiff:
                combinedDiff += f"## unstaged\n{unstagedDiff}"
            truncatedDiff, isTruncated = truncateText(
                in_text=combinedDiff,
                in_maxChars=in_maxCharsPerFile,
            )
            fileItems.append(
                {
                    "filePath": filePath,
                    "diff": truncatedDiff,
                    "truncated": isTruncated,
                }
            )
        ret = {
            "isGitRepo": True,
            "totalFiles": len(allFiles),
            "offset": boundedOffset,
            "limit": boundedLimit,
            "files": fileItems,
            "error": "",
        }
        return ret

    def _listChangedFiles(self) -> list[str]:
        ret: list[str]
        files: list[str] = []
        seenFiles: set[str] = set()
        for stagedFlag in [False, True]:
            gitArgs = ["diff", "--name-only"]
            if stagedFlag is True:
                gitArgs.append("--cached")
            exitCode, stdoutText, _stderrText = self._runGitCommand(in_gitArgs=gitArgs)
            if exitCode != 0:
                continue
            for oneLine in stdoutText.splitlines():
                normalizedLine = oneLine.strip()
                if not normalizedLine:
                    continue
                if normalizedLine in seenFiles:
                    continue
                seenFiles.add(normalizedLine)
                files.append(normalizedLine)
        ret = files
        return ret

    def _readDiffForFile(self, in_filePath: str, in_staged: bool) -> str:
        ret: str
        gitArgs = ["diff"]
        if in_staged is True:
            gitArgs.append("--cached")
        gitArgs.extend(["--", in_filePath])
        exitCode, stdoutText, _stderrText = self._runGitCommand(in_gitArgs=gitArgs)
        if exitCode != 0:
            ret = ""
        else:
            ret = stdoutText
        return ret

    def _isGitRepository(self) -> bool:
        ret: bool
        exitCode, stdoutText, _stderrText = self._runGitCommand(
            in_gitArgs=["rev-parse", "--is-inside-work-tree"]
        )
        ret = exitCode == 0 and stdoutText.strip().lower() == "true"
        return ret

    def _runGitCommand(self, in_gitArgs: list[str]) -> tuple[int, str, str]:
        ret: tuple[int, str, str]
        args = ["git"] + in_gitArgs
        try:
            ret = self._commandRunner(args, self._repoRootPath)
        except Exception as in_exception:
            ret = (1, "", f"git command failed: {in_exception}")
        return ret
