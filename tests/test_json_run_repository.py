import json
from pathlib import Path
from tempfile import TemporaryDirectory

from app.observability.stores.jsonRunRepository import JsonRunRepository


def testJsonRunRepositoryWritesRunFileAndIndex() -> None:
    with TemporaryDirectory() as tempDir:
        repository = JsonRunRepository(in_dataRootPath=tempDir)
        runRecord = {
            "traceId": "t1",
            "runId": "r1",
            "sessionId": "telegram:1",
            "runStatus": "completed",
            "completionReason": "final_answer",
            "selectedModel": "model",
            "createdAt": "2026-01-01T00:00:00+00:00",
            "finishedAt": "2026-01-01T00:00:01+00:00",
            "finalAnswer": "ok",
        }

        repository.saveRun(in_runRecord=runRecord)

        runFilePath = Path(tempDir) / "runs" / "r1.json"
        indexFilePath = Path(tempDir) / "runs" / "index.jsonl"
        runFileData = json.loads(runFilePath.read_text(encoding="utf-8"))
        indexLine = indexFilePath.read_text(encoding="utf-8").splitlines()[0]
        indexData = json.loads(indexLine)

    assert runFileData["runId"] == "r1"
    assert indexData["runId"] == "r1"
    assert indexData["completionReason"] == "final_answer"


def testJsonRunRepositoryReadsListAndDetails() -> None:
    with TemporaryDirectory() as tempDir:
        repository = JsonRunRepository(in_dataRootPath=tempDir)
        repository.saveRun(
            in_runRecord={
                "traceId": "t1",
                "runId": "r1",
                "sessionId": "telegram:1",
                "runStatus": "completed",
                "completionReason": "final_answer",
                "selectedModel": "model",
                "createdAt": "2026-01-01T00:00:00+00:00",
                "finishedAt": "2026-01-01T00:00:01+00:00",
            }
        )
        repository.saveRun(
            in_runRecord={
                "traceId": "t2",
                "runId": "r2",
                "sessionId": "telegram:2",
                "runStatus": "completed",
                "completionReason": "stop_response",
                "selectedModel": "model",
                "createdAt": "2026-01-01T00:00:02+00:00",
                "finishedAt": "2026-01-01T00:00:03+00:00",
            }
        )

        listItems = repository.listRuns(in_limit=10, in_offset=0)
        runItem = repository.getRunById(in_runId="r1")
        missingItem = repository.getRunById(in_runId="missing")

    assert len(listItems) == 2
    assert listItems[0]["runId"] == "r2"
    assert listItems[1]["runId"] == "r1"
    assert runItem is not None
    assert runItem["runId"] == "r1"
    assert missingItem is None
