from dataclasses import dataclass
from typing import Any, Literal


@dataclass(frozen=True)
class RoutingResolutionEntity:
    skillsBlock: str
    selectedSkillIds: list[str]
    allowToolCalls: bool
    requiredFirstSuccessfulToolName: str
    memoryMode: Literal["full", "long_term_only"]
    routingSource: Literal["llm", "fallback"]
    routingPlanDump: dict[str, Any]
    routingPromptSnapshot: str
    routingRawModelResponse: str | None
    routingParseErrorCode: str | None
    routingParseErrorMessage: str | None
    routingFallbackReason: str | None
    routingDiagnostics: tuple[dict[str, str | None], ...]
