import os
from pathlib import Path
from typing import Any

import requests

from app.common.contouringRequestsPolicy import ContouringRequestsPolicy
from app.domain.protocols.loggerProtocol import LoggerProtocol
from app.integrations.telegram.telegramFileDownloaderProtocol import (
    TelegramFileDownloaderProtocol,
)


class TelegramFileDownloader(TelegramFileDownloaderProtocol):
    def __init__(
        self,
        *,
        in_telegramBotToken: str,
        in_httpPolicy: ContouringRequestsPolicy,
        in_logger: LoggerProtocol,
    ) -> None:
        self._telegramBotToken = str(in_telegramBotToken or "").strip()
        self._httpPolicy = in_httpPolicy
        self._logger = in_logger

    def downloadTelegramFileToPath(
        self,
        *,
        in_fileId: str,
        in_outPath: str,
        in_maxBytes: int,
        in_timeoutSeconds: float,
    ) -> None:
        fileIdValue = str(in_fileId or "").strip()
        outPathValue = Path(str(in_outPath or "")).resolve()
        maxBytesValue = max(1, int(in_maxBytes))
        timeoutSecondsValue = max(1.0, float(in_timeoutSeconds))

        filePath = self._resolveTelegramFilePath(
            in_fileId=fileIdValue,
            in_timeoutSeconds=timeoutSecondsValue,
        )
        self._downloadTelegramFileContent(
            in_filePath=filePath,
            in_outPath=str(outPathValue),
            in_maxBytes=maxBytesValue,
            in_timeoutSeconds=timeoutSecondsValue,
        )

    def _resolveTelegramFilePath(self, *, in_fileId: str, in_timeoutSeconds: float) -> str:
        ret: str
        apiUrl = f"https://api.telegram.org/bot{self._telegramBotToken}/getFile"
        response = self._httpPolicy.get(
            apiUrl,
            in_params={"file_id": in_fileId},
            in_timeoutSeconds=in_timeoutSeconds,
        )
        response.raise_for_status()
        payload: Any = response.json()
        filePathValue = ""
        if isinstance(payload, dict):
            resultValue = payload.get("result")
            if isinstance(resultValue, dict):
                filePathCandidate = resultValue.get("file_path")
                if isinstance(filePathCandidate, str):
                    filePathValue = filePathCandidate.strip()
        if filePathValue == "":
            raise RuntimeError("telegram_getFile_missing_file_path")
        ret = filePathValue
        return ret

    def _downloadTelegramFileContent(
        self,
        *,
        in_filePath: str,
        in_outPath: str,
        in_maxBytes: int,
        in_timeoutSeconds: float,
    ) -> None:
        outPathValue = Path(str(in_outPath or "")).resolve()
        outPathValue.parent.mkdir(parents=True, exist_ok=True)
        apiUrl = f"https://api.telegram.org/file/bot{self._telegramBotToken}/{in_filePath}"
        response = self._httpPolicy.get(
            apiUrl,
            in_timeoutSeconds=in_timeoutSeconds,
        )
        response.raise_for_status()
        content = response.content
        if len(content) > int(in_maxBytes):
            raise RuntimeError(f"telegram_file_too_large bytes={len(content)} max={in_maxBytes}")
        outPathValue.write_bytes(content)
        try:
            os.chmod(outPathValue, 0o600)
        except Exception as in_exc:
            self._logger.error(f"telegram_file_chmod_error {in_exc}")

