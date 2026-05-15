import json

from app.scheduler.schedulerDigestTelegramSuppress import shouldSuppressSchedulerDigestTelegram


def _toolResult(in_toolName: str, in_data: dict) -> dict:
    ret = {
        "ok": True,
        "tool_name": in_toolName,
        "data": json.dumps(in_data, ensure_ascii=False),
        "error": None,
        "meta": {},
    }
    return ret


def testShouldNotSuppressNonDigestJob() -> None:
    shouldSuppressFlag, diagnostics = shouldSuppressSchedulerDigestTelegram(
        in_jobId="job1",
        in_runRecord={"toolResults": []},
    )
    assert shouldSuppressFlag is False
    assert diagnostics is None


def testShouldSuppressEmailDigestWhenReadEmailCountZero() -> None:
    runRecord = {
        "toolResults": [
            _toolResult("read_email", {"count": 0, "items": []}),
        ],
    }
    shouldSuppressFlag, diagnostics = shouldSuppressSchedulerDigestTelegram(
        in_jobId="email_digest_hourly",
        in_runRecord=runRecord,
    )
    assert shouldSuppressFlag is True
    assert diagnostics is not None
    assert diagnostics.get("itemCount") == 0


def testShouldNotSuppressEmailDigestWhenReadEmailHasItems() -> None:
    runRecord = {
        "toolResults": [
            _toolResult("read_email", {"count": 2, "items": [{}, {}]}),
        ],
    }
    shouldSuppressFlag, diagnostics = shouldSuppressSchedulerDigestTelegram(
        in_jobId="email_digest_hourly",
        in_runRecord=runRecord,
    )
    assert shouldSuppressFlag is False
    assert diagnostics is None


def testShouldSuppressNewsDigestWhenUserTopicFetchedCountZero() -> None:
    runRecord = {
        "toolResults": [
            _toolResult("digest_telegram_news", {"count": 0, "items": []}),
            _toolResult(
                "user_topic_telegram_digest",
                {"status": "ready", "count": None},
            ),
            _toolResult(
                "user_topic_telegram_digest",
                {"status": "fetched", "count": 0, "items": []},
            ),
        ],
    }
    shouldSuppressFlag, diagnostics = shouldSuppressSchedulerDigestTelegram(
        in_jobId="telegram_news_digest_hourly",
        in_runRecord=runRecord,
    )
    assert shouldSuppressFlag is True
    assert diagnostics is not None


def testShouldNotSuppressNewsDigestWhenUserTopicFetchedHasItems() -> None:
    runRecord = {
        "toolResults": [
            _toolResult("digest_telegram_news", {"count": 0, "items": []}),
            _toolResult(
                "user_topic_telegram_digest",
                {"status": "fetched", "count": 3, "items": [{}, {}, {}]},
            ),
        ],
    }
    shouldSuppressFlag, diagnostics = shouldSuppressSchedulerDigestTelegram(
        in_jobId="telegram_news_digest_hourly",
        in_runRecord=runRecord,
    )
    assert shouldSuppressFlag is False
    assert diagnostics is None


def testShouldSuppressNewsDigestWhenOnlyDigestTelegramNewsCountZero() -> None:
    runRecord = {
        "toolResults": [
            _toolResult("digest_telegram_news", {"count": 0, "items": []}),
        ],
    }
    shouldSuppressFlag, diagnostics = shouldSuppressSchedulerDigestTelegram(
        in_jobId="telegram_news_digest_hourly",
        in_runRecord=runRecord,
    )
    assert shouldSuppressFlag is True
    assert diagnostics is not None


def testShouldNotSuppressWhenNoRelevantToolResults() -> None:
    shouldSuppressFlag, diagnostics = shouldSuppressSchedulerDigestTelegram(
        in_jobId="email_digest_hourly",
        in_runRecord={"toolResults": []},
    )
    assert shouldSuppressFlag is False
    assert diagnostics is None


def testEmailDigestUsesLastReadEmailCount() -> None:
    runRecord = {
        "toolResults": [
            _toolResult("read_email", {"count": 0, "items": []}),
            _toolResult("read_email", {"count": 1, "items": [{}]}),
        ],
    }
    shouldSuppressFlag, diagnostics = shouldSuppressSchedulerDigestTelegram(
        in_jobId="email_digest_hourly",
        in_runRecord=runRecord,
    )
    assert shouldSuppressFlag is False
    assert diagnostics is None
