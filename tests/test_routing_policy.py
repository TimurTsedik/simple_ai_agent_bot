from app.runtime.routingPolicy import resolveRequiredFirstSuccessfulToolNameFromSkills


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
