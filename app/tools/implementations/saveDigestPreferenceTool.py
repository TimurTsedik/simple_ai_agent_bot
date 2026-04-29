import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.memory.stores.markdownMemoryStore import MarkdownMemoryStore
from app.tools.telegramUsernameNormalize import normalizeTelegramChannelUsername


@dataclass
class SaveDigestPreferenceTool:
    in_memoryStore: MarkdownMemoryStore

    def execute(self, in_args: dict[str, Any]) -> dict[str, Any]:
        ret: dict[str, Any]
        topicsRaw = [t for t in in_args.get("likedTopics", []) if isinstance(t, str)]
        channelsRaw = [c for c in in_args.get("likedChannels", []) if isinstance(c, str)]
        keywordsRaw = [k for k in in_args.get("likedKeywords", []) if isinstance(k, str)]
        noteText = str(in_args.get("userNote", "") or "").strip()

        topicsNorm = []
        seenT: set[str] = set()
        for t in topicsRaw:
            key = t.strip().lower()
            if key and key not in seenT:
                seenT.add(key)
                topicsNorm.append(key)

        channelsNorm: list[str] = []
        seenC: set[str] = set()
        for c in channelsRaw:
            norm = normalizeTelegramChannelUsername(in_raw=c)
            if norm is not None and norm not in seenC:
                seenC.add(norm)
                channelsNorm.append(norm)

        keywordsNorm: list[str] = []
        seenK: set[str] = set()
        for k in keywordsRaw:
            word = k.strip()
            if word and word.lower() not in seenK:
                seenK.add(word.lower())
                keywordsNorm.append(word)

        if (
            len(topicsNorm) == 0
            and len(channelsNorm) == 0
            and len(keywordsNorm) == 0
            and noteText == ""
        ):
            ret = {
                "ok": False,
                "message": "Нечего сохранить: заполните likedTopics, likedChannels, likedKeywords или userNote.",
            }
            return ret

        payload = {
            "kind": "digest_user_preference",
            "likedTopics": topicsNorm,
            "likedChannels": channelsNorm,
            "likedKeywords": keywordsNorm,
            "userNote": noteText,
            "savedAt": datetime.now(UTC).isoformat(),
        }
        lineText = "- digest_pref_json: " + json.dumps(payload, ensure_ascii=False, sort_keys=True)
        existingLines = self.in_memoryStore.readLongTermMemory()
        mergedLines = list(existingLines)
        if lineText not in mergedLines:
            mergedLines.append(lineText)
        self.in_memoryStore.writeLongTermMemory(in_lines=mergedLines)
        ret = {
            "ok": True,
            "message": "Предпочтение для будущих дайджестов сохранено в долгосрочную память.",
            "saved": payload,
        }
        return ret
