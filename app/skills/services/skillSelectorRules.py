"""
Fallback skill selection when LLM routing fails (invalid/empty route_plan).

Primary routing is implemented in `LlmRoutingPlanResolver`. This module only
preserves coarse, structured heuristics so a failed router still gets sensible
skills and tool gates — not lexical perfection across word forms.
"""

import re

from app.skills.services.skillModels import SkillModel


# --- Shared substrings (fallback only; kept short on purpose) ---

_fallbackEmailMarkers = (
    "e-mail",
    "e‑mail",
    "email",
    "imap",
    "inbox",
    "письм",
    "писем",
    "письмо",
    "почт",
    "отправител",
    "домен",
)

_fallbackDigestNewsMarkers = (
    "дайджест",
    "digest",
    "новост",
    "обзор",
    "сводк",
)

_fallbackTelegramMarkers = ("telegram", "телеграм", "канал", "пост")

_fallbackReminderMarkers = (
    "напомни",
    "напомнить",
    "не забудь",
    "не забудьте",
    "reminder",
)

_fallbackWebMarkers = (
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
)

_fallbackFeedbackMarkers = (
    "понравил",
    "запомни",
    "сохрани",
    "сохранить",
    "сохрани в память",
    "нравятся такие",
    "хочу больше так",
    "мне нравится",
    "понравилась новость",
)

_digestComposerPhrases = ("составь дайджест", "сделай дайджест", "дайджест")

# "дайджест новостей за час" → general telegram digest, not per-user topic digest
_timeWindowNearDigestPattern = re.compile(
    r"(?:дайджест|digest|новост).{0,40}?\bза\b",
    re.IGNORECASE | re.DOTALL,
)

# "дайджест новостей <topic>" capture (third token): e.g. техники
_digestNewsTopicTokenPattern = re.compile(
    r"(?:дайджест|digest)\s+новост\w*\s+([^\s,.;:!?]+)",
)


