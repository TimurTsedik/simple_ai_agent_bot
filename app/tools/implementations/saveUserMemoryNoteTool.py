import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.memory.stores.markdownMemoryStore import MarkdownMemoryStore


@dataclass
class SaveUserMemoryNoteTool:
    in_memoryStore: MarkdownMemoryStore

    def execute(
        self,
        in_args: dict[str, Any],
        *,
        in_memoryPrincipalId: str,
    ) -> dict[str, Any]:
        ret: dict[str, Any]
        note_text = str(in_args.get("noteText", "") or "").strip()
        if note_text == "":
            ret = {
                "ok": False,
                "message": "noteText пустой: сформулируй, что сохранить, и повтори вызов.",
            }
        else:
            payload = {
                "kind": "explicit_user_note",
                "text": note_text,
                "savedAt": datetime.now(UTC).isoformat(),
            }
            line_text = "- user_memory_json: " + json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
            )
            existing_lines = self.in_memoryStore.readLongTermMemory(
                in_memoryPrincipalId=in_memoryPrincipalId,
            )
            merged_lines = list(existing_lines)
            if line_text not in merged_lines:
                merged_lines.append(line_text)
            self.in_memoryStore.writeLongTermMemory(
                in_memoryPrincipalId=in_memoryPrincipalId,
                in_lines=merged_lines,
            )
            ret = {
                "ok": True,
                "message": "Запись добавлена в долгосрочную память.",
                "saved": payload,
            }
        return ret
