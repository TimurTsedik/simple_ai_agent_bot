"""Идентификаторы внутренних run-ов планировщика — в namespace памяти администратора."""


from app.common.memoryPrincipal import formatTelegramUserMemoryPrincipal


def normalizeScheduledInternalSessionId(in_sessionId: str, in_adminTelegramUserId: int) -> str:
    """Превращает legacy `scheduler:...` в `telegramUser:<admin>:scheduler:...` (SANITIZED dir)."""

    raw = str(in_sessionId or "").strip()
    adminPrincipal = formatTelegramUserMemoryPrincipal(in_telegramUserId=in_adminTelegramUserId)
    if raw == "":
        ret = f"{adminPrincipal}:scheduler:default"
        return ret
    if raw.startswith(f"{adminPrincipal}:"):
        ret = raw
        return ret
    if raw.startswith("telegramUser:"):
        ret = raw
        return ret
    ret = f"{adminPrincipal}:{raw}"
    return ret
