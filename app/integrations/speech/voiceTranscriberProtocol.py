from typing import Protocol


class VoiceTranscriberProtocol(Protocol):
    def transcribeToText(
        self,
        *,
        in_audioPath: str,
        in_language: str,
        in_maxSeconds: int,
    ) -> str: ...

