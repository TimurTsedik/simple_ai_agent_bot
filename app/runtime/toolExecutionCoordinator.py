from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from dataclasses import dataclass
import json
import os
import weakref
from time import monotonic
from typing import Any

from pydantic import ValidationError

from app.common.truncation import truncateText
from app.tools.registry.toolRegistry import ToolRegistry


def _shutdownExecutorPoolSilently(in_executor: ThreadPoolExecutor) -> None:
    try:
        in_executor.shutdown(wait=False)
    except RuntimeError:
        pass


@dataclass(frozen=True)
class ToolResultEnvelopeModel:
    ok: bool
    tool_name: str
    data: Any
    error: dict[str, str] | None
    meta: dict[str, Any]


class ToolExecutionCoordinator:
    def __init__(
        self,
        in_toolRegistry: ToolRegistry,
        in_maxToolOutputChars: int,
        in_executorMaxWorkers: int | None = None,
    ) -> None:
        self._toolRegistry = in_toolRegistry
        self._maxToolOutputChars = in_maxToolOutputChars
        maxWorkers = in_executorMaxWorkers
        if maxWorkers is None:
            maxWorkers = max(4, (os.cpu_count() or 1) * 2)
        maxWorkers = max(1, int(maxWorkers))
        self._executor = ThreadPoolExecutor(
            max_workers=maxWorkers,
            thread_name_prefix="tool_exec",
        )
        self._executorShutdown = False
        weakref.finalize(self, _shutdownExecutorPoolSilently, self._executor)

    def execute(
        self,
        in_toolName: str,
        in_rawArgs: dict[str, Any],
        in_memoryPrincipalId: str,
    ) -> ToolResultEnvelopeModel:
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
                future = self._executor.submit(
                    self._invokeToolCallableWithPrincipal,
                    toolDefinition.executeCallable,
                    validatedArgs,
                    in_memoryPrincipalId,
                )
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

    @staticmethod
    def _invokeToolCallableWithPrincipal(
        in_executeCallable: Any,
        in_validatedArgs: dict[str, Any],
        in_memoryPrincipalId: str,
    ) -> Any:
        ret: Any
        ret = in_executeCallable(
            in_validatedArgs,
            in_memoryPrincipalId=in_memoryPrincipalId,
        )
        return ret

    def shutdown(self, in_wait: bool = True) -> None:
        if self._executorShutdown is True:
            return
        self._executorShutdown = True
        try:
            self._executor.shutdown(wait=in_wait)
        except RuntimeError:
            pass

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

        if in_toolName == "user_topic_telegram_digest":
            payload["status"] = in_data.get("status")
            payload["topicKey"] = in_data.get("topicKey")
            payload["hint"] = in_data.get("hint")
            payload["message"] = in_data.get("message")
            items = in_data.get("items", [])
            if isinstance(items, list):
                payload["itemsPreviewCount"] = len(items)
                sampleLinksUserTopic: list[str] = []
                for oneItem in items[:3]:
                    if isinstance(oneItem, dict) and isinstance(oneItem.get("link"), str):
                        sampleLinksUserTopic.append(oneItem["link"])
                payload["sampleLinks"] = sampleLinksUserTopic
            channelErrors = in_data.get("channelErrors", {})
            payload["channelErrorsCount"] = (
                len(channelErrors) if isinstance(channelErrors, dict) else None
            )
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
            diagnostics = in_data.get("diagnostics", {})
            if isinstance(diagnostics, dict):
                payload["diagnostics"] = {
                    "totalParsedPosts": diagnostics.get("totalParsedPosts"),
                    "totalDedupedPosts": diagnostics.get("totalDedupedPosts"),
                    "filteredOutByTime": diagnostics.get("filteredOutByTime"),
                    "filteredOutByKeywords": diagnostics.get("filteredOutByKeywords"),
                    "fetchErrorChannelsCount": diagnostics.get("fetchErrorChannelsCount"),
                    "returnedItemsCount": diagnostics.get("returnedItemsCount"),
                    "keywordsAppliedCount": diagnostics.get("keywordsAppliedCount"),
                }
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
