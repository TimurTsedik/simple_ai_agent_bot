"""Форматирование tenant-ключа памяти для изоляции пользователей (Telegram)."""


def formatTelegramUserMemoryPrincipal(in_telegramUserId: int) -> str:
    ret: str
    ret = f"telegramUser:{int(in_telegramUserId)}"
    return ret


def parseTelegramUserIdFromMemoryPrincipal(in_memoryPrincipalId: str) -> int | None:
    """Извлекает числовой Telegram user id из ключа вида telegramUser:<id>."""

    ret: int | None = None
    raw = str(in_memoryPrincipalId or "").strip()
    prefix = "telegramUser:"
    if raw.startswith(prefix) is True:
        tail = raw[len(prefix) :].strip()
        try:
            parsed = int(tail)
        except ValueError:
            parsed = None
        if parsed is not None and parsed >= 1:
            ret = parsed
    return ret
