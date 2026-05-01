from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, ValidationError


class RoutingPlanYamlModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["route_plan"]
    selected_skill_ids: list[str]
    allow_tool_calls: bool
    required_first_successful_tool_name: str = ""
    memory_mode: Literal["full", "long_term_only"]


@dataclass(frozen=True)
class RoutingPlanParseOutcomeModel:
    isValid: bool
    validatedPlan: RoutingPlanYamlModel | None
    errorCode: str | None
    errorMessage: str | None


def validateAgainstCatalog(
    in_plan: RoutingPlanYamlModel,
    in_knownSkillIds: set[str],
    in_registeredToolNames: set[str],
) -> RoutingPlanParseOutcomeModel:
    ret: RoutingPlanParseOutcomeModel
    trimmedSkillIds: list[str] = []
    duplicateBlock: set[str] = set()
    for skillIdRaw in list(in_plan.selected_skill_ids or []):
        skillIdNormalized = str(skillIdRaw or "").strip()
        if skillIdNormalized == "":
            continue
        if skillIdNormalized not in duplicateBlock:
            trimmedSkillIds.append(skillIdNormalized)
            duplicateBlock.add(skillIdNormalized)
    if len(trimmedSkillIds) == 0:
        ret = RoutingPlanParseOutcomeModel(
            isValid=False,
            validatedPlan=None,
            errorCode="EMPTY_SKILL_SELECTION",
            errorMessage="Routing plan must include at least one non-empty selected_skill_ids entry.",
        )
        return ret
    allowedSkillSubset: list[str] = []
    for skillIdNormalized in trimmedSkillIds:
        if skillIdNormalized in in_knownSkillIds:
            allowedSkillSubset.append(skillIdNormalized)
    if len(allowedSkillSubset) == 0:
        ret = RoutingPlanParseOutcomeModel(
            isValid=False,
            validatedPlan=None,
            errorCode="FILTERED_SKILL_SELECTION_EMPTY",
            errorMessage="All selected_skill_ids were unknown after filtering.",
        )
        return ret
    normalizedRequiredToolName = str(
        in_plan.required_first_successful_tool_name or ""
    ).strip()
    if normalizedRequiredToolName != "":
        if normalizedRequiredToolName not in in_registeredToolNames:
            ret = RoutingPlanParseOutcomeModel(
                isValid=False,
                validatedPlan=None,
                errorCode="UNKNOWN_REQUIRED_TOOL_NAME",
                errorMessage=(
                    f"Unknown required_first_successful_tool_name "
                    f"'{normalizedRequiredToolName}'."
                ),
            )
            return ret
    allowToolCallsValue = bool(in_plan.allow_tool_calls)
    effectiveRequiredToolName = normalizedRequiredToolName
    if allowToolCallsValue is False and effectiveRequiredToolName != "":
        effectiveRequiredToolName = ""
    clonedPlan = RoutingPlanYamlModel(
        type="route_plan",
        selected_skill_ids=list(allowedSkillSubset),
        allow_tool_calls=allowToolCallsValue,
        required_first_successful_tool_name=effectiveRequiredToolName,
        memory_mode=in_plan.memory_mode,
    )
    ret = RoutingPlanParseOutcomeModel(
        isValid=True,
        validatedPlan=clonedPlan,
        errorCode=None,
        errorMessage=None,
    )
    return ret


def routingPlanYamlToDump(in_plan: RoutingPlanYamlModel) -> dict[str, Any]:
    ret = in_plan.model_dump(mode="python")
    return ret


def coerceRoutingYamlModel(in_payload: dict) -> RoutingPlanParseOutcomeModel:
    ret: RoutingPlanParseOutcomeModel
    try:
        routedModelValue = RoutingPlanYamlModel.model_validate(in_payload)
    except ValidationError as in_exc:
        ret = RoutingPlanParseOutcomeModel(
            isValid=False,
            validatedPlan=None,
            errorCode="INVALID_ROUTING_SCHEMA",
            errorMessage=str(in_exc),
        )
        return ret
    outputTypeRaw = str(in_payload.get("type") or "")
    if outputTypeRaw != "route_plan":
        ret = RoutingPlanParseOutcomeModel(
            isValid=False,
            validatedPlan=None,
            errorCode="INVALID_ROUTING_TYPE",
            errorMessage="Root type must equal 'route_plan'.",
        )
        return ret
    ret = RoutingPlanParseOutcomeModel(
        isValid=True,
        validatedPlan=routedModelValue,
        errorCode=None,
        errorMessage=None,
    )
    return ret
