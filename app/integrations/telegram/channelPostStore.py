import json
from pathlib import Path
from typing import Any


class ChannelPostStore:
    def __init__(self, in_dataRootPath: str) -> None:
        self._telegramDirPath = Path(in_dataRootPath) / "telegram"
        self._telegramDirPath.mkdir(parents=True, exist_ok=True)
        self._channelPostsFilePath = self._telegramDirPath / "channel_posts.jsonl"

    def appendChannelPost(self, in_channelPostData: dict[str, Any]) -> None:
        with self._channelPostsFilePath.open("a", encoding="utf-8") as fileHandle:
            fileHandle.write(json.dumps(in_channelPostData, ensure_ascii=False) + "\n")

    def readChannelPosts(self) -> list[dict[str, Any]]:
        ret: list[dict[str, Any]]
        items: list[dict[str, Any]] = []
        if self._channelPostsFilePath.exists():
            for lineText in self._channelPostsFilePath.read_text(encoding="utf-8").splitlines():
                try:
                    parsedValue = json.loads(lineText)
                    if isinstance(parsedValue, dict):
                        items.append(parsedValue)
                except json.JSONDecodeError:
                    pass
        ret = items
        return ret
