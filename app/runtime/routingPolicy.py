def resolveRequiredFirstSuccessfulToolNameFromSkills(
    in_selectedSkillIds: list[str],
) -> str:
    ret: str
    selectedSkillSetValue = set(in_selectedSkillIds)
    if (
        "telegram_digest_feedback" in selectedSkillSetValue
        or "email_preference_feedback" in selectedSkillSetValue
    ):
        ret = ""
        return ret
    if (
        "compose_digest" in selectedSkillSetValue
        and "read_and_analyze_email" in selectedSkillSetValue
    ):
        ret = "read_email"
    elif "read_and_analyze_email" in selectedSkillSetValue:
        ret = "read_email"
    elif "user_topic_telegram_digest" in selectedSkillSetValue:
        ret = "user_topic_telegram_digest"
    elif "telegram_news_digest" in selectedSkillSetValue:
        ret = "digest_telegram_news"
    else:
        ret = ""
    return ret
