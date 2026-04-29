from app.config.settingsModels import SettingsModel
from app.memory.stores.markdownMemoryStore import MarkdownMemoryStore
from app.tools.digestTopicSeeds import collectSeedKeywordsForTopics
from app.tools.implementations.digestTelegramNewsTool import DigestTelegramNewsTool
from app.tools.implementations.readEmailTool import ReadEmailTool
from app.tools.implementations.readMemoryFileTool import ReadMemoryFileTool
from app.tools.implementations.saveDigestPreferenceTool import SaveDigestPreferenceTool
from app.tools.implementations.webSearchTool import WebSearchTool
from app.tools.registry.toolRegistry import ToolDefinitionModel, ToolRegistry
from app.tools.registry.toolSchemas import (
    DigestTelegramNewsArgsModel,
    ReadEmailArgsModel,
    ReadMemoryFileArgsModel,
    SaveDigestPreferenceArgsModel,
    WebSearchArgsModel,
)


def buildToolRegistry(
    in_settings: SettingsModel,
    in_memoryStore: MarkdownMemoryStore,
) -> ToolRegistry:
    ret: ToolRegistry
    def _getDigestChannels() -> list[str]:
        retChannels = list(in_settings.tools.telegramNewsDigest.digestChannelUsernames)
        if len(retChannels) == 0:
            retChannels = list(in_settings.telegram.digestChannelUsernames)
        return retChannels

    def _getDefaultNewsKeywords() -> list[str]:
        toolTickers = list(in_settings.tools.telegramNewsDigest.portfolioTickers)
        toolKeywords = list(in_settings.tools.telegramNewsDigest.digestSemanticKeywords)
        if len(toolTickers) == 0 and len(toolKeywords) == 0:
            toolTickers = list(in_settings.telegram.portfolioTickers)
            toolKeywords = list(in_settings.telegram.digestSemanticKeywords)
        retKeywords = toolTickers + toolKeywords
        return retKeywords

    digestTool = DigestTelegramNewsTool(
        getDigestChannelUsernames=_getDigestChannels,
        getDefaultKeywords=_getDefaultNewsKeywords,
        getTopicSeedsForTopics=collectSeedKeywordsForTopics,
    )
    saveDigestPreferenceTool = SaveDigestPreferenceTool(in_memoryStore=in_memoryStore)
    readMemoryFileTool = ReadMemoryFileTool(
        in_allowedReadOnlyPaths=in_settings.security.allowedReadOnlyPaths
    )
    readEmailTool = ReadEmailTool(
        in_emailSettings=in_settings.tools.emailReader,
        in_password=in_settings.emailAppPassword,
    )
    webSearchTool = WebSearchTool()
    toolDefinitions = [
        ToolDefinitionModel(
            name="digest_telegram_news",
            description=(
                "Собирает краткий дайджест новостей из публичных telegram-каналов "
                "по ключевым словам и времени. "
                "Аргумент channels задаёт список публичных username (с @ или без); "
                "если пусто — используются каналы из конфигурации. "
                "Аргумент topics добавляет seed-ключи (ai, economy, crypto, markets, tech, custom). "
                "Порядок ключей: keywords из запроса, затем seeds по topics, затем дефолты из конфига."
            ),
            argsModel=DigestTelegramNewsArgsModel,
            timeoutSeconds=20,
            executeCallable=digestTool.execute,
        ),
        ToolDefinitionModel(
            name="save_digest_preference",
            description=(
                "Сохраняет в долгосрочную память предпочтения пользователя по дайджестам "
                "(темы, каналы, ключевые слова, заметка). Вызывай после того, как пользователь "
                "ответил на уточняющие вопросы о том, что именно ему нравится."
            ),
            argsModel=SaveDigestPreferenceArgsModel,
            timeoutSeconds=5,
            executeCallable=saveDigestPreferenceTool.execute,
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
        ToolDefinitionModel(
            name="read_email",
            description=(
                "Читает письма из почтового ящика по IMAP (например, последние непрочитанные)."
            ),
            argsModel=ReadEmailArgsModel,
            timeoutSeconds=45,
            executeCallable=readEmailTool.execute,
        ),
        ToolDefinitionModel(
            name="web_search",
            description=(
                "Ищет информацию в интернете по текстовому запросу (DuckDuckGo) и "
                "может скачать top-N страниц для извлечения текста."
            ),
            argsModel=WebSearchArgsModel,
            timeoutSeconds=30,
            executeCallable=webSearchTool.execute,
        ),
    ]
    ret = ToolRegistry(in_toolDefinitions=toolDefinitions)
    return ret
