from pathlib import Path
from tempfile import TemporaryDirectory

from app.skills.services.skillSelectorRules import SkillSelectorRules
from app.skills.services.skillService import SkillService
from app.skills.stores.markdownSkillStore import MarkdownSkillStore


def testSkillServiceSelectsUserTopicDigestSkill() -> None:
    with TemporaryDirectory() as tempDir:
        skillsDirPath = Path(tempDir)
        (skillsDirPath / "default_assistant.md").write_text(
            "# Default\nbase",
            encoding="utf-8",
        )
        (skillsDirPath / "user_topic_telegram_digest.md").write_text(
            "# User topic digest\nutd",
            encoding="utf-8",
        )
        service = SkillService(
            in_skillStore=MarkdownSkillStore(in_skillsDirPath=str(skillsDirPath)),
            in_skillSelectorRules=SkillSelectorRules(),
            in_skillSelectionMaxCount=4,
        )

        selection = service.buildSkillsSelection(
            in_userMessage="создай дайджест новостей по теме ИИ",
        )

    assert "user_topic_telegram_digest" in selection.selectedSkillIds
    assert "compose_digest" not in selection.selectedSkillIds


def testSkillServiceSelectsUserTopicDigestSkillForInlineTopicPhrase() -> None:
    with TemporaryDirectory() as tempDir:
        skillsDirPath = Path(tempDir)
        (skillsDirPath / "default_assistant.md").write_text(
            "# Default\nbase",
            encoding="utf-8",
        )
        (skillsDirPath / "user_topic_telegram_digest.md").write_text(
            "# User topic digest\nutd",
            encoding="utf-8",
        )
        (skillsDirPath / "compose_digest.md").write_text(
            "# Compose digest\ncompose",
            encoding="utf-8",
        )
        (skillsDirPath / "telegram_news_digest.md").write_text(
            "# Telegram News Digest\nnews",
            encoding="utf-8",
        )
        service = SkillService(
            in_skillStore=MarkdownSkillStore(in_skillsDirPath=str(skillsDirPath)),
            in_skillSelectorRules=SkillSelectorRules(),
            in_skillSelectionMaxCount=4,
        )

        selection = service.buildSkillsSelection(
            in_userMessage="создай дайджест новостей техники",
        )

    assert "user_topic_telegram_digest" in selection.selectedSkillIds
    assert "compose_digest" not in selection.selectedSkillIds
    assert "telegram_news_digest" not in selection.selectedSkillIds


def testSkillServiceKeepsTelegramNewsDigestForTimeWindowRequest() -> None:
    with TemporaryDirectory() as tempDir:
        skillsDirPath = Path(tempDir)
        (skillsDirPath / "default_assistant.md").write_text(
            "# Default\nbase",
            encoding="utf-8",
        )
        (skillsDirPath / "telegram_news_digest.md").write_text(
            "# Telegram News Digest\nnews",
            encoding="utf-8",
        )
        service = SkillService(
            in_skillStore=MarkdownSkillStore(in_skillsDirPath=str(skillsDirPath)),
            in_skillSelectorRules=SkillSelectorRules(),
            in_skillSelectionMaxCount=4,
        )

        selection = service.buildSkillsSelection(
            in_userMessage="сделай дайджест новостей за час",
        )

    assert "user_topic_telegram_digest" not in selection.selectedSkillIds
    assert "telegram_news_digest" in selection.selectedSkillIds


def testSkillServiceSelectsUserTopicDigestForTelegramChannelListFollowup() -> None:
    with TemporaryDirectory() as tempDir:
        skillsDirPath = Path(tempDir)
        (skillsDirPath / "default_assistant.md").write_text(
            "# Default\nbase",
            encoding="utf-8",
        )
        (skillsDirPath / "user_topic_telegram_digest.md").write_text(
            "# User topic digest\nutd",
            encoding="utf-8",
        )
        service = SkillService(
            in_skillStore=MarkdownSkillStore(in_skillsDirPath=str(skillsDirPath)),
            in_skillSelectorRules=SkillSelectorRules(),
            in_skillSelectionMaxCount=4,
        )

        selection = service.buildSkillsSelection(
            in_userMessage="@technomedia, @hiaimedia, @ru_tech_talk, @rozetked, @Wylsared",
        )

    assert "user_topic_telegram_digest" in selection.selectedSkillIds


