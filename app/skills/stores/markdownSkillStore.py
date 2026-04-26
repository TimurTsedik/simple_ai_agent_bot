from pathlib import Path

from app.skills.services.skillModels import SkillModel


class MarkdownSkillStore:
    def __init__(self, in_skillsDirPath: str) -> None:
        self._skillsDirPath = Path(in_skillsDirPath)

    def loadAllSkills(self) -> list[SkillModel]:
        ret: list[SkillModel]
        skillItems: list[SkillModel] = []
        if self._skillsDirPath.exists():
            for filePath in sorted(self._skillsDirPath.glob("*.md")):
                content = filePath.read_text(encoding="utf-8")
                title = filePath.stem
                for lineText in content.splitlines():
                    if lineText.startswith("# "):
                        title = lineText[2:].strip()
                        break
                skillItems.append(
                    SkillModel(
                        skillId=filePath.stem,
                        title=title,
                        content=content,
                    )
                )
        ret = skillItems
        return ret
