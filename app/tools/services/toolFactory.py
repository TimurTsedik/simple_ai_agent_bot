from app.config.settingsModels import SettingsModel
from app.tools.implementations.digestTelegramNewsTool import DigestTelegramNewsTool
from app.tools.implementations.readMemoryFileTool import ReadMemoryFileTool
from app.tools.registry.toolRegistry import ToolDefinitionModel, ToolRegistry
from app.tools.registry.toolSchemas import (
    DigestTelegramNewsArgsModel,
    ReadMemoryFileArgsModel,
)


def buildToolRegistry(in_settings: SettingsModel) -> ToolRegistry:
    ret: ToolRegistry
    defaultNewsKeywords = (
        in_settings.telegram.portfolioTickers + in_settings.telegram.digestSemanticKeywords
    )
    digestTool = DigestTelegramNewsTool(
        digestChannelUsernames=in_settings.telegram.digestChannelUsernames,
        defaultKeywords=defaultNewsKeywords,
    )
    readMemoryFileTool = ReadMemoryFileTool(
        in_allowedReadOnlyPaths=in_settings.security.allowedReadOnlyPaths
    )
    toolDefinitions = [
        ToolDefinitionModel(
            name="digest_telegram_news",
            description=(
                "Собирает краткий дайджест новостей из публичных telegram-каналов "
                "по ключевым словам и времени."
            ),
            argsModel=DigestTelegramNewsArgsModel,
            timeoutSeconds=20,
            executeCallable=digestTool.execute,
        ),
        ToolDefinitionModel(
            name="read_memory_file",
            description=(
                "Читает файл только из разрешенных read-only путей для памяти и логов."
            ),
            argsModel=ReadMemoryFileArgsModel,
            timeoutSeconds=5,
            executeCallable=readMemoryFileTool.execute,
        ),
    ]
    ret = ToolRegistry(in_toolDefinitions=toolDefinitions)
    return ret