def testSkillServiceToolLikelyRequiredForTelegramChannelListFollowup() -> None:
    with TemporaryDirectory() as tempDir:
        skillsDirPath = Path(tempDir)
        (skillsDirPath / "default_assistant.md").write_text(
            "# Default\nbase",
            encoding="utf-8",
        )
        service = SkillService(
            in_skillStore=MarkdownSkillStore(in_skillsDirPath=str(skillsDirPath)),
            in_skillSelectorRules=SkillSelectorRules(),
            in_skillSelectionMaxCount=4,
        )

        isRequired = service.isToolLikelyRequired(
            in_userMessage="@technomedia, @hiaimedia, @ru_tech_talk, @rozetked, @Wylsared"
        )

    assert isRequired is True


def testSkillServiceSelectsUserTopicDigestForKeywordListFollowup() -> None:
    with TemporaryDirectory() as tempDir:
        skillsDirPath = Path(tempDir)
        (skillsDirPath / "default_assistant.md").write_text(
            "# Default\nbase",
            encoding="utf-8",
        )
        (skillsDirPath / "user_topic_telegram_digest.md").write_text(
            "# User topic digest\nutd",
            encoding="utf-8",
        )
        service = SkillService(
            in_skillStore=MarkdownSkillStore(in_skillsDirPath=str(skillsDirPath)),
            in_skillSelectorRules=SkillSelectorRules(),
            in_skillSelectionMaxCount=4,
        )

        selection = service.buildSkillsSelection(
            in_userMessage="apple, гаджет, видеокарта, память, новинка",
        )

    assert "user_topic_telegram_digest" in selection.selectedSkillIds


def testExplicitMemoryNoteDoesNotTriggerKeywordListUserTopicHeuristic() -> None:
    rules = SkillSelectorRules()
    selectedIds = rules.selectRelevantSkillIds(
        "привет, запиши, что меня зовут Тимур",
    )
    assert "remember_user_note" in selectedIds
    assert "user_topic_telegram_digest" not in selectedIds


def testSkillServiceToolLikelyRequiredForKeywordListFollowup() -> None:
    with TemporaryDirectory() as tempDir:
        skillsDirPath = Path(tempDir)
        (skillsDirPath / "default_assistant.md").write_text(
            "# Default\nbase",
            encoding="utf-8",
        )
        service = SkillService(
            in_skillStore=MarkdownSkillStore(in_skillsDirPath=str(skillsDirPath)),
            in_skillSelectorRules=SkillSelectorRules(),
            in_skillSelectionMaxCount=4,
        )

        isRequired = service.isToolLikelyRequired(
            in_userMessage="apple, гаджет, видеокарта, память, новинка"
        )

    assert isRequired is True


def testSkillServiceSelectsDefaultAndNewsSkills() -> None:
    with TemporaryDirectory() as tempDir:
        skillsDirPath = Path(tempDir)
        (skillsDirPath / "default_assistant.md").write_text(
            "# Default\nbase",
            encoding="utf-8",
        )
        (skillsDirPath / "telegram_news_digest.md").write_text(
            "# News\nnews",
            encoding="utf-8",
        )
        (skillsDirPath / "web_research.md").write_text(
            "# Web Research\nweb",
            encoding="utf-8",
        )
        service = SkillService(
            in_skillStore=MarkdownSkillStore(in_skillsDirPath=str(skillsDirPath)),
            in_skillSelectorRules=SkillSelectorRules(),
            in_skillSelectionMaxCount=4,
        )

        block = service.buildSkillsBlock(in_userMessage="Сделай AI дайджест новостей")

    assert "Skill: Default" in block
    assert "Skill: News" in block


