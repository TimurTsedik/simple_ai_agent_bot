from app.security.webSessionAuth import createSessionCookieValue
from app.security.webSessionAuth import hashAdminToken
from app.security.webSessionAuth import parseSessionCookieValue


def testSessionCookieRoundtrip() -> None:
    tokenHash = hashAdminToken(in_rawToken="token-1", in_secret="secret-1")
    cookieValue = createSessionCookieValue(
        in_tokenHash=tokenHash,
        in_secret="secret-1",
        in_ttlSeconds=3600,
    )
    payload = parseSessionCookieValue(
        in_cookieValue=cookieValue,
        in_secret="secret-1",
    )

    assert payload is not None
    assert payload.get("tokenHash") == tokenHash


def testSessionCookieRejectsInvalidSignature() -> None:
    tokenHash = hashAdminToken(in_rawToken="token-1", in_secret="secret-1")
    cookieValue = createSessionCookieValue(
        in_tokenHash=tokenHash,
        in_secret="secret-1",
        in_ttlSeconds=3600,
    )
    payload = parseSessionCookieValue(
        in_cookieValue=cookieValue,
        in_secret="wrong-secret",
    )

    assert payload is None
