import json
from pathlib import Path
from tempfile import TemporaryDirectory

from app.config.settingsModels import MemorySettings
from app.memory.stores.markdownMemoryStore import MarkdownMemoryStore
from app.tools.implementations.userTopicDigestTool import UserTopicDigestTool
from app.tools.implementations.userTopicDigestTool import normalizeUserDigestTopicKey


class FakeFetchEngine:
    def __init__(self, in_postsByChannel: dict[str, list[dict]]) -> None:
        self._postsByChannel = in_postsByChannel

    def fetchRawPostsForChannels(
        self,
        in_channels: list[str],
        io_channelErrors: dict[str, str] | None = None,
    ) -> list[dict]:
        ret: list[dict]
        collected: list[dict] = []
        for channelName in in_channels:
            channelKey = str(channelName or "").strip().lower()
            postsList = self._postsByChannel.get(channelKey, [])
            collected.extend(postsList)
        ret = collected
        return ret


def testNormalizeUserDigestTopicKeyCollapsesWhitespace() -> None:
    ret = normalizeUserDigestTopicKey(in_topicLabel="  ИИ   рынок  ")
    assert ret == "ии рынок"


def testUserTopicDigestToolNeedsChannelsOnFirstCall() -> None:
    with TemporaryDirectory() as tempDir:
        memorySettings = MemorySettings(
            memoryRootPath=str(Path(tempDir) / "memory"),
            longTermFileName="long_term.md",
            sessionSummaryFileName="summary.md",
            recentMessagesFileName="recent.md",
        )
        store = MarkdownMemoryStore(in_memorySettings=memorySettings)
        tool = UserTopicDigestTool(
            in_memoryStore=store,
            in_dataRootPath=str(Path(tempDir) / "data"),
            in_fetchEngine=FakeFetchEngine(in_postsByChannel={}),
        )
        result = tool.execute(
            in_args={
                "topic": "ИИ",
                "channels": [],
                "keywords": [],
                "fetchUnread": False,
                "deleteTopic": False,
            }
        )
    assert result["status"] == "needs_channels"
    assert result["topicKey"] == "ии"


def testUserTopicDigestToolNeedsKeywordsAfterChannels() -> None:
    with TemporaryDirectory() as tempDir:
        memorySettings = MemorySettings(
            memoryRootPath=str(Path(tempDir) / "memory"),
            longTermFileName="long_term.md",
            sessionSummaryFileName="summary.md",
            recentMessagesFileName="recent.md",
        )
        store = MarkdownMemoryStore(in_memorySettings=memorySettings)
        tool = UserTopicDigestTool(
            in_memoryStore=store,
            in_dataRootPath=str(Path(tempDir) / "data"),
            in_fetchEngine=FakeFetchEngine(in_postsByChannel={}),
        )
        tool.execute(
            in_args={
                "topic": "ИИ",
                "channels": ["@alpha_news"],
                "keywords": [],
                "fetchUnread": False,
                "deleteTopic": False,
            }
        )
        result = tool.execute(
            in_args={
                "topic": "ИИ",
                "channels": [],
                "keywords": [],
                "fetchUnread": False,
                "deleteTopic": False,
            }
        )
    assert result["status"] == "needs_keywords"
    saved = result.get("savedConfig")
    assert isinstance(saved, dict)
    assert "alpha_news" in saved.get("channels", [])


