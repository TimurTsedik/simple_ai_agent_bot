import json
import os
from pathlib import Path
from typing import Any, Iterator


def sessionsEquivalentForAdminRunsView(
    in_recordSessionId: str,
    in_allowedSessionId: str,
) -> bool:
    """Старые раны в index имели sessionId `telegram:<id>`, сейчас tenant — `telegramUser:<id>`."""

    left = str(in_recordSessionId or "").strip()
    right = str(in_allowedSessionId or "").strip()
    ret = False
    if left == right:
        ret = True
    elif (
        left.startswith("telegram:")
        and right.startswith("telegramUser:")
        and left[len("telegram:") :] == right[len("telegramUser:") :]
    ):
        ret = True
    elif (
        left.startswith("telegramUser:")
        and right.startswith("telegram:")
        and left[len("telegramUser:") :] == right[len("telegram:") :]
    ):
        ret = True
    return ret


class JsonRunRepository:
    def __init__(self, in_dataRootPath: str) -> None:
        self._runsDirPath = Path(in_dataRootPath) / "runs"
        self._runsDirPath.mkdir(parents=True, exist_ok=True)
        self._indexFilePath = self._runsDirPath / "index.jsonl"

    def saveRun(self, in_runRecord: dict[str, Any]) -> None:
        runId = str(in_runRecord.get("runId", "unknown"))
        runFilePath = self._runsDirPath / f"{runId}.json"
        payloadText = json.dumps(in_runRecord, ensure_ascii=False, indent=2)
        tmpFilePath = runFilePath.with_suffix(f"{runFilePath.suffix}.tmp.{os.getpid()}")
        tmpFilePath.write_text(payloadText, encoding="utf-8")
        os.replace(str(tmpFilePath), str(runFilePath))
        indexRecord = {
            "runId": in_runRecord.get("runId"),
            "traceId": in_runRecord.get("traceId"),
            "sessionId": in_runRecord.get("sessionId"),
            "runStatus": in_runRecord.get("runStatus"),
            "completionReason": in_runRecord.get("completionReason"),
            "selectedModel": in_runRecord.get("selectedModel"),
            "createdAt": in_runRecord.get("createdAt"),
            "finishedAt": in_runRecord.get("finishedAt"),
        }
        with self._indexFilePath.open("a", encoding="utf-8") as fileHandle:
            fileHandle.write(json.dumps(indexRecord, ensure_ascii=False) + "\n")
            fileHandle.flush()
            os.fsync(fileHandle.fileno())

    def getRunById(self, in_runId: str) -> dict[str, Any] | None:
        ret: dict[str, Any] | None
        runFilePath = self._runsDirPath / f"{in_runId}.json"
        if runFilePath.exists():
            parsedValue = json.loads(runFilePath.read_text(encoding="utf-8"))
            if isinstance(parsedValue, dict):
                ret = parsedValue
            else:
                ret = None
        else:
            ret = None
        return ret

    def listRuns(
        self,
        in_limit: int,
        in_offset: int = 0,
        in_session_id: str | None = None,
    ) -> list[dict[str, Any]]:
        boundedLimit = max(1, in_limit)
        boundedOffset = max(0, in_offset)
        ret: list[dict[str, Any]]
        if in_session_id is None:
            needCount = boundedOffset + boundedLimit
            recordsNewestFirst = self._loadIndexRecordsNewestFirstUpTo(
                in_needCount=needCount,
            )
            ret = recordsNewestFirst[boundedOffset : boundedOffset + boundedLimit]
            return ret
        matchedRecords: list[dict[str, Any]] = []
        for lineText in self._iterIndexLinesNewestFirst():
            if not lineText.strip():
                continue
            try:
                parsedValue = json.loads(lineText)
            except json.JSONDecodeError:
                continue
            if not isinstance(parsedValue, dict):
                continue
            record_session = str(parsedValue.get("sessionId", "") or "")
            if sessionsEquivalentForAdminRunsView(
                in_recordSessionId=record_session,
                in_allowedSessionId=str(in_session_id),
            ) is False:
                continue
            matchedRecords.append(parsedValue)
            needTotal = boundedOffset + boundedLimit
            if len(matchedRecords) >= needTotal:
                break
        ret = matchedRecords[boundedOffset : boundedOffset + boundedLimit]
        return ret

    def _loadIndexRecordsNewestFirstUpTo(self, in_needCount: int) -> list[dict[str, Any]]:
        ret: list[dict[str, Any]] = []
        if in_needCount > 0 and self._indexFilePath.exists():
            parsedCount = 0
            for lineText in self._iterIndexLinesNewestFirst():
                if not lineText.strip():
                    continue
                try:
                    parsedValue = json.loads(lineText)
                except json.JSONDecodeError:
                    continue
                if not isinstance(parsedValue, dict):
                    continue
                ret.append(parsedValue)
                parsedCount += 1
                if parsedCount >= in_needCount:
                    break
        return ret

    def _iterIndexLinesNewestFirst(self) -> Iterator[str]:
        if self._indexFilePath.exists() is False:
            return
        chunkSizeBytes = 65536
        lineBuffer = b""
        with self._indexFilePath.open("rb") as fileHandle:
            fileHandle.seek(0, os.SEEK_END)
            filePos = fileHandle.tell()
            while filePos > 0:
                stepBytes = min(chunkSizeBytes, filePos)
                filePos -= stepBytes
                fileHandle.seek(filePos)
                chunkBytes = fileHandle.read(stepBytes) + lineBuffer
                splitParts = chunkBytes.split(b"\n")
                lineBuffer = splitParts[0]
                partIndex = len(splitParts) - 1
                while partIndex >= 1:
                    candidateLine = splitParts[partIndex]
                    partIndex -= 1
                    if candidateLine.strip():
                        yield candidateLine.decode("utf-8", errors="replace")
            if lineBuffer.strip():
                yield lineBuffer.decode("utf-8", errors="replace")
