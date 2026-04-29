import json
import os
from pathlib import Path
from threading import Lock
from typing import Any

from app.common.timeProvider import getUtcNowIso


def extractProviderUsageTokenCounts(in_responseData: dict[str, Any]) -> tuple[int, int, int]:
    """Извлекает prompt/completion/total tokens из OpenAI-совместимого usage в ответе провайдера."""
    ret: tuple[int, int, int]
    promptTokens = 0
    completionTokens = 0
    totalTokens = 0
    usageValue = in_responseData.get("usage")
    if isinstance(usageValue, dict):

        def readNonNegativeInt(in_key: str) -> int:
            retInner: int
            rawValue = usageValue.get(in_key)
            if isinstance(rawValue, bool):
                retInner = 0
            elif isinstance(rawValue, int) and rawValue >= 0:
                retInner = rawValue
            elif isinstance(rawValue, float) and rawValue >= 0:
                retInner = int(rawValue)
            else:
                retInner = 0
            return retInner

        promptTokens = readNonNegativeInt(in_key="prompt_tokens")
        completionTokens = readNonNegativeInt(in_key="completion_tokens")
        totalTokens = readNonNegativeInt(in_key="total_tokens")
    ret = (promptTokens, completionTokens, totalTokens)
    return ret


def _emptyTotals() -> dict[str, Any]:
    ret = {
        "calls": 0,
        "success": 0,
        "errors": 0,
        "promptTokens": 0,
        "completionTokens": 0,
        "totalTokens": 0,
    }
    return ret


def _emptyModelEntry() -> dict[str, Any]:
    ret = {
        "calls": 0,
        "success": 0,
        "errors": 0,
        "promptTokens": 0,
        "completionTokens": 0,
        "totalTokens": 0,
        "lastErrorCode": "",
    }
    return ret


def _defaultPayload() -> dict[str, Any]:
    ret = {
        "schemaVersion": 1,
        "updatedAt": "",
        "totals": _emptyTotals(),
        "models": {},
    }
    return ret


