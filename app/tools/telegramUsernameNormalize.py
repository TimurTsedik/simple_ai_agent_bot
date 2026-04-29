"""Normalize and validate public Telegram channel usernames for t.me/s/<name> scraping."""


def normalizeTelegramChannelUsername(in_raw: str) -> str | None:
    ret: str | None
    trimmed = in_raw.strip().lower()
    if trimmed.startswith("@"):
        trimmed = trimmed[1:]
    if len(trimmed) < 4 or len(trimmed) > 32:
        ret = None
        return ret
    allowedChars = set("abcdefghijklmnopqrstuvwxyz0123456789_")
    if not all(ch in allowedChars for ch in trimmed):
        ret = None
        return ret
    if not trimmed[0].isalpha():
        ret = None
        return ret
    ret = trimmed
    return ret
