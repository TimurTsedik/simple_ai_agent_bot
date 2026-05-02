import html
import json
from urllib.parse import quote
from typing import Any
from zoneinfo import ZoneInfo

from app.common.webDisplayTime import formatIso8601ForWeb
from app.common.webDisplayTime import formatTimestampFieldsDeepCopy


def buildAdminRunNavQuery(in_runsScope: str, in_raw: bool = False) -> str:
    parts: list[str] = []
    if in_runsScope == "all":
        parts.append("scope=all")
    if in_raw is True:
        parts.append("raw=1")
    ret = ""
    if len(parts) > 0:
        ret = "?" + "&".join(parts)
    return ret


def _renderLayout(in_title: str, in_content: str, in_showNav: bool = True) -> str:
    ret: str
    navBlock = _renderNav() if in_showNav else ""
    ret = (
        "<!doctype html>"
        "<html><head>"
        f"<title>{html.escape(in_title)}</title>"
        "<link rel='icon' href='/favicon.ico?v=1' type='image/x-icon' />"
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
        ".scroll-pre{max-height:min(70vh,560px);overflow:auto;}"
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


def _renderModelStatsSection(in_snapshot: Any, in_displayZone: ZoneInfo) -> str:
    ret = ""
    if isinstance(in_snapshot, dict) is True:
        totalsValue = in_snapshot.get("totals")
        if isinstance(totalsValue, dict) is False:
            totalsValue = {}
        modelsList = in_snapshot.get("models")
        if isinstance(modelsList, list) is False:
            modelsList = []
        updatedAtRaw = str(in_snapshot.get("updatedAt", "") or "").strip()
        if updatedAtRaw != "":
            updatedAt = formatIso8601ForWeb(in_value=updatedAtRaw, in_zone=in_displayZone)
        else:
            updatedAt = ""

        rowsHtmlParts: list[str] = []
        rowsHtmlParts.append(
            "<tr>"
            "<td><strong>Итого</strong></td>"
            f"<td>{html.escape(str(totalsValue.get('calls', 0)))}</td>"
            f"<td>{html.escape(str(totalsValue.get('success', 0)))}</td>"
            f"<td>{html.escape(str(totalsValue.get('errors', 0)))}</td>"
            f"<td>{html.escape(str(totalsValue.get('promptTokens', 0)))}</td>"
            f"<td>{html.escape(str(totalsValue.get('completionTokens', 0)))}</td>"
            f"<td>{html.escape(str(totalsValue.get('totalTokens', 0)))}</td>"
            "<td></td>"
            "</tr>"
        )
        for row in modelsList:
            if isinstance(row, dict) is False:
                continue
            rowsHtmlParts.append(
                "<tr>"
                f"<td>{html.escape(str(row.get('modelName', '')))}</td>"
                f"<td>{html.escape(str(row.get('calls', 0)))}</td>"
                f"<td>{html.escape(str(row.get('success', 0)))}</td>"
                f"<td>{html.escape(str(row.get('errors', 0)))}</td>"
                f"<td>{html.escape(str(row.get('promptTokens', 0)))}</td>"
                f"<td>{html.escape(str(row.get('completionTokens', 0)))}</td>"
                f"<td>{html.escape(str(row.get('totalTokens', 0)))}</td>"
                f"<td>{html.escape(str(row.get('lastErrorCode', '')))}</td>"
                "</tr>"
            )
        rowsHtml = "".join(rowsHtmlParts)
        metaLine = (
            f"<p class='muted' style='margin:0 0 8px 0;'>Обновлено: {html.escape(updatedAt)}</p>"
            if updatedAt
            else "<p class='muted' style='margin:0 0 8px 0;'>Обновлено: —</p>"
        )
        ret = (
            "<div class='card col12'>"
            "<h3 style='margin:0 0 8px 0;'>Статистика LLM (provider)</h3>"
            f"{metaLine}"
            "<p class='muted' style='margin:0 0 8px 0;'>"
            "Счётчики обновляются после каждого HTTP-вызова к провайдеру. "
            "Токены берутся из поля <span class='muted'>usage</span> ответа (prompt / completion / total)."
            "</p>"
            "<table>"
            "<thead><tr>"
            "<th>Модель</th><th>Вызовы</th><th>Успехи</th><th>Ошибки</th>"
            "<th>Токены (prompt)</th><th>Токены (completion)</th><th>Токены (total)</th><th>Последняя ошибка</th>"
            "</tr></thead>"
            f"<tbody>{rowsHtml}</tbody>"
            "</table>"
            "</div>"
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
        "<a href='/memory/long-term'>Memory</a>"
        "<a href='/users'>Users</a>"
        "<a href='/config/tools'>Tool config</a>"
        "<a href='/config/schedules'>Schedules config</a>"
        "<a href='/git/status'>Git Status</a>"
        "<a href='/git/diff'>Git Diff</a>"
        "<form method='post' action='/logout' style='margin:0;'>"
        "<button class='btn' type='submit'>Выйти</button>"
        "</form>"
        "</div>"
        "</div>"
    )
    return ret


def renderLongTermMemoryPage(
    in_path: str,
    in_contentText: str,
    in_maxChars: int,
    in_truncated: bool,
) -> str:
    ret: str
    truncatedNote = (
        "<p class='warning'>Показан усечённый вывод (truncated).</p>"
        if in_truncated is True
        else ""
    )
    content = (
        "<h1 class='title'>Long-term memory</h1>"
        f"<p class='muted'>Файл: {html.escape(in_path)}</p>"
        f"<p class='muted'>maxChars: {html.escape(str(in_maxChars))}</p>"
        f"{truncatedNote}"
        f"<pre>{html.escape(in_contentText)}</pre>"
    )
    ret = _renderLayout(in_title="Long-term memory", in_content=content, in_showNav=True)
    return ret


def renderIndexPage(in_stats: dict[str, Any], in_displayZone: ZoneInfo) -> str:
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
    runs_scope_hint_text = str(in_stats.get("adminRunsScopeHint", "") or "").strip()
    runs_scope_hint_html = (
        f"<p class='muted' style='margin:10px 0 0 0;font-size:14px;line-height:1.45;'>"
        f"{html.escape(runs_scope_hint_text)}"
        "</p>"
        if runs_scope_hint_text != ""
        else ""
    )
    content = (
        "<h1 class='title'>simple-ai-agent-bot</h1>"
        "<p class='muted' style='margin-top:0;'>Admin dashboard</p>"
        f"<div class='row'>{badge}<span class='muted'>security.adminWritesEnabled</span></div>"
        f"{runs_scope_hint_html}"
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
        f"{_renderModelStatsSection(in_snapshot=in_stats.get('modelStats'), in_displayZone=in_displayZone)}"
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


def renderLogsPage(in_logItems: list[Any], in_displayZone: ZoneInfo) -> str:
    ret: str
    renderedItems = []
    for oneItem in in_logItems:
        if isinstance(oneItem, dict) is True:
            logDict = dict(oneItem)
            tsValue = logDict.get("timestamp")
            if isinstance(tsValue, str) is True:
                logDict["timestamp"] = formatIso8601ForWeb(
                    in_value=tsValue,
                    in_zone=in_displayZone,
                )
            lineText = json.dumps(logDict, ensure_ascii=False)
        else:
            lineText = str(oneItem)
        renderedItems.append(f"<pre>{html.escape(lineText)}</pre>")
    content = (
        "<h1 class='title'>Run Logs</h1>"
        f"<p class='muted'>Показаны последние {len(in_logItems)} записей.</p>"
        + ("".join(renderedItems) if renderedItems else "<p>Логи пока отсутствуют.</p>")
    )
    ret = _renderLayout(in_title="Logs", in_content=content, in_showNav=True)
    return ret


def renderRunsPage(
    in_runItems: list[Any],
    in_displayZone: ZoneInfo,
    in_adminRunsScopeHint: str = "",
    in_runsScope: str = "admin",
    in_limit: int = 50,
    in_offset: int = 0,
) -> str:
    ret: str
    rows = []
    scope_query = buildAdminRunNavQuery(in_runsScope, False)
    for runItem in in_runItems:
        runId = str(runItem.get("runId", "unknown"))
        sessionId = str(runItem.get("sessionId", ""))
        status = str(runItem.get("runStatus", ""))
        reason = str(runItem.get("completionReason", ""))
        createdAtRaw = str(runItem.get("createdAt", "")).strip()
        if createdAtRaw != "":
            createdAt = formatIso8601ForWeb(in_value=createdAtRaw, in_zone=in_displayZone)
        else:
            createdAt = ""
        rows.append(
            "<tr>"
            f"<td><a href='/runs/{html.escape(runId)}{scope_query}'>{html.escape(runId)}</a></td>"
            f"<td>{html.escape(sessionId)}</td>"
            f"<td>{html.escape(status)}</td>"
            f"<td>{html.escape(reason)}</td>"
            f"<td>{html.escape(createdAt)}</td>"
            "</tr>"
        )
    bodyRows = "".join(rows) if rows else "<tr><td colspan='5'>Запусков пока нет.</td></tr>"
    scope_hint_block = ""
    if str(in_adminRunsScopeHint or "").strip() != "":
        scope_hint_block = (
            f"<p class='muted' style='margin:0 0 12px 0;font-size:14px;line-height:1.45;'>"
            f"{html.escape(str(in_adminRunsScopeHint).strip())}"
            "</p>"
        )
    admin_selected = " selected" if in_runsScope != "all" else ""
    all_selected = " selected" if in_runsScope == "all" else ""
    scope_form = (
        "<form method='get' class='row' style='align-items:center;gap:10px;flex-wrap:wrap;margin:0 0 14px 0;'>"
        "<label for='runs_scope_select' class='muted'>Показать:</label>"
        "<select class='btn' name='scope' id='runs_scope_select' onchange='this.form.submit()'>"
        f"<option value='admin'{admin_selected}>только tenant админа</option>"
        f"<option value='all'{all_selected}>все sessionId</option>"
        "</select>"
        f"<input type='hidden' name='limit' value='{html.escape(str(in_limit))}' />"
        f"<input type='hidden' name='offset' value='{html.escape(str(in_offset))}' />"
        "</form>"
    )
    content = (
        "<h1 class='title'>Runs</h1>"
        f"{scope_form}"
        f"{scope_hint_block}"
        f"<p class='muted'>Показаны последние {len(in_runItems)} запусков.</p>"
        "<table>"
        "<thead><tr><th>runId</th><th>sessionId</th><th>status</th>"
        "<th>completionReason</th><th>createdAt</th></tr></thead>"
        f"<tbody>{bodyRows}</tbody>"
        "</table>"
    )
    ret = _renderLayout(in_title="Runs", in_content=content, in_showNav=True)
    return ret


_RUN_DETAILS_PRE_MAX = 24000


def _truncateForAdminPre(in_text: str, in_maxChars: int) -> tuple[str, bool]:
    ret: tuple[str, bool]
    textValue = str(in_text or "")
    if len(textValue) <= in_maxChars:
        ret = (textValue, False)
        return ret
    ret = (textValue[:in_maxChars] + "\n\n… [truncated]", True)
    return ret


def _jsonPreEscaped(in_value: Any, in_maxChars: int) -> str:
    ret: str
    try:
        rawText = json.dumps(in_value, ensure_ascii=False, indent=2)
    except TypeError:
        rawText = str(in_value)
    bodyText, didTruncate = _truncateForAdminPre(in_text=rawText, in_maxChars=in_maxChars)
    truncNote = "<p class='warning'>Показано усечённо.</p>" if didTruncate is True else ""
    ret = f"{truncNote}<pre class='scroll-pre'>{html.escape(bodyText)}</pre>"
    return ret


def _renderStructuredRunDetailsContent(
    in_runId: str,
    in_runDict: dict[str, Any],
    in_runs_scope: str = "admin",
) -> str:
    ret: str
    timingDict = in_runDict.get("timing")
    if isinstance(timingDict, dict) is False:
        timingDict = {}
    execMs = timingDict.get("executionDurationMs", "")
    stepCount = timingDict.get("stepCount", "")
    toolCallCount = timingDict.get("toolCallCount", "")
    traceId = str(in_runDict.get("traceId", "") or "")
    sessionId = str(in_runDict.get("sessionId", "") or "")
    sourceType = str(in_runDict.get("sourceType", "") or "")
    runStatus = str(in_runDict.get("runStatus", "") or "")
    completionReason = str(in_runDict.get("completionReason", "") or "")
    selectedModel = str(in_runDict.get("selectedModel", "") or "")
    createdAt = str(in_runDict.get("createdAt", "") or "")
    finishedAt = str(in_runDict.get("finishedAt", "") or "")
    inputMessage = str(in_runDict.get("inputMessage", "") or "")
    finalAnswer = str(in_runDict.get("finalAnswer", "") or "")
    selectedSkills = in_runDict.get("selectedSkills", [])
    skillsText = ""
    if isinstance(selectedSkills, list) and len(selectedSkills) > 0:
        skillsListItems = []
        for skillId in selectedSkills:
            skillsListItems.append(f"<li>{html.escape(str(skillId))}</li>")
        skillsText = "<ul>" + "".join(skillsListItems) + "</ul>"
    else:
        skillsText = "<p class='muted'>—</p>"
    routingSource = str(in_runDict.get("routingSource", "") or "")
    routingParseErrorCode = str(in_runDict.get("routingParseErrorCode", "") or "")
    routingParseErrorMessage = str(in_runDict.get("routingParseErrorMessage", "") or "")
    routingFallbackReason = str(in_runDict.get("routingFallbackReason", "") or "")
    routingPlan = in_runDict.get("routingPlan")
    routingDiagnostics = in_runDict.get("routingDiagnostics")
    routingRawModelResponse = str(in_runDict.get("routingRawModelResponse", "") or "")
    routingPromptSnapshot = str(in_runDict.get("routingPromptSnapshot", "") or "")
    toolCallsList = in_runDict.get("toolCalls", [])
    if isinstance(toolCallsList, list) is False:
        toolCallsList = []
    toolRows: list[str] = []
    indexValue = 0
    for callItem in toolCallsList:
        indexValue += 1
        if isinstance(callItem, dict) is False:
            toolRows.append(
                "<tr>"
                f"<td>{html.escape(str(indexValue))}</td>"
                "<td colspan='2'><span class='muted'>invalid toolCall shape</span></td>"
                "</tr>"
            )
            continue
        toolName = str(callItem.get("toolName", "") or "")
        argsValue = callItem.get("args")
        try:
            argsJsonFull = json.dumps(argsValue, ensure_ascii=False)
        except TypeError:
            argsJsonFull = str(argsValue)
        argsPretty = argsJsonFull[:500] + ("…" if len(argsJsonFull) > 500 else "")
        toolRows.append(
            "<tr>"
            f"<td>{html.escape(str(indexValue))}</td>"
            f"<td>{html.escape(toolName)}</td>"
            f"<td><code>{html.escape(argsPretty)}</code></td>"
            "</tr>"
        )
    toolTableBody = "".join(toolRows) if toolRows else "<tr><td colspan='3' class='muted'>Нет вызовов</td></tr>"
    toolResultsList = in_runDict.get("toolResults", [])
    if isinstance(toolResultsList, list) is False:
        toolResultsList = []
    resultRows: list[str] = []
    indexResult = 0
    for resultItem in toolResultsList:
        indexResult += 1
        if isinstance(resultItem, dict) is False:
            resultRows.append(
                "<tr>"
                f"<td>{html.escape(str(indexResult))}</td>"
                "<td colspan='3'><span class='muted'>invalid result</span></td>"
                "</tr>"
            )
            continue
        toolNameR = str(resultItem.get("tool_name", "") or "")
        okFlag = bool(resultItem.get("ok", False))
        okLabel = "ok" if okFlag is True else "fail"
        badgeClass = "badge-ok" if okFlag is True else "badge-bad"
        dataRaw = resultItem.get("data")
        dataHint = ""
        if dataRaw is None:
            dataHint = "—"
        else:
            dataStr = str(dataRaw)
            dataHint = f"{len(dataStr)} символов"
        resultRows.append(
            "<tr>"
            f"<td>{html.escape(str(indexResult))}</td>"
            f"<td>{html.escape(toolNameR)}</td>"
            f"<td><span class='badge {badgeClass}'>{html.escape(okLabel)}</span></td>"
            f"<td>{html.escape(dataHint)}</td>"
            "</tr>"
        )
    resultsTableBody = (
        "".join(resultRows) if resultRows else "<tr><td colspan='4' class='muted'>Нет результатов</td></tr>"
    )
    observationsList = in_runDict.get("observations", [])
    obsCount = len(observationsList) if isinstance(observationsList, list) else 0
    rawResponses = in_runDict.get("rawModelResponses", [])
    rawRespCount = len(rawResponses) if isinstance(rawResponses, list) else 0
    memoryCandidates = in_runDict.get("memoryCandidates", [])
    memBlock = ""
    if isinstance(memoryCandidates, list) and len(memoryCandidates) > 0:
        memItems = "".join(f"<li>{html.escape(str(x))}</li>" for x in memoryCandidates)
        memBlock = f"<ul>{memItems}</ul>"
    else:
        memBlock = "<p class='muted'>—</p>"
    finalAnswerBody, finalTrunc = _truncateForAdminPre(
        in_text=finalAnswer, in_maxChars=_RUN_DETAILS_PRE_MAX
    )
    finalNote = "<p class='warning'>Показано усечённо.</p>" if finalTrunc is True else ""
    runEscaped = html.escape(in_runId)
    nav_query = buildAdminRunNavQuery(in_runs_scope, False)
    raw_query = buildAdminRunNavQuery(in_runs_scope, True)
    ret = (
        f"<h1 class='title'>Run {runEscaped}</h1>"
        "<p class='row'>"
        f"<a href='/runs/{runEscaped}/steps{nav_query}'>Шаги agent loop</a>"
        "<span class='muted'> · </span>"
        f"<a href='/runs/{runEscaped}{raw_query}'>Сырой JSON</a>"
        "</p>"
        "<div class='card' style='margin-top:12px;'>"
        "<h3 style='margin:0 0 10px 0;'>Обзор</h3>"
        f"<div class='kv'><div class='k'>traceId</div><div class='v'>{html.escape(traceId)}</div></div>"
        f"<div class='kv'><div class='k'>sessionId</div><div class='v'>{html.escape(sessionId)}</div></div>"
        f"<div class='kv'><div class='k'>sourceType</div><div class='v'>{html.escape(sourceType)}</div></div>"
        f"<div class='kv'><div class='k'>runStatus</div><div class='v'>{html.escape(runStatus)}</div></div>"
        f"<div class='kv'><div class='k'>completionReason</div><div class='v'>{html.escape(completionReason)}</div></div>"
        f"<div class='kv'><div class='k'>selectedModel</div><div class='v'>{html.escape(selectedModel)}</div></div>"
        f"<div class='kv'><div class='k'>createdAt</div><div class='v'>{html.escape(createdAt)}</div></div>"
        f"<div class='kv'><div class='k'>finishedAt</div><div class='v'>{html.escape(finishedAt)}</div></div>"
        f"<div class='kv'><div class='k'>executionDurationMs</div><div class='v'>{html.escape(str(execMs))}</div></div>"
        f"<div class='kv'><div class='k'>stepCount</div><div class='v'>{html.escape(str(stepCount))}</div></div>"
        f"<div class='kv'><div class='k'>toolCallCount (loop)</div><div class='v'>{html.escape(str(toolCallCount))}</div></div>"
        "</div>"
        "<div class='card' style='margin-top:12px;'>"
        "<h3 style='margin:0 0 10px 0;'>Ввод пользователя</h3>"
        f"<pre class='scroll-pre'>{html.escape(inputMessage)}</pre>"
        "</div>"
        "<div class='card' style='margin-top:12px;'>"
        "<h3 style='margin:0 0 10px 0;'>Skills</h3>"
        f"{skillsText}"
        "</div>"
        "<div class='card' style='margin-top:12px;'>"
        "<h3 style='margin:0 0 10px 0;'>Маршрутизация</h3>"
        f"<div class='kv'><div class='k'>routingSource</div><div class='v'>{html.escape(routingSource)}</div></div>"
        f"<div class='kv'><div class='k'>routingParseErrorCode</div><div class='v'>{html.escape(routingParseErrorCode)}</div></div>"
        f"<div class='kv'><div class='k'>routingParseErrorMessage</div><div class='v'>{html.escape(routingParseErrorMessage)}</div></div>"
        f"<div class='kv'><div class='k'>routingFallbackReason</div><div class='v'>{html.escape(routingFallbackReason)}</div></div>"
        "<details><summary>routingPlan</summary>"
        f"{_jsonPreEscaped(in_value=routingPlan, in_maxChars=_RUN_DETAILS_PRE_MAX)}"
        "</details>"
        "<details><summary>routingDiagnostics</summary>"
        f"{_jsonPreEscaped(in_value=routingDiagnostics, in_maxChars=_RUN_DETAILS_PRE_MAX)}"
        "</details>"
        "<details><summary>routingRawModelResponse</summary>"
        f"<pre class='scroll-pre'>{html.escape(_truncateForAdminPre(in_text=routingRawModelResponse, in_maxChars=_RUN_DETAILS_PRE_MAX)[0])}</pre>"
        "</details>"
        "<details><summary>routingPromptSnapshot</summary>"
        f"<pre class='scroll-pre'>{html.escape(_truncateForAdminPre(in_text=routingPromptSnapshot, in_maxChars=_RUN_DETAILS_PRE_MAX)[0])}</pre>"
        "</details>"
        "</div>"
        "<div class='card' style='margin-top:12px;'>"
        "<h3 style='margin:0 0 10px 0;'>Финальный ответ</h3>"
        f"{finalNote}"
        f"<pre class='scroll-pre'>{html.escape(finalAnswerBody)}</pre>"
        "</div>"
        "<div class='card' style='margin-top:12px;'>"
        "<h3 style='margin:0 0 10px 0;'>Вызовы инструментов</h3>"
        "<table>"
        "<thead><tr><th>#</th><th>tool</th><th>args</th></tr></thead>"
        f"<tbody>{toolTableBody}</tbody>"
        "</table>"
        "</div>"
        "<div class='card' style='margin-top:12px;'>"
        "<h3 style='margin:0 0 10px 0;'>Результаты инструментов</h3>"
        "<table>"
        "<thead><tr><th>#</th><th>tool</th><th>ok</th><th>data</th></tr></thead>"
        f"<tbody>{resultsTableBody}</tbody>"
        "</table>"
        "</div>"
        "<div class='card' style='margin-top:12px;'>"
        "<h3 style='margin:0 0 10px 0;'>Наблюдения и ответы модели</h3>"
        f"<div class='kv'><div class='k'>observations (шаги)</div><div class='v'>{html.escape(str(obsCount))} записей — полный текст в «Шаги agent loop»</div></div>"
        f"<div class='kv'><div class='k'>rawModelResponses</div><div class='v'>{html.escape(str(rawRespCount))} шт.</div></div>"
        "</div>"
        "<div class='card' style='margin-top:12px;'>"
        "<h3 style='margin:0 0 10px 0;'>Кандидаты в память</h3>"
        f"{memBlock}"
        "</div>"
        "<div class='card' style='margin-top:12px;'>"
        "<h3 style='margin:0 0 10px 0;'>Крупные артефакты</h3>"
        "<details><summary>effectiveConfigSnapshot</summary>"
        f"{_jsonPreEscaped(in_value=in_runDict.get('effectiveConfigSnapshot'), in_maxChars=_RUN_DETAILS_PRE_MAX)}"
        "</details>"
        "<details><summary>promptSnapshot (полный промпт последнего шага / агрегат)</summary>"
        f"<pre class='scroll-pre'>{html.escape(_truncateForAdminPre(in_text=str(in_runDict.get('promptSnapshot', '') or ''), in_maxChars=_RUN_DETAILS_PRE_MAX)[0])}</pre>"
        "</details>"
        "<details><summary>parsedResponses (JSON)</summary>"
        f"{_jsonPreEscaped(in_value=in_runDict.get('parsedResponses'), in_maxChars=_RUN_DETAILS_PRE_MAX)}"
        "</details>"
        "<details><summary>rawModelResponses (список)</summary>"
        f"{_jsonPreEscaped(in_value=in_runDict.get('rawModelResponses'), in_maxChars=_RUN_DETAILS_PRE_MAX)}"
        "</details>"
        "<details><summary>fallbackEvents</summary>"
        f"{_jsonPreEscaped(in_value=in_runDict.get('fallbackEvents'), in_maxChars=_RUN_DETAILS_PRE_MAX)}"
        "</details>"
        "</div>"
    )
    return ret


def renderRunDetailsPage(
    in_runId: str,
    in_runItem: dict[str, Any],
    in_displayZone: ZoneInfo,
    in_rawView: bool = False,
    in_runsScope: str = "admin",
) -> str:
    ret: str
    displayRunItem = formatTimestampFieldsDeepCopy(in_value=in_runItem, in_zone=in_displayZone)
    if isinstance(displayRunItem, dict) is False:
        displayRunItem = in_runItem
    runDict: dict[str, Any]
    if isinstance(displayRunItem, dict) is True:
        runDict = displayRunItem
    elif isinstance(in_runItem, dict) is True:
        runDict = in_runItem
    else:
        runDict = {}
    if in_rawView is True:
        prettyJson = json.dumps(runDict, ensure_ascii=False, indent=2)
        runEscaped = html.escape(in_runId)
        scope_only_query = buildAdminRunNavQuery(in_runsScope, False)
        content = (
            f"<h1 class='title'>Run {runEscaped} — сырой JSON</h1>"
            "<p class='row'>"
            f"<a href='/runs/{runEscaped}{scope_only_query}'>Структурированный вид</a>"
            "<span class='muted'> · </span>"
            f"<a href='/runs/{runEscaped}/steps{scope_only_query}'>Шаги agent loop</a>"
            "</p>"
            f"<pre class='scroll-pre'>{html.escape(prettyJson)}</pre>"
        )
        ret = _renderLayout(in_title="Run Details (raw)", in_content=content, in_showNav=True)
        return ret
    structuredContent = _renderStructuredRunDetailsContent(
        in_runId=in_runId,
        in_runDict=runDict,
        in_runs_scope=in_runsScope,
    )
    ret = _renderLayout(in_title="Run Details", in_content=structuredContent, in_showNav=True)
    return ret


def renderRunStepsPage(
    in_runId: str,
    in_stepItems: list[dict[str, Any]],
    in_runsScope: str = "admin",
) -> str:
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
    back_query = buildAdminRunNavQuery(in_runsScope, False)
    content = (
        f"<h1 class='title'>Run {html.escape(in_runId)} — Agentic Loop Steps</h1>"
        f"<p><a href='/runs/{html.escape(in_runId)}{back_query}'>Назад к обзору run</a></p>"
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


def renderSchedulesConfigViewPage(
    in_schedulesYamlText: str,
    in_schedulesPath: str,
) -> str:
    ret: str
    content = (
        "<h1 class='title'>Scheduler settings (schedules.yaml)</h1>"
        "<p class='muted'>Read-only preview текущего scheduler-конфига.</p>"
        f"<p class='muted'>Path: {html.escape(in_schedulesPath)}</p>"
        f"<pre>{html.escape(in_schedulesYamlText)}</pre>"
    )
    ret = _renderLayout(in_title="Schedules Config", in_content=content, in_showNav=True)
    return ret


def renderTelegramUsersPage(
    in_user_rows_html: str,
    in_registry_path_text: str,
    in_notice_ok_text: str,
    in_notice_error_text: str,
    in_writes_enabled: bool,
) -> str:
    badge = (
        "<span class='badge badge-ok'>writes enabled</span>"
        if in_writes_enabled is True
        else "<span class='badge badge-warn'>read-only</span>"
    )
    noticeOk = ""
    if str(in_notice_ok_text or "").strip() != "":
        noticeOk = f"<p class='badge badge-ok' style='margin:0 0 12px 0;'>{html.escape(in_notice_ok_text)}</p>"
    noticeErr = ""
    if str(in_notice_error_text or "").strip() != "":
        noticeErr = f"<p class='danger' style='margin:0 0 12px 0;'>{html.escape(in_notice_error_text)}</p>"
    disabled_form = ""
    writes_disabled_tip = ""
    if in_writes_enabled is False:
        disabled_form = "disabled"
        writes_disabled_tip = (
            "<p class='muted'>Создание пользователей отключено (<code>security.adminWritesEnabled</code>)."
            "</p>"
        )
    input_style = (
        "padding:8px 10px;border:1px solid #2c3a63;border-radius:10px;"
        "background:#0e1529;color:#e8ecf6;min-width:220px;"
    )
    content = (
        "<h1 class='title'>Пользователи Telegram</h1>"
        f"<div class='row'>{badge}</div>"
        f"<p class='muted'>Общий реестр: <code>{html.escape(in_registry_path_text)}</code></p>"
        f"{writes_disabled_tip}"
        f"{noticeOk}{noticeErr}"
        "<div class='col12'><h2 class='muted' style='font-size:16px;margin:16px 0 8px 0;'>Новый пользователь</h2>"
        "<form method='post' action='/users/create' style='margin-bottom:20px;'>"
        "<div class='row' style='margin-bottom:8px;'><label><span class='muted'>Telegram ID</span><br />"
        f"<input type='number' min='1' name='telegram_user_id' required {disabled_form} "
        f"style='{input_style}' /></label></div>"
        "<div class='row' style='margin-bottom:8px;'><label><span class='muted'>Отображаемое имя (необязательно)"
        "</span><br />"
        f"<input type='text' name='display_name' {disabled_form} style='{input_style};min-width:320px;' />"
        "</label></div>"
        "<div class='row' style='margin-bottom:8px;'><label><span class='muted'>Заметка (необязательно)"
        "</span><br />"
        f"<input type='text' name='note' {disabled_form} style='{input_style};min-width:320px;' />"
        "</label></div>"
        f"<button class='btn' type='submit' {disabled_form}>Создать</button>"
        "</form></div>"
        "<h2 class='muted' style='font-size:16px;margin:16px 0 8px 0;'>Зарегистрированные в реестре</h2>"
        "<table><thead><tr><th>Telegram ID</th><th>Имя</th><th>Создан</th><th>Заметка</th>"
        "</tr></thead>"
        f"<tbody>{in_user_rows_html}</tbody></table>"
    )
    ret = _renderLayout(in_title="Telegram Users", in_content=content, in_showNav=True)
    return ret
