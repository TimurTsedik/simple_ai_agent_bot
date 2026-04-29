import json
import re
from dataclasses import dataclass
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError


class ToolCallOutputModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["tool_call"]
    reason: str
    action: str
    args: dict[str, Any]


class FinalOutputModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["final"]
    reason: str
    final_answer: str
    memory_candidates: list[str] | None = None


class StopOutputModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["stop"]
    reason: str
    final_answer: str
    memory_candidates: list[str] | None = None


class LegacyToolCallOutputModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tool: str
    args: dict[str, Any]


@dataclass(frozen=True)
class ParsedOutputModel:
    outputType: str
    reason: str
    action: str | None
    args: dict[str, Any] | None
    finalAnswer: str | None
    memoryCandidates: list[str] | None


@dataclass(frozen=True)
class ParseResultModel:
    isValid: bool
    parsedOutput: ParsedOutputModel | None
    errorCode: str | None
    errorMessage: str | None


class OutputParser:
    def parse(self, in_rawText: str) -> ParseResultModel:
        ret: ParseResultModel
        normalizedText = self._normalizeRawText(in_rawText=in_rawText)
        decodedValue: Any = None
        yamlError: yaml.YAMLError | None = None
        jsonError: json.JSONDecodeError | None = None
        try:
            decodedValue = yaml.safe_load(normalizedText)
        except yaml.YAMLError as in_exc:
            yamlError = in_exc
            decodedValue = None

        if isinstance(decodedValue, dict) is False:
            try:
                decodedValue = json.loads(normalizedText)
                jsonError = None
            except json.JSONDecodeError as in_exc:
                jsonError = in_exc

        if decodedValue is None:
            detailParts: list[str] = []
            if yamlError is not None:
                detailParts.append(f"YAML: {yamlError}")
            if jsonError is not None:
                detailParts.append(f"JSON: {jsonError}")
            detailText = "; ".join(detailParts) if len(detailParts) > 0 else "Empty document."
            errorCode = "INVALID_FORMAT"
            if yamlError is not None and jsonError is not None:
                errorCode = "INVALID_FORMAT"
            elif yamlError is not None and jsonError is None:
                errorCode = "INVALID_YAML"
            elif yamlError is None and jsonError is not None:
                errorCode = "INVALID_JSON"
            ret = ParseResultModel(
                isValid=False,
                parsedOutput=None,
                errorCode=errorCode,
                errorMessage=detailText,
            )
        elif isinstance(decodedValue, dict) is False:
            ret = ParseResultModel(
                isValid=False,
                parsedOutput=None,
                errorCode="INVALID_SCHEMA",
                errorMessage="Model output root must be a mapping (YAML object / JSON object).",
            )
        else:
            outputType = decodedValue.get("type")
            if outputType == "tool_call":
                ret = self._parseToolCall(in_payload=decodedValue)
            elif outputType == "final":
                ret = self._parseFinal(in_payload=decodedValue)
            elif outputType == "stop":
                ret = self._parseStop(in_payload=decodedValue)
            elif "tool" in decodedValue and "args" in decodedValue:
                ret = self._parseLegacyToolCall(in_payload=decodedValue)
            else:
                ret = ParseResultModel(
                    isValid=False,
                    parsedOutput=None,
                    errorCode="INVALID_SCHEMA",
                    errorMessage="Unknown model output type.",
                )
        return ret

    def _normalizeRawText(self, in_rawText: str) -> str:
        ret: str
        trimmed = in_rawText.strip()
        fencePattern = re.compile(
            r"^\s*```(?:yaml|yml|json)?\s*\r?\n(.*?)\r?\n```\s*$",
            re.DOTALL | re.IGNORECASE,
        )
        match = fencePattern.match(trimmed)
        if match is not None:
            ret = match.group(1).strip()
        else:
            ret = trimmed
        return ret

    def _parseToolCall(self, in_payload: dict[str, Any]) -> ParseResultModel:
        ret: ParseResultModel
        try:
            validated = ToolCallOutputModel.model_validate(in_payload)
            parsed = ParsedOutputModel(
                outputType="tool_call",
                reason=validated.reason,
                action=validated.action,
                args=validated.args,
                finalAnswer=None,
                memoryCandidates=None,
            )
            ret = ParseResultModel(
                isValid=True,
                parsedOutput=parsed,
                errorCode=None,
                errorMessage=None,
            )
        except ValidationError as in_exc:
            ret = ParseResultModel(
                isValid=False,
                parsedOutput=None,
                errorCode="INVALID_SCHEMA",
                errorMessage=str(in_exc),
            )
        return ret

    def _parseLegacyToolCall(self, in_payload: dict[str, Any]) -> ParseResultModel:
        ret: ParseResultModel
        try:
            validated = LegacyToolCallOutputModel.model_validate(in_payload)
            parsed = ParsedOutputModel(
                outputType="tool_call",
                reason="legacy_tool_call",
                action=validated.tool,
                args=validated.args,
                finalAnswer=None,
                memoryCandidates=None,
            )
            ret = ParseResultModel(
                isValid=True,
                parsedOutput=parsed,
                errorCode=None,
                errorMessage=None,
            )
        except ValidationError as in_exc:
            ret = ParseResultModel(
                isValid=False,
                parsedOutput=None,
                errorCode="INVALID_SCHEMA",
                errorMessage=str(in_exc),
            )
        return ret

    def _parseFinal(self, in_payload: dict[str, Any]) -> ParseResultModel:
        ret: ParseResultModel
        try:
            validated = FinalOutputModel.model_validate(in_payload)
            parsed = ParsedOutputModel(
                outputType="final",
                reason=validated.reason,
                action=None,
                args=None,
                finalAnswer=validated.final_answer,
                memoryCandidates=validated.memory_candidates,
            )
            ret = ParseResultModel(
                isValid=True,
                parsedOutput=parsed,
                errorCode=None,
                errorMessage=None,
            )
        except ValidationError as in_exc:
            ret = ParseResultModel(
                isValid=False,
                parsedOutput=None,
                errorCode="INVALID_SCHEMA",
                errorMessage=str(in_exc),
            )
        return ret

    def _parseStop(self, in_payload: dict[str, Any]) -> ParseResultModel:
        ret: ParseResultModel
        try:
            validated = StopOutputModel.model_validate(in_payload)
            parsed = ParsedOutputModel(
                outputType="stop",
                reason=validated.reason,
                action=None,
                args=None,
                finalAnswer=validated.final_answer,
                memoryCandidates=validated.memory_candidates,
            )
            ret = ParseResultModel(
                isValid=True,
                parsedOutput=parsed,
                errorCode=None,
                errorMessage=None,
            )
        except ValidationError as in_exc:
            ret = ParseResultModel(
                isValid=False,
                parsedOutput=None,
                errorCode="INVALID_SCHEMA",
                errorMessage=str(in_exc),
            )
        return ret
