from app.common.memoryPrincipal import (
    formatTelegramUserMemoryPrincipal,
    parseTelegramUserIdFromMemoryPrincipal,
)


def testFormatAndParseTelegramUserPrincipalRoundTrip() -> None:
    principal = formatTelegramUserMemoryPrincipal(in_telegramUserId=42)
    assert principal == "telegramUser:42"
    assert parseTelegramUserIdFromMemoryPrincipal(in_memoryPrincipalId=principal) == 42


def testParsePrincipalRejectsInvalid() -> None:
    assert parseTelegramUserIdFromMemoryPrincipal(in_memoryPrincipalId="") is None
    assert parseTelegramUserIdFromMemoryPrincipal(in_memoryPrincipalId="telegram:1") is None
    assert parseTelegramUserIdFromMemoryPrincipal(in_memoryPrincipalId="telegramUser:abc") is None
    assert parseTelegramUserIdFromMemoryPrincipal(in_memoryPrincipalId="telegramUser:0") is None
