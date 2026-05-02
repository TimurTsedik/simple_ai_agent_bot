import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.memory.stores.markdownMemoryStore import MarkdownMemoryStore


@dataclass
class SaveEmailPreferenceTool:
    in_memoryStore: MarkdownMemoryStore

    def execute(
        self,
        in_args: dict[str, Any],
        *,
        in_memoryPrincipalId: str,
    ) -> dict[str, Any]:
        ret: dict[str, Any]
        sendersRaw = [
            s for s in in_args.get("preferredSenders", []) if isinstance(s, str)
        ]
        keywordsRaw = [
            k for k in in_args.get("preferredKeywords", []) if isinstance(k, str)
        ]
        noteText = str(in_args.get("userNote", "") or "").strip()

        sendersNorm: list[str] = []
        seenSenders: set[str] = set()
        for senderText in sendersRaw:
            normalized = senderText.strip().lower()
            if normalized == "":
                continue
            if normalized in seenSenders:
                continue
            seenSenders.add(normalized)
            sendersNorm.append(normalized)

        keywordsNorm: list[str] = []
        seenKeywords: set[str] = set()
        for keywordText in keywordsRaw:
            word = keywordText.strip()
            if word == "":
                continue
            keyLower = word.lower()
            if keyLower in seenKeywords:
                continue
            seenKeywords.add(keyLower)
            keywordsNorm.append(word)

        if (
            len(sendersNorm) == 0
            and len(keywordsNorm) == 0
            and noteText == ""
        ):
            ret = {
                "ok": False,
                "message": (
                    "Нечего сохранить: заполните preferredSenders, preferredKeywords или userNote."
                ),
            }
            return ret

        payload = {
            "kind": "email_user_preference",
            "preferredSenders": sendersNorm,
            "preferredKeywords": keywordsNorm,
            "userNote": noteText,
            "savedAt": datetime.now(UTC).isoformat(),
        }
        lineText = "- email_pref_json: " + json.dumps(
            payload, ensure_ascii=False, sort_keys=True
        )
        existingLines = self.in_memoryStore.readLongTermMemory(
            in_memoryPrincipalId=in_memoryPrincipalId,
        )
        mergedLines = list(existingLines)
        if lineText not in mergedLines:
            mergedLines.append(lineText)
        self.in_memoryStore.writeLongTermMemory(
            in_memoryPrincipalId=in_memoryPrincipalId,
            in_lines=mergedLines,
        )
        ret = {
            "ok": True,
            "message": (
                "Email-предпочтение (отправители/ключи) сохранено в долгосрочную память."
            ),
            "saved": payload,
        }
        return ret
