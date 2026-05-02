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
            "sessionId": "telegramUser:1",
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


def testJsonRunRepositoryListRunsFiltersByExactSessionId() -> None:
    with TemporaryDirectory() as tempDir:
        repository = JsonRunRepository(in_dataRootPath=tempDir)
        repository.saveRun(
            in_runRecord={
                "traceId": "t_legacy",
                "runId": "r_legacy",
                "sessionId": "telegram:99",
                "runStatus": "completed",
                "completionReason": "final_answer",
                "selectedModel": "model",
                "createdAt": "2026-01-01T00:00:00+00:00",
                "finishedAt": "2026-01-01T00:00:01+00:00",
            }
        )
        repository.saveRun(
            in_runRecord={
                "traceId": "t_ok",
                "runId": "r_ok",
                "sessionId": "telegramUser:99",
                "runStatus": "completed",
                "completionReason": "final_answer",
                "selectedModel": "model",
                "createdAt": "2026-01-01T00:00:02+00:00",
                "finishedAt": "2026-01-01T00:00:03+00:00",
            }
        )
        filteredLegacyPrefix = repository.listRuns(
            in_limit=10,
            in_offset=0,
            in_session_id="telegramUser:99",
        )
        filteredExact = repository.listRuns(
            in_limit=10,
            in_offset=0,
            in_session_id="telegram:99",
        )

    assert len(filteredLegacyPrefix) == 1
    assert filteredLegacyPrefix[0]["runId"] == "r_ok"
    assert len(filteredExact) == 1
    assert filteredExact[0]["runId"] == "r_legacy"


def testJsonRunRepositoryReadsListAndDetails() -> None:
    with TemporaryDirectory() as tempDir:
        repository = JsonRunRepository(in_dataRootPath=tempDir)
        repository.saveRun(
            in_runRecord={
                "traceId": "t1",
                "runId": "r1",
                "sessionId": "telegramUser:1",
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
                "sessionId": "telegramUser:2",
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


def testJsonRunRepositoryListRunsTailReadOrderAndPagination() -> None:
    with TemporaryDirectory() as tempDir:
        runsDir = Path(tempDir) / "runs"
        runsDir.mkdir(parents=True)
        indexPath = runsDir / "index.jsonl"
        totalLines = 250
        lines: list[str] = []
        for index in range(1, totalLines + 1):
            record = {
                "runId": f"r{index:04d}",
                "traceId": f"t{index}",
                "sessionId": "s",
                "runStatus": "completed",
                "completionReason": "final_answer",
                "selectedModel": "m",
                "createdAt": "2026-01-01",
                "finishedAt": "2026-01-01",
            }
            lines.append(json.dumps(record, ensure_ascii=False))
            if index % 50 == 0:
                lines.append("not json")
        indexPath.write_text("\n".join(lines) + "\n", encoding="utf-8")
        repository = JsonRunRepository(in_dataRootPath=tempDir)

        firstPage = repository.listRuns(in_limit=5, in_offset=0)
        secondPage = repository.listRuns(in_limit=5, in_offset=5)
        thirdPage = repository.listRuns(in_limit=3, in_offset=10)

    assert [item["runId"] for item in firstPage] == [
        "r0250",
        "r0249",
        "r0248",
        "r0247",
        "r0246",
    ]
    assert [item["runId"] for item in secondPage] == [
        "r0245",
        "r0244",
        "r0243",
        "r0242",
        "r0241",
    ]
    assert [item["runId"] for item in thirdPage] == ["r0240", "r0239", "r0238"]
