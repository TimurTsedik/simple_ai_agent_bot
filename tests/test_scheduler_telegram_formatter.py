from app.integrations.telegram.schedulerTelegramFormatter import (
    formatReminderTelegramMessage,
    formatSchedulerTelegramMessage,
)


def testFormatSchedulerTelegramMessageEmailDigestHeader() -> None:
    text = formatSchedulerTelegramMessage(
        in_jobId="email_digest_hourly",
        in_sessionId="scheduler:email",
        in_runId="run-123",
        in_finalAnswer="Непрочитанные письма: 0",
    )

    assert text.startswith("Email digest\n")
    assert "Расписание:" not in text
    assert "Сессия:" not in text
    assert "RunId:" not in text


def testFormatSchedulerTelegramMessageEmailDigestAddsBlankLinesAroundSeparator() -> None:
    text = formatSchedulerTelegramMessage(
        in_jobId="email_digest_hourly",
        in_sessionId="scheduler:email",
        in_runId="run-123",
        in_finalAnswer="A\n---\nB",
    )

    assert "A\n\n---\n\nB" in text


def testFormatSchedulerTelegramMessageNonEmailDigestKeepsTechnicalHeader() -> None:
    text = formatSchedulerTelegramMessage(
        in_jobId="telegram_news_digest_hourly",
        in_sessionId="scheduler:telegram_news",
        in_runId="run-999",
        in_finalAnswer="ok",
    )

    assert text.startswith("News digest\n")


def testFormatSchedulerTelegramMessageTelegramNewsAddsBlankLinesAroundSeparator() -> None:
    text = formatSchedulerTelegramMessage(
        in_jobId="telegram_news_digest_hourly",
        in_sessionId="scheduler:telegram_news",
        in_runId="run-999",
        in_finalAnswer="A\n---\nB",
    )

    assert "A\n\n---\n\nB" in text


def testFormatReminderTelegramMessageBuildsReadableHeader() -> None:
    text = formatReminderTelegramMessage(
        in_reminderId="reminder-123",
        in_message="Выпей воду",
    )

    assert text.startswith("Напоминание (reminder-123)")
    assert "Выпей воду" in text

