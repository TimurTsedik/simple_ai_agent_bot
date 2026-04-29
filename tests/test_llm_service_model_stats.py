from pathlib import Path
from tempfile import TemporaryDirectory

from app.application.services.modelStatsService import ModelStatsService
from app.config.settingsModels import LoggingSettings, ModelSettings
from app.domain.entities.llmCompletionResult import LlmCompletionResultModel
from app.models.providers.openRouterClient import OpenRouterClientError
from app.models.services.llmService import LlmService


class FakeOpenRouterClient:
    def __init__(self, in_scenarios: dict[str, list[dict | Exception]]) -> None:
        self._scenarios = in_scenarios
        self._indices: dict[str, int] = {}

    def createChatCompletion(
        self,
        in_modelName: str,
        in_promptText: str,
        *,
        in_timeoutSeconds: int | None = None,
        in_useJsonObjectResponseFormat: bool = False,
    ) -> dict:
        ret: dict
        _ = (in_promptText, in_timeoutSeconds, in_useJsonObjectResponseFormat)
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


def _makeLoggingSettings(in_logsDirPath: str) -> LoggingSettings:
    ret = LoggingSettings(
        logsDirPath=in_logsDirPath,
        runLogsFileName="run.jsonl",
        appLogsFileName="app.log",
        maxBytes=1024 * 1024,
        backupCount=2,
    )
    return ret


def testLlmServiceRecordsModelStatsOnSuccess() -> None:
    with TemporaryDirectory() as tempDir:
        logsDirPath = str(Path(tempDir) / "logs")
        dataRoot = str(Path(tempDir) / "data")
        Path(logsDirPath).mkdir(parents=True)
        Path(dataRoot).mkdir(parents=True)
        stats = ModelStatsService(in_dataRootPath=dataRoot)
        fakeClient = FakeOpenRouterClient(
            in_scenarios={
                "primary": [
                    {
                        "usage": {
                            "prompt_tokens": 11,
                            "completion_tokens": 22,
                            "total_tokens": 33,
                        },
                        "choices": [
                            {
                                "message": {
                                    "content": '{"type":"final","reason":"ok","final_answer":"A"}',
                                }
                            }
                        ],
                    }
                ]
            }
        )
        service = LlmService(
            in_openRouterClient=fakeClient,  # type: ignore[arg-type]
            in_modelSettings=_makeModelSettings(),
            in_loggingSettings=_makeLoggingSettings(in_logsDirPath=logsDirPath),
            in_modelStatsService=stats,
        )
        result = service.complete(in_modelName="primary", in_promptText="x")
        snap = stats.getSnapshot()

    assert isinstance(result, LlmCompletionResultModel)
    assert snap["totals"]["calls"] == 1
    assert snap["totals"]["success"] == 1
    assert snap["totals"]["errors"] == 0
    assert snap["totals"]["promptTokens"] == 11
    assert snap["totals"]["completionTokens"] == 22
    assert snap["totals"]["totalTokens"] == 33


def testLlmServiceRecordsModelStatsOnFallback() -> None:
    with TemporaryDirectory() as tempDir:
        logsDirPath = str(Path(tempDir) / "logs")
        dataRoot = str(Path(tempDir) / "data")
        Path(logsDirPath).mkdir(parents=True)
        Path(dataRoot).mkdir(parents=True)
        stats = ModelStatsService(in_dataRootPath=dataRoot)
        fakeClient = FakeOpenRouterClient(
            in_scenarios={
                "primary": [
                    OpenRouterClientError(code="TIMEOUT", message="timeout"),
                    OpenRouterClientError(code="TIMEOUT", message="timeout"),
                ],
                "secondary": [
                    {
                        "usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
                        "choices": [
                            {
                                "message": {
                                    "content": '{"type":"final","reason":"ok","final_answer":"B"}',
                                }
                            }
                        ],
                    }
                ],
            }
        )
        service = LlmService(
            in_openRouterClient=fakeClient,  # type: ignore[arg-type]
            in_modelSettings=_makeModelSettings(),
            in_loggingSettings=_makeLoggingSettings(in_logsDirPath=logsDirPath),
            in_modelStatsService=stats,
        )
        result = service.complete(in_modelName="primary", in_promptText="x")
        snap = stats.getSnapshot()

    assert isinstance(result, LlmCompletionResultModel)
    assert '"final_answer":"B"' in result.content
    assert snap["totals"]["calls"] == 3
    assert snap["totals"]["success"] == 1
    assert snap["totals"]["errors"] == 2
    assert snap["totals"]["promptTokens"] == 1
    assert snap["totals"]["completionTokens"] == 2
    assert snap["totals"]["totalTokens"] == 3
