from pathlib import Path

from app.common.memoryPrincipal import formatTelegramUserMemoryPrincipal
from app.config.defaultTenantSessionYaml import (
    DEFAULT_TENANT_SCHEDULES_YAML_TEXT,
    DEFAULT_TENANT_TOOLS_YAML_TEXT,
)
from app.config.settingsModels import MemorySettings


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

    toolsYamlPath = sessionDir / "tools.yaml"
    if toolsYamlPath.exists() is False:
        toolsYamlPath.write_text(DEFAULT_TENANT_TOOLS_YAML_TEXT, encoding="utf-8")

    schedulesYamlPath = sessionDir / "schedules.yaml"
    if schedulesYamlPath.exists() is False:
        schedulesYamlPath.write_text(DEFAULT_TENANT_SCHEDULES_YAML_TEXT, encoding="utf-8")
