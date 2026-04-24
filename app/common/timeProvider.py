from datetime import UTC, datetime


def getUtcNowIso() -> str:
    ret = datetime.now(UTC).isoformat()
    return ret
