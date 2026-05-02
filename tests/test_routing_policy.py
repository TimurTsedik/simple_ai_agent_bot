from app.runtime.routingPolicy import (
    hasExplicitRecurringScheduleIntent,
    resolveRequiredFirstSuccessfulToolNameFromSkills,
)


def testRoutingPolicyClearsToolsForDigestFeedbackSkills() -> None:
    ret = resolveRequiredFirstSuccessfulToolNameFromSkills(
        in_selectedSkillIds=["default_assistant", "telegram_digest_feedback"],
    )
    assert ret == ""


def testRoutingPolicyPreferReadEmailWhenComposeDigestAndEmailSkills() -> None:
    ret = resolveRequiredFirstSuccessfulToolNameFromSkills(
        in_selectedSkillIds=["compose_digest", "read_and_analyze_email"],
    )
    assert ret == "read_email"


def testRoutingPolicyPreferUserTopicDigestTool() -> None:
    ret = resolveRequiredFirstSuccessfulToolNameFromSkills(
        in_selectedSkillIds=["user_topic_telegram_digest"],
    )
    assert ret == "user_topic_telegram_digest"


def testRoutingPolicyPrefersSaveUserMemoryNoteWhenRememberSkillPresent() -> None:
    ret = resolveRequiredFirstSuccessfulToolNameFromSkills(
        in_selectedSkillIds=[
            "default_assistant",
            "remember_user_note",
            "user_topic_telegram_digest",
        ],
    )
    assert ret == "save_user_memory_note"


def testRoutingPolicyPrefersScheduleRecurringWhenRecurringIntentAndSkill() -> None:
    ret = resolveRequiredFirstSuccessfulToolNameFromSkills(
        in_selectedSkillIds=[
            "default_assistant",
            "schedule_recurring_agent_run",
            "user_topic_telegram_digest",
        ],
        in_userMessage="создай повторяющееся событие каждый день в 10 утра дайджест по теме AI",
    )
    assert ret == "schedule_recurring_agent_run"


def testRoutingPolicyKeepsUserTopicWhenNoRecurringWording() -> None:
    ret = resolveRequiredFirstSuccessfulToolNameFromSkills(
        in_selectedSkillIds=[
            "default_assistant",
            "schedule_recurring_agent_run",
            "user_topic_telegram_digest",
        ],
        in_userMessage="дайджест новостей в телеграм по теме AI",
    )
    assert ret == "user_topic_telegram_digest"


def testHasExplicitRecurringScheduleIntentDetectsRussianPhrases() -> None:
    assert hasExplicitRecurringScheduleIntent("каждый день в 10") is True
    assert hasExplicitRecurringScheduleIntent("просто дайджест по AI") is False
