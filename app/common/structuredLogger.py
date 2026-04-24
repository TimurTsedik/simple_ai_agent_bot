import json
import logging
from pathlib import Path
from typing import Any

from logging.handlers import RotatingFileHandler

from app.config.settingsModels import LoggingSettings
from app.common.timeProvider import getUtcNowIso


def createAppLogger(in_loggingSettings: LoggingSettings) -> logging.Logger:
    ret: logging.Logger
    loggerName = "simpleAiAgentBot"
    logger = logging.getLogger(loggerName)
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    logsDir = Path(in_loggingSettings.logsDirPath)
    logsDir.mkdir(parents=True, exist_ok=True)
    logFilePath = logsDir / in_loggingSettings.appLogsFileName

    fileHandler = RotatingFileHandler(
        filename=logFilePath,
        maxBytes=in_loggingSettings.maxBytes,
        backupCount=in_loggingSettings.backupCount,
        encoding="utf-8",
    )
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    fileHandler.setFormatter(formatter)
    logger.addHandler(fileHandler)
    ret = logger
    return ret


def writeJsonlEvent(
    in_loggingSettings: LoggingSettings,
    in_eventType: str,
    in_payload: dict[str, Any],
) -> None:
    logsDir = Path(in_loggingSettings.logsDirPath)
    logsDir.mkdir(parents=True, exist_ok=True)
    runLogPath = logsDir / in_loggingSettings.runLogsFileName

    eventData = {
        "timestamp": getUtcNowIso(),
        "eventType": in_eventType,
        **in_payload,
    }
    with runLogPath.open("a", encoding="utf-8") as fileHandle:
        fileHandle.write(json.dumps(eventData, ensure_ascii=False) + "\n")
