import json
from dataclasses import dataclass
from typing import Any, Literal

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


class StopOutputModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["stop"]
    reason: str
    final_answer: str


@dataclass(frozen=True)
class ParsedOutputModel:
    outputType: str
    reason: str
    action: str | None
    args: dict[str, Any] | None
    finalAnswer: str | None


@dataclass(frozen=True)
class ParseResultModel:
    isValid: bool
    parsedOutput: ParsedOutputModel | None
    errorCode: str | None
    errorMessage: str | None


class OutputParser:
    def parse(self, in_rawText: str) -> ParseResultModel:
        ret: ParseResultModel
        decodedValue: Any = None
        decodeError: json.JSONDecodeError | None = None
        try:
            decodedValue = json.loads(in_rawText)
        except json.JSONDecodeError as in_exc:
            decodeError = in_exc

        if decodeError is not None:
            ret = ParseResultModel(
                isValid=False,
                parsedOutput=None,
                errorCode="INVALID_JSON",
                errorMessage=str(decodeError),
            )
        elif not isinstance(decodedValue, dict):
            ret = ParseResultModel(
                isValid=False,
                parsedOutput=None,
                errorCode="INVALID_SCHEMA",
                errorMessage="Model output root must be an object.",
            )
        else:
            outputType = decodedValue.get("type")
            if outputType == "tool_call":
                ret = self._parseToolCall(in_payload=decodedValue)
            elif outputType == "final":
                ret = self._parseFinal(in_payload=decodedValue)
            elif outputType == "stop":
                ret = self._parseStop(in_payload=decodedValue)
            else:
                ret = ParseResultModel(
                    isValid=False,
                    parsedOutput=None,
                    errorCode="INVALID_SCHEMA",
                    errorMessage="Unknown model output type.",
                )
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
