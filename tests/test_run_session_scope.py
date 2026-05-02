from app.common.runSessionScope import sessionIdMatchesTenantPrincipal


def testSessionIdMatchesTenantPrincipalExactAndChildNamespaces() -> None:
    p = "telegramUser:16739703"
    assert sessionIdMatchesTenantPrincipal("telegramUser:16739703", p) is True
    assert sessionIdMatchesTenantPrincipal("telegramUser:16739703:scheduler:email", p) is True
    assert sessionIdMatchesTenantPrincipal("telegramUser:16739703:scheduler:telegram_news", p) is True
    assert sessionIdMatchesTenantPrincipal("telegramUser:16739704", p) is False
    assert sessionIdMatchesTenantPrincipal("telegramUser:167397031", p) is False
