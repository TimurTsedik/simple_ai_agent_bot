from app.tools.implementations.digestTelegramNewsTool import DigestTelegramNewsTool


def testDigestToolFiltersByChannelKeywordAndDate() -> None:
    htmlByChannel = {
        "https://t.me/s/channel_one": """
        <div data-post="channel_one/10">
          <time datetime="2023-11-15T00:15:00+00:00"></time>
          <div class="tgme_widget_message_text js-message_text">AI release from channel one</div>
        </div>
        """,
        "https://t.me/s/channel_two": """
        <div data-post="channel_two/11">
          <time datetime="2023-11-15T00:16:00+00:00"></time>
          <div class="tgme_widget_message_text js-message_text">Unrelated message</div>
        </div>
        """,
    }
    tool = DigestTelegramNewsTool(
        getDigestChannelUsernames=lambda: ["channel_one", "channel_two"],
        getDefaultKeywords=lambda: [],
        fetchHtmlCallable=lambda in_url, _in_timeout: htmlByChannel[in_url],
    )

    result = tool.execute(
        in_args={
            "keywords": ["ai"],
            "sinceUnixTs": 1700000000,
            "maxItems": 5,
        },
        in_memoryPrincipalId="telegramUser:1",
    )

    assert result["count"] == 1
    assert result["items"][0]["channel"] == "channel_one"
    assert result["items"][0]["link"] == "https://t.me/channel_one/10"


def testDigestToolUsesDefaultKeywordsWhenRequestKeywordsEmpty() -> None:
    htmlPage = """
    <div data-post="cbrstocks/20">
      <time datetime="2023-11-15T03:00:00+00:00"></time>
      <div class="tgme_widget_message_text js-message_text">Минфин и ОФЗ: новое размещение</div>
    </div>
    <div data-post="cbrstocks/21">
      <time datetime="2023-11-15T03:01:00+00:00"></time>
      <div class="tgme_widget_message_text js-message_text">Погода в городе</div>
    </div>
    """
    tool = DigestTelegramNewsTool(
        getDigestChannelUsernames=lambda: ["cbrstocks"],
        getDefaultKeywords=lambda: ["офз", "минфин"],
        fetchHtmlCallable=lambda _in_url, _in_timeout: htmlPage,
    )

    result = tool.execute(
        in_args={
            "keywords": [],
            "sinceUnixTs": 1700000000,
            "maxItems": 10,
        },
        in_memoryPrincipalId="telegramUser:1",
    )

    assert result["count"] == 1
    assert "ОФЗ" in result["items"][0]["summary"]
    assert result["items"][0]["link"] == "https://t.me/cbrstocks/20"


def testDigestToolUsesTodayStartWhenSinceIsZero() -> None:
    htmlPage = """
    <div data-post="markettwits/30">
      <time datetime="1970-01-01T00:01:39+00:00"></time>
      <div class="tgme_widget_message_text js-message_text">РФ рынок</div>
    </div>
    <div data-post="markettwits/31">
      <time datetime="1970-01-01T00:01:41+00:00"></time>
      <div class="tgme_widget_message_text js-message_text">РФ рынок сегодня</div>
    </div>
    """
    tool = DigestTelegramNewsTool(
        getDigestChannelUsernames=lambda: ["markettwits"],
        getDefaultKeywords=lambda: ["рф"],
        todayStartUnixTsProvider=lambda: 100,
        fetchHtmlCallable=lambda _in_url, _in_timeout: htmlPage,
    )

    result = tool.execute(
        in_args={
            "keywords": [],
            "sinceUnixTs": 0,
            "maxItems": 10,
        },
        in_memoryPrincipalId="telegramUser:1",
    )

    assert result["count"] == 1
    assert result["items"][0]["dateUnixTs"] == "101"
    assert result["sinceUnixTsUsed"] == 100


def testDigestToolUsesSinceHoursWhenProvided() -> None:
    htmlPage = """
    <div data-post="markettwits/50">
      <time datetime="2026-04-26T09:00:00+00:00"></time>
      <div class="tgme_widget_message_text js-message_text">инфляция</div>
    </div>
    <div data-post="markettwits/51">
      <time datetime="2026-04-26T11:00:00+00:00"></time>
      <div class="tgme_widget_message_text js-message_text">инфляция снова</div>
    </div>
    """
    tool = DigestTelegramNewsTool(
        getDigestChannelUsernames=lambda: ["markettwits"],
        getDefaultKeywords=lambda: ["инфляция"],
        nowUnixTsProvider=lambda: 20000,
        fetchHtmlCallable=lambda _in_url, _in_timeout: htmlPage,
    )

    result = tool.execute(
        in_args={
            "keywords": [],
            "sinceHours": 1,
            "maxItems": 10,
        },
        in_memoryPrincipalId="telegramUser:1",
    )

    assert result["sinceUnixTsUsed"] == 16400
    assert result["count"] == 2


