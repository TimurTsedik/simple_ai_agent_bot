from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class LlmCompletionResultModel:
    content: str
    selectedModel: str
    fallbackEvents: list[dict[str, Any]]
