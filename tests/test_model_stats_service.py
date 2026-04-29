import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from tempfile import TemporaryDirectory

from app.application.services.modelStatsService import (
    ModelStatsService,
    extractProviderUsageTokenCounts,
)


def testExtractProviderUsageTokenCounts() -> None:
    data = {
        "usage": {"prompt_tokens": 5, "completion_tokens": 7, "total_tokens": 12},
        "choices": [],
    }
    pt, ct, tt = extractProviderUsageTokenCounts(in_responseData=data)
    assert (pt, ct, tt) == (5, 7, 12)


def testModelStatsServiceIncrementsAndPersists() -> None:
    with TemporaryDirectory() as tempDir:
        service = ModelStatsService(in_dataRootPath=tempDir)
        service.recordAttempt(
            in_modelName="m-a",
            in_didSucceed=True,
            in_promptTokens=10,
            in_completionTokens=20,
            in_totalTokens=30,
            in_errorCode="",
        )
        service.recordAttempt(
            in_modelName="m-a",
            in_didSucceed=False,
            in_promptTokens=0,
            in_completionTokens=0,
            in_totalTokens=0,
            in_errorCode="TIMEOUT",
        )
        snap = service.getSnapshot()
        diskData = json.loads((Path(tempDir) / "model_stats.json").read_text(encoding="utf-8"))

    assert snap["totals"]["calls"] == 2
    assert snap["totals"]["success"] == 1
    assert snap["totals"]["errors"] == 1
    assert snap["totals"]["promptTokens"] == 10
    assert snap["totals"]["completionTokens"] == 20
    assert snap["totals"]["totalTokens"] == 30
    assert len(snap["models"]) == 1
    row = snap["models"][0]
    assert row["modelName"] == "m-a"
    assert row["calls"] == 2
    assert row["success"] == 1
    assert row["errors"] == 1
    assert row["lastErrorCode"] == "TIMEOUT"

    assert diskData["schemaVersion"] == 1
    assert diskData["totals"]["calls"] == 2


def testModelStatsServiceConcurrentIncrements() -> None:
    with TemporaryDirectory() as tempDir:
        service = ModelStatsService(in_dataRootPath=tempDir)

        def worker() -> None:
            service.recordAttempt(
                in_modelName="concurrent",
                in_didSucceed=True,
                in_promptTokens=1,
                in_completionTokens=1,
                in_totalTokens=2,
                in_errorCode="",
            )

        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(worker) for _ in range(40)]
            for future in as_completed(futures):
                future.result()

        snap = service.getSnapshot()

    assert snap["totals"]["calls"] == 40
    assert snap["totals"]["success"] == 40
    assert snap["totals"]["promptTokens"] == 40
