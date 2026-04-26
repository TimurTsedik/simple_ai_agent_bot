import html
import json
from urllib.parse import quote
from typing import Any


def _renderLayout(in_title: str, in_content: str, in_showNav: bool = True) -> str:
    ret: str
    navBlock = _renderNav() if in_showNav else ""
    ret = (
        "<!doctype html>"
        "<html><head>"
        f"<title>{html.escape(in_title)}</title>"
        "<meta charset='utf-8' />"
        "<meta name='viewport' content='width=device-width, initial-scale=1' />"
        "<style>"
        "body{margin:0;background:#0b1020;color:#e8ecf6;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;}"
        ".container{max-width:1100px;margin:0 auto;padding:20px;}"
        ".card{background:#131a2e;border:1px solid #273252;border-radius:14px;padding:16px 18px;margin-bottom:14px;}"
        ".title{font-size:24px;font-weight:700;margin:0 0 10px 0;}"
        ".muted{color:#9ca9c6;}"
        "a{color:#86b7ff;text-decoration:none;}a:hover{text-decoration:underline;}"
        ".nav{display:flex;gap:10px;align-items:center;flex-wrap:wrap;}"
        ".nav a{display:inline-block;padding:8px 12px;background:#1a2442;border:1px solid #2c3a63;border-radius:10px;}"
        ".btn{padding:8px 12px;border:1px solid #2c3a63;border-radius:10px;background:#1a2442;color:#e8ecf6;cursor:pointer;}"
        ".btn:hover{background:#22305a;}"
        "table{width:100%;border-collapse:collapse;}"
        "th,td{border-bottom:1px solid #273252;padding:10px 8px;text-align:left;vertical-align:top;}"
        "th{color:#aab7d6;font-weight:600;}"
        "pre{white-space:pre-wrap;word-break:break-word;background:#0e1529;border:1px solid #273252;border-radius:10px;padding:10px;margin:8px 0;}"
        ".row{display:flex;gap:10px;align-items:center;flex-wrap:wrap;}"
        ".danger{color:#ffb4b4;}"
        ".warning{color:#ffd38a;}"
        "details{margin:8px 0;}"
        "input[type='password']{padding:8px 10px;border:1px solid #2c3a63;border-radius:10px;background:#0e1529;color:#e8ecf6;min-width:260px;}"
        "ul{margin:8px 0 0 18px;padding:0;}"
        "li{margin:6px 0;}"
        "</style>"
        "</head><body>"
        "<div class='container'>"
        f"{navBlock}"
        "<div class='card'>"
        f"{in_content}"
        "</div>"
        "</div>"
        "</body></html>"
    )
    return ret


def _renderNav() -> str:
    ret: str
    ret = (
        "<div class='card'>"
        "<div class='nav'>"
        "<a href='/'>Главная</a>"
        "<a href='/runs'>Runs</a>"
        "<a href='/logs'>Logs</a>"
        "<a href='/git/status'>Git Status</a>"
        "<a href='/git/diff'>Git Diff</a>"
        "<form method='post' action='/logout' style='margin:0;'>"
        "<button class='btn' type='submit'>Выйти</button>"
        "</form>"
        "</div>"
        "</div>"
    )
    return ret


def renderIndexPage() -> str:
    ret: str
    content = (
        "<h1 class='title'>simple-ai-agent-bot</h1>"
        "<p class='muted'>Сервис запущен.</p>"
        "<ul>"
        "<li><a href='/health'>/health</a> — статус сервиса</li>"
        "<li><a href='/docs'>/docs</a> — Swagger UI</li>"
        "<li><a href='/runs'>/runs</a> — список запусков</li>"
        "<li><a href='/logs'>/logs</a> — просмотр последних логов</li>"
        "<li><a href='/git/status'>/git/status</a> — git status</li>"
        "<li><a href='/git/diff'>/git/diff</a> — git diff</li>"
        "</ul>"
    )
    ret = _renderLayout(in_title="Admin", in_content=content, in_showNav=True)
    return ret


