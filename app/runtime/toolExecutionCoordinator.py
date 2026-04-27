from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from dataclasses import dataclass
import json
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
                    truncatedData, isTruncated = self._serializeToolData(
                        in_toolName=in_toolName,
                        in_data=data,
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

    def _serializeToolData(self, in_toolName: str, in_data: Any, in_maxChars: int) -> tuple[str, bool]:
        ret: tuple[str, bool]
        if isinstance(in_data, (dict, list)):
            serializedData = json.dumps(in_data, ensure_ascii=False)
            if len(serializedData) <= in_maxChars:
                ret = (serializedData, False)
            else:
                previewObj = self._buildJsonPreview(in_toolName=in_toolName, in_data=in_data)
                previewText = json.dumps(previewObj, ensure_ascii=False)
                truncatedPreview, _isTruncated = truncateText(
                    in_text=previewText,
                    in_maxChars=in_maxChars,
                )
                ret = (truncatedPreview, True)
        else:
            serializedData = str(in_data)
            truncatedText, isTruncated = truncateText(
                in_text=serializedData,
                in_maxChars=in_maxChars,
            )
            ret = (truncatedText, isTruncated)
        return ret

    def _buildJsonPreview(self, in_toolName: str, in_data: Any) -> dict[str, Any]:
        ret: dict[str, Any]
        payload: dict[str, Any] = {
            "_preview": True,
            "_tool_name": in_toolName,
        }
        if not isinstance(in_data, dict):
            ret = {"_preview": True, "_tool_name": in_toolName, "type": type(in_data).__name__}
            return ret

        if in_toolName == "web_search":
            results = in_data.get("results", [])
            fetchedPages = in_data.get("fetchedPages", [])
            blockedUrls = in_data.get("blockedUrls", [])
            fetchErrors = in_data.get("fetchErrors", [])
            sampleResultUrls: list[str] = []
            if isinstance(results, list):
                for item in results[:5]:
                    if isinstance(item, dict) and isinstance(item.get("url"), str):
                        sampleResultUrls.append(item["url"])
            sampleFetchedUrls: list[str] = []
            if isinstance(fetchedPages, list):
                for item in fetchedPages[:3]:
                    if isinstance(item, dict) and isinstance(item.get("url"), str):
                        sampleFetchedUrls.append(item["url"])
            payload["query"] = in_data.get("query")
            payload["searchProvider"] = in_data.get("searchProvider")
            payload["resultsCount"] = len(results) if isinstance(results, list) else None
            payload["fetchedPagesCount"] = (
                len(fetchedPages) if isinstance(fetchedPages, list) else None
            )
            payload["blockedUrlsCount"] = (
                len(blockedUrls) if isinstance(blockedUrls, list) else None
            )
            payload["fetchErrorsCount"] = (
                len(fetchErrors) if isinstance(fetchErrors, list) else None
            )
            payload["sampleResultUrls"] = sampleResultUrls
            payload["sampleFetchedUrls"] = sampleFetchedUrls
            ret = payload
            return ret

        if in_toolName == "digest_telegram_news":
            items = in_data.get("items", [])
            sampleLinks: list[str] = []
            previewItems: list[dict[str, Any]] = []
            if isinstance(items, list):
                for oneItem in items[:3]:
                    if isinstance(oneItem, dict):
                        linkValue = oneItem.get("link")
                        if isinstance(linkValue, str):
                            sampleLinks.append(linkValue)
                        previewItems.append(
                            {
                                "channel": oneItem.get("channel"),
                                "dateUnixTs": oneItem.get("dateUnixTs"),
                                "summary": str(oneItem.get("summary", ""))[:240],
                                "link": linkValue,
                            }
                        )
            payload["count"] = in_data.get("count")
            payload["sinceUnixTsUsed"] = in_data.get("sinceUnixTsUsed")
            payload["itemsPreview"] = previewItems
            payload["sampleLinks"] = sampleLinks[:5]
            channelErrors = in_data.get("channelErrors", {})
            payload["channelErrorsCount"] = (
                len(channelErrors) if isinstance(channelErrors, dict) else None
            )
            ret = payload
            return ret

        ret = payload
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
