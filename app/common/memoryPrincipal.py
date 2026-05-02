"""Форматирование tenant-ключа памяти для изоляции пользователей (Telegram)."""


def formatTelegramUserMemoryPrincipal(in_telegramUserId: int) -> str:
    ret: str
    ret = f"telegramUser:{int(in_telegramUserId)}"
    return ret
