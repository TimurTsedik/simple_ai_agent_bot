from app.common.schedulerSessionId import (
    isScheduledInternalRunSessionId,
    normalizeScheduledInternalSessionId,
)


def testNormalizeScheduledInternalSessionIdPrefixesLegacySchedulerNamespaces() -> None:
    normalized = normalizeScheduledInternalSessionId(
        in_sessionId="scheduler:email",
        in_scopeTelegramUserId=16739703,
    )
    assert normalized == "telegramUser:16739703:scheduler:email"


def testNormalizeLeavesExplicitAdminScopedSessionUntouched() -> None:
    same = normalizeScheduledInternalSessionId(
        in_sessionId="telegramUser:16739703:scheduler:email",
        in_scopeTelegramUserId=16739703,
    )
    assert same == "telegramUser:16739703:scheduler:email"


def testNormalizeLeavesForeignTelegramUserSessionUntouched() -> None:
    ret = normalizeScheduledInternalSessionId(
        in_sessionId="telegramUser:999:custom",
        in_scopeTelegramUserId=16739703,
    )
    assert ret == "telegramUser:999:custom"


def testIsScheduledInternalRunSessionIdDetectsSchedulerNamespace() -> None:
    assert isScheduledInternalRunSessionId(in_sessionId="telegramUser:1:scheduler:email") is True
    assert isScheduledInternalRunSessionId(in_sessionId="telegramUser:1:chat") is False