def testDigestToolMergesRequestedAndDefaultKeywords() -> None:
    htmlPage = """
    <div data-post="cbrstocks/100">
      <time datetime="2026-04-26T10:00:00+00:00"></time>
      <div class="tgme_widget_message_text js-message_text">ЦБ РФ обновил прогноз по инфляции</div>
    </div>
    """
    tool = DigestTelegramNewsTool(
        getDigestChannelUsernames=lambda: ["cbrstocks"],
        getDefaultKeywords=lambda: ["цб", "инфляция"],
        fetchHtmlCallable=lambda _in_url, _in_timeout: htmlPage,
    )

    result = tool.execute(
        in_args={
            "keywords": ["узкая фраза которой нет в посте"],
            "sinceUnixTs": 1700000000,
            "maxItems": 10,
        },
        in_memoryPrincipalId="telegramUser:1",
    )

    assert result["count"] == 1
    assert result["items"][0]["channel"] == "cbrstocks"
    assert result.get("channelErrors") == {}


def testDigestToolUsesFallbackPatternWhenPrimaryMissingTime() -> None:
    htmlPage = """
    <div data-post="cbrstocks/200">
      <div class="tgme_widget_message_text js-message_text">ЦБ РФ и инфляция</div>
      <time datetime="2026-04-26T12:00:00+00:00"></time>
    </div>
    """
    tool = DigestTelegramNewsTool(
        getDigestChannelUsernames=lambda: ["cbrstocks"],
        getDefaultKeywords=lambda: ["инфляция"],
        fetchHtmlCallable=lambda _in_url, _in_timeout: htmlPage,
    )

    result = tool.execute(
        in_args={
            "keywords": [],
            "sinceUnixTs": 1700000000,
            "maxItems": 10,
        },
        in_memoryPrincipalId="telegramUser:1",
    )

    assert result["count"] == 1
    assert "инфляция" in result["items"][0]["summary"].lower()


def testDigestToolUsesExplicitChannelsFromArgs() -> None:
    htmlByChannel = {
        "https://t.me/s/only_here": """
        <div data-post="only_here/1">
          <time datetime="2023-11-15T00:15:00+00:00"></time>
          <div class="tgme_widget_message_text js-message_text">alpha beta</div>
        </div>
        """,
        "https://t.me/s/other_ch": """
        <div data-post="other_ch/2">
          <time datetime="2023-11-15T00:16:00+00:00"></time>
          <div class="tgme_widget_message_text js-message_text">gamma delta</div>
        </div>
        """,
    }
    tool = DigestTelegramNewsTool(
        getDigestChannelUsernames=lambda: ["other_ch", "ignored_default"],
        getDefaultKeywords=lambda: [],
        fetchHtmlCallable=lambda in_url, _in_timeout: htmlByChannel[in_url],
    )

    result = tool.execute(
        in_args={
            "channels": ["@only_here"],
            "keywords": ["alpha"],
            "sinceUnixTs": 1700000000,
            "maxItems": 5,
        },
        in_memoryPrincipalId="telegramUser:1",
    )

    assert result["count"] == 1
    assert result["resolvedChannels"] == ["only_here"]
    assert result["items"][0]["channel"] == "only_here"


def testDigestToolUsesTopicSeedsForAiTopic() -> None:
    htmlPage = """
    <div data-post="ai_news/1">
      <time datetime="2023-11-15T01:00:00+00:00"></time>
      <div class="tgme_widget_message_text js-message_text">OpenAI released a new model today</div>
    </div>
    """
    tool = DigestTelegramNewsTool(
        getDigestChannelUsernames=lambda: ["ai_news"],
        getDefaultKeywords=lambda: [],
        fetchHtmlCallable=lambda _in_url, _in_timeout: htmlPage,
    )

    result = tool.execute(
        in_args={
            "topics": ["ai"],
            "keywords": [],
            "sinceUnixTs": 1700000000,
            "maxItems": 5,
        },
        in_memoryPrincipalId="telegramUser:1",
    )

    assert result["count"] == 1
    assert "openai" in result["items"][0]["summary"].lower()
    assert result["resolvedTopics"] == ["ai"]


def testDigestToolReportsInvalidChannelArgsAndFallsBackToConfig() -> None:
    htmlPage = """
    <div data-post="fallback_ch/1">
      <time datetime="2023-11-15T02:00:00+00:00"></time>
      <div class="tgme_widget_message_text js-message_text">keyword match</div>
    </div>
    """
    tool = DigestTelegramNewsTool(
        getDigestChannelUsernames=lambda: ["fallback_ch"],
        getDefaultKeywords=lambda: ["keyword"],
        fetchHtmlCallable=lambda _in_url, _in_timeout: htmlPage,
    )

    result = tool.execute(
        in_args={
            "channels": ["@@@", "bad name!"],
            "keywords": [],
            "sinceUnixTs": 1700000000,
            "maxItems": 5,
        },
        in_memoryPrincipalId="telegramUser:1",
    )

    assert "invalidChannelArgs" in result
    assert result["resolvedChannels"] == ["fallback_ch"]
    assert result["count"] == 1


