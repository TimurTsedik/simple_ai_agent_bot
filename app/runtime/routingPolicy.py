def hasExplicitRecurringScheduleIntent(in_userMessage: str) -> bool:
    """True если пользователь явно просит повторяющееся/по расписанию действие (не одноразовый запрос)."""

    ret: bool
    m = str(in_userMessage or "").lower()
    if m.strip() == "":
        ret = False
    else:
        recurringMarkers = (
            "повторяющ",
            "регулярн",
            "каждый день",
            "каждый час",
            "каждые ",
            "раз в день",
            "раз в час",
            "по расписанию",
            "ежедневн",
            "ежечас",
            "интервал",
            "recurring",
            "every day",
            "every hour",
        )
        ret = any(marker in m for marker in recurringMarkers)
    return ret


def resolveRequiredFirstSuccessfulToolNameFromSkills(
    in_selectedSkillIds: list[str],
    in_userMessage: str = "",
) -> str:
    ret: str
    selectedSkillSetValue = set(in_selectedSkillIds)
    if (
        "telegram_digest_feedback" in selectedSkillSetValue
        or "email_preference_feedback" in selectedSkillSetValue
    ):
        ret = ""
    elif (
        "compose_digest" in selectedSkillSetValue
        and "read_and_analyze_email" in selectedSkillSetValue
    ):
        ret = "read_email"
    elif "read_and_analyze_email" in selectedSkillSetValue:
        ret = "read_email"
    elif "remember_user_note" in selectedSkillSetValue:
        ret = "save_user_memory_note"
    elif (
        "schedule_recurring_agent_run" in selectedSkillSetValue
        and hasExplicitRecurringScheduleIntent(in_userMessage=in_userMessage) is True
    ):
        ret = "schedule_recurring_agent_run"
    elif "user_topic_telegram_digest" in selectedSkillSetValue:
        ret = "user_topic_telegram_digest"
    elif "telegram_news_digest" in selectedSkillSetValue:
        ret = "digest_telegram_news"
    else:
        ret = ""
    return ret