def testSkillServiceSelectsWebResearchSkill() -> None:
    with TemporaryDirectory() as tempDir:
        skillsDirPath = Path(tempDir)
        (skillsDirPath / "default_assistant.md").write_text(
            "# Default\nbase",
            encoding="utf-8",
        )
        (skillsDirPath / "web_research.md").write_text(
            "# Web Research\nweb",
            encoding="utf-8",
        )
        service = SkillService(
            in_skillStore=MarkdownSkillStore(in_skillsDirPath=str(skillsDirPath)),
            in_skillSelectorRules=SkillSelectorRules(),
            in_skillSelectionMaxCount=4,
        )

        block = service.buildSkillsBlock(in_userMessage="Найди в интернете источники по теме")

    assert "Skill: Web Research" in block


def testSkillServiceSelectsReadAndAnalyzeEmailSkill() -> None:
    with TemporaryDirectory() as tempDir:
        skillsDirPath = Path(tempDir)
        (skillsDirPath / "default_assistant.md").write_text(
            "# Default\nbase",
            encoding="utf-8",
        )
        (skillsDirPath / "read_and_analyze_email.md").write_text(
            "# Read and Analyze Email\nemail",
            encoding="utf-8",
        )
        service = SkillService(
            in_skillStore=MarkdownSkillStore(in_skillsDirPath=str(skillsDirPath)),
            in_skillSelectorRules=SkillSelectorRules(),
            in_skillSelectionMaxCount=4,
        )

        block = service.buildSkillsBlock(in_userMessage="Проверь почту и проанализируй письма")

    assert "Skill: Read and Analyze Email" in block


def testSkillServiceSelectsReadAndAnalyzeEmailSkillForUnreadDigestPhrase() -> None:
    with TemporaryDirectory() as tempDir:
        skillsDirPath = Path(tempDir)
        (skillsDirPath / "default_assistant.md").write_text(
            "# Default\nbase",
            encoding="utf-8",
        )
        (skillsDirPath / "compose_digest.md").write_text(
            "# Compose Digest\ncompose",
            encoding="utf-8",
        )
        (skillsDirPath / "read_and_analyze_email.md").write_text(
            "# Read and Analyze Email\nemail",
            encoding="utf-8",
        )
        (skillsDirPath / "telegram_news_digest.md").write_text(
            "# Telegram News Digest\nnews",
            encoding="utf-8",
        )
        service = SkillService(
            in_skillStore=MarkdownSkillStore(in_skillsDirPath=str(skillsDirPath)),
            in_skillSelectorRules=SkillSelectorRules(),
            in_skillSelectionMaxCount=4,
        )

        selection = service.buildSkillsSelection(
            in_userMessage="сделай дайджест непрочитанных писем",
        )

    assert "read_and_analyze_email" in selection.selectedSkillIds
    assert "telegram_news_digest" not in selection.selectedSkillIds


def testSkillServiceToolLikelyRequiredForUnreadEmailDigestPhrase() -> None:
    with TemporaryDirectory() as tempDir:
        skillsDirPath = Path(tempDir)
        (skillsDirPath / "default_assistant.md").write_text(
            "# Default\nbase",
            encoding="utf-8",
        )
        service = SkillService(
            in_skillStore=MarkdownSkillStore(in_skillsDirPath=str(skillsDirPath)),
            in_skillSelectorRules=SkillSelectorRules(),
            in_skillSelectionMaxCount=4,
        )

        isRequired = service.isToolLikelyRequired(
            in_userMessage="сделай дайджест непрочитанных писем",
        )

    assert isRequired is True


