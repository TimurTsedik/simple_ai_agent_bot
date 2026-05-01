import json
from typing import Any

import yaml

from app.runtime.llmStructuredTextNormalizer import normalizeStructuredLlmText
from app.runtime.routingPlanModels import (
    RoutingPlanParseOutcomeModel,
    coerceRoutingYamlModel,
    validateAgainstCatalog,
)


class RoutePlanParser:
    def parseAndValidateCatalog(
        self,
        in_rawText: str,
        in_knownSkillIds: set[str],
        in_registeredToolNames: set[str],
    ) -> RoutingPlanParseOutcomeModel:
        ret: RoutingPlanParseOutcomeModel
        normalizedText = normalizeStructuredLlmText(in_rawText=in_rawText)
        decodedValue: Any = None
        yamlErrorHolder: yaml.YAMLError | None = None
        jsonErrorHolder: json.JSONDecodeError | None = None
        try:
            decodedValue = yaml.safe_load(normalizedText)
        except yaml.YAMLError as in_exc:
            yamlErrorHolder = in_exc
            decodedValue = None

        if isinstance(decodedValue, dict) is False:
            try:
                decodedValue = json.loads(normalizedText)
                jsonErrorHolder = None
            except json.JSONDecodeError as in_exc:
                jsonErrorHolder = in_exc

        if decodedValue is None:
            detailParts: list[str] = []
            if yamlErrorHolder is not None:
                detailParts.append(f"YAML: {yamlErrorHolder}")
            if jsonErrorHolder is not None:
                detailParts.append(f"JSON: {jsonErrorHolder}")
            detailTextValue = "; ".join(detailParts) if len(detailParts) > 0 else "Empty."
            codeValue = "INVALID_ROUTING_FORMAT"
            ret = RoutingPlanParseOutcomeModel(
                isValid=False,
                validatedPlan=None,
                errorCode=codeValue,
                errorMessage=detailTextValue,
            )
            return ret
        if isinstance(decodedValue, dict) is False:
            ret = RoutingPlanParseOutcomeModel(
                isValid=False,
                validatedPlan=None,
                errorCode="INVALID_ROUTING_SHAPE",
                errorMessage="Route plan root must be a mapping.",
            )
            return ret
        coerceOutcome = coerceRoutingYamlModel(in_payload=decodedValue)
        if coerceOutcome.isValid is False or coerceOutcome.validatedPlan is None:
            ret = coerceOutcome
            return ret
        ret = validateAgainstCatalog(
            in_plan=coerceOutcome.validatedPlan,
            in_knownSkillIds=in_knownSkillIds,
            in_registeredToolNames=in_registeredToolNames,
        )
        return ret
