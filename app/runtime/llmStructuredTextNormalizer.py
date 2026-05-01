import re


def normalizeStructuredLlmText(in_rawText: str) -> str:
    ret: str
    trimmedText = str(in_rawText or "").strip()
    fencePattern = re.compile(
        r"^\s*```(?:yaml|yml|json)?\s*\r?\n(.*?)\r?\n```\s*$",
        re.DOTALL | re.IGNORECASE,
    )
    matchResult = fencePattern.match(trimmedText)
    if matchResult is not None:
        ret = matchResult.group(1).strip()
    else:
        ret = trimmedText
    return ret