def testSkillServiceSelectsDigestFeedbackSkill() -> None:
    with TemporaryDirectory() as tempDir:
        skillsDirPath = Path(tempDir)
        (skillsDirPath / "default_assistant.md").write_text(
            "# Default\nbase",
            encoding="utf-8",
        )
        (skillsDirPath / "telegram_digest_feedback.md").write_text(
            "# Feedback\nfeedback",
            encoding="utf-8",
        )
        service = SkillService(
            in_skillStore=MarkdownSkillStore(in_skillsDirPath=str(skillsDirPath)),
            in_skillSelectorRules=SkillSelectorRules(),
            in_skillSelectionMaxCount=4,
        )

        block = service.buildSkillsBlock(
            in_userMessage="Запомни, мне понравилась новость из дайджеста про рынок"
        )

    assert "Skill: Feedback" in block


def testSkillServiceSelectsEmailPreferenceFeedbackSkill() -> None:
    with TemporaryDirectory() as tempDir:
        skillsDirPath = Path(tempDir)
        (skillsDirPath / "default_assistant.md").write_text(
            "# Default\nbase",
            encoding="utf-8",
        )
        (skillsDirPath / "email_preference_feedback.md").write_text(
            "# Email Preference Feedback\nemail-pref",
            encoding="utf-8",
        )
        (skillsDirPath / "read_and_analyze_email.md").write_text(
            "# Read and Analyze Email\nemail",
            encoding="utf-8",
        )
        service = SkillService(
            in_skillStore=MarkdownSkillStore(in_skillsDirPath=str(skillsDirPath)),
            in_skillSelectorRules=SkillSelectorRules(),
            in_skillSelectionMaxCount=4,
        )

        selection = service.buildSkillsSelection(
            in_userMessage="запомни, что письма от research@aton.ru важные"
        )

    assert "email_preference_feedback" in selection.selectedSkillIds
    assert "telegram_digest_feedback" not in selection.selectedSkillIds


def testSkillServiceSelectsEmailPreferenceFeedbackSkillForSaveImportantSendersMessage() -> None:
    with TemporaryDirectory() as tempDir:
        skillsDirPath = Path(tempDir)
        (skillsDirPath / "default_assistant.md").write_text(
            "# Default\nbase",
            encoding="utf-8",
        )
        (skillsDirPath / "email_preference_feedback.md").write_text(
            "# Email Preference Feedback\nemail-pref",
            encoding="utf-8",
        )
        service = SkillService(
            in_skillStore=MarkdownSkillStore(in_skillsDirPath=str(skillsDirPath)),
            in_skillSelectorRules=SkillSelectorRules(),
            in_skillSelectionMaxCount=4,
        )

        selection = service.buildSkillsSelection(
            in_userMessage="сохрани важные отправители e-mail: @noip.com, @yaensb.ru"
        )

    assert "email_preference_feedback" in selection.selectedSkillIds


def testSkillServiceSelectsEmailPreferenceFeedbackSkillForFollowupDomainListMessage() -> None:
    with TemporaryDirectory() as tempDir:
        skillsDirPath = Path(tempDir)
        (skillsDirPath / "default_assistant.md").write_text(
            "# Default\nbase",
            encoding="utf-8",
        )
        (skillsDirPath / "email_preference_feedback.md").write_text(
            "# Email Preference Feedback\nemail-pref",
            encoding="utf-8",
        )
        service = SkillService(
            in_skillStore=MarkdownSkillStore(in_skillsDirPath=str(skillsDirPath)),
            in_skillSelectorRules=SkillSelectorRules(),
            in_skillSelectionMaxCount=4,
        )

        selection = service.buildSkillsSelection(
            in_userMessage="любые адреса с этих доменов @noip.com, @yaensb.ru"
        )

    assert "email_preference_feedback" in selection.selectedSkillIds


def testSkillServiceToolLikelyRequiredForEmailPreferenceSaveFollowup() -> None:
    with TemporaryDirectory() as tempDir:
        skillsDirPath = Path(tempDir)
        (skillsDirPath / "default_assistant.md").write_text(
            "# Default\nbase",
            encoding="utf-8",
        )
        service = SkillService(
            in_skillStore=MarkdownSkillStore(in_skillsDirPath=str(skillsDirPath)),
            in_skillSelectorRules=SkillSelectorRules(),
            in_skillSelectionMaxCount=4,
        )

        isRequired = service.isToolLikelyRequired(
            in_userMessage="любые адреса с этих доменов @noip.com, @yaensb.ru"
        )

    assert isRequired is True


