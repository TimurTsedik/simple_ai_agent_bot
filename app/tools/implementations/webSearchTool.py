from dataclasses import dataclass
import html
import ipaddress
import re
from typing import Any, Callable
from urllib.parse import parse_qs, quote_plus, unquote, urlparse
from time import monotonic

import requests


def _defaultFetchHtml(in_url: str, in_timeoutSeconds: int) -> str:
    ret: str
    response = requests.get(
        in_url,
        timeout=in_timeoutSeconds,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            )
        },
    )
    response.raise_for_status()
    response.encoding = response.encoding or "utf-8"
    ret = response.text
    return ret


def _isPrivateOrLocalHost(in_host: str) -> bool:
    ret: bool
    host = in_host.strip().lower()
    if host in {"localhost", "127.0.0.1", "::1"}:
        ret = True
    else:
        isIp = False
        try:
            ipValue = ipaddress.ip_address(host)
            isIp = True
        except ValueError:
            isIp = False
        if isIp is True:
            ret = bool(
                ipValue.is_private
                or ipValue.is_loopback
                or ipValue.is_link_local
                or ipValue.is_multicast
                or ipValue.is_reserved
            )
        else:
            ret = host.endswith(".local")
    return ret


def _validateHttpUrlOrRaise(in_url: str) -> None:
    parsed = urlparse(in_url)
    scheme = (parsed.scheme or "").lower()
    host = parsed.hostname or ""
    if scheme not in {"http", "https"}:
        raise PermissionError("Only http/https URLs are allowed.")
    if host == "":
        raise PermissionError("URL host is missing.")
    if _isPrivateOrLocalHost(in_host=host) is True:
        raise PermissionError("Localhost/private IP URLs are not allowed.")


def _normalizeAndUnwrapDdgUrl(in_url: str) -> str:
    ret: str
    urlValue = in_url.strip()
    if urlValue.startswith("//"):
        urlValue = "https:" + urlValue

    parsed = urlparse(urlValue)
    host = (parsed.hostname or "").lower()
    if host.endswith("duckduckgo.com") and parsed.path.startswith("/l/"):
        queryMap = parse_qs(parsed.query or "")
        uddgList = queryMap.get("uddg", [])
        if len(uddgList) > 0:
            candidate = unquote(str(uddgList[0]).strip())
            candidateParsed = urlparse(candidate)
            scheme = (candidateParsed.scheme or "").lower()
            if scheme in {"http", "https"}:
                ret = candidate
            else:
                ret = urlValue
        else:
            ret = urlValue
    else:
        ret = urlValue
    return ret


def _extractPlainText(in_html: str) -> str:
    ret: str
    noScripts = re.sub(r"<script[\\s\\S]*?</script>", " ", in_html, flags=re.IGNORECASE)
    noStyles = re.sub(r"<style[\\s\\S]*?</style>", " ", noScripts, flags=re.IGNORECASE)
    withoutTags = re.sub(r"<[^>]+>", " ", noStyles)
    unescaped = html.unescape(withoutTags)
    normalized = re.sub(r"\\s+", " ", unescaped).strip()
    ret = normalized
    return ret


def _parseDdgHtmlResults(in_htmlText: str, in_maxResults: int) -> list[dict[str, str]]:
    ret: list[dict[str, str]]
    results: list[dict[str, str]] = []

    # DuckDuckGo HTML endpoint typically uses result__a links and result__snippet.
    # We keep it regex-based to avoid extra deps and parse liberally.
    linkPattern = re.compile(
        r'<a[^>]*class="[^"]*result__a[^"]*"[^>]*href="(?P<href>[^"]+)"[^>]*>(?P<title>[\s\S]*?)</a>',
        re.IGNORECASE,
    )
    snippetPattern = re.compile(
        r'<a[^>]*class="[^"]*result__snippet[^"]*"[^>]*>(?P<snippet>[\s\S]*?)</a>',
        re.IGNORECASE,
    )

    for linkMatch in linkPattern.finditer(in_htmlText):
        if len(results) >= in_maxResults:
            break
        rawHref = html.unescape(linkMatch.group("href")).strip()
        href = _normalizeAndUnwrapDdgUrl(in_url=rawHref)
        titleText = _extractPlainText(linkMatch.group("title"))
        startIndex = linkMatch.end()
        windowHtml = in_htmlText[startIndex : startIndex + 3000]
        snippetText = ""
        snippetMatch = snippetPattern.search(windowHtml)
        if snippetMatch is not None:
            snippetText = _extractPlainText(snippetMatch.group("snippet"))
        results.append(
            {
                "title": titleText[:200],
                "url": href,
                "snippet": snippetText[:400],
            }
        )

    ret = results
    return ret


