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
        ".grid{display:grid;grid-template-columns:repeat(12,minmax(0,1fr));gap:12px;}"
        ".col6{grid-column:span 6;}"
        ".col4{grid-column:span 4;}"
        ".col12{grid-column:span 12;}"
        "@media(max-width:900px){.col6,.col4{grid-column:span 12;}}"
        ".kpi{font-size:20px;font-weight:700;margin:0;}"
        ".kv{display:flex;justify-content:space-between;gap:10px;border-bottom:1px solid #273252;padding:8px 0;}"
        ".kv:last-child{border-bottom:none;}"
        ".kv .k{color:#aab7d6;}"
        ".kv .v{color:#e8ecf6;max-width:65%;text-align:right;word-break:break-word;}"
        ".danger{color:#ffb4b4;}"
        ".warning{color:#ffd38a;}"
        ".badge{display:inline-block;padding:2px 8px;border-radius:999px;font-size:12px;border:1px solid #2c3a63;background:#1a2442;color:#e8ecf6;}"
        ".badge-ok{border-color:#2b6a4a;background:#123122;color:#bff7d5;}"
        ".badge-warn{border-color:#7a5a1e;background:#2a1e0e;color:#ffd38a;}"
        ".badge-bad{border-color:#6a2b2b;background:#2a1010;color:#ffb4b4;}"
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
        "<a href='/tools'>Tools</a>"
        "<a href='/skills'>Skills</a>"
        "<a href='/config/tools'>Tool config</a>"
        "<a href='/git/status'>Git Status</a>"
        "<a href='/git/diff'>Git Diff</a>"
        "<form method='post' action='/logout' style='margin:0;'>"
        "<button class='btn' type='submit'>Выйти</button>"
        "</form>"
        "</div>"
        "</div>"
    )
    return ret


