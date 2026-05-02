from app.tools.implementations.webSearchTool import WebSearchTool


def testWebSearchToolParsesResultsAndFetchesPages() -> None:
    ddgHtml = """
    <div class="results_links results_links_deep web-result">
      <h2 class="result__title">
        <a class="result__a" href="https://example.com/a">Title A</a>
      </h2>
      <a class="result__snippet">Snippet A</a>
    </div></div>
    <div class="results_links results_links_deep web-result">
      <h2 class="result__title">
        <a class="result__a" href="https://example.com/b">Title B</a>
      </h2>
      <a class="result__snippet">Snippet B</a>
    </div></div>
    """
    pageHtmlA = "<html><body><h1>A</h1><p>hello</p></body></html>"
    pageHtmlB = "<html><body><h1>B</h1><p>world</p></body></html>"

    def fakeFetch(in_url: str, in_timeout: int) -> str:
        _ = in_timeout
        if "duckduckgo.com/html/" in in_url:
            return ddgHtml
        if in_url == "https://example.com/a":
            return pageHtmlA
        if in_url == "https://example.com/b":
            return pageHtmlB
        raise KeyError(in_url)

    tool = WebSearchTool(fetchHtmlCallable=fakeFetch)
    result = tool.execute(
        in_args={
            "query": "test query",
            "maxResults": 10,
            "fetchTopN": 2,
            "maxCharsPerPage": 8000,
        },
        in_memoryPrincipalId="telegramUser:1",
    )

    assert result["searchProvider"] == "duckduckgo_html"
    assert len(result["results"]) == 2
    assert result["results"][0]["url"] == "https://example.com/a"
    assert len(result["fetchedPages"]) == 2
    assert "hello" in result["fetchedPages"][0]["text"]


def testWebSearchToolBlocksLocalhostUrls() -> None:
    ddgHtml = """
    <div class="results_links results_links_deep web-result">
      <a class="result__a" href="http://localhost/secret">Bad</a>
      <a class="result__snippet">Snippet</a>
    </div></div>
    """

    def fakeFetch(in_url: str, in_timeout: int) -> str:
        _ = in_timeout
        if "duckduckgo.com/html/" in in_url:
            return ddgHtml
        raise KeyError(in_url)

    tool = WebSearchTool(fetchHtmlCallable=fakeFetch)

    result = tool.execute(
        in_args={"query": "x", "maxResults": 1, "fetchTopN": 1, "maxCharsPerPage": 8000},
        in_memoryPrincipalId="telegramUser:1",
    )
    assert len(result.get("blockedUrls", [])) == 1
    assert result["blockedUrls"][0]["url"] == "http://localhost/secret"
    assert len(result.get("fetchedPages", [])) == 0


def testWebSearchToolUnwrapsDdgRedirectUrls() -> None:
    ddgHtml = """
    <div class="results_links results_links_deep web-result">
      <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fa&rut=abc">A</a>
      <a class="result__snippet">Snippet</a>
    </div></div>
    """
    pageHtmlA = "<html><body><h1>A</h1><p>hello</p></body></html>"

    def fakeFetch(in_url: str, in_timeout: int) -> str:
        _ = in_timeout
        if "duckduckgo.com/html/" in in_url:
            return ddgHtml
        if in_url == "https://example.com/a":
            return pageHtmlA
        raise KeyError(in_url)

    tool = WebSearchTool(fetchHtmlCallable=fakeFetch)
    result = tool.execute(
        in_args={"query": "x", "maxResults": 1, "fetchTopN": 1, "maxCharsPerPage": 8000},
        in_memoryPrincipalId="telegramUser:1",
    )
    assert len(result.get("results", [])) == 1
    assert result["results"][0]["url"] == "https://example.com/a"
    assert len(result.get("fetchedPages", [])) == 1
    assert result["fetchedPages"][0]["url"] == "https://example.com/a"


def testWebSearchToolStopsFetchingOnDeadline() -> None:
    ddgHtml = """
    <div class="results_links results_links_deep web-result">
      <a class="result__a" href="https://example.com/a">A</a>
      <a class="result__snippet">Snippet</a>
    </div></div>
    <div class="results_links results_links_deep web-result">
      <a class="result__a" href="https://example.com/b">B</a>
      <a class="result__snippet">Snippet</a>
    </div></div>
    <div class="results_links results_links_deep web-result">
      <a class="result__a" href="https://example.com/c">C</a>
      <a class="result__snippet">Snippet</a>
    </div></div>
    """

    callCount: dict[str, int] = {"page": 0}

    def fakeFetch(in_url: str, in_timeout: int) -> str:
        _ = in_timeout
        if "duckduckgo.com/html/" in in_url:
            return ddgHtml
        callCount["page"] += 1
        # Simulate slow fetch by raising an error for later pages.
        if callCount["page"] >= 2:
            raise TimeoutError("slow")
        return "<html><body><p>ok</p></body></html>"

    tool = WebSearchTool(fetchHtmlCallable=fakeFetch)
    result = tool.execute(
        in_args={"query": "x", "maxResults": 3, "fetchTopN": 3, "maxCharsPerPage": 8000},
        in_memoryPrincipalId="telegramUser:1",
    )
    assert len(result.get("results", [])) == 3
    assert len(result.get("fetchedPages", [])) >= 1
    assert isinstance(result.get("meta", {}).get("maxTotalSeconds"), float)

