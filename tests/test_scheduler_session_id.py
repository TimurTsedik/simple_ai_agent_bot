from app.common.schedulerSessionId import normalizeScheduledInternalSessionId


def testNormalizeScheduledInternalSessionIdPrefixesLegacySchedulerNamespaces() -> None:
    normalized = normalizeScheduledInternalSessionId(
        in_sessionId="scheduler:email",
        in_adminTelegramUserId=16739703,
    )
    assert normalized == "telegramUser:16739703:scheduler:email"


def testNormalizeLeavesExplicitAdminScopedSessionUntouched() -> None:
    same = normalizeScheduledInternalSessionId(
        in_sessionId="telegramUser:16739703:scheduler:email",
        in_adminTelegramUserId=16739703,
    )
    assert same == "telegramUser:16739703:scheduler:email"


def testNormalizeLeavesForeignTelegramUserSessionUntouched() -> None:
    ret = normalizeScheduledInternalSessionId(
        in_sessionId="telegramUser:999:custom",
        in_adminTelegramUserId=16739703,
    )
    assert ret == "telegramUser:999:custom"
