import os
from pathlib import Path
import re
from typing import Any

import yaml
from dotenv import dotenv_values
from pydantic import ValidationError

from app.config.defaults import DEFAULT_ENV_PATH
from app.config.settingsModels import (
    EmailReaderToolSettings,
    SchedulerSettings,
    SettingsModel,
    TelegramNewsDigestToolSettings,
)


class SettingsLoadError(RuntimeError):
    pass


def _readYamlFile(in_path: Path) -> dict[str, Any]:
    ret: dict[str, Any]
    if not in_path.exists():
        raise SettingsLoadError(f"Config file is not found: {in_path}")
    with in_path.open("r", encoding="utf-8") as fileHandle:
        loadedData = yaml.safe_load(fileHandle) or {}
    if not isinstance(loadedData, dict):
        raise SettingsLoadError("Config root must be a mapping")
    ret = loadedData
    return ret


def _readDotEnvFile(in_path: Path) -> dict[str, str]:
    ret: dict[str, str]
    if in_path.exists():
        loadedValues = dotenv_values(in_path)
        normalizedValues = {
            key: value
            for key, value in loadedValues.items()
            if isinstance(key, str) and isinstance(value, str)
        }
        ret = normalizedValues
    else:
        ret = {}
    return ret


def _applyEnvOverrides(
    in_configData: dict[str, Any],
    in_dotEnvValues: dict[str, str],
) -> dict[str, Any]:
    ret = dict(in_configData)
    ret["telegramBotToken"] = os.getenv(
        "TELEGRAM_BOT_TOKEN", in_dotEnvValues.get("TELEGRAM_BOT_TOKEN", "")
    )
    ret["openRouterApiKey"] = os.getenv(
        "OPENROUTER_API_KEY", in_dotEnvValues.get("OPENROUTER_API_KEY", "")
    )
    ret["sessionCookieSecret"] = os.getenv(
        "SESSION_COOKIE_SECRET", in_dotEnvValues.get("SESSION_COOKIE_SECRET", "")
    )
    ret["emailAppPassword"] = os.getenv(
        "EMAIL_APP_PASSWORD", in_dotEnvValues.get("EMAIL_APP_PASSWORD", "")
    )
    rawAdminTokens = os.getenv(
        "ADMIN_RAW_TOKENS", in_dotEnvValues.get("ADMIN_RAW_TOKENS", "")
    )
    ret["adminRawTokens"] = _parseAdminTokens(in_rawValue=rawAdminTokens)
    return ret


def _parseAdminTokens(in_rawValue: str) -> list[str]:
    ret: list[str]
    ret = [item.strip() for item in in_rawValue.split(",") if item.strip()]
    return ret


def _validateAdminTokens(in_tokens: list[str]) -> None:
    tokenPattern = re.compile(r"^[A-Za-z0-9._-]+$")
    seenTokens: set[str] = set()
    for tokenValue in in_tokens:
        if len(tokenValue) < 16:
            raise SettingsLoadError(
                "Invalid settings: each ADMIN_RAW_TOKENS value must be at least 16 chars."
            )
        if tokenPattern.fullmatch(tokenValue) is None:
            raise SettingsLoadError(
                "Invalid settings: ADMIN_RAW_TOKENS has unsupported characters."
            )
        if tokenValue in seenTokens:
            raise SettingsLoadError(
                "Invalid settings: ADMIN_RAW_TOKENS contains duplicate values."
            )
        seenTokens.add(tokenValue)


