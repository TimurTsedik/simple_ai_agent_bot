"""Пути к tools.yaml и schedules.yaml в каталоге сессии администратора (tenant UI)."""

from pathlib import Path

from app.common.memoryPrincipal import formatTelegramUserMemoryPrincipal


def resolveAdminTenantSessionDirectoryPath(
    in_memoryRootPath: str,
    in_adminTelegramUserId: int,
) -> Path:
    ret: Path
    principal_text = formatTelegramUserMemoryPrincipal(
        in_telegramUserId=in_adminTelegramUserId,
    )
    sanitized_segment = principal_text.replace(":", "_")
    memory_root = Path(in_memoryRootPath)
    if memory_root.is_absolute() is False:
        memory_root = memory_root.resolve()
    ret = (memory_root / "sessions" / sanitized_segment).resolve()
    return ret


def resolveAdminTenantToolsYamlPath(in_memoryRootPath: str, in_adminTelegramUserId: int) -> Path:
    ret: Path
    ret = (
        resolveAdminTenantSessionDirectoryPath(
            in_memoryRootPath=in_memoryRootPath,
            in_adminTelegramUserId=in_adminTelegramUserId,
        )
        / "tools.yaml"
    ).resolve()
    return ret


def resolveAdminTenantSchedulesYamlPath(
    in_memoryRootPath: str,
    in_adminTelegramUserId: int,
) -> Path:
    ret: Path
    ret = (
        resolveAdminTenantSessionDirectoryPath(
            in_memoryRootPath=in_memoryRootPath,
            in_adminTelegramUserId=in_adminTelegramUserId,
        )
        / "schedules.yaml"
    ).resolve()
    return ret