def renderLoginPage(in_errorText: str = "") -> str:
    ret: str
    errorBlock = (
        f"<p class='danger'>{html.escape(in_errorText)}</p>" if in_errorText else ""
    )
    content = (
        "<h1 class='title'>Вход в админку</h1>"
        "<p class='muted'>Введите admin token.</p>"
        f"{errorBlock}"
        "<form method='post' action='/login'>"
        "<div class='row'>"
        "<input name='adminToken' type='password' placeholder='Admin token' />"
        "<button class='btn' type='submit'>Войти</button>"
        "</div>"
        "</form>"
    )
    ret = _renderLayout(in_title="Login", in_content=content, in_showNav=False)
    return ret


def renderLogsPage(in_logItems: list[Any]) -> str:
    ret: str
    renderedItems = []
    for oneItem in in_logItems:
        renderedItems.append(f"<pre>{html.escape(str(oneItem))}</pre>")
    content = (
        "<h1 class='title'>Run Logs</h1>"
        f"<p class='muted'>Показаны последние {len(in_logItems)} записей.</p>"
        + ("".join(renderedItems) if renderedItems else "<p>Логи пока отсутствуют.</p>")
    )
    ret = _renderLayout(in_title="Logs", in_content=content, in_showNav=True)
    return ret


def renderRunsPage(in_runItems: list[Any]) -> str:
    ret: str
    rows = []
    for runItem in in_runItems:
        runId = str(runItem.get("runId", "unknown"))
        sessionId = str(runItem.get("sessionId", ""))
        status = str(runItem.get("runStatus", ""))
        reason = str(runItem.get("completionReason", ""))
        createdAt = str(runItem.get("createdAt", ""))
        rows.append(
            "<tr>"
            f"<td><a href='/runs/{html.escape(runId)}'>{html.escape(runId)}</a></td>"
            f"<td>{html.escape(sessionId)}</td>"
            f"<td>{html.escape(status)}</td>"
            f"<td>{html.escape(reason)}</td>"
            f"<td>{html.escape(createdAt)}</td>"
            "</tr>"
        )
    bodyRows = "".join(rows) if rows else "<tr><td colspan='5'>Запусков пока нет.</td></tr>"
    content = (
        "<h1 class='title'>Runs</h1>"
        f"<p class='muted'>Показаны последние {len(in_runItems)} запусков.</p>"
        "<table>"
        "<thead><tr><th>runId</th><th>sessionId</th><th>status</th>"
        "<th>completionReason</th><th>createdAt</th></tr></thead>"
        f"<tbody>{bodyRows}</tbody>"
        "</table>"
    )
    ret = _renderLayout(in_title="Runs", in_content=content, in_showNav=True)
    return ret


def renderRunDetailsPage(in_runId: str, in_runItem: dict[str, Any]) -> str:
    ret: str
    prettyJson = json.dumps(in_runItem, ensure_ascii=False, indent=2)
    content = (
        f"<h1 class='title'>Run {html.escape(in_runId)}</h1>"
        f"<p><a href='/runs/{html.escape(in_runId)}/steps'>Открыть шаги agentic loop</a></p>"
        f"<pre>{html.escape(prettyJson)}</pre>"
    )
    ret = _renderLayout(in_title="Run Details", in_content=content, in_showNav=True)
    return ret


def renderRunStepsPage(in_runId: str, in_stepItems: list[dict[str, Any]]) -> str:
    ret: str
    blocks: list[str] = []
    for stepItem in in_stepItems:
        if not isinstance(stepItem, dict):
            continue
        stepIndex = str(stepItem.get("stepIndex", ""))
        status = str(stepItem.get("status", ""))
        toolCallJson = json.dumps(stepItem.get("toolCall"), ensure_ascii=False, indent=2)
        toolResultJson = json.dumps(stepItem.get("toolResult"), ensure_ascii=False, indent=2)
        parsedJson = json.dumps(
            stepItem.get("parsedModelResponse"), ensure_ascii=False, indent=2
        )
        promptText = str(stepItem.get("promptSnapshot", ""))
        rawResponse = str(stepItem.get("rawModelResponse", ""))
        blocks.append(
            "<div class='card'>"
            f"<h3>Step {html.escape(stepIndex)} — {html.escape(status)}</h3>"
            "<details><summary>Prompt sent to LLM</summary>"
            f"<pre>{html.escape(promptText)}</pre></details>"
            "<details><summary>Raw model response</summary>"
            f"<pre>{html.escape(rawResponse)}</pre></details>"
            "<details><summary>Parsed model response</summary>"
            f"<pre>{html.escape(parsedJson)}</pre></details>"
            "<details><summary>Tool call</summary>"
            f"<pre>{html.escape(toolCallJson)}</pre></details>"
            "<details><summary>Tool result</summary>"
            f"<pre>{html.escape(toolResultJson)}</pre></details>"
            "</div>"
        )
    content = (
        f"<h1 class='title'>Run {html.escape(in_runId)} — Agentic Loop Steps</h1>"
        f"<p><a href='/runs/{html.escape(in_runId)}'>Назад к полному run</a></p>"
        + ("".join(blocks) if blocks else "<p>Для этого запуска шаги не найдены.</p>")
    )
    ret = _renderLayout(in_title="Run Steps", in_content=content, in_showNav=True)
    return ret


