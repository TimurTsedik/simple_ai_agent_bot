"""Идентификаторы внутренних run-ов планировщика — в namespace памяти администратора."""

import re

from app.common.memoryPrincipal import formatTelegramUserMemoryPrincipal


def normalizeScheduledInternalSessionId(in_sessionId: str, in_scopeTelegramUserId: int) -> str:
    """Превращает legacy `scheduler:...` в `telegramUser:<id>:scheduler:...` (SANITIZED dir).

    in_scopeTelegramUserId — владелец tenant (каталог sessions/telegramUser_<id>/), не обязательно admin.
    """

    raw = str(in_sessionId or "").strip()
    scopePrincipal = formatTelegramUserMemoryPrincipal(in_telegramUserId=in_scopeTelegramUserId)
    if raw == "":
        ret = f"{scopePrincipal}:scheduler:default"
        return ret
    if raw.startswith(f"{scopePrincipal}:"):
        ret = raw
        return ret
    if raw.startswith("telegramUser:"):
        ret = raw
        return ret
    ret = f"{scopePrincipal}:{raw}"
    return ret


def sanitizeSchedulerSessionSlug(in_raw: str) -> str:
    """Безопасный суффикс для `...:scheduler:<slug>` (каталог на диске)."""

    ret: str
    collapsed = re.sub(r"[^a-zA-Z0-9_]+", "_", str(in_raw or "").strip().lower())
    collapsed = re.sub(r"_+", "_", collapsed).strip("_")
    if len(collapsed) > 48:
        collapsed = collapsed[:48]
    if collapsed == "":
        ret = "task"
    else:
        ret = collapsed
    return ret


def isScheduledInternalRunSessionId(in_sessionId: str) -> bool:
    """True для сессий вида `...:scheduler:...` (каталог `sessions/..._scheduler_...` на диске)."""

    ret: bool
    ret = ":scheduler:" in str(in_sessionId or "")
    return ret
