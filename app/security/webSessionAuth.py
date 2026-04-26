import base64
import hashlib
import hmac
import json
from time import time


def hashAdminToken(in_rawToken: str, in_secret: str) -> str:
    ret: str
    digestValue = hmac.new(
        in_secret.encode("utf-8"),
        in_rawToken.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    ret = digestValue
    return ret


def createSessionCookieValue(
    in_tokenHash: str,
    in_secret: str,
    in_ttlSeconds: int,
) -> str:
    ret: str
    payload = {
        "tokenHash": in_tokenHash,
        "exp": int(time()) + in_ttlSeconds,
    }
    payloadJson = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    payloadEncoded = base64.urlsafe_b64encode(payloadJson.encode("utf-8")).decode("ascii")
    signature = hmac.new(
        in_secret.encode("utf-8"),
        payloadEncoded.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()
    ret = f"{payloadEncoded}.{signature}"
    return ret


def parseSessionCookieValue(
    in_cookieValue: str,
    in_secret: str,
) -> dict | None:
    ret: dict | None
    try:
        payloadEncoded, signature = in_cookieValue.split(".", 1)
    except ValueError:
        ret = None
        return ret
    expectedSignature = hmac.new(
        in_secret.encode("utf-8"),
        payloadEncoded.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(signature, expectedSignature):
        ret = None
        return ret
    try:
        payloadRaw = base64.urlsafe_b64decode(payloadEncoded.encode("ascii"))
        payloadData = json.loads(payloadRaw.decode("utf-8"))
    except (ValueError, json.JSONDecodeError):
        ret = None
        return ret
    tokenHash = payloadData.get("tokenHash")
    expiresAt = payloadData.get("exp")
    if not isinstance(tokenHash, str) or not isinstance(expiresAt, int):
        ret = None
        return ret
    if int(time()) >= expiresAt:
        ret = None
        return ret
    ret = payloadData
    return ret
