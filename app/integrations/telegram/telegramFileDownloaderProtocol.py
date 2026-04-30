from typing import Protocol


class TelegramFileDownloaderProtocol(Protocol):
    def downloadTelegramFileToPath(
        self,
        *,
        in_fileId: str,
        in_outPath: str,
        in_maxBytes: int,
        in_timeoutSeconds: float,
    ) -> None: ...