def loadSettings(in_configPath: str, in_envPath: str = DEFAULT_ENV_PATH) -> SettingsModel:
    ret: SettingsModel
    configPath = Path(in_configPath)
    envPath = Path(in_envPath)
    configData = _readYamlFile(in_path=configPath)
    dotEnvValues = _readDotEnvFile(in_path=envPath)
    mergedData = _applyEnvOverrides(
        in_configData=configData,
        in_dotEnvValues=dotEnvValues,
    )
    try:
        baseSettings = SettingsModel.model_validate(mergedData)
    except ValidationError as in_exc:
        raise SettingsLoadError(f"Invalid settings: {in_exc}") from in_exc
    if len(baseSettings.adminRawTokens) == 0:
        raise SettingsLoadError(
            "Invalid settings: ADMIN_RAW_TOKENS is required for web auth."
        )
    if len(baseSettings.adminRawTokens) > baseSettings.security.maxAdminTokens:
        raise SettingsLoadError(
            "Invalid settings: ADMIN_RAW_TOKENS count exceeds security.maxAdminTokens."
        )
    _validateAdminTokens(in_tokens=baseSettings.adminRawTokens)

    # Tool-specific settings (tools.yaml) with backward compatibility:
    # - If tools.yaml exists, prefer it.
    # - Otherwise, fallback to legacy telegram.* fields.
    toolsConfigPath = Path(baseSettings.tools.toolsConfigPath)
    if toolsConfigPath.is_absolute() is False:
        # Resolve relative to current working directory.
        # `toolsConfigPath` can be "./app/config/tools.yaml" and should not be joined with
        # config directory (would duplicate "app/config").
        toolsConfigPath = toolsConfigPath.resolve()

    toolsData: dict[str, Any] | None = None
    if toolsConfigPath.exists():
        loadedToolsData = _readYamlFile(in_path=toolsConfigPath)
        toolsData = loadedToolsData if isinstance(loadedToolsData, dict) else None

    legacyDigest = TelegramNewsDigestToolSettings(
        digestChannelUsernames=list(baseSettings.telegram.digestChannelUsernames),
        portfolioTickers=list(baseSettings.telegram.portfolioTickers),
        digestSemanticKeywords=list(baseSettings.telegram.digestSemanticKeywords),
    )
    effectiveDigest: TelegramNewsDigestToolSettings
    effectiveEmail: EmailReaderToolSettings
    if toolsData is None:
        effectiveDigest = legacyDigest
        effectiveEmail = EmailReaderToolSettings()
    else:
        try:
            parsedDigest = TelegramNewsDigestToolSettings.model_validate(
                toolsData.get("telegramNewsDigest", {}) if isinstance(toolsData, dict) else {}
            )
            effectiveDigest = parsedDigest
        except ValidationError:
            effectiveDigest = legacyDigest
        try:
            parsedEmail = EmailReaderToolSettings.model_validate(
                toolsData.get("emailReader", {}) if isinstance(toolsData, dict) else {}
            )
            effectiveEmail = parsedEmail
        except ValidationError:
            effectiveEmail = EmailReaderToolSettings()

    ret = baseSettings.model_copy(
        update={
            "tools": baseSettings.tools.model_copy(
                update={"telegramNewsDigest": effectiveDigest, "emailReader": effectiveEmail}
            )
        }
    )
    # Scheduler settings (schedules.yaml). Optional unless scheduler.enabled=true.
    schedulesPath = Path(ret.scheduler.schedulesConfigPath)
    if schedulesPath.is_absolute() is False:
        schedulesPath = schedulesPath.resolve()
    if ret.scheduler.enabled is True:
        if schedulesPath.exists() is False:
            raise SettingsLoadError(f"Scheduler is enabled but schedules file is missing: {schedulesPath}")
        loadedSchedulesData = _readYamlFile(in_path=schedulesPath)
        try:
            parsedScheduler = SchedulerSettings.model_validate(
                {"enabled": True, **loadedSchedulesData} if isinstance(loadedSchedulesData, dict) else {"enabled": True}
            )
        except ValidationError as in_exc:
            raise SettingsLoadError(f"Invalid scheduler settings: {in_exc}") from in_exc
        effectiveScheduler = parsedScheduler.model_copy(
            update={
                "enabled": ret.scheduler.enabled,
                "schedulesConfigPath": ret.scheduler.schedulesConfigPath,
                "tickSeconds": ret.scheduler.tickSeconds,
            }
        )
        ret = ret.model_copy(update={"scheduler": effectiveScheduler})
    return ret
