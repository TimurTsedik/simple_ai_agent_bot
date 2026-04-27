import json
from pathlib import Path
from tempfile import TemporaryDirectory

from app.config.settingsModels import LoggingSettings, ModelSettings
from app.domain.entities.llmCompletionResult import LlmCompletionResultModel
from app.models.providers.openRouterClient import OpenRouterClientError
from app.models.services.llmService import LlmService


class FakeOpenRouterClient:
    def __init__(self, in_scenarios: dict[str, list[dict | Exception]]) -> None:
        self._scenarios = in_scenarios
        self._indices: dict[str, int] = {}

    def createChatCompletion(self, in_modelName: str, in_promptText: str) -> dict:
        ret: dict
        _ = in_promptText
        sequence = self._scenarios.get(in_modelName, [])
        index = self._indices.get(in_modelName, 0)
        if index >= len(sequence):
            raise OpenRouterClientError(
                code="UNAVAILABLE",
                message=f"No scenario for model {in_modelName}",
            )
        value = sequence[index]
        self._indices[in_modelName] = index + 1
        if isinstance(value, Exception):
            raise value
        ret = value
        return ret


def _makeModelSettings() -> ModelSettings:
    ret = ModelSettings(
        openRouterBaseUrl="https://openrouter.ai/api/v1",
        primaryModel="primary",
        secondaryModel="secondary",
        tertiaryModel="tertiary",
        requestTimeoutSeconds=45,
        retryCountBeforeFallback=1,
        returnToPrimaryCooldownSeconds=60,
    )
    return ret


def _makeLoggingSettings(in_logsDirPath: str = "./data/test-logs") -> LoggingSettings:
    ret = LoggingSettings(
        logsDirPath=in_logsDirPath,
        runLogsFileName="run.jsonl",
        appLogsFileName="app.log",
        maxBytes=1024 * 1024,
        backupCount=2,
    )
    return ret


def testLlmServiceReturnsPrimaryResponse() -> None:
    fakeClient = FakeOpenRouterClient(
        in_scenarios={
            "primary": [
                {
                    "choices": [{"message": {"content": '{"type":"final","reason":"ok","final_answer":"A"}'}}]
                }
            ]
        }
    )
    service = LlmService(
        in_openRouterClient=fakeClient,  # type: ignore[arg-type]
        in_modelSettings=_makeModelSettings(),
        in_loggingSettings=_makeLoggingSettings(),
    )

    result = service.complete(in_modelName="primary", in_promptText="test")

    assert isinstance(result, LlmCompletionResultModel)
    assert '"type":"final"' in result.content
    assert result.selectedModel == "primary"
    assert any(one.get("event") == "model_success" for one in result.fallbackEvents)


def testLlmServiceFallbacksToSecondary() -> None:
    fakeClient = FakeOpenRouterClient(
        in_scenarios={
            "primary": [
                OpenRouterClientError(code="TIMEOUT", message="timeout"),
                OpenRouterClientError(code="TIMEOUT", message="timeout"),
            ],
            "secondary": [
                {
                    "choices": [{"message": {"content": '{"type":"final","reason":"ok","final_answer":"B"}'}}]
                }
            ],
        }
    )
    service = LlmService(
        in_openRouterClient=fakeClient,  # type: ignore[arg-type]
        in_modelSettings=_makeModelSettings(),
        in_loggingSettings=_makeLoggingSettings(),
    )

    result = service.complete(in_modelName="primary", in_promptText="test")

    assert '"final_answer":"B"' in result.content
    assert result.selectedModel == "secondary"
    assert any(one.get("event") == "model_error" for one in result.fallbackEvents)


def testLlmServiceReturnsStopWhenAllModelsFail() -> None:
    fakeClient = FakeOpenRouterClient(
        in_scenarios={
            "primary": [OpenRouterClientError(code="TIMEOUT", message="timeout")] * 2,
            "secondary": [OpenRouterClientError(code="UNAVAILABLE", message="down")] * 2,
            "tertiary": [OpenRouterClientError(code="RATE_LIMIT", message="429")] * 2,
        }
    )
    service = LlmService(
        in_openRouterClient=fakeClient,  # type: ignore[arg-type]
        in_modelSettings=_makeModelSettings(),
        in_loggingSettings=_makeLoggingSettings(),
    )

    result = service.complete(in_modelName="primary", in_promptText="test")

    assert '"type":"stop"' in result.content
    assert "llm_unavailable" in result.content


def testLlmServiceSanitizesReasoningInRawLogs() -> None:
    with TemporaryDirectory() as tempDir:
        logsDirPath = str(Path(tempDir))
        fakeClient = FakeOpenRouterClient(
            in_scenarios={
                "primary": [
                    {
                        "choices": [
                            {
                                "message": {
                                    "content": '{"type":"final","reason":"ok","final_answer":"done"}',
                                    "reasoning": "internal chain of thought",
                                    "reasoning_details": [{"text": "debug"}],
                                }
                            }
                        ]
                    }
                ]
            }
        )
        service = LlmService(
            in_openRouterClient=fakeClient,  # type: ignore[arg-type]
            in_modelSettings=_makeModelSettings(),
            in_loggingSettings=_makeLoggingSettings(in_logsDirPath=logsDirPath),
        )

        completion = service.complete(in_modelName="primary", in_promptText="test")
        _ = completion.content
        runLogPath = Path(logsDirPath) / "run.jsonl"
        lines = runLogPath.read_text(encoding="utf-8").splitlines()
        lastEvent = json.loads(lines[-1])
        rawResponseValue = str(lastEvent.get("rawResponse", ""))

    assert "reasoning_details" not in rawResponseValue
    assert "internal chain of thought" not in rawResponseValue