def testUserTopicDigestToolFetchUnreadRespectsKeywordsAndState() -> None:
    with TemporaryDirectory() as tempDir:
        dataRoot = Path(tempDir) / "data"
        memorySettings = MemorySettings(
            memoryRootPath=str(Path(tempDir) / "memory"),
            longTermFileName="long_term.md",
            sessionSummaryFileName="summary.md",
            recentMessagesFileName="recent.md",
        )
        store = MarkdownMemoryStore(in_memorySettings=memorySettings)
        postsAlpha = [
            {
                "message_id": 10,
                "date": 1000,
                "text": "про inflation рынок",
                "chat": {"username": "alpha_news"},
            },
            {
                "message_id": 11,
                "date": 2000,
                "text": "про inflation рынок ещё",
                "chat": {"username": "alpha_news"},
            },
        ]
        tool = UserTopicDigestTool(
            in_memoryStore=store,
            in_dataRootPath=str(dataRoot),
            in_fetchEngine=FakeFetchEngine(in_postsByChannel={"alpha_news": postsAlpha}),
        )
        tool.execute(
            in_args={
                "topic": "Рынок",
                "channels": ["alpha_news"],
                "keywords": ["inflation"],
                "fetchUnread": False,
                "deleteTopic": False,
            }
        )
        firstFetch = tool.execute(
            in_args={
                "topic": "Рынок",
                "fetchUnread": True,
                "channels": [],
                "keywords": [],
                "deleteTopic": False,
            }
        )
        secondFetch = tool.execute(
            in_args={
                "topic": "Рынок",
                "fetchUnread": True,
                "channels": [],
                "keywords": [],
                "deleteTopic": False,
            }
        )
        assert firstFetch["count"] == 2
        assert secondFetch["count"] == 0
        statePath = dataRoot / "state" / "telegram_digest_read_state.json"
        stateText = statePath.read_text(encoding="utf-8")
        statePayload = json.loads(stateText)
        assert statePayload["channelLastSeenMessageId"]["alpha_news"] == 11


def testUserTopicDigestToolDeletesTopicConfig() -> None:
    with TemporaryDirectory() as tempDir:
        memorySettings = MemorySettings(
            memoryRootPath=str(Path(tempDir) / "memory"),
            longTermFileName="long_term.md",
            sessionSummaryFileName="summary.md",
            recentMessagesFileName="recent.md",
        )
        store = MarkdownMemoryStore(in_memorySettings=memorySettings)
        tool = UserTopicDigestTool(
            in_memoryStore=store,
            in_dataRootPath=str(Path(tempDir) / "data"),
            in_fetchEngine=FakeFetchEngine(in_postsByChannel={}),
        )
        tool.execute(
            in_args={
                "topic": "Тема",
                "channels": ["chan"],
                "keywords": ["kw"],
                "fetchUnread": False,
                "deleteTopic": False,
            }
        )
        deleteResult = tool.execute(
            in_args={
                "topic": "Тема",
                "deleteTopic": True,
                "channels": [],
                "keywords": [],
                "fetchUnread": False,
            }
        )
        missingResult = tool.execute(
            in_args={
                "topic": "Тема",
                "fetchUnread": False,
                "channels": [],
                "keywords": [],
                "deleteTopic": False,
            }
        )
    assert deleteResult["status"] == "deleted"
    assert missingResult["status"] == "needs_channels"


def testUserTopicDigestToolCapsTwentyPerChannel() -> None:
    with TemporaryDirectory() as tempDir:
        memorySettings = MemorySettings(
            memoryRootPath=str(Path(tempDir) / "memory"),
            longTermFileName="long_term.md",
            sessionSummaryFileName="summary.md",
            recentMessagesFileName="recent.md",
        )
        store = MarkdownMemoryStore(in_memorySettings=memorySettings)
        manyPosts = []
        indexValue = 0
        while indexValue < 30:
            messageIdValue = 100 + indexValue
            manyPosts.append(
                {
                    "message_id": messageIdValue,
                    "date": 5000 + indexValue,
                    "text": "keyword match text",
                    "chat": {"username": "wide_channel"},
                }
            )
            indexValue += 1
        tool = UserTopicDigestTool(
            in_memoryStore=store,
            in_dataRootPath=str(Path(tempDir) / "data"),
            in_fetchEngine=FakeFetchEngine(in_postsByChannel={"wide_channel": manyPosts}),
        )
        tool.execute(
            in_args={
                "topic": "Много",
                "channels": ["wide_channel"],
                "keywords": ["keyword"],
                "fetchUnread": False,
                "deleteTopic": False,
            }
        )
        fetchResult = tool.execute(
            in_args={
                "topic": "Много",
                "fetchUnread": True,
                "channels": [],
                "keywords": [],
                "deleteTopic": False,
            }
        )
        assert fetchResult["count"] == 20