class SkillSelectorRules:
    def _looksLikeTelegramChannelList(self, in_loweredMessage: str) -> bool:
        ret: bool
        rawText = str(in_loweredMessage or "").strip()
        if rawText == "":
            ret = False
            return ret
        handlePattern = re.compile(r"(?:^|[\s,;])@([a-z0-9_]{4,})\b")
        tmePattern = re.compile(r"(?:^|[\s,;])(?:https?://)?t\.me/([a-z0-9_]{4,})\b")
        hasAtHandle = handlePattern.search(rawText) is not None
        hasTmeHandle = tmePattern.search(rawText) is not None
        hasEmailLikeDomain = (
            re.search(r"@[a-z0-9._-]+\.[a-z]{2,}", rawText) is not None
        )
        ret = (hasAtHandle or hasTmeHandle) and hasEmailLikeDomain is False
        return ret

    def _looksLikeKeywordListFollowup(self, in_loweredMessage: str) -> bool:
        ret: bool
        rawText = str(in_loweredMessage or "").strip()
        if rawText == "":
            ret = False
            return ret
        if self._hasExplicitUserNoteIntent(in_loweredMessage=rawText.lower()) is True:
            ret = False
            return ret
        hasSeparator = any(separator in rawText for separator in [",", ";", "\n"])
        if hasSeparator is False:
            ret = False
            return ret
        if (
            "@" in rawText
            or "t.me/" in rawText
            or "http://" in rawText
            or "https://" in rawText
        ):
            ret = False
            return ret
        normalizedText = rawText.replace("\n", ",").replace(";", ",")
        rawItems = [item.strip() for item in normalizedText.split(",")]
        items = [item for item in rawItems if item != ""]
        if len(items) < 2 or len(items) > 12:
            ret = False
            return ret
        stopWords = {
            "да",
            "нет",
            "ок",
            "окей",
            "спасибо",
            "привет",
            "здравствуйте",
        }
        validCount = 0
        for item in items:
            if len(item) > 48:
                continue
            if item in stopWords:
                continue
            if re.search(r"[a-zа-я0-9]", item) is None:
                continue
            validCount += 1
        ret = validCount >= 2
        return ret

    def _hasUserTopicDigestIntent(self, in_loweredMessage: str) -> bool:
        ret: bool
        loweredValue = in_loweredMessage
        hasDigestIntent = any(
            marker in loweredValue for marker in _fallbackDigestNewsMarkers
        )
        if hasDigestIntent is False:
            ret = False
            return ret
        if "по теме" in loweredValue:
            ret = True
            return ret
        if _timeWindowNearDigestPattern.search(loweredValue) is not None:
            ret = False
            return ret
        matchDigestTopic = _digestNewsTopicTokenPattern.search(loweredValue)
        if matchDigestTopic is None:
            ret = False
            return ret
        topicTokenCandidate = matchDigestTopic.group(1).strip().lower()
        temporalTopicTokens = {
            "за",
            "на",
            "из",
            "последние",
            "последний",
            "последнюю",
            "последних",
            "час",
            "часа",
            "часов",
            "день",
            "дня",
            "дней",
        }
        if topicTokenCandidate in temporalTopicTokens:
            ret = False
            return ret
        ret = True
        return ret

    def _isShortConfirmationMessage(self, in_loweredMessage: str) -> bool:
        ret: bool
        textValue = str(in_loweredMessage or "").strip()
        confirmationWords = {
            "да",
            "ага",
            "ок",
            "окей",
            "подтверждаю",
            "yes",
            "y",
        }
        ret = textValue in confirmationWords
        return ret

    def _hasReminderIntent(self, in_loweredMessage: str) -> bool:
        ret: bool
        strippedLowered = str(in_loweredMessage or "").strip()
        ret = strippedLowered.startswith("помни") or any(
            item in in_loweredMessage for item in _fallbackReminderMarkers
        )
        return ret

    def _hasRecurringScheduledJobIntent(self, in_loweredMessage: str) -> bool:
        ret: bool
        m = str(in_loweredMessage or "")
        recurring_flag = any(
            marker in m
            for marker in (
                "каждый час",
                "каждые ",
                "ежечас",
                "раз в час",
                "раз в день",
                "ежедневн",
                "регулярн",
                "по расписанию",
                "автоматически при",
                "интервал",
                "запланируй",
            )
        )
        digest_or_mail_flag = any(
            marker in m for marker in _fallbackDigestNewsMarkers
        ) or any(marker in m for marker in _fallbackEmailMarkers)
        ret = recurring_flag is True and digest_or_mail_flag is True
        return ret

    def _hasExplicitUserNoteIntent(self, in_loweredMessage: str) -> bool:
        ret: bool
        m = str(in_loweredMessage or "")
        has_verb = (
            "запомни" in m
            or "запиши" in m
            or "сохрани в память" in m
        )
        ret = has_verb is True
        return ret

    def _hasEmailMarkers(self, in_loweredMessage: str) -> bool:
        ret: bool
        ret = any(marker in in_loweredMessage for marker in _fallbackEmailMarkers)
        return ret

    def isToolLikelyRequired(self, in_userMessage: str) -> bool:
        ret: bool
        loweredMessage = in_userMessage.lower()
        preferenceSaveMarkers = (
            "отправител",
            "домен",
            "важные отправители",
            "важный отправитель",
            "запомни",
            "сохрани",
            "сохранить",
        )
        looksLikeDomainList = "@" in loweredMessage and "." in loweredMessage
        wantsEmailPreferenceSave = any(
            item in loweredMessage for item in preferenceSaveMarkers
        )
        digestOrNewsHint = (
            any(m in loweredMessage for m in _fallbackDigestNewsMarkers)
            or any(m in loweredMessage for m in _fallbackTelegramMarkers)
            or "рынок" in loweredMessage
        )
        ret = (
            digestOrNewsHint
            or any(item in loweredMessage for item in _fallbackWebMarkers)
            or self._hasReminderIntent(in_loweredMessage=loweredMessage)
            or self._hasRecurringScheduledJobIntent(in_loweredMessage=loweredMessage)
            or self._hasExplicitUserNoteIntent(in_loweredMessage=loweredMessage)
            or self._looksLikeTelegramChannelList(in_loweredMessage=loweredMessage)
            or self._looksLikeKeywordListFollowup(in_loweredMessage=loweredMessage)
            or self._isShortConfirmationMessage(in_loweredMessage=loweredMessage)
            or (
                wantsEmailPreferenceSave is True and looksLikeDomainList is True
            )
            or (
                wantsEmailPreferenceSave is True and self._hasEmailMarkers(loweredMessage) is True
            )
            or (
                digestOrNewsHint is False
                and self._hasEmailMarkers(loweredMessage) is True
                and wantsEmailPreferenceSave is False
                and loweredMessage.strip() != ""
            )
        )
        return ret

    def selectRelevantSkillIds(self, in_userMessage: str) -> list[str]:
        ret: list[str]
        loweredMessage = in_userMessage.lower()
        selectedIds: list[str] = ["default_assistant"]
        looksLikeTelegramChannelListFlag = self._looksLikeTelegramChannelList(
            in_loweredMessage=loweredMessage
        )
        looksLikeKeywordListFollowupFlag = self._looksLikeKeywordListFollowup(
            in_loweredMessage=loweredMessage
        )
        digestContextHint = (
            any(w in loweredMessage for w in _fallbackDigestNewsMarkers)
            or any(w in loweredMessage for w in _fallbackTelegramMarkers)
            or "стать" in loweredMessage
        )
        hasEmailContext = self._hasEmailMarkers(loweredMessage)
        if any(marker in loweredMessage for marker in _fallbackFeedbackMarkers):
            if hasEmailContext is True:
                if "email_preference_feedback" not in selectedIds:
                    selectedIds.insert(1, "email_preference_feedback")
            elif digestContextHint is True or "предпочт" in loweredMessage:
                if "telegram_digest_feedback" not in selectedIds:
                    selectedIds.insert(1, "telegram_digest_feedback")
        else:
            looksLikeDomainList = "@" in loweredMessage and "." in loweredMessage
            if looksLikeDomainList is True and hasEmailContext is True:
                if "email_preference_feedback" not in selectedIds:
                    selectedIds.insert(1, "email_preference_feedback")
        hasFeedbackIntentFlag = (
            "telegram_digest_feedback" in selectedIds
            or "email_preference_feedback" in selectedIds
        )
        if (
            hasFeedbackIntentFlag is False
            and self._hasExplicitUserNoteIntent(in_loweredMessage=loweredMessage) is True
            and "remember_user_note" not in selectedIds
        ):
            selectedIds.insert(1, "remember_user_note")
        hasUserTopicDigestIntentFlag = self._hasUserTopicDigestIntent(
            in_loweredMessage=loweredMessage
        )
        if (
            hasFeedbackIntentFlag is False
            and hasUserTopicDigestIntentFlag is True
            and "user_topic_telegram_digest" not in selectedIds
        ):
            selectedIds.insert(1, "user_topic_telegram_digest")
        elif (
            hasFeedbackIntentFlag is False
            and looksLikeTelegramChannelListFlag is True
            and "user_topic_telegram_digest" not in selectedIds
        ):
            selectedIds.insert(1, "user_topic_telegram_digest")
        elif (
            hasFeedbackIntentFlag is False
            and looksLikeKeywordListFollowupFlag is True
            and "user_topic_telegram_digest" not in selectedIds
        ):
            selectedIds.insert(1, "user_topic_telegram_digest")
        webSelectionMarkers = ("поиск", "найди", "найти", "в интернете")
        webSelectionMarkersExtra = ("источник", "ссылк")
        if any(item in loweredMessage for item in webSelectionMarkers):
            selectedIds.append("web_research")
        elif any(item in loweredMessage for item in webSelectionMarkersExtra):
            selectedIds.append("web_research")
        if hasEmailContext is True:
            selectedIds.append("read_and_analyze_email")
        if any(item in loweredMessage for item in _digestComposerPhrases):
            if "user_topic_telegram_digest" not in selectedIds:
                selectedIds.append("compose_digest")
        if self._hasRecurringScheduledJobIntent(in_loweredMessage=loweredMessage):
            if "schedule_recurring_agent_run" not in selectedIds:
                selectedIds.insert(1, "schedule_recurring_agent_run")
        if self._hasReminderIntent(in_loweredMessage=loweredMessage):
            selectedIds.append("schedule_reminder")
        if self._isShortConfirmationMessage(in_loweredMessage=loweredMessage):
            if "schedule_reminder" not in selectedIds:
                selectedIds.append("schedule_reminder")
        generalTelegramDigestMarkersEnglish = ("news", "digest", "telegram")
        generalTelegramDigestMarkersRu = ("рынок", "обзор", "сводка")
        if (
            hasFeedbackIntentFlag is False
            and "user_topic_telegram_digest" not in selectedIds
            and hasEmailContext is False
            and (
                any(m in loweredMessage for m in _fallbackDigestNewsMarkers)
                or any(m in loweredMessage for m in generalTelegramDigestMarkersEnglish)
                or any(m in loweredMessage for m in generalTelegramDigestMarkersRu)
            )
        ):
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
