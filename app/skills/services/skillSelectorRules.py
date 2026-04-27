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
        webKeywords = [
            "поиск",
            "найди",
            "найти",
            "в интернете",
            "в сети",
            "источник",
            "источники",
            "ссылк",
            "проверь по",
            "что пишут",
            "google",
            "duckduckgo",
        ]
        ret = any(item in loweredMessage for item in newsKeywords + webKeywords)
        return ret

    def selectRelevantSkillIds(self, in_userMessage: str) -> list[str]:
        ret: list[str]
        loweredMessage = in_userMessage.lower()
        selectedIds: list[str] = ["default_assistant"]
        if any(item in loweredMessage for item in ["поиск", "найди", "найти", "в интернете", "источник", "ссылк"]):
            selectedIds.append("web_research")
        if any(item in loweredMessage for item in ["составь дайджест", "сделай дайджест", "дайджест"]):
            selectedIds.append("compose_digest")
        if any(item in loweredMessage for item in ["news", "digest", "новост", "дайджест", "рынок", "обзор", "сводка", "телеграм", "telegram"]):
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