class ModelStatsService:
    """Инкрементальная статистика обращений к LLM-провайдеру (per-model + totals), хранится в JSON."""

    def __init__(self, in_dataRootPath: str) -> None:
        self._dataRootPath = Path(in_dataRootPath)
        self._statsFilePath = self._dataRootPath / "model_stats.json"
        self._lock = Lock()

    def recordAttempt(
        self,
        in_modelName: str,
        in_didSucceed: bool,
        in_promptTokens: int,
        in_completionTokens: int,
        in_totalTokens: int,
        in_errorCode: str,
    ) -> None:
        modelKey = str(in_modelName or "unknown")
        promptTokens = max(0, int(in_promptTokens))
        completionTokens = max(0, int(in_completionTokens))
        totalTokens = max(0, int(in_totalTokens))
        errorCodeText = str(in_errorCode or "")
        with self._lock:
            payload = self._readPayloadOrDefault()
            totals = payload["totals"]
            modelsMap = payload["models"]
            if not isinstance(totals, dict):
                totals = _emptyTotals()
                payload["totals"] = totals
            if not isinstance(modelsMap, dict):
                modelsMap = {}
                payload["models"] = modelsMap

            self._incrementBucket(
                in_bucket=totals,
                in_didSucceed=in_didSucceed,
                in_promptTokens=promptTokens,
                in_completionTokens=completionTokens,
                in_totalTokens=totalTokens,
            )

            modelEntry = modelsMap.get(modelKey)
            if not isinstance(modelEntry, dict):
                modelEntry = _emptyModelEntry()
                modelsMap[modelKey] = modelEntry
            self._incrementBucket(
                in_bucket=modelEntry,
                in_didSucceed=in_didSucceed,
                in_promptTokens=promptTokens,
                in_completionTokens=completionTokens,
                in_totalTokens=totalTokens,
            )
            if in_didSucceed is False:
                modelEntry["lastErrorCode"] = errorCodeText
            else:
                modelEntry["lastErrorCode"] = ""

            payload["updatedAt"] = getUtcNowIso()
            self._atomicWriteJson(in_payload=payload)

    def getSnapshot(self) -> dict[str, Any]:
        ret: dict[str, Any]
        with self._lock:
            payload = self._readPayloadOrDefault()
            modelsMap = payload.get("models", {})
            if not isinstance(modelsMap, dict):
                modelsMap = {}
            rows: list[dict[str, Any]] = []
            for modelName in sorted(modelsMap.keys()):
                entryValue = modelsMap.get(modelName)
                if not isinstance(entryValue, dict):
                    continue
                rows.append(
                    {
                        "modelName": str(modelName),
                        "calls": int(entryValue.get("calls", 0) or 0),
                        "success": int(entryValue.get("success", 0) or 0),
                        "errors": int(entryValue.get("errors", 0) or 0),
                        "promptTokens": int(entryValue.get("promptTokens", 0) or 0),
                        "completionTokens": int(entryValue.get("completionTokens", 0) or 0),
                        "totalTokens": int(entryValue.get("totalTokens", 0) or 0),
                        "lastErrorCode": str(entryValue.get("lastErrorCode", "") or ""),
                    }
                )
            totalsValue = payload.get("totals", _emptyTotals())
            if not isinstance(totalsValue, dict):
                totalsValue = _emptyTotals()
            ret = {
                "schemaVersion": int(payload.get("schemaVersion", 1) or 1),
                "updatedAt": str(payload.get("updatedAt", "") or ""),
                "totals": {
                    "calls": int(totalsValue.get("calls", 0) or 0),
                    "success": int(totalsValue.get("success", 0) or 0),
                    "errors": int(totalsValue.get("errors", 0) or 0),
                    "promptTokens": int(totalsValue.get("promptTokens", 0) or 0),
                    "completionTokens": int(totalsValue.get("completionTokens", 0) or 0),
                    "totalTokens": int(totalsValue.get("totalTokens", 0) or 0),
                },
                "models": rows,
            }
        return ret

    def _incrementBucket(
        self,
        in_bucket: dict[str, Any],
        in_didSucceed: bool,
        in_promptTokens: int,
        in_completionTokens: int,
        in_totalTokens: int,
    ) -> None:
        in_bucket["calls"] = int(in_bucket.get("calls", 0) or 0) + 1
        if in_didSucceed is True:
            in_bucket["success"] = int(in_bucket.get("success", 0) or 0) + 1
            in_bucket["promptTokens"] = int(in_bucket.get("promptTokens", 0) or 0) + in_promptTokens
            in_bucket["completionTokens"] = (
                int(in_bucket.get("completionTokens", 0) or 0) + in_completionTokens
            )
            in_bucket["totalTokens"] = int(in_bucket.get("totalTokens", 0) or 0) + in_totalTokens
        else:
            in_bucket["errors"] = int(in_bucket.get("errors", 0) or 0) + 1

    def _readPayloadOrDefault(self) -> dict[str, Any]:
        ret: dict[str, Any]
        if self._statsFilePath.exists() is False:
            ret = _defaultPayload()
            return ret
        try:
            rawText = self._statsFilePath.read_text(encoding="utf-8")
            parsedValue = json.loads(rawText)
            if isinstance(parsedValue, dict) and int(parsedValue.get("schemaVersion", 0) or 0) >= 1:
                ret = parsedValue
            else:
                ret = _defaultPayload()
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            ret = _defaultPayload()
        return ret

    def _atomicWriteJson(self, in_payload: dict[str, Any]) -> None:
        self._dataRootPath.mkdir(parents=True, exist_ok=True)
        tmpPath = self._statsFilePath.with_suffix(self._statsFilePath.suffix + f".tmp.{os.getpid()}")
        tmpPath.write_text(
            json.dumps(in_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(str(tmpPath), str(self._statsFilePath))
