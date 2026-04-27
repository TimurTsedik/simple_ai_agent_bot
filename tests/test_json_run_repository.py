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


def testJsonRunRepositorySkipsCorruptIndexLines() -> None:
    with TemporaryDirectory() as tempDir:
        runsDir = Path(tempDir) / "runs"
        runsDir.mkdir(parents=True)
        indexPath = runsDir / "index.jsonl"
        indexPath.write_text(
            '{"runId":"good","traceId":"t","sessionId":"s","runStatus":"completed",'
            '"completionReason":"final_answer","selectedModel":"m",'
            '"createdAt":"2026-01-01","finishedAt":"2026-01-01"}\n'
            "not valid json line\n"
            '{"runId":"good2","traceId":"t2","sessionId":"s2","runStatus":"completed",'
            '"completionReason":"final_answer","selectedModel":"m",'
            '"createdAt":"2026-01-02","finishedAt":"2026-01-02"}\n',
            encoding="utf-8",
        )
        repository = JsonRunRepository(in_dataRootPath=tempDir)
        listItems = repository.listRuns(in_limit=10, in_offset=0)

    assert len(listItems) == 2
    assert {item["runId"] for item in listItems} == {"good2", "good"}