@dataclass
class WebSearchTool:
    fetchHtmlCallable: Callable[[str, int], str] = _defaultFetchHtml

    def execute(
        self,
        in_args: dict[str, Any],
        *,
        in_memoryPrincipalId: str,
    ) -> dict[str, Any]:
        ret: dict[str, Any]
        startedAt = monotonic()
        query = str(in_args.get("query", "")).strip()
        maxResults = int(in_args.get("maxResults", 10))
        fetchTopN = int(in_args.get("fetchTopN", 5))
        maxCharsPerPage = int(in_args.get("maxCharsPerPage", 8000))

        if query == "":
            raise ValueError("query must be non-empty")

        maxResults = min(max(1, maxResults), 10)
        fetchTopN = min(max(0, fetchTopN), 5)
        maxCharsPerPage = min(max(256, maxCharsPerPage), 200000)

        # Keep an internal deadline to avoid tool-level TIMEOUT in coordinator.
        # This makes the tool return partial results instead of timing out.
        maxTotalSeconds = 25.0
        deadlineMonotonic = startedAt + maxTotalSeconds

        def _remainingSeconds() -> float:
            retSeconds = deadlineMonotonic - monotonic()
            return retSeconds

        ddgUrl = f"https://duckduckgo.com/html/?q={quote_plus(query)}"
        remainingForSearch = _remainingSeconds()
        if remainingForSearch <= 0:
            remainingForSearch = 0.1
        searchTimeout = int(min(10.0, max(1.0, remainingForSearch)))
        searchHtml = self.fetchHtmlCallable(ddgUrl, searchTimeout)
        parsedResults = _parseDdgHtmlResults(
            in_htmlText=searchHtml,
            in_maxResults=maxResults,
        )

        fetchedPages: list[dict[str, str]] = []
        blockedUrls: list[dict[str, str]] = []
        fetchErrors: list[dict[str, str]] = []
        for oneResult in parsedResults[:fetchTopN]:
            if _remainingSeconds() <= 0:
                fetchErrors.append(
                    {"url": "", "error": "deadline_exceeded_before_fetch_topn"}
                )
                break
            urlValue = str(oneResult.get("url", "")).strip()
            if urlValue == "":
                continue
            try:
                _validateHttpUrlOrRaise(in_url=urlValue)
            except PermissionError as in_exc:
                blockedUrls.append({"url": urlValue, "reason": str(in_exc)})
                continue
            try:
                remainingForPage = _remainingSeconds()
                if remainingForPage <= 0:
                    fetchErrors.append({"url": urlValue, "error": "deadline_exceeded"})
                    break
                pageTimeout = int(min(10.0, max(1.0, remainingForPage)))
                pageHtml = self.fetchHtmlCallable(urlValue, pageTimeout)
                plainText = _extractPlainText(in_html=pageHtml)
                fetchedPages.append(
                    {
                        "url": urlValue,
                        "title": str(oneResult.get("title", ""))[:200],
                        "text": plainText[:maxCharsPerPage],
                    }
                )
            except Exception as in_exc:
                fetchErrors.append({"url": urlValue, "error": str(in_exc)})
                continue

        ret = {
            "query": query,
            "searchProvider": "duckduckgo_html",
            "results": parsedResults,
            "fetchedPages": fetchedPages,
            "blockedUrls": blockedUrls,
            "fetchErrors": fetchErrors,
            "meta": {
                "maxResults": maxResults,
                "fetchTopN": fetchTopN,
                "maxCharsPerPage": maxCharsPerPage,
                "maxTotalSeconds": maxTotalSeconds,
            },
        }
        return ret

