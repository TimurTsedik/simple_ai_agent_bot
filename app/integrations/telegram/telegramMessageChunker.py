from __future__ import annotations


def splitTelegramMessage(
    in_text: str,
    in_maxChars: int,
    in_preferSeparator: str = "\n---\n",
) -> list[str]:
    ret: list[str]
    textValue = in_text or ""
    maxChars = int(in_maxChars)
    if maxChars < 200:
        maxChars = 200
    if len(textValue) <= maxChars:
        ret = [textValue]
        return ret

    separator = in_preferSeparator if in_preferSeparator else "\n"
    parts = textValue.split(separator)

    chunks: list[str] = []
    current = ""
    for part in parts:
        candidate = part if current == "" else current + separator + part
        if len(candidate) <= maxChars:
            current = candidate
        else:
            if current:
                chunks.append(current)
                current = ""
                if len(part) <= maxChars:
                    current = part
                else:
                    # Hard split oversized part (worst-case fallback).
                    index = 0
                    while index < len(part):
                        chunks.append(part[index : index + maxChars])
                        index += maxChars
            else:
                # No current buffer but part itself doesn't fit.
                index = 0
                while index < len(part):
                    chunks.append(part[index : index + maxChars])
                    index += maxChars
                current = ""

    if current:
        chunks.append(current)

    ret = chunks if chunks else [textValue[:maxChars]]
    return ret

