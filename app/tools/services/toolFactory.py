from app.config.settingsModels import SettingsModel
from app.memory.stores.markdownMemoryStore import MarkdownMemoryStore
from app.reminders.reminderConfigStore import ReminderConfigStore
from app.tools.implementations.deleteReminderTool import DeleteReminderTool
from app.tools.digestTopicSeeds import collectSeedKeywordsForTopics
from app.tools.implementations.digestTelegramNewsTool import DigestTelegramNewsTool
from app.tools.implementations.userTopicDigestTool import UserTopicDigestTool
from app.tools.implementations.listRemindersTool import ListRemindersTool
from app.tools.implementations.readEmailTool import ReadEmailTool
from app.tools.implementations.readMemoryFileTool import ReadMemoryFileTool
from app.tools.implementations.scheduleReminderTool import ScheduleReminderTool
from app.tools.implementations.saveDigestPreferenceTool import SaveDigestPreferenceTool
from app.tools.implementations.saveEmailPreferenceTool import SaveEmailPreferenceTool
from app.tools.implementations.webSearchTool import WebSearchTool
from app.tools.registry.toolRegistry import ToolDefinitionModel, ToolRegistry
from app.tools.registry.toolSchemas import (
    DeleteReminderArgsModel,
    DigestTelegramNewsArgsModel,
    ListRemindersArgsModel,
    ReadEmailArgsModel,
    ReadMemoryFileArgsModel,
    ScheduleReminderArgsModel,
    SaveDigestPreferenceArgsModel,
    SaveEmailPreferenceArgsModel,
    UserTopicTelegramDigestArgsModel,
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
    userTopicFetchEngine = DigestTelegramNewsTool(
        getDigestChannelUsernames=lambda: [],
        getDefaultKeywords=lambda: [],
        getTopicSeedsForTopics=collectSeedKeywordsForTopics,
    )
    userTopicDigestTool = UserTopicDigestTool(
        in_memoryStore=in_memoryStore,
        in_dataRootPath=in_settings.app.dataRootPath,
        in_fetchEngine=userTopicFetchEngine,
    )
    saveDigestPreferenceTool = SaveDigestPreferenceTool(in_memoryStore=in_memoryStore)
    saveEmailPreferenceTool = SaveEmailPreferenceTool(in_memoryStore=in_memoryStore)
    readMemoryFileTool = ReadMemoryFileTool(
        in_allowedReadOnlyPaths=in_settings.security.allowedReadOnlyPaths
    )
    readEmailTool = ReadEmailTool(
        in_emailSettings=in_settings.tools.emailReader,
        in_password=in_settings.emailAppPassword,
    )
    webSearchTool = WebSearchTool()
    reminderConfigStore = ReminderConfigStore(
        in_schedulesConfigPath=in_settings.scheduler.schedulesConfigPath
    )
    scheduleReminderTool = ScheduleReminderTool(in_reminderConfigStore=reminderConfigStore)
    listRemindersTool = ListRemindersTool(
        in_reminderConfigStore=reminderConfigStore,
        in_dataRootPath=in_settings.app.dataRootPath,
    )
    deleteReminderTool = DeleteReminderTool(
        in_reminderConfigStore=reminderConfigStore,
        in_dataRootPath=in_settings.app.dataRootPath,
    )
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
            name="user_topic_telegram_digest",
            description=(
                "Пользовательские дайджесты Telegram по именованной теме: хранит каналы и ключевые слова "
                "в долгосрочной памяти, ведёт state непрочитанных постов, до 20 постов на канал. "
                "Каналы в args — только @username или t.me/...; без @ латинские токены считаются "
                "ключевыми словами, не каналами. "
                "fetchUnread=false — проверка/пошаговая настройка (merge channels/keywords); "
                "fetchUnread=true — загрузка новых постов; deleteTopic=true — удалить настройки темы."
            ),
            argsModel=UserTopicTelegramDigestArgsModel,
            timeoutSeconds=45,
            executeCallable=userTopicDigestTool.execute,
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
            name="save_email_preference",
            description=(
                "Сохраняет в долгосрочную память предпочтения пользователя по email "
                "(preferredSenders, preferredKeywords, userNote). Письма от preferredSenders "
                "должны попадать в категорию 1 email-дайджеста. Вызывай после явного подтверждения "
                "пользователем того, кого/что считать предпочтительным."
            ),
            argsModel=SaveEmailPreferenceArgsModel,
            timeoutSeconds=5,
            executeCallable=saveEmailPreferenceTool.execute,
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
                "Читает письма из почтового ящика по IMAP. По умолчанию только непрочитанные: "
                "IMAP SEARCH UNSEEN, затем отсечение по флагу \\Seen в FETCH (FLAGS), тело через BODY.PEEK[] "
                "(без автопометки прочитанным до markAsRead). Не выключай unreadOnly для дайджеста «непрочитанных»."
            ),
            argsModel=ReadEmailArgsModel,
            timeoutSeconds=45,
            executeCallable=readEmailTool.execute,
        ),
        ToolDefinitionModel(
            name="schedule_reminder",
            description=(
                "Создает или обновляет напоминание в scheduler schedules.yaml "
                "(строго структурированные поля расписания, без свободного NLP-парсинга)."
            ),
            argsModel=ScheduleReminderArgsModel,
            timeoutSeconds=5,
            executeCallable=scheduleReminderTool.execute,
        ),
        ToolDefinitionModel(
            name="list_reminders",
            description=(
                "Возвращает список reminder-ов из schedules.yaml и их runtime state из jobs_state.json."
            ),
            argsModel=ListRemindersArgsModel,
            timeoutSeconds=5,
            executeCallable=listRemindersTool.execute,
        ),
        ToolDefinitionModel(
            name="delete_reminder",
            description=(
                "Удаляет reminder по reminderId из schedules.yaml и runtime state."
            ),
            argsModel=DeleteReminderArgsModel,
            timeoutSeconds=5,
            executeCallable=deleteReminderTool.execute,
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
