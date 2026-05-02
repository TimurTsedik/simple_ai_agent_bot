from typing import Literal

from app.config.settingsModels import ModelSettings
from app.domain.entities.llmCompletionResult import LlmCompletionResultModel
from app.domain.protocols.llmClientProtocol import LlmClientProtocol
from app.runtime.promptBuilder import PromptBuilder
from app.runtime.routePlanParser import RoutePlanParser
from app.domain.entities.routingResolution import RoutingResolutionEntity
from app.runtime.routingPlanModels import (
    RoutingPlanYamlModel,
    routingPlanYamlToDump,
)
from app.runtime.routingPolicy import (
    hasExplicitRecurringScheduleIntent,
    resolveRequiredFirstSuccessfulToolNameFromSkills,
)
from app.skills.services.skillService import SkillService
from app.tools.registry.toolRegistry import ToolRegistry


class LlmRoutingPlanResolver:
    def __init__(
        self,
        in_llmClient: LlmClientProtocol,
        in_promptBuilder: PromptBuilder,
        in_routePlanParser: RoutePlanParser,
        in_skillService: SkillService,
        in_toolRegistry: ToolRegistry,
        in_modelSettings: ModelSettings,
    ) -> None:
        self._llmClient = in_llmClient
        self._promptBuilder = in_promptBuilder
        self._routePlanParser = in_routePlanParser
        self._skillService = in_skillService
        self._toolRegistry = in_toolRegistry
        self._modelSettings = in_modelSettings

    def resolve(self, in_userMessage: str) -> RoutingResolutionEntity:
        ret: RoutingResolutionEntity
        knownSkillDefs = self._skillService.loadAllSkills()
        knownSkillIdsValue = {
            skillItem.skillId for skillItem in knownSkillDefs
        }
        toolNameSetValue = {
            definitionItem.name for definitionItem in self._toolRegistry.listTools()
        }
        toolCatalogLinesValue = sorted(toolNameSetValue)
        routingToolsBlockValue = (
            ", ".join(f"`{nameItem}`" for nameItem in toolCatalogLinesValue)
            if len(toolCatalogLinesValue) > 0
            else "(none)"
        )
        skillsRoutingCatalogValue = self._skillService.buildSkillsRoutingCatalogSummary()
        routingPromptTextValue = self._promptBuilder.buildRoutingPrompt(
            in_userMessage=in_userMessage,
            in_registeredToolBulletList=routingToolsBlockValue,
            in_skillsCatalogBlock=skillsRoutingCatalogValue,
        )
        routingLlmOutcome = self._llmClient.complete(
            in_modelName=self._modelSettings.primaryModel,
            in_promptText=routingPromptTextValue,
            in_timeoutSeconds=int(self._modelSettings.requestTimeoutSeconds),
            in_useJsonObjectResponseFormat=False,
        )
        parseOutcomeModel = self._routePlanParser.parseAndValidateCatalog(
            in_rawText=routingLlmOutcome.content,
            in_knownSkillIds=knownSkillIdsValue,
            in_registeredToolNames=toolNameSetValue,
        )
        diagnosticsBuffer: list[dict[str, str | None]] = []

        if routingLlmOutcome.content.strip() == "":
            diagnosticsBuffer.append({"kind": "router_llm_empty", "detail": None})

        parseErrorCodeValue: str | None = parseOutcomeModel.errorCode
        parseErrorMessageValue: str | None = parseOutcomeModel.errorMessage

        if parseOutcomeModel.isValid is False or parseOutcomeModel.validatedPlan is None:
            diagnosticsBuffer.append(
                {
                    "kind": "routing_parse_validation_failed",
                    "detail": parseErrorMessageValue,
                }
            )
            diagnosticsBuffer.extend(
                self._adaptLlmDiagnostics(in_completionResult=routingLlmOutcome)
            )
            fallbackReasonTextValue = parseErrorMessageValue or parseErrorCodeValue
            ret = self._buildFallbackRoutingResolution(
                in_userMessage=in_userMessage,
                in_routingPromptSnapshot=routingPromptTextValue,
                in_routingRawModelResponse=routingLlmOutcome.content,
                in_parseErrorCode=parseErrorCodeValue,
                in_parseErrorMessage=parseErrorMessageValue,
                in_fallbackReasonResolved=fallbackReasonTextValue,
                in_diagnosticsExtras=tuple(diagnosticsBuffer),
            )
            return ret

        normalizedPlanSnapshot = parseOutcomeModel.validatedPlan
        skillIdsAdjustedValue = self._prependDefaultAssistantIfAbsent(
            in_selectedSkillIds=normalizedPlanSnapshot.selected_skill_ids,
        )
        requiredToolGuardedValue = self._applyGuardsToLlmRequiredTool(
            in_selectedSkillIds=skillIdsAdjustedValue,
            in_candidateRequiredToolName=(
                normalizedPlanSnapshot.required_first_successful_tool_name
            ),
            in_allowToolCalls=normalizedPlanSnapshot.allow_tool_calls,
        )
        policyFirstToolValue = resolveRequiredFirstSuccessfulToolNameFromSkills(
            in_selectedSkillIds=skillIdsAdjustedValue,
            in_userMessage=in_userMessage,
        )
        forceScheduleRecurringFirstTool = (
            "schedule_recurring_agent_run" in set(skillIdsAdjustedValue)
            and hasExplicitRecurringScheduleIntent(in_userMessage=in_userMessage) is True
        )
        if (
            policyFirstToolValue == "schedule_recurring_agent_run"
            or forceScheduleRecurringFirstTool is True
        ):
            requiredToolGuardedValue = "schedule_recurring_agent_run"
        sanitizedPlanApplied = RoutingPlanYamlModel(
            type="route_plan",
            selected_skill_ids=skillIdsAdjustedValue,
            allow_tool_calls=normalizedPlanSnapshot.allow_tool_calls,
            required_first_successful_tool_name=requiredToolGuardedValue,
            memory_mode=normalizedPlanSnapshot.memory_mode,
        )
        didHeuristicOverrideFlag = False
        if sanitizedPlanApplied.allow_tool_calls is False:
            sanitizedPlanApplied = RoutingPlanYamlModel(
                type="route_plan",
                selected_skill_ids=list(sanitizedPlanApplied.selected_skill_ids),
                allow_tool_calls=False,
                required_first_successful_tool_name="",
                memory_mode=sanitizedPlanApplied.memory_mode,
            )
            sanitizedPlanApplied, didHeuristicOverrideFlag = (
                self._applyHeuristicOverrideIfLlmDisallowedTools(
                    in_userMessage=in_userMessage,
                    in_plan=sanitizedPlanApplied,
                )
            )
        diagnosticsBuffer.extend(
            self._adaptLlmDiagnostics(in_completionResult=routingLlmOutcome)
        )
        if didHeuristicOverrideFlag is True:
            diagnosticsBuffer.append(
                {
                    "kind": "routing_llm_heuristic_override",
                    "detail": (
                        "allow_tool_calls forced true (rule-based tool-needed heuristics "
                        "overrode router LLM)"
                    ),
                }
            )
        routingDiagnosticsMerged = tuple(diagnosticsBuffer)
        selectionEnvelope = self._skillService.buildSkillsSelectionForSortedSkillIds(
            in_selectedSkillIds=list(sanitizedPlanApplied.selected_skill_ids),
        )
        effectiveRequiredFinalValue = ""
        if sanitizedPlanApplied.allow_tool_calls is True:
            effectiveRequiredFinalValue = str(
                sanitizedPlanApplied.required_first_successful_tool_name or ""
            ).strip()
        ret = RoutingResolutionEntity(
            skillsBlock=selectionEnvelope.skillsBlock,
            selectedSkillIds=list(selectionEnvelope.selectedSkillIds),
            allowToolCalls=bool(sanitizedPlanApplied.allow_tool_calls),
            requiredFirstSuccessfulToolName=effectiveRequiredFinalValue,
            memoryMode=sanitizedPlanApplied.memory_mode,
            routingSource="llm",
            routingPlanDump=routingPlanYamlToDump(in_plan=sanitizedPlanApplied),
            routingPromptSnapshot=routingPromptTextValue,
            routingRawModelResponse=routingLlmOutcome.content,
            routingParseErrorCode=None,
            routingParseErrorMessage=None,
            routingFallbackReason=None,
            routingDiagnostics=routingDiagnosticsMerged,
        )
        return ret

    def _applyHeuristicOverrideIfLlmDisallowedTools(
        self,
        in_userMessage: str,
        in_plan: RoutingPlanYamlModel,
    ) -> tuple[RoutingPlanYamlModel, bool]:
        """When the router LLM sets allow_tool_calls=false but the message clearly needs tools."""

        ret: tuple[RoutingPlanYamlModel, bool]
        if in_plan.allow_tool_calls is True:
            ret = (in_plan, False)
            return ret
        if self._skillService.isToolLikelyRequired(in_userMessage=in_userMessage) is False:
            ret = (in_plan, False)
            return ret
        ruleSelectionEnvelopeValue = self._skillService.buildSkillsSelection(
            in_userMessage=in_userMessage,
        )
        skillIdsPrependedValue = self._prependDefaultAssistantIfAbsent(
            in_selectedSkillIds=list(ruleSelectionEnvelopeValue.selectedSkillIds),
        )
        selectionEnvelopeAdjustedValue = (
            self._skillService.buildSkillsSelectionForSortedSkillIds(
                in_selectedSkillIds=skillIdsPrependedValue,
            )
        )
        requiredToolRawValue = resolveRequiredFirstSuccessfulToolNameFromSkills(
            in_selectedSkillIds=list(selectionEnvelopeAdjustedValue.selectedSkillIds),
            in_userMessage=in_userMessage,
        )
        requiredToolGuardedValue = self._applyGuardsToLlmRequiredTool(
            in_selectedSkillIds=list(selectionEnvelopeAdjustedValue.selectedSkillIds),
            in_candidateRequiredToolName=requiredToolRawValue,
            in_allowToolCalls=True,
        )
        skillIdsSetForMemoryValue = set(selectionEnvelopeAdjustedValue.selectedSkillIds)
        memoryModeResolvedValue: Literal["full", "long_term_only"]
        if (
            "compose_digest" in skillIdsSetForMemoryValue
            and "read_and_analyze_email" in skillIdsSetForMemoryValue
        ):
            memoryModeResolvedValue = "long_term_only"
        else:
            memoryModeResolvedValue = "full"
        correctedPlanValue = RoutingPlanYamlModel(
            type="route_plan",
            selected_skill_ids=list(selectionEnvelopeAdjustedValue.selectedSkillIds),
            allow_tool_calls=True,
            required_first_successful_tool_name=requiredToolGuardedValue,
            memory_mode=memoryModeResolvedValue,
        )
        ret = (correctedPlanValue, True)
        return ret

    def _applyGuardsToLlmRequiredTool(
        self,
        in_selectedSkillIds: list[str],
        in_candidateRequiredToolName: str,
        in_allowToolCalls: bool,
    ) -> str:
        ret: str
        if in_allowToolCalls is False:
            ret = ""
            return ret
        selectedSkillIdsSetValue = set(in_selectedSkillIds)
        feedbackSkillDetected = (
            "telegram_digest_feedback" in selectedSkillIdsSetValue
            or "email_preference_feedback" in selectedSkillIdsSetValue
        )
        if feedbackSkillDetected is True:
            ret = ""
            return ret
        ret = str(in_candidateRequiredToolName or "").strip()
        return ret

    def _prependDefaultAssistantIfAbsent(
        self,
        in_selectedSkillIds: list[str],
    ) -> list[str]:
        ret: list[str]
        trimmedListValue = []
        duplicateGuardValue = set()
        for skillRaw in list(in_selectedSkillIds or []):
            skillNormalized = str(skillRaw or "").strip()
            if skillNormalized == "":
                continue
            if skillNormalized not in duplicateGuardValue:
                trimmedListValue.append(skillNormalized)
                duplicateGuardValue.add(skillNormalized)
        if "default_assistant" not in trimmedListValue:
            ret = ["default_assistant"] + trimmedListValue
        else:
            ret = trimmedListValue
        return ret

    def _adaptLlmDiagnostics(
        self,
        in_completionResult: LlmCompletionResultModel,
    ) -> list[dict[str, str | None]]:
        ret: list[dict[str, str | None]]
        bufferedItems: list[dict[str, str | None]] = []
        fallbackEventsParsed = getattr(
            in_completionResult,
            "fallbackEvents",
            (),
        )
        if isinstance(fallbackEventsParsed, (list, tuple)) is False:
            ret = bufferedItems
            return ret
        for eventSlice in fallbackEventsParsed:
            if isinstance(eventSlice, dict) is False:
                continue
            codeText = (
                str(eventSlice.get("errorCode"))
                if eventSlice.get("errorCode") is not None
                else ""
            ).strip()
            messageTextValue = (
                str(eventSlice.get("errorMessage"))
                if eventSlice.get("errorMessage") is not None
                else ""
            ).strip()
            bufferedItems.append(
                {
                    "kind": (
                        str(eventSlice.get("event"))
                        if eventSlice.get("event") is not None
                        else "llm_fallback"
                    ),
                    "detail": f"{codeText}: {messageTextValue}".strip()
                    if len(codeText) > 0 or len(messageTextValue) > 0
                    else None,
                },
            )
        ret = bufferedItems
        return ret

    def _buildFallbackRoutingResolution(
        self,
        in_userMessage: str,
        in_routingPromptSnapshot: str,
        in_routingRawModelResponse: str | None,
        in_parseErrorCode: str | None,
        in_parseErrorMessage: str | None,
        in_fallbackReasonResolved: str | None,
        in_diagnosticsExtras: tuple[dict[str, str | None], ...],
    ) -> RoutingResolutionEntity:
        ret: RoutingResolutionEntity
        selectionFallbackValue = (
            self._skillService.buildSkillsSelection(
                in_userMessage=in_userMessage,
            )
        )
        enforcedRequiredToolFallback = resolveRequiredFirstSuccessfulToolNameFromSkills(
            in_selectedSkillIds=list(selectionFallbackValue.selectedSkillIds),
            in_userMessage=in_userMessage,
        )
        allowToolsFallbackBool = (
            self._skillService.isToolLikelyRequired(
                in_userMessage=in_userMessage,
            )
        )
        memoryModeFallbackComputed: Literal["full", "long_term_only"]
        fallbackSkillSetParsed = set(selectionFallbackValue.selectedSkillIds)
        if (
            "compose_digest" in fallbackSkillSetParsed
            and "read_and_analyze_email" in fallbackSkillSetParsed
        ):
            memoryModeFallbackComputed = "long_term_only"
        else:
            memoryModeFallbackComputed = "full"
        requiredToolAfterAllowFlag = enforcedRequiredToolFallback
        if allowToolsFallbackBool is False:
            requiredToolAfterAllowFlag = ""
        fallbackYamlPlanValue = RoutingPlanYamlModel(
            type="route_plan",
            selected_skill_ids=list(selectionFallbackValue.selectedSkillIds),
            allow_tool_calls=allowToolsFallbackBool,
            required_first_successful_tool_name=requiredToolAfterAllowFlag,
            memory_mode=memoryModeFallbackComputed,
        )
        bufferDiagnosticsMerged: list[dict[str, str | None]]
        bufferDiagnosticsMerged = list(in_diagnosticsExtras)
        fallbackDetailText = (
            str(in_fallbackReasonResolved)
            if in_fallbackReasonResolved is not None
            else ""
        )
        bufferDiagnosticsMerged.append({"kind": "routing_fallback_triggered", "detail": fallbackDetailText})

        fallbackSelectionAdjusted = (
            self._skillService.buildSkillsSelectionForSortedSkillIds(
                in_selectedSkillIds=(
                    self._prependDefaultAssistantIfAbsent(
                        in_selectedSkillIds=fallbackYamlPlanValue.selected_skill_ids,
                    )
                ),
            )
        )
        finalizedFallbackPlan = RoutingPlanYamlModel(
            type="route_plan",
            selected_skill_ids=list(fallbackSelectionAdjusted.selectedSkillIds),
            allow_tool_calls=fallbackYamlPlanValue.allow_tool_calls,
            required_first_successful_tool_name=(
                fallbackYamlPlanValue.required_first_successful_tool_name
            ),
            memory_mode=fallbackYamlPlanValue.memory_mode,
        )
        ret = RoutingResolutionEntity(
            skillsBlock=fallbackSelectionAdjusted.skillsBlock,
            selectedSkillIds=list(fallbackSelectionAdjusted.selectedSkillIds),
            allowToolCalls=bool(finalizedFallbackPlan.allow_tool_calls),
            requiredFirstSuccessfulToolName=(
                finalizedFallbackPlan.required_first_successful_tool_name
            ),
            memoryMode=finalizedFallbackPlan.memory_mode,
            routingSource="fallback",
            routingPlanDump=routingPlanYamlToDump(in_plan=finalizedFallbackPlan),
            routingPromptSnapshot=in_routingPromptSnapshot,
            routingRawModelResponse=in_routingRawModelResponse,
            routingParseErrorCode=in_parseErrorCode,
            routingParseErrorMessage=in_parseErrorMessage,
            routingFallbackReason=(
                fallbackDetailText
                if fallbackDetailText != ""
                else in_parseErrorMessage
            ),
            routingDiagnostics=tuple(bufferDiagnosticsMerged),
        )
        return ret
