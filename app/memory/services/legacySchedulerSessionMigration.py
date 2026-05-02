"""Перенос директорий sessions/scheduler_* под tenant администратора."""

import shutil
from pathlib import Path

from app.common.schedulerSessionId import normalizeScheduledInternalSessionId


def ensureLegacySchedulerSessionDirsMigrated(
    in_memoryRootPath: str,
    in_adminTelegramUserId: int,
) -> None:
    memoryRoot = Path(in_memoryRootPath).resolve()
    sessionsRoot = memoryRoot / "sessions"
    if sessionsRoot.is_dir() is False:
        return

    legacySessionIds = [
        "scheduler:email",
        "scheduler:telegram_news",
        "scheduler:default",
    ]

    for legacySid in legacySessionIds:
        legacyDir = sessionsRoot / legacySid.replace(":", "_")
        if legacyDir.is_dir() is False:
            continue
        newSid = normalizeScheduledInternalSessionId(
            in_sessionId=legacySid,
            in_adminTelegramUserId=in_adminTelegramUserId,
        )
        targetDir = sessionsRoot / newSid.replace(":", "_")
        if targetDir.exists() is True:
            continue
        targetDir.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(legacyDir.resolve()), str(targetDir.resolve()))
