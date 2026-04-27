import json
import os
from pathlib import Path
from typing import Any


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

    def listRuns(self, in_limit: int, in_offset: int = 0) -> list[dict[str, Any]]:
        ret: list[dict[str, Any]]
        boundedLimit = max(1, in_limit)
        boundedOffset = max(0, in_offset)
        records: list[dict[str, Any]] = []
        if self._indexFilePath.exists():
            lines = self._indexFilePath.read_text(encoding="utf-8").splitlines()
            for lineText in lines:
                if not lineText.strip():
                    continue
                try:
                    parsedValue = json.loads(lineText)
                    if isinstance(parsedValue, dict):
                        records.append(parsedValue)
                except json.JSONDecodeError:
                    continue
        records.reverse()
        ret = records[boundedOffset : boundedOffset + boundedLimit]
        return ret
