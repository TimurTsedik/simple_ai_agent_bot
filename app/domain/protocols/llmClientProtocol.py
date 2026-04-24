from typing import Protocol


class LlmClientProtocol(Protocol):
    def complete(self, in_modelName: str, in_promptText: str) -> str:
        ...
