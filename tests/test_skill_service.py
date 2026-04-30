from pathlib import Path
from tempfile import TemporaryDirectory

from app.skills.services.skillSelectorRules import SkillSelectorRules
from app.skills.services.skillService import SkillService
from app.skills.stores.markdownSkillStore import MarkdownSkillStore


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
