from dataclasses import dataclass

from app.skills.services.skillModels import SkillModel
from app.skills.services.skillSelectorRules import SkillSelectorRules
from app.skills.stores.markdownSkillStore import MarkdownSkillStore


@dataclass(frozen=True)
class SkillSelectionResultModel:
    selectedSkillIds: list[str]
    skillsBlock: str


class SkillService:
    def __init__(
        self,
        in_skillStore: MarkdownSkillStore,
        in_skillSelectorRules: SkillSelectorRules,
        in_skillSelectionMaxCount: int,
    ) -> None:
        self._skillStore = in_skillStore
        self._skillSelectorRules = in_skillSelectorRules
        self._skillSelectionMaxCount = in_skillSelectionMaxCount

    def loadAllSkills(self) -> list[SkillModel]:
        ret: list[SkillModel]
        ret = self._skillStore.loadAllSkills()
        return ret

    def buildSkillsSelectionForSortedSkillIds(
        self,
        in_selectedSkillIds: list[str],
    ) -> SkillSelectionResultModel:
        ret: SkillSelectionResultModel
        allSkills = self._skillStore.loadAllSkills()
        selectedItems = self._skillSelectorRules.pickSkillItems(
            in_skills=allSkills,
            in_selectedSkillIds=in_selectedSkillIds,
            in_maxCount=self._skillSelectionMaxCount,
        )
        renderedSkillBlocks = [
            f"## Skill: {item.title}\n{item.content}" for item in selectedItems
        ]
        ret = SkillSelectionResultModel(
            selectedSkillIds=[item.skillId for item in selectedItems],
            skillsBlock="\n\n".join(renderedSkillBlocks),
        )
        return ret

    def buildSkillsRoutingCatalogSummary(self) -> str:
        ret: str
        lines: list[str] = []
        for skillItem in self._skillStore.loadAllSkills():
            lineText = (
                f"- id: `{skillItem.skillId}` — {skillItem.title}"
            ).strip()
            lines.append(lineText)
        ret = "\n".join(lines)
        return ret

    def buildSkillsSelection(self, in_userMessage: str) -> SkillSelectionResultModel:
        ret: SkillSelectionResultModel
        allSkills = self._skillStore.loadAllSkills()
        selectedIds = self._skillSelectorRules.selectRelevantSkillIds(
            in_userMessage=in_userMessage
        )
        selectedItems = self._skillSelectorRules.pickSkillItems(
            in_skills=allSkills,
            in_selectedSkillIds=selectedIds,
            in_maxCount=self._skillSelectionMaxCount,
        )
        renderedItems = [
            f"## Skill: {item.title}\n{item.content}" for item in selectedItems
        ]
        ret = SkillSelectionResultModel(
            selectedSkillIds=[item.skillId for item in selectedItems],
            skillsBlock="\n\n".join(renderedItems),
        )
        return ret

    def buildSkillsBlock(self, in_userMessage: str) -> str:
        ret: str
        selectionResult = self.buildSkillsSelection(in_userMessage=in_userMessage)
        ret = selectionResult.skillsBlock
        return ret

    def isToolLikelyRequired(self, in_userMessage: str) -> bool:
        ret: bool
        ret = self._skillSelectorRules.isToolLikelyRequired(in_userMessage=in_userMessage)
        return ret
