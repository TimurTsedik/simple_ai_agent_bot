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
        service = SkillService(
            in_skillStore=MarkdownSkillStore(in_skillsDirPath=str(skillsDirPath)),
            in_skillSelectorRules=SkillSelectorRules(),
            in_skillSelectionMaxCount=4,
        )

        block = service.buildSkillsBlock(in_userMessage="Сделай AI дайджест новостей")

    assert "Skill: Default" in block
    assert "Skill: News" in block
