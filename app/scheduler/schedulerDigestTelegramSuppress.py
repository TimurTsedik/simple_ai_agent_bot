import json
from typing import Any


def _parseToolResultData(in_toolResult: dict[str, Any]) -> dict[str, Any] | None:
    ret: dict[str, Any] | None
    if in_toolResult.get("ok") is not True:
        ret = None
        return ret
    rawData = in_toolResult.get("data")
    parsedValue: dict[str, Any] | None = None
    if isinstance(rawData, dict):
        parsedValue = rawData
    elif isinstance(rawData, str) and rawData.strip() != "":
        try:
            loadedValue = json.loads(rawData)
        except json.JSONDecodeError:
            loadedValue = None
        if isinstance(loadedValue, dict):
            parsedValue = loadedValue
    ret = parsedValue
    return ret


def _extractCountFromParsedData(in_parsedData: dict[str, Any]) -> int:
    ret: int
    countRaw = in_parsedData.get("count", 0)
    try:
        ret = int(countRaw or 0)
    except (TypeError, ValueError):
        ret = 0
    return ret


def _resolveNewsDigestItemCount(in_toolResults: list[dict[str, Any]]) -> int | None:
    ret: int | None
    userTopicFetchedCount: int | None = None
    digestTelegramNewsCount: int | None = None
    for oneToolResult in in_toolResults:
        if not isinstance(oneToolResult, dict):
            continue
        toolName = str(oneToolResult.get("tool_name", "") or "")
        parsedData = _parseToolResultData(in_toolResult=oneToolResult)
        if parsedData is None:
            continue
        if toolName == "user_topic_telegram_digest":
            statusValue = str(parsedData.get("status", "") or "").strip().lower()
            if statusValue == "fetched":
                userTopicFetchedCount = _extractCountFromParsedData(in_parsedData=parsedData)
        elif toolName == "digest_telegram_news":
            digestTelegramNewsCount = _extractCountFromParsedData(in_parsedData=parsedData)
    if userTopicFetchedCount is not None:
        ret = userTopicFetchedCount
    elif digestTelegramNewsCount is not None:
        ret = digestTelegramNewsCount
    else:
        ret = None
    return ret


def _resolveEmailDigestItemCount(in_toolResults: list[dict[str, Any]]) -> int | None:
    ret: int | None
    lastReadEmailCount: int | None = None
    for oneToolResult in in_toolResults:
        if not isinstance(oneToolResult, dict):
            continue
        toolName = str(oneToolResult.get("tool_name", "") or "")
        if toolName != "read_email":
            continue
        parsedData = _parseToolResultData(in_toolResult=oneToolResult)
        if parsedData is None:
            continue
        lastReadEmailCount = _extractCountFromParsedData(in_parsedData=parsedData)
    ret = lastReadEmailCount
    return ret


def shouldSuppressSchedulerDigestTelegram(
    in_jobId: str,
    in_runRecord: dict[str, Any] | None,
) -> tuple[bool, dict[str, Any] | None]:
    """Returns (shouldSuppress, diagnosticsPayload for logging)."""
    ret: tuple[bool, dict[str, Any] | None]
    jobIdValue = str(in_jobId or "")
    isEmailDigestJob = "email_digest" in jobIdValue
    isNewsDigestJob = "telegram_news_digest" in jobIdValue
    if isEmailDigestJob is False and isNewsDigestJob is False:
        ret = (False, None)
        return ret
    if in_runRecord is None or not isinstance(in_runRecord, dict):
        ret = (False, None)
        return ret
    toolResultsRaw = in_runRecord.get("toolResults", [])
    toolResultsList: list[dict[str, Any]] = []
    if isinstance(toolResultsRaw, list):
        for oneEntry in toolResultsRaw:
            if isinstance(oneEntry, dict):
                toolResultsList.append(oneEntry)
    resolvedCount: int | None = None
    resolvedToolKind = ""
    if isEmailDigestJob is True:
        resolvedCount = _resolveEmailDigestItemCount(in_toolResults=toolResultsList)
        resolvedToolKind = "read_email"
    elif isNewsDigestJob is True:
        resolvedCount = _resolveNewsDigestItemCount(in_toolResults=toolResultsList)
        resolvedToolKind = "telegram_digest"
    if resolvedCount is None:
        ret = (False, None)
        return ret
    if resolvedCount == 0:
        diagnosticsPayload = {
            "jobId": jobIdValue,
            "digestKind": resolvedToolKind,
            "itemCount": resolvedCount,
        }
        ret = (True, diagnosticsPayload)
    else:
        ret = (False, None)
    return ret
