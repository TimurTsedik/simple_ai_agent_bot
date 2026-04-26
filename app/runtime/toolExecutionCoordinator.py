from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from dataclasses import dataclass
from time import monotonic
from typing import Any

from pydantic import ValidationError

from app.common.truncation import truncateText
from app.tools.registry.toolRegistry import ToolRegistry


@dataclass(frozen=True)
class ToolResultEnvelopeModel:
    ok: bool
    tool_name: str
    data: Any
    error: dict[str, str] | None
    meta: dict[str, Any]


class ToolExecutionCoordinator:
    def __init__(self, in_toolRegistry: ToolRegistry, in_maxToolOutputChars: int) -> None:
        self._toolRegistry = in_toolRegistry
        self._maxToolOutputChars = in_maxToolOutputChars

    def execute(self, in_toolName: str, in_rawArgs: dict[str, Any]) -> ToolResultEnvelopeModel:
        ret: ToolResultEnvelopeModel
        startedAt = monotonic()
        toolDefinition = self._toolRegistry.getTool(in_toolName=in_toolName)
        if toolDefinition is None:
            ret = self._buildError(
                in_toolName=in_toolName,
                in_errorCode="NOT_FOUND",
                in_message="Tool is not found.",
                in_startedAtMonotonic=startedAt,
            )
        else:
            validatedArgs: dict[str, Any] | None
            validationError: ValidationError | None = None
            try:
                validatedModel = toolDefinition.argsModel.model_validate(in_rawArgs)
                validatedArgs = validatedModel.model_dump()
            except ValidationError as in_exc:
                validatedArgs = None
                validationError = in_exc

            if validationError is not None or validatedArgs is None:
                ret = self._buildError(
                    in_toolName=in_toolName,
                    in_errorCode="VALIDATION_ERROR",
                    in_message=str(validationError),
                    in_startedAtMonotonic=startedAt,
                )
            else:
                with ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(toolDefinition.executeCallable, validatedArgs)
                    data: Any = None
                    executionError: Exception | None = None
                    didTimeout = False
                    try:
                        data = future.result(timeout=toolDefinition.timeoutSeconds)
                    except FuturesTimeoutError:
                        didTimeout = True
                        future.cancel()
                    except Exception as in_exc:
                        executionError = in_exc

                if didTimeout is True:
                    ret = self._buildError(
                        in_toolName=in_toolName,
                        in_errorCode="TIMEOUT",
                        in_message="Tool execution timed out",
                        in_startedAtMonotonic=startedAt,
                    )
                elif executionError is not None:
                    errorCode = "EXECUTION_ERROR"
                    if isinstance(executionError, PermissionError):
                        errorCode = "ACCESS_DENIED"
                    elif isinstance(executionError, FileNotFoundError):
                        errorCode = "NOT_FOUND"
                    ret = self._buildError(
                        in_toolName=in_toolName,
                        in_errorCode=errorCode,
                        in_message=str(executionError),
                        in_startedAtMonotonic=startedAt,
                    )
                else:
                    serializedData = str(data)
                    truncatedData, isTruncated = truncateText(
                        in_text=serializedData,
                        in_maxChars=self._maxToolOutputChars,
                    )
                    durationMs = int((monotonic() - startedAt) * 1000)
                    ret = ToolResultEnvelopeModel(
                        ok=True,
                        tool_name=in_toolName,
                        data=truncatedData,
                        error=None,
                        meta={
                            "duration_ms": durationMs,
                            "truncated": isTruncated,
                        },
                    )
        return ret

    def _buildError(
        self,
        in_toolName: str,
        in_errorCode: str,
        in_message: str,
        in_startedAtMonotonic: float,
    ) -> ToolResultEnvelopeModel:
        ret: ToolResultEnvelopeModel
        durationMs = int((monotonic() - in_startedAtMonotonic) * 1000)
        ret = ToolResultEnvelopeModel(
            ok=False,
            tool_name=in_toolName,
            data=None,
            error={
                "code": in_errorCode,
                "message": in_message,
            },
            meta={"duration_ms": durationMs},
        )
        return ret