def testSkillServiceFeedbackIntentDoesNotPullTelegramNewsDigestSkill() -> None:
    with TemporaryDirectory() as tempDir:
        skillsDirPath = Path(tempDir)
        (skillsDirPath / "default_assistant.md").write_text(
            "# Default\nbase",
            encoding="utf-8",
        )
        (skillsDirPath / "telegram_digest_feedback.md").write_text(
            "# Feedback\nfeedback",
            encoding="utf-8",
        )
        (skillsDirPath / "telegram_news_digest.md").write_text(
            "# News\nnews",
            encoding="utf-8",
        )
        service = SkillService(
            in_skillStore=MarkdownSkillStore(in_skillsDirPath=str(skillsDirPath)),
            in_skillSelectorRules=SkillSelectorRules(),
            in_skillSelectionMaxCount=4,
        )

        selection = service.buildSkillsSelection(
            in_userMessage="мне понравились новости из @how2ai, запомни"
        )

    assert "telegram_digest_feedback" in selection.selectedSkillIds
    assert "telegram_news_digest" not in selection.selectedSkillIds


def testSkillServiceDetectsWhenToolsAreNotRequired() -> None:
    with TemporaryDirectory() as tempDir:
        skillsDirPath = Path(tempDir)
        (skillsDirPath / "default_assistant.md").write_text(
            "# Default\nbase",
            encoding="utf-8",
        )
        service = SkillService(
            in_skillStore=MarkdownSkillStore(in_skillsDirPath=str(skillsDirPath)),
            in_skillSelectorRules=SkillSelectorRules(),
            in_skillSelectionMaxCount=4,
        )

        isRequired = service.isToolLikelyRequired(in_userMessage="кто ты?")

    assert isRequired is False


def testSkillServiceSelectsScheduleReminderSkill() -> None:
    with TemporaryDirectory() as tempDir:
        skillsDirPath = Path(tempDir)
        (skillsDirPath / "default_assistant.md").write_text(
            "# Default\nbase",
            encoding="utf-8",
        )
        (skillsDirPath / "schedule_reminder.md").write_text(
            "# Schedule Reminder\nreminders",
            encoding="utf-8",
        )
        service = SkillService(
            in_skillStore=MarkdownSkillStore(in_skillsDirPath=str(skillsDirPath)),
            in_skillSelectorRules=SkillSelectorRules(),
            in_skillSelectionMaxCount=4,
        )

        selection = service.buildSkillsSelection(
            in_userMessage="напомни завтра в 10:00 созвон"
        )

    assert "schedule_reminder" in selection.selectedSkillIds


def testSkillServiceToolLikelyRequiredForPolitePomniReminder() -> None:
    with TemporaryDirectory() as tempDir:
        skillsDirPath = Path(tempDir)
        (skillsDirPath / "default_assistant.md").write_text(
            "# Default\nbase",
            encoding="utf-8",
        )
        (skillsDirPath / "schedule_reminder.md").write_text(
            "# Schedule Reminder\nreminders",
            encoding="utf-8",
        )
        service = SkillService(
            in_skillStore=MarkdownSkillStore(in_skillsDirPath=str(skillsDirPath)),
            in_skillSelectorRules=SkillSelectorRules(),
            in_skillSelectionMaxCount=4,
        )

        isRequired = service.isToolLikelyRequired(
            in_userMessage="Помни, пожалуйста, завтра в 11 утра про подпись"
        )
        selection = service.buildSkillsSelection(
            in_userMessage="Помни, пожалуйста, завтра в 11 утра про подпись"
        )

    assert isRequired is True
    assert "schedule_reminder" in selection.selectedSkillIds


