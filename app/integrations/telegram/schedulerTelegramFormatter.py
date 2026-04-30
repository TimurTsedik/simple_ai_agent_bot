def formatSchedulerTelegramMessage(
    in_jobId: str,
    in_sessionId: str,
    in_runId: str,
    in_finalAnswer: str,
) -> str:
    ret: str
    jobIdValue = str(in_jobId or "")
    headerText: str
    if "email_digest" in jobIdValue:
        headerText = "Email digest\n"
    elif "telegram_news_digest" in jobIdValue:
        headerText = "News digest\n"
    else:
        headerText = (
            f"Расписание: {in_jobId}\n"
            f"Сессия: {in_sessionId}\n"
            f"RunId: {in_runId}\n"
        )

    bodyText = str(in_finalAnswer or "").strip()
    if ("email_digest" in jobIdValue or "telegram_news_digest" in jobIdValue) and bodyText:
        bodyText = bodyText.replace("\n---\n", "\n\n---\n\n").strip()

    ret = headerText + "\n" + bodyText if bodyText else headerText
    return ret

