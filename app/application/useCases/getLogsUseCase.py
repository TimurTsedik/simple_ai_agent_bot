import json
from pathlib import Path
from typing import Any

from app.config.settingsModels import LoggingSettings


class GetLogsUseCase:
    def __init__(self, in_loggingSettings: LoggingSettings) -> None:
        self._loggingSettings = in_loggingSettings

    def execute(self, in_limit: int) -> list[dict[str, Any]]:
        ret: list[dict[str, Any]]
        boundedLimit = max(1, in_limit)
        logsPath = Path(self._loggingSettings.logsDirPath) / self._loggingSettings.runLogsFileName
        events: list[dict[str, Any]] = []
        if logsPath.exists():
            lines = logsPath.read_text(encoding="utf-8").splitlines()
            tailLines = lines[-boundedLimit:]
            for lineText in reversed(tailLines):
                try:
                    parsedValue = json.loads(lineText)
                    if isinstance(parsedValue, dict):
                        events.append(parsedValue)
                except json.JSONDecodeError:
                    pass
        ret = events
        return ret
