from app.skills.services.skillModels import SkillModel


class SkillSelectorRules:
    def isToolLikelyRequired(self, in_userMessage: str) -> bool:
        ret: bool
        loweredMessage = in_userMessage.lower()
        newsKeywords = [
            "news",
            "digest",
            "новост",
            "дайджест",
            "telegram",
            "телеграм",
            "рынок",
            "рынку",
            "сводка",
            "обзор",
        ]
        ret = any(item in loweredMessage for item in newsKeywords)
        return ret

    def selectRelevantSkillIds(self, in_userMessage: str) -> list[str]:
        ret: list[str]
        loweredMessage = in_userMessage.lower()
        selectedIds: list[str] = ["default_assistant"]
        _ = loweredMessage
        if self.isToolLikelyRequired(in_userMessage=in_userMessage):
            selectedIds.append("telegram_news_digest")
        ret = selectedIds
        return ret

    def pickSkillItems(
        self,
        in_skills: list[SkillModel],
        in_selectedSkillIds: list[str],
        in_maxCount: int,
    ) -> list[SkillModel]:
        ret: list[SkillModel]
        selectedItems: list[SkillModel] = []
        selectedSet = set(in_selectedSkillIds)
        for skillItem in in_skills:
            if skillItem.skillId in selectedSet:
                selectedItems.append(skillItem)
            if len(selectedItems) >= in_maxCount:
                break
        ret = selectedItems
        return ret