def testDigestToolRecordsChannelFetchErrors() -> None:
    def failingFetch(in_url: str, in_timeout: int) -> str:
        _ = in_timeout
        if "bad_channel" in in_url:
            raise ConnectionError("network down")
        return (
            '<div data-post="ok_ch/1">'
            '<time datetime="2026-04-26T12:00:00+00:00"></time>'
            '<div class="tgme_widget_message_text">инфляция растёт</div></div>'
        )

    tool = DigestTelegramNewsTool(
        getDigestChannelUsernames=lambda: ["bad_channel", "ok_ch"],
        getDefaultKeywords=lambda: ["инфляция"],
        fetchHtmlCallable=failingFetch,
        todayStartUnixTsProvider=lambda: 0,
        fetchRetryDelaysSeconds=(0.01, 0.01),
        sleepCallable=lambda _s: None,
    )

    result = tool.execute(
        in_args={"keywords": [], "sinceUnixTs": 0, "maxItems": 10},
        in_memoryPrincipalId="telegramUser:1",
    )

    assert "bad_channel" in result.get("channelErrors", {})
    assert result["count"] >= 1


def testDigestToolDiagnosticsShowsKeywordFiltering() -> None:
    htmlPage = """
    <div data-post="larchanka/1">
      <time datetime="2026-04-29T10:00:00+00:00"></time>
      <div class="tgme_widget_message_text js-message_text">релиз продукта без ai-слов</div>
    </div>
    <div data-post="larchanka/2">
      <time datetime="2026-04-29T11:00:00+00:00"></time>
      <div class="tgme_widget_message_text js-message_text">еще один пост без seed-ключей</div>
    </div>
    """
    tool = DigestTelegramNewsTool(
        getDigestChannelUsernames=lambda: ["larchanka"],
        getDefaultKeywords=lambda: [],
        fetchHtmlCallable=lambda _in_url, _in_timeout: htmlPage,
    )

    result = tool.execute(
        in_args={
            "channels": ["@larchanka"],
            "topics": ["ai"],
            "keywords": [],
            "sinceUnixTs": 1,
            "maxItems": 10,
        },
        in_memoryPrincipalId="telegramUser:1",
    )
    diagnostics = result.get("diagnostics", {})

    assert result["count"] == 0
    assert diagnostics.get("totalParsedPosts") == 2
    assert diagnostics.get("filteredOutByKeywords") == 2
    assert diagnostics.get("returnedItemsCount") == 0


def testDigestToolDoesNotMixTextWithPreviousPostInPrimaryPattern() -> None:
    htmlPage = """
    <div class="tgme_widget_message_wrap" data-post="mix_ch/100">
      <time datetime="2026-04-29T10:00:00+00:00"></time>
      <div class="tgme_widget_message_photo_wrap">photo only without text block</div>
    </div>
    <div class="tgme_widget_message_wrap" data-post="mix_ch/101">
      <time datetime="2026-04-29T10:05:00+00:00"></time>
      <div class="tgme_widget_message_text js-message_text">keyword from second post</div>
    </div>
    """
    tool = DigestTelegramNewsTool(
        getDigestChannelUsernames=lambda: ["mix_ch"],
        getDefaultKeywords=lambda: ["keyword"],
        fetchHtmlCallable=lambda _in_url, _in_timeout: htmlPage,
    )

    result = tool.execute(
        in_args={
            "keywords": [],
            "sinceUnixTs": 1,
            "maxItems": 10,
        },
        in_memoryPrincipalId="telegramUser:1",
    )

    assert result["count"] == 1
    assert result["items"][0]["summary"] == "keyword from second post"
    assert result["items"][0]["link"] == "https://t.me/mix_ch/101"


def testDigestToolDoesNotMixTextWithPreviousPostInFallbackPattern() -> None:
    htmlPage = """
    <div class="tgme_widget_message_wrap" data-post="mix_fb/200">
      <div class="tgme_widget_message_photo_wrap">photo only without text block</div>
      <time datetime="2026-04-29T11:00:00+00:00"></time>
    </div>
    <div class="tgme_widget_message_wrap" data-post="mix_fb/201">
      <div class="tgme_widget_message_text js-message_text">fallback keyword in second post</div>
      <time datetime="2026-04-29T11:05:00+00:00"></time>
    </div>
    """
    tool = DigestTelegramNewsTool(
        getDigestChannelUsernames=lambda: ["mix_fb"],
        getDefaultKeywords=lambda: ["fallback keyword"],
        fetchHtmlCallable=lambda _in_url, _in_timeout: htmlPage,
    )

    result = tool.execute(
        in_args={
            "keywords": [],
            "sinceUnixTs": 1,
            "maxItems": 10,
        },
        in_memoryPrincipalId="telegramUser:1",
    )

    assert result["count"] == 1
    assert result["items"][0]["summary"] == "fallback keyword in second post"
    assert result["items"][0]["link"] == "https://t.me/mix_fb/201"
