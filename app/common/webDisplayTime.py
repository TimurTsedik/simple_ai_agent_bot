from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def resolveDisplayZone(in_timeZoneName: str) -> ZoneInfo:
    ret: ZoneInfo
    nameText = str(in_timeZoneName or "").strip()
    if nameText == "":
        ret = ZoneInfo("UTC")
        return ret
    try:
        ret = ZoneInfo(nameText)
    except ZoneInfoNotFoundError:
        ret = ZoneInfo("UTC")
    return ret


def formatIso8601ForWeb(in_value: str, in_zone: ZoneInfo) -> str:
    ret: str
    textValue = str(in_value or "").strip()
    if textValue == "":
        ret = str(in_value)
        return ret
    try:
        normalizedText = textValue.replace("Z", "+00:00")
        parsedDt = datetime.fromisoformat(normalizedText)
        if parsedDt.tzinfo is None:
            parsedDt = parsedDt.replace(tzinfo=UTC)
        localizedDt = parsedDt.astimezone(in_zone)
        ret = localizedDt.strftime("%Y-%m-%d %H:%M:%S %Z")
    except ValueError:
        ret = str(in_value)
    return ret


def formatUnixEpochSecondsForWeb(in_epochSeconds: float, in_zone: ZoneInfo) -> str:
    ret: str
    localizedDt = datetime.fromtimestamp(float(in_epochSeconds), tz=UTC).astimezone(in_zone)
    ret = localizedDt.strftime("%Y-%m-%d %H:%M:%S %Z")
    return ret


_TIME_FIELD_KEYS = frozenset({"createdAt", "finishedAt", "timestamp", "updatedAt"})


def formatTimestampFieldsDeepCopy(in_value: Any, in_zone: ZoneInfo) -> Any:
    """Рекурсивно копирует структуру и форматирует известные строковые поля времени для HTML."""
    ret: Any
    if isinstance(in_value, dict):
        newDict: dict[str, Any] = {}
        for keyItem, valueItem in in_value.items():
            if keyItem in _TIME_FIELD_KEYS and isinstance(valueItem, str):
                newDict[keyItem] = formatIso8601ForWeb(in_value=valueItem, in_zone=in_zone)
            else:
                newDict[keyItem] = formatTimestampFieldsDeepCopy(in_value=valueItem, in_zone=in_zone)
        ret = newDict
    elif isinstance(in_value, list):
        ret = [formatTimestampFieldsDeepCopy(in_value=item, in_zone=in_zone) for item in in_value]
    else:
        ret = in_value
    return ret
