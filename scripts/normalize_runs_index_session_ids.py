"""
Одноразовая нормализация sessionId в data/runs/index.jsonl:
замена префикса telegram:<digits> на telegramUser:<digits> в поле sessionId каждой JSON-строки.

Создаёт резервную копию index.jsonl рядом с файлом перед записью.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path


_TELEGRAM_NUMERIC_SESSION = re.compile(r"^telegram:(\d+)$")


def _normalizeSessionIdValue(in_sessionId: object) -> tuple[str, bool]:
    raw = str(in_sessionId or "").strip()
    matched = _TELEGRAM_NUMERIC_SESSION.fullmatch(raw)
    changed = False
    if matched is not None:
        raw = f"telegramUser:{matched.group(1)}"
        changed = True
    ret = (raw, changed)
    return ret


def _processIndexFile(in_indexPath: Path) -> tuple[bool, int]:
    changedLines = 0
    didProcess = False
    if in_indexPath.exists() is True:
        didProcess = True
        backupName = f"{in_indexPath.name}.bak.{datetime.now(tz=timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
        backupPath = in_indexPath.parent / backupName
        backupPath.write_bytes(in_indexPath.read_bytes())
        outLines: list[str] = []
        for lineText in in_indexPath.read_text(encoding="utf-8").splitlines():
            stripped = lineText.strip()
            if stripped == "":
                outLines.append(lineText)
                continue
            try:
                parsed = json.loads(lineText)
            except json.JSONDecodeError:
                outLines.append(lineText)
                continue
            if isinstance(parsed, dict) and "sessionId" in parsed:
                newVal, didChange = _normalizeSessionIdValue(in_sessionId=parsed.get("sessionId"))
                if didChange is True:
                    parsed = dict(parsed)
                    parsed["sessionId"] = newVal
                    changedLines += 1
                outLines.append(json.dumps(parsed, ensure_ascii=False))
            else:
                outLines.append(lineText)
        tmpPath = in_indexPath.with_suffix(f"{in_indexPath.suffix}.tmp.{os.getpid()}")
        tmpPath.write_text("\n".join(outLines) + ("\n" if outLines else ""), encoding="utf-8")
        os.replace(str(tmpPath), str(in_indexPath))
    ret = (didProcess, changedLines)
    return ret


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Normalize telegram:<id> to telegramUser:<id> in runs index.jsonl sessionId fields.",
    )
    parser.add_argument(
        "--data-root",
        default="./data",
        help="Корень данных (по умолчанию ./data); индекс: <data-root>/runs/index.jsonl",
    )
    parsed = parser.parse_args()
    dataRoot = Path(parsed.data_root)
    indexPath = dataRoot / "runs" / "index.jsonl"
    didProcess, changed = _processIndexFile(in_indexPath=indexPath)
    if didProcess is False:
        print(
            f"Нечего делать: нет файла {indexPath.resolve()} "
            "(индекс появится после первых сохранённых ранов)."
        )
    else:
        print(f"Обработан {indexPath}: изменено строк с sessionId: {changed}.")


if __name__ == "__main__":
    main()
