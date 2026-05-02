import json
import subprocess
import sys
from pathlib import Path


def testNormalizeRunsIndexScriptRewritesTelegramSessionPrefix(tmp_path: Path) -> None:
    dataRoot = tmp_path / "d"
    runsDir = dataRoot / "runs"
    runsDir.mkdir(parents=True)
    indexPath = runsDir / "index.jsonl"
    indexPath.write_text(
        '{"runId":"a","traceId":"t","sessionId":"telegram:5","runStatus":"x",'
        '"completionReason":"c","selectedModel":"m","createdAt":"2026-01-01","finishedAt":"2026-01-01"}\n',
        encoding="utf-8",
    )
    repoRoot = Path(__file__).resolve().parents[1]
    scriptPath = repoRoot / "scripts" / "normalize_runs_index_session_ids.py"
    subprocess.run(
        [
            sys.executable,
            str(scriptPath),
            "--data-root",
            str(dataRoot),
        ],
        check=True,
        cwd=str(repoRoot),
    )
    line = indexPath.read_text(encoding="utf-8").strip()
    parsed = json.loads(line)
    assert parsed["sessionId"] == "telegramUser:5"
    backups = list(runsDir.glob("index.jsonl.bak.*"))
    assert len(backups) == 1
