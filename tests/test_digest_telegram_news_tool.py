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
        digestChannelUsernames=["channel_one", "channel_two"],
        defaultKeywords=[],
        fetchHtmlCallable=lambda in_url, _in_timeout: htmlByChannel[in_url],
    )

    result = tool.execute(
        in_args={
            "keywords": ["ai"],
            "sinceUnixTs": 1700000000,
            "maxItems": 5,
        }
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
        digestChannelUsernames=["cbrstocks"],
        defaultKeywords=["офз", "минфин"],
        fetchHtmlCallable=lambda _in_url, _in_timeout: htmlPage,
    )

    result = tool.execute(
        in_args={
            "keywords": [],
            "sinceUnixTs": 1700000000,
            "maxItems": 10,
        }
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
        digestChannelUsernames=["markettwits"],
        defaultKeywords=["рф"],
        todayStartUnixTsProvider=lambda: 100,
        fetchHtmlCallable=lambda _in_url, _in_timeout: htmlPage,
    )

    result = tool.execute(
        in_args={
            "keywords": [],
            "sinceUnixTs": 0,
            "maxItems": 10,
        }
    )

    assert result["count"] == 1
    assert result["items"][0]["dateUnixTs"] == "101"
    assert result["sinceUnixTsUsed"] == 100


def testDigestToolMergesRequestedAndDefaultKeywords() -> None:
    htmlPage = """
    <div data-post="cbrstocks/100">
      <time datetime="2026-04-26T10:00:00+00:00"></time>
      <div class="tgme_widget_message_text js-message_text">ЦБ РФ обновил прогноз по инфляции</div>
    </div>
    """
    tool = DigestTelegramNewsTool(
        digestChannelUsernames=["cbrstocks"],
        defaultKeywords=["цб", "инфляция"],
        fetchHtmlCallable=lambda _in_url, _in_timeout: htmlPage,
    )

    result = tool.execute(
        in_args={
            "keywords": ["узкая фраза которой нет в посте"],
            "sinceUnixTs": 1700000000,
            "maxItems": 10,
        }
    )

    assert result["count"] == 1
    assert result["items"][0]["channel"] == "cbrstocks"
