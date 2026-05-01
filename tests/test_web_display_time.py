from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from app.common.webDisplayTime import formatIso8601ForWeb
from app.common.webDisplayTime import formatTimestampFieldsDeepCopy
from app.common.webDisplayTime import formatUnixEpochSecondsForWeb
from app.common.webDisplayTime import resolveDisplayZone
from app.presentation.web.adminPages import renderRunDetailsPage
from app.presentation.web.adminPages import renderRunsPage


def test_resolveDisplayZone_returns_zone_for_valid_name() -> None:
    ret = resolveDisplayZone(in_timeZoneName="Europe/Moscow")
    assert str(ret) == "Europe/Moscow"


def test_resolveDisplayZone_invalid_name_falls_back_to_utc() -> None:
    ret = resolveDisplayZone(in_timeZoneName="Not/A_Real_Zone_12345")
    assert ret == ZoneInfo("UTC")


def test_resolveDisplayZone_blank_falls_back_to_utc() -> None:
    ret = resolveDisplayZone(in_timeZoneName="   ")
    assert ret == ZoneInfo("UTC")


def test_format_iso8601_for_web_converts_to_zone() -> None:
    zoneMoscow = ZoneInfo("Europe/Moscow")
    ret = formatIso8601ForWeb(
        in_value="2024-01-15T12:00:00Z",
        in_zone=zoneMoscow,
    )
    assert "2024-01-15" in ret
    assert "15:00:00" in ret


def test_format_iso8601_for_web_unparseable_returns_original() -> None:
    zoneUtc = ZoneInfo("UTC")
    ret = formatIso8601ForWeb(in_value="not-a-date", in_zone=zoneUtc)
    assert ret == "not-a-date"


def test_format_unix_epoch_seconds_for_web_utc_epoch() -> None:
    zoneUtc = ZoneInfo("UTC")
    epochZero = datetime(1970, 1, 1, 0, 0, 0, tzinfo=UTC).timestamp()
    ret = formatUnixEpochSecondsForWeb(in_epochSeconds=float(epochZero), in_zone=zoneUtc)
    assert "1970-01-01" in ret
    assert "00:00:00" in ret


def test_format_timestamp_fields_deep_copy_formats_known_keys() -> None:
    zoneUtc = ZoneInfo("UTC")
    inData = {
        "createdAt": "2024-01-15T12:00:00Z",
        "nested": {"timestamp": "2024-01-15T13:00:00+00:00"},
        "other": "unchanged",
    }
    ret = formatTimestampFieldsDeepCopy(in_value=inData, in_zone=zoneUtc)
    assert isinstance(ret, dict) is True
    assert ret["other"] == "unchanged"
    assert "2024-01-15 12:00:00" in str(ret["createdAt"])
    assert "2024-01-15 13:00:00" in str(ret["nested"]["timestamp"])


def test_render_runs_page_shows_created_at_in_display_zone() -> None:
    zoneMoscow = ZoneInfo("Europe/Moscow")
    retHtml = renderRunsPage(
        in_runItems=[
            {
                "runId": "run-test-1",
                "sessionId": "sess",
                "runStatus": "done",
                "completionReason": "ok",
                "createdAt": "2024-01-15T12:00:00Z",
            }
        ],
        in_displayZone=zoneMoscow,
    )
    assert "run-test-1" in retHtml
    assert "15:00:00" in retHtml


def test_render_run_details_page_formats_timestamp_fields_in_json() -> None:
    zoneMoscow = ZoneInfo("Europe/Moscow")
    retHtml = renderRunDetailsPage(
        in_runId="run-x",
        in_runItem={
            "runId": "run-x",
            "createdAt": "2024-01-15T12:00:00Z",
            "finishedAt": "2024-01-15T12:30:00Z",
        },
        in_displayZone=zoneMoscow,
    )
    assert "15:00:00" in retHtml
    assert "15:30:00" in retHtml
    assert "Обзор" in retHtml


def test_render_run_details_page_raw_view_shows_json_not_overview_title() -> None:
    zoneMoscow = ZoneInfo("Europe/Moscow")
    retHtml = renderRunDetailsPage(
        in_runId="run-y",
        in_runItem={"runId": "run-y", "inputMessage": "ping"},
        in_displayZone=zoneMoscow,
        in_rawView=True,
    )
    assert "сырой JSON" in retHtml
    assert "inputMessage" in retHtml
    assert "ping" in retHtml
