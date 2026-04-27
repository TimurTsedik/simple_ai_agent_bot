from datetime import UTC, datetime, timedelta
from typing import Any

from app.common.structuredLogger import writeJsonlEvent
from app.config.settingsModels import LoggingSettings, ModelSettings
from app.domain.entities.llmCompletionResult import LlmCompletionResultModel
from app.domain.policies.fallbackPolicy import FallbackPolicy
from app.domain.protocols.llmClientProtocol import LlmClientProtocol
from app.models.providers.openRouterClient import OpenRouterClient, OpenRouterClientError


class LlmService(LlmClientProtocol):
    def __init__(
        self,
        in_openRouterClient: OpenRouterClient,
        in_modelSettings: ModelSettings,
        in_loggingSettings: LoggingSettings,
    ) -> None:
        self._openRouterClient = in_openRouterClient
        self._modelSettings = in_modelSettings
        self._loggingSettings = in_loggingSettings
        self._fallbackPolicy = FallbackPolicy(in_modelSettings=in_modelSettings)
        self._primarySuppressedUntil: datetime | None = None

    def complete(
        self, in_modelName: str, in_promptText: str
    ) -> LlmCompletionResultModel:
        ret: LlmCompletionResultModel
        now = datetime.now(UTC)
        isPrimarySuppressed = (
            self._primarySuppressedUntil is not None and now < self._primarySuppressedUntil
        )
        modelOrder = self._fallbackPolicy.buildModelOrder(
            in_preferredModel=in_modelName,
            in_isPrimarySuppressed=isPrimarySuppressed,
        ).modelOrder
        lastError: OpenRouterClientError | None = None
        didComplete = False
        extractedText = ""
        successModelName = in_modelName
        fallbackEvents: list[dict[str, Any]] = []
        lastModelName = in_modelName

        for modelName in modelOrder:
            lastModelName = modelName
            for _attemptIndex in range(self._modelSettings.retryCountBeforeFallback + 1):
                try:
                    rawResponse = self._openRouterClient.createChatCompletion(
                        in_modelName=modelName,
                        in_promptText=in_promptText,
                    )
                    sanitizedRawResponse = self._sanitizeRawResponseForLogs(
                        in_rawResponse=rawResponse
                    )
                    writeJsonlEvent(
                        in_loggingSettings=self._loggingSettings,
                        in_eventType="llm_raw_response",
                        in_payload={
                            "selectedModel": modelName,
                            "rawResponse": str(sanitizedRawResponse),
                        },
                    )
                    extractedText = self._extractAssistantText(in_responseData=rawResponse)
                    self._onModelSuccess(in_modelName=modelName)
                    successModelName = modelName
                    didComplete = True
                    fallbackEvents.append(
                        {
                            "event": "model_success",
                            "model": modelName,
                        }
                    )
                except OpenRouterClientError as in_exc:
                    lastError = in_exc
                    fallbackEvents.append(
                        {
                            "event": "model_error",
                            "model": modelName,
                            "errorCode": in_exc.code,
                            "errorMessage": in_exc.message,
                        }
                    )
                    writeJsonlEvent(
                        in_loggingSettings=self._loggingSettings,
                        in_eventType="llm_fallback_event",
                        in_payload={
                            "selectedModel": modelName,
                            "errorCode": in_exc.code,
                            "errorMessage": in_exc.message,
                        },
                    )
                if didComplete is True:
                    break
            if didComplete is True:
                break

        if didComplete is False:
            errorMessage = "LLM call failed after fallback attempts."
            if lastError is not None:
                errorMessage = f"{errorMessage} Last error: {lastError}"
            stopResponse = (
                '{"type":"stop","reason":"llm_unavailable","final_answer":"'
                + errorMessage
                + '"}'
            )
            extractedText = stopResponse
            successModelName = lastModelName

        ret = LlmCompletionResultModel(
            content=extractedText,
            selectedModel=successModelName,
            fallbackEvents=fallbackEvents,
        )
        return ret

    def _extractAssistantText(self, in_responseData: dict[str, Any]) -> str:
        ret: str
        choices = in_responseData.get("choices")
        if not isinstance(choices, list) or len(choices) == 0:
            raise OpenRouterClientError(
                code="INVALID_RESPONSE",
                message="choices array is missing in provider response.",
            )
        firstChoice = choices[0]
        if not isinstance(firstChoice, dict):
            raise OpenRouterClientError(
                code="INVALID_RESPONSE",
                message="choices[0] must be object.",
            )
        messageData = firstChoice.get("message")
        if not isinstance(messageData, dict):
            raise OpenRouterClientError(
                code="INVALID_RESPONSE",
                message="message object is missing.",
            )
        content = messageData.get("content")
        if not isinstance(content, str) or content.strip() == "":
            raise OpenRouterClientError(
                code="INVALID_RESPONSE",
                message="message content is missing or empty.",
            )
        ret = content
        return ret

    def _onModelSuccess(self, in_modelName: str) -> None:
        if in_modelName == self._modelSettings.primaryModel:
            self._primarySuppressedUntil = None
        else:
            self._primarySuppressedUntil = datetime.now(UTC) + timedelta(
                seconds=self._modelSettings.returnToPrimaryCooldownSeconds
            )

    def _sanitizeRawResponseForLogs(self, in_rawResponse: dict[str, Any]) -> dict[str, Any]:
        ret: dict[str, Any]
        sanitized = dict(in_rawResponse)
        choicesValue = sanitized.get("choices")
        if isinstance(choicesValue, list):
            sanitizedChoices: list[Any] = []
            for oneChoice in choicesValue:
                if isinstance(oneChoice, dict):
                    sanitizedChoice = dict(oneChoice)
                    messageValue = sanitizedChoice.get("message")
                    if isinstance(messageValue, dict):
                        sanitizedMessage = dict(messageValue)
                        sanitizedMessage.pop("reasoning", None)
                        sanitizedMessage.pop("reasoning_details", None)
                        sanitizedChoice["message"] = sanitizedMessage
                    sanitizedChoices.append(sanitizedChoice)
                else:
                    sanitizedChoices.append(oneChoice)
            sanitized["choices"] = sanitizedChoices
        ret = sanitized
        return ret