def renderGitStatusPage(in_statusResult: dict[str, Any]) -> str:
    ret: str
    isGitRepo = bool(in_statusResult.get("isGitRepo", False))
    branch = str(in_statusResult.get("branch", ""))
    isClean = bool(in_statusResult.get("isClean", True))
    itemLines = in_statusResult.get("items", [])
    if not isinstance(itemLines, list):
        itemLines = []
    errorText = str(in_statusResult.get("error", ""))
    itemsBlock = (
        "<p>Изменений нет.</p>"
        if len(itemLines) == 0
        else f"<pre>{html.escape(chr(10).join(str(item) for item in itemLines))}</pre>"
    )
    content = (
        "<h1 class='title'>Git Status</h1>"
        f"<p>Git repository: {'yes' if isGitRepo else 'no'}</p>"
        f"<p>Branch: {html.escape(branch)}</p>"
        f"<p>Clean: {'yes' if isClean else 'no'}</p>"
        + (f"<p class='danger'>Error: {html.escape(errorText)}</p>" if errorText else "")
        + itemsBlock
    )
    ret = _renderLayout(in_title="Git Status", in_content=content, in_showNav=True)
    return ret


def renderGitDiffPage(
    in_diffResult: dict[str, Any],
    in_offset: int,
    in_limit: int,
    in_filePath: str,
    in_maxCharsPerFile: int,
) -> str:
    ret: str
    isGitRepo = bool(in_diffResult.get("isGitRepo", False))
    totalFiles = int(in_diffResult.get("totalFiles", 0))
    currentOffset = int(in_diffResult.get("offset", in_offset))
    currentLimit = int(in_diffResult.get("limit", in_limit))
    errorText = str(in_diffResult.get("error", ""))
    files = in_diffResult.get("files", [])
    if not isinstance(files, list):
        files = []
    renderedFiles: list[str] = []
    for oneFile in files:
        if not isinstance(oneFile, dict):
            continue
        onePath = str(oneFile.get("filePath", ""))
        oneDiff = str(oneFile.get("diff", ""))
        oneTruncated = bool(oneFile.get("truncated", False))
        renderedFiles.append(
            "<div class='card'>"
            f"<h3>{html.escape(onePath)}</h3>"
            f"<pre>{html.escape(oneDiff)}</pre>"
            + (
                "<p class='warning'>Diff truncated for safety.</p>"
                if oneTruncated
                else ""
            )
            + "</div>"
        )
    prevOffset = max(0, currentOffset - currentLimit)
    nextOffset = currentOffset + currentLimit
    baseLink = (
        f"/git/diff?limit={currentLimit}&maxCharsPerFile={in_maxCharsPerFile}"
        f"&filePath={quote(in_filePath)}"
    )
    content = (
        "<h1 class='title'>Git Diff</h1>"
        f"<p>Git repository: {'yes' if isGitRepo else 'no'}</p>"
        f"<p>Total changed files: {totalFiles}</p>"
        + (f"<p class='danger'>Error: {html.escape(errorText)}</p>" if errorText else "")
        + "<p>"
        + f"<a href='{baseLink}&offset={prevOffset}'>Prev</a> | "
        + f"<a href='{baseLink}&offset={nextOffset}'>Next</a>"
        + "</p>"
        + ("".join(renderedFiles) if renderedFiles else "<p>Diff data is empty.</p>")
    )
    ret = _renderLayout(in_title="Git Diff", in_content=content, in_showNav=True)
    return ret
