"""Одноразовая миграция глобального long_term.md в namespace пользователя (admin)."""

import shutil
from pathlib import Path


def ensureLegacyDigestReadStateMigrated(
    in_dataRootPath: str,
    in_targetMemoryPrincipalId: str,
) -> None:
    """Переносит старый telegram_digest_read_state.json в per-tenant файл."""

    rootPath = Path(in_dataRootPath).resolve()
    legacyPath = rootPath / "state" / "telegram_digest_read_state.json"
    sanitized = str(in_targetMemoryPrincipalId or "").strip().replace(":", "_")
    newDir = rootPath / "state" / "telegram_digest_read_state"
    targetPath = newDir / f"{sanitized}.json"
    if targetPath.exists() is True:
        return
    if legacyPath.exists() is False or legacyPath.is_file() is False:
        return
    newDir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(legacyPath, targetPath)


def ensureLegacyRootLongTermMigrated(
    in_memoryRootPath: str,
    in_longTermFileName: str,
    in_targetMemoryPrincipalId: str,
) -> None:
    """Если в корне memory остался legacy long_term.md, копирует в сессию principal и переименовывает legacy."""

    memoryRoot = Path(in_memoryRootPath).resolve()
    legacyPath = memoryRoot / in_longTermFileName
    if legacyPath.exists() is False or legacyPath.is_file() is False:
        return
    sanitized = in_targetMemoryPrincipalId.replace(":", "_")
    sessionDir = memoryRoot / "sessions" / sanitized
    sessionDir.mkdir(parents=True, exist_ok=True)
    targetPath = sessionDir / in_longTermFileName
    if targetPath.exists() is False:
        shutil.copyfile(legacyPath, targetPath)
    backupPath = legacyPath.with_name(legacyPath.name + ".migrated.bak")
    if backupPath.exists() is False:
        legacyPath.replace(backupPath)
