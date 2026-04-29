from dataclasses import dataclass
from typing import Any

import requests


@dataclass(frozen=True)
class OpenRouterClientError(Exception):
    code: str
    message: str

    def __str__(self) -> str:
        ret = f"{self.code}: {self.message}"
        return ret


class OpenRouterClient:
    def __init__(
        self,
        in_baseUrl: str,
        in_apiKey: str,
        in_timeoutSeconds: int,
    ) -> None:
        self._baseUrl = in_baseUrl.rstrip("/")
        self._apiKey = in_apiKey
        self._timeoutSeconds = in_timeoutSeconds

    def createChatCompletion(
        self,
        in_modelName: str,
        in_promptText: str,
        *,
        in_timeoutSeconds: int | None = None,
        in_useJsonObjectResponseFormat: bool = False,
    ) -> dict[str, Any]:
        ret: dict[str, Any]
        url = f"{self._baseUrl}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._apiKey}",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "model": in_modelName,
            "messages": [{"role": "user", "content": in_promptText}],
            "temperature": 0,
        }
        if in_useJsonObjectResponseFormat is True:
            payload["response_format"] = {"type": "json_object"}
        timeoutValue = self._timeoutSeconds if in_timeoutSeconds is None else in_timeoutSeconds
        try:
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=timeoutValue,
            )
        except requests.Timeout as in_exc:
            raise OpenRouterClientError(
                code="TIMEOUT",
                message="OpenRouter request timeout.",
            ) from in_exc
        except requests.RequestException as in_exc:
            raise OpenRouterClientError(
                code="UNAVAILABLE",
                message=f"OpenRouter request failed: {in_exc}",
            ) from in_exc

        if response.status_code == 429:
            raise OpenRouterClientError(
                code="RATE_LIMIT",
                message="OpenRouter rate limit reached.",
            )
        if response.status_code >= 500:
            raise OpenRouterClientError(
                code="PROVIDER_ERROR",
                message=f"OpenRouter server error: {response.status_code}",
            )
        if response.status_code >= 400:
            raise OpenRouterClientError(
                code="UNAVAILABLE",
                message=f"OpenRouter client error: {response.status_code}",
            )
        try:
            parsedPayload = response.json()
        except ValueError as in_exc:
            raise OpenRouterClientError(
                code="INVALID_RESPONSE",
                message="Provider returned malformed JSON payload.",
            ) from in_exc
        if isinstance(parsedPayload, dict):
            ret = parsedPayload
        else:
            raise OpenRouterClientError(
                code="INVALID_RESPONSE",
                message="Provider payload root is not object.",
            )
        return ret