def testSkillServiceToolLikelyRequiredForReminderIntent() -> None:
    with TemporaryDirectory() as tempDir:
        skillsDirPath = Path(tempDir)
        (skillsDirPath / "default_assistant.md").write_text(
            "# Default\nbase",
            encoding="utf-8",
        )
        service = SkillService(
            in_skillStore=MarkdownSkillStore(in_skillsDirPath=str(skillsDirPath)),
            in_skillSelectorRules=SkillSelectorRules(),
            in_skillSelectionMaxCount=4,
        )

        isRequired = service.isToolLikelyRequired(
            in_userMessage="напомни мне завтра в 9:00"
        )

    assert isRequired is True


def testSkillServiceSelectsScheduleReminderSkillForShortConfirmation() -> None:
    with TemporaryDirectory() as tempDir:
        skillsDirPath = Path(tempDir)
        (skillsDirPath / "default_assistant.md").write_text(
            "# Default\nbase",
            encoding="utf-8",
        )
        (skillsDirPath / "schedule_reminder.md").write_text(
            "# Schedule Reminder\nreminders",
            encoding="utf-8",
        )
        service = SkillService(
            in_skillStore=MarkdownSkillStore(in_skillsDirPath=str(skillsDirPath)),
            in_skillSelectorRules=SkillSelectorRules(),
            in_skillSelectionMaxCount=4,
        )

        selection = service.buildSkillsSelection(in_userMessage="да")

    assert "schedule_reminder" in selection.selectedSkillIds


def testSkillServiceToolLikelyRequiredForShortConfirmation() -> None:
    with TemporaryDirectory() as tempDir:
        skillsDirPath = Path(tempDir)
        (skillsDirPath / "default_assistant.md").write_text(
            "# Default\nbase",
            encoding="utf-8",
        )
        service = SkillService(
            in_skillStore=MarkdownSkillStore(in_skillsDirPath=str(skillsDirPath)),
            in_skillSelectorRules=SkillSelectorRules(),
            in_skillSelectionMaxCount=4,
        )

        isRequired = service.isToolLikelyRequired(in_userMessage="да")

    assert isRequired is True


def testSkillServiceSelectsRememberUserNoteSkill() -> None:
    with TemporaryDirectory() as tempDir:
        skillsDirPath = Path(tempDir)
        (skillsDirPath / "default_assistant.md").write_text(
            "# Default\nbase",
            encoding="utf-8",
        )
        (skillsDirPath / "remember_user_note.md").write_text(
            "# Remember\nnote",
            encoding="utf-8",
        )
        service = SkillService(
            in_skillStore=MarkdownSkillStore(in_skillsDirPath=str(skillsDirPath)),
            in_skillSelectorRules=SkillSelectorRules(),
            in_skillSelectionMaxCount=4,
        )
        selection = service.buildSkillsSelection(
            in_userMessage="Запомни, что я работаю удалённо из Берлина"
        )

    assert "remember_user_note" in selection.selectedSkillIds


def testSkillServicePrefersDigestFeedbackOverRememberUserNote() -> None:
    with TemporaryDirectory() as tempDir:
        skillsDirPath = Path(tempDir)
        (skillsDirPath / "default_assistant.md").write_text(
            "# Default\nbase",
            encoding="utf-8",
        )
        (skillsDirPath / "telegram_digest_feedback.md").write_text(
            "# Digest feedback\ndf",
            encoding="utf-8",
        )
        (skillsDirPath / "remember_user_note.md").write_text(
            "# Remember\nnote",
            encoding="utf-8",
        )
        service = SkillService(
            in_skillStore=MarkdownSkillStore(in_skillsDirPath=str(skillsDirPath)),
            in_skillSelectorRules=SkillSelectorRules(),
            in_skillSelectionMaxCount=4,
        )
        selection = service.buildSkillsSelection(
            in_userMessage="Запомни, мне понравилась новость про рынок из дайджеста"
        )

    assert "telegram_digest_feedback" in selection.selectedSkillIds
    assert "remember_user_note" not in selection.selectedSkillIds
