import shutil
from pathlib import Path

from app.common.memoryPrincipal import formatTelegramUserMemoryPrincipal
from app.config.defaultTenantSessionYaml import (
    DEFAULT_TENANT_SCHEDULES_YAML_TEXT,
    DEFAULT_TENANT_TOOLS_YAML_TEXT,
)
from app.config.settingsModels import MemorySettings


def _ensureSessionTextFile(in_path: Path, in_defaultText: str) -> None:
    if in_path.is_file() is True:
        return
    if in_path.exists() is True:
        if in_path.is_dir() is True:
            shutil.rmtree(str(in_path))
        else:
            in_path.unlink()
    in_path.write_text(in_defaultText, encoding="utf-8")


def provisionTelegramUserWorkspaceIfNeeded(
    in_telegramUserId: int,
    in_memorySettings: MemorySettings,
) -> None:
    principalText = formatTelegramUserMemoryPrincipal(in_telegramUserId=in_telegramUserId)
    sanitizedPrincipal = principalText.replace(":", "_")
    memoryRoot = Path(in_memorySettings.memoryRootPath)
    if memoryRoot.is_absolute() is False:
        memoryRoot = memoryRoot.resolve()
    sessionDir = memoryRoot / "sessions" / sanitizedPrincipal
    sessionDir.mkdir(parents=True, exist_ok=True)

    longTermPath = sessionDir / in_memorySettings.longTermFileName
    if longTermPath.exists() is False:
        longTermPath.write_text("", encoding="utf-8")

    summaryPath = sessionDir / in_memorySettings.sessionSummaryFileName
    if summaryPath.exists() is False:
        summaryPath.write_text("", encoding="utf-8")

    recentPath = sessionDir / in_memorySettings.recentMessagesFileName
    if recentPath.exists() is False:
        recentPath.write_text("", encoding="utf-8")

    _ensureSessionTextFile(
        in_path=sessionDir / "tools.yaml",
        in_defaultText=DEFAULT_TENANT_TOOLS_YAML_TEXT,
    )
    _ensureSessionTextFile(
        in_path=sessionDir / "schedules.yaml",
        in_defaultText=DEFAULT_TENANT_SCHEDULES_YAML_TEXT,
    )
