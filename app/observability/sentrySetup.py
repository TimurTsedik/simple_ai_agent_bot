import logging

from app.config.settingsModels import SettingsModel
from app.domain.protocols.loggerProtocol import LoggerProtocol

# basedpyright: reportMissingImports=false


def configureSentry(in_settings: SettingsModel, in_logger: LoggerProtocol | None) -> bool:
    ret = False
    sentrySettings = in_settings.sentry
    dsnValue = str(sentrySettings.dsn or "").strip()
    if sentrySettings.enabled is not True:
        if in_logger is not None:
            in_logger.info("Sentry is disabled by configuration.")
    elif dsnValue == "":
        if in_logger is not None:
            in_logger.error("Sentry is enabled but DSN is empty; integration is skipped.")
    else:
        try:
            import sentry_sdk  # type: ignore[import-not-found]
            from sentry_sdk.integrations.fastapi import (  # type: ignore[import-not-found]
                FastApiIntegration,
            )
            from sentry_sdk.integrations.logging import (  # type: ignore[import-not-found]
                LoggingIntegration,
            )
        except ImportError:
            if in_logger is not None:
                in_logger.error(
                    "Sentry SDK is not installed; add sentry-sdk to dependencies."
                )
        else:
            effectiveEnvironment = str(sentrySettings.environment or "").strip()
            if effectiveEnvironment == "":
                effectiveEnvironment = str(in_settings.app.environment or "").strip()
            effectiveRelease = str(sentrySettings.release or "").strip()
            sentry_sdk.init(
                dsn=dsnValue,
                environment=effectiveEnvironment or None,
                release=effectiveRelease or None,
                traces_sample_rate=float(sentrySettings.tracesSampleRate),
                profiles_sample_rate=float(sentrySettings.profilesSampleRate),
                send_default_pii=bool(sentrySettings.sendDefaultPii),
                integrations=[
                    FastApiIntegration(),
                    LoggingIntegration(level=logging.INFO, event_level=logging.ERROR),
                ],
            )
            if in_logger is not None:
                in_logger.info("Sentry successfully configured.")
            ret = True
    return ret


def captureSentryException(in_exception: Exception) -> None:
    try:
        import sentry_sdk  # type: ignore[import-not-found]
    except ImportError:
        return
    sentry_sdk.capture_exception(in_exception)
