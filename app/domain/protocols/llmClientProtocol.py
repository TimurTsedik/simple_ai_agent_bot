from typing import Protocol

from app.domain.entities.llmCompletionResult import LlmCompletionResultModel


class LlmClientProtocol(Protocol):
    def complete(
        self, in_modelName: str, in_promptText: str
    ) -> LlmCompletionResultModel:
        ...