def renderIndexPage(in_stats: dict[str, Any]) -> str:
    ret: str
    badge = (
        "<span class='badge badge-ok'>writes enabled</span>"
        if bool(in_stats.get("adminWritesEnabled", False)) is True
        else "<span class='badge badge-warn'>read-only</span>"
    )
    lastRunId = str(in_stats.get("lastRunId", ""))
    lastRunLink = (
        f"<a href='/runs/{html.escape(lastRunId)}'>{html.escape(lastRunId)}</a>"
        if lastRunId
        else "<span class='muted'>—</span>"
    )
    content = (
        "<h1 class='title'>simple-ai-agent-bot</h1>"
        "<p class='muted' style='margin-top:0;'>Admin dashboard</p>"
        f"<div class='row'>{badge}<span class='muted'>security.adminWritesEnabled</span></div>"
        "<div class='grid' style='margin-top:12px;'>"
        "<div class='card col4'>"
        "<p class='muted' style='margin:0;'>Tools</p>"
        f"<p class='kpi'>{html.escape(str(in_stats.get('toolsCount','0')))}</p>"
        "</div>"
        "<div class='card col4'>"
        "<p class='muted' style='margin:0;'>Skills</p>"
        f"<p class='kpi'>{html.escape(str(in_stats.get('skillsCount','0')))}</p>"
        "</div>"
        "<div class='card col4'>"
        "<p class='muted' style='margin:0;'>Runs (indexed)</p>"
        f"<p class='kpi'>{html.escape(str(in_stats.get('runsCount','0')))}</p>"
        "</div>"
        "<div class='card col6'>"
        "<h3 style='margin:0 0 8px 0;'>Runtime limits</h3>"
        f"<div class='kv'><div class='k'>maxPromptChars</div><div class='v'>{html.escape(str(in_stats.get('maxPromptChars','')))}</div></div>"
        f"<div class='kv'><div class='k'>maxToolOutputChars</div><div class='v'>{html.escape(str(in_stats.get('maxToolOutputChars','')))}</div></div>"
        f"<div class='kv'><div class='k'>maxExecutionSeconds</div><div class='v'>{html.escape(str(in_stats.get('maxExecutionSeconds','')))}</div></div>"
        "</div>"
        "<div class='card col6'>"
        "<h3 style='margin:0 0 8px 0;'>Models</h3>"
        f"<div class='kv'><div class='k'>primary</div><div class='v'>{html.escape(str(in_stats.get('primaryModel','—')))}</div></div>"
        f"<div class='kv'><div class='k'>secondary</div><div class='v'>{html.escape(str(in_stats.get('secondaryModel','—')))}</div></div>"
        f"<div class='kv'><div class='k'>tertiary</div><div class='v'>{html.escape(str(in_stats.get('tertiaryModel','—')))}</div></div>"
        "</div>"
        "<div class='card col6'>"
        "<h3 style='margin:0 0 8px 0;'>Last run</h3>"
        f"<div class='kv'><div class='k'>runId</div><div class='v'>{lastRunLink}</div></div>"
        f"<div class='kv'><div class='k'>sessionId</div><div class='v'>{html.escape(str(in_stats.get('lastRunSessionId','—')))}</div></div>"
        f"<div class='kv'><div class='k'>model</div><div class='v'>{html.escape(str(in_stats.get('lastRunSelectedModel','—')))}</div></div>"
        f"<div class='kv'><div class='k'>status</div><div class='v'>{html.escape(str(in_stats.get('lastRunStatus','—')))}</div></div>"
        f"<div class='kv'><div class='k'>reason</div><div class='v'>{html.escape(str(in_stats.get('lastRunReason','—')))}</div></div>"
        f"<div class='kv'><div class='k'>createdAt</div><div class='v'>{html.escape(str(in_stats.get('lastRunCreatedAt','—')))}</div></div>"
        "</div>"
        "<div class='card col6'>"
        "<h3 style='margin:0 0 8px 0;'>Context size</h3>"
        f"<div class='kv'><div class='k'>active (recent+summary)</div><div class='v'>{html.escape(str(in_stats.get('contextActive','—')))}</div></div>"
        f"<div class='kv'><div class='k'>recent.md</div><div class='v'>{html.escape(str(in_stats.get('contextRecent','—')))}</div></div>"
        f"<div class='kv'><div class='k'>summary.md</div><div class='v'>{html.escape(str(in_stats.get('contextSummary','—')))}</div></div>"
        f"<div class='kv'><div class='k'>long_term.md</div><div class='v'>{html.escape(str(in_stats.get('contextLongTerm','—')))}</div></div>"
        "</div>"
        "<div class='card col12'>"
        "<h3 style='margin:0 0 8px 0;'>Storage</h3>"
        f"<div class='kv'><div class='k'>tools.yaml</div><div class='v'>{html.escape(str(in_stats.get('toolsYamlInfo','—')))}</div></div>"
        f"<div class='kv'><div class='k'>memory dir</div><div class='v'>{html.escape(str(in_stats.get('memoryInfo','—')))}</div></div>"
        f"<div class='kv'><div class='k'>logs dir</div><div class='v'>{html.escape(str(in_stats.get('logsInfo','—')))}</div></div>"
        "</div>"
        "</div>"
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
        observationText = str(stepItem.get("observation", ""))
        observationSummary = ""
        if observationText:
            try:
                parsedObs = json.loads(observationText)
                if isinstance(parsedObs, dict):
                    kindValue = str(parsedObs.get("kind", ""))
                    if kindValue == "tool_call_blocked":
                        reasonValue = str(parsedObs.get("reason", ""))
                        messageValue = str(parsedObs.get("message", ""))
                        observationSummary = (
                            "<div class='row'>"
                            "<span class='badge badge-warn'>guard</span>"
                            f"<span class='muted'>tool_call_blocked</span>"
                            "</div>"
                            f"<p class='muted'>reason: {html.escape(reasonValue)}</p>"
                            f"<p>{html.escape(messageValue)}</p>"
                        )
                    elif kindValue == "tool_observation":
                        toolValue = str(parsedObs.get("tool_name", ""))
                        okValue = bool(parsedObs.get("ok", False))
                        badgeClass = "badge-ok" if okValue is True else "badge-bad"
                        observationSummary = (
                            "<div class='row'>"
                            f"<span class='badge {badgeClass}'>observation</span>"
                            f"<span class='muted'>{html.escape(toolValue)}</span>"
                            "</div>"
                        )
            except json.JSONDecodeError:
                observationSummary = ""

        badgeCss = "badge"
        if status in ("final",):
            badgeCss = "badge badge-ok"
        elif status in ("tool_call", "running"):
            badgeCss = "badge"
        elif status in ("tool_call_blocked", "parse_error"):
            badgeCss = "badge badge-warn"
        else:
            badgeCss = "badge badge-bad"

        toolCallJson = json.dumps(stepItem.get("toolCall"), ensure_ascii=False, indent=2)
        toolResultJson = json.dumps(stepItem.get("toolResult"), ensure_ascii=False, indent=2)
        parsedJson = json.dumps(
            stepItem.get("parsedModelResponse"), ensure_ascii=False, indent=2
        )
        promptText = str(stepItem.get("promptSnapshot", ""))
        rawResponse = str(stepItem.get("rawModelResponse", ""))
        blocks.append(
            "<div class='card'>"
            "<div class='row'>"
            f"<h3 style='margin:0;'>Step {html.escape(stepIndex)}</h3>"
            f"<span class='{badgeCss}'>{html.escape(status)}</span>"
            "</div>"
            + (observationSummary if observationSummary else "")
            + "<details><summary>Prompt sent to LLM</summary>"
            f"<pre>{html.escape(promptText)}</pre></details>"
            "<details><summary>Raw model response</summary>"
            f"<pre>{html.escape(rawResponse)}</pre></details>"
            "<details><summary>Parsed model response</summary>"
            f"<pre>{html.escape(parsedJson)}</pre></details>"
            "<details><summary>Tool call</summary>"
            f"<pre>{html.escape(toolCallJson)}</pre></details>"
            "<details><summary>Tool result</summary>"
            f"<pre>{html.escape(toolResultJson)}</pre></details>"
            "<details><summary>Observation</summary>"
            f"<pre>{html.escape(observationText)}</pre></details>"
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


def renderToolsPage(in_toolItems: list[dict[str, Any]]) -> str:
    ret: str
    blocks: list[str] = []
    for item in in_toolItems:
        nameValue = str(item.get("name", ""))
        descValue = str(item.get("description", ""))
        schemaValue = item.get("argsSchema")
        schemaJson = json.dumps(schemaValue, ensure_ascii=False, indent=2)
        blocks.append(
            "<div class='card'>"
            f"<h3 style='margin:0 0 6px 0;'>{html.escape(nameValue)}</h3>"
            f"<p class='muted' style='margin:0 0 8px 0;'>{html.escape(descValue)}</p>"
            "<details><summary>Args schema</summary>"
            f"<pre>{html.escape(schemaJson)}</pre></details>"
            "</div>"
        )
    content = (
        "<h1 class='title'>Tools</h1>"
        f"<p class='muted'>Всего: {len(in_toolItems)}</p>"
        + ("".join(blocks) if blocks else "<p>Инструменты не найдены.</p>")
    )
    ret = _renderLayout(in_title="Tools", in_content=content, in_showNav=True)
    return ret


def renderSkillsPage(
    in_skillItems: list[dict[str, str]], in_adminWritesEnabled: bool
) -> str:
    ret: str
    rows: list[str] = []
    for item in in_skillItems:
        skillId = str(item.get("skillId", ""))
        titleValue = str(item.get("title", ""))
        editLink = f"/skills/{quote(skillId)}"
        rows.append(
            "<tr>"
            f"<td>{html.escape(skillId)}</td>"
            f"<td>{html.escape(titleValue)}</td>"
            f"<td><a href='{html.escape(editLink)}'>Открыть</a></td>"
            "</tr>"
        )
    bodyRows = (
        "".join(rows) if rows else "<tr><td colspan='3'>Skills не найдены.</td></tr>"
    )
    badge = (
        "<span class='badge badge-ok'>writes enabled</span>"
        if in_adminWritesEnabled is True
        else "<span class='badge badge-warn'>read-only</span>"
    )
    content = (
        "<h1 class='title'>Skills</h1>"
        f"<div class='row'>{badge}<span class='muted'>Редактирование управляется security.adminWritesEnabled</span></div>"
        "<table>"
        "<thead><tr><th>skillId</th><th>title</th><th>action</th></tr></thead>"
        f"<tbody>{bodyRows}</tbody>"
        "</table>"
    )
    ret = _renderLayout(in_title="Skills", in_content=content, in_showNav=True)
    return ret


def renderSkillEditPage(
    in_skillId: str,
    in_title: str,
    in_contentText: str,
    in_errorText: str,
    in_adminWritesEnabled: bool,
) -> str:
    ret: str
    badge = (
        "<span class='badge badge-ok'>writes enabled</span>"
        if in_adminWritesEnabled is True
        else "<span class='badge badge-warn'>read-only</span>"
    )
    errorBlock = (
        f"<p class='danger'>{html.escape(in_errorText)}</p>" if in_errorText else ""
    )
    disabledAttr = "" if in_adminWritesEnabled is True else "disabled"
    content = (
        f"<h1 class='title'>Skill: {html.escape(in_title)}</h1>"
        f"<p class='muted'>id: {html.escape(in_skillId)}</p>"
        f"<div class='row'>{badge}</div>"
        f"{errorBlock}"
        "<form method='post'>"
        f"<textarea name='content' rows='24' style='width:100%;padding:10px;border-radius:10px;border:1px solid #273252;background:#0e1529;color:#e8ecf6;' {disabledAttr}>"
        f"{html.escape(in_contentText)}"
        "</textarea>"
        "<div class='row' style='margin-top:10px;'>"
        f"<button class='btn' type='submit' {disabledAttr}>Сохранить</button>"
        f"<a class='btn' href='/skills'>Назад</a>"
        "</div>"
        "</form>"
    )
    ret = _renderLayout(in_title="Edit Skill", in_content=content, in_showNav=True)
    return ret


def renderToolsConfigEditPage(
    in_toolsYamlText: str,
    in_errorText: str,
    in_adminWritesEnabled: bool,
) -> str:
    ret: str
    badge = (
        "<span class='badge badge-ok'>writes enabled</span>"
        if in_adminWritesEnabled is True
        else "<span class='badge badge-warn'>read-only</span>"
    )
    errorBlock = (
        f"<p class='danger'>{html.escape(in_errorText)}</p>" if in_errorText else ""
    )
    disabledAttr = "" if in_adminWritesEnabled is True else "disabled"
    content = (
        "<h1 class='title'>Tool settings (tools.yaml)</h1>"
        f"<div class='row'>{badge}</div>"
        f"{errorBlock}"
        "<form method='post'>"
        f"<textarea name='content' rows='24' style='width:100%;padding:10px;border-radius:10px;border:1px solid #273252;background:#0e1529;color:#e8ecf6;' {disabledAttr}>"
        f"{html.escape(in_toolsYamlText)}"
        "</textarea>"
        "<div class='row' style='margin-top:10px;'>"
        f"<button class='btn' type='submit' {disabledAttr}>Сохранить</button>"
        f"<a class='btn' href='/'>Назад</a>"
        "</div>"
        "</form>"
    )
    ret = _renderLayout(in_title="Tool Config", in_content=content, in_showNav=True)
    return ret
