import imaplib
import re
import html
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from email.header import decode_header
from email.message import Message
from email.parser import BytesParser
from email.policy import default
from typing import Any, Protocol

from app.config.settingsModels import EmailReaderToolSettings


class ImapClientProtocol(Protocol):
    def login(self, user: str, password: str) -> Any: ...
    def select(self, mailbox: str, readonly: bool = True) -> Any: ...
    def uid(self, command: str, *args: Any) -> Any: ...
    def logout(self) -> Any: ...


def _decodeHeaderValue(in_value: str | bytes | None) -> str:
    ret: str
    if in_value is None:
        ret = ""
    else:
        rawValue = in_value.decode("utf-8", errors="replace") if isinstance(in_value, bytes) else str(in_value)
        parts = decode_header(rawValue)
        decoded = []
        for valuePart, encoding in parts:
            if isinstance(valuePart, bytes):
                try:
                    decoded.append(valuePart.decode(encoding or "utf-8", errors="replace"))
                except Exception:
                    decoded.append(valuePart.decode("utf-8", errors="replace"))
            else:
                decoded.append(str(valuePart))
        ret = "".join(decoded).strip()
    return ret


def _parseEmailDateToUnixTs(in_dateHeader: str) -> int | None:
    ret: int | None
    try:
        # Standard RFC2822 parsing via email.utils is a bit heavy; use datetime parsing fallback
        from email.utils import parsedate_to_datetime  # lazy import

        dtValue = parsedate_to_datetime(in_dateHeader)
        if dtValue.tzinfo is None:
            dtValue = dtValue.replace(tzinfo=timezone.utc)
        ret = int(dtValue.timestamp())
    except Exception:
        ret = None
    return ret


def _detectLangHint(in_text: str) -> str:
    ret: str
    textValue = in_text or ""
    cyrCount = 0
    letterCount = 0
    for ch in textValue:
        code = ord(ch)
        if (0x0410 <= code <= 0x044F) or code == 0x0401 or code == 0x0451:
            cyrCount += 1
            letterCount += 1
        elif ("A" <= ch <= "Z") or ("a" <= ch <= "z"):
            letterCount += 1
        elif ch.isalpha():
            letterCount += 1
    if letterCount == 0:
        ret = "unknown"
    else:
        ret = "ru" if (cyrCount / float(letterCount)) >= 0.2 else "non_ru"
    return ret


def _cleanPlainText(in_text: str) -> str:
    ret: str
    textValue = in_text or ""
    # Normalize broken schemes like "h t t p s://"
    textValue = re.sub(r"(?i)h\s*t\s*t\s*p\s*s?\s*://", "http://", textValue)
    # Drop long URLs (tracking/noise), keep readable text.
    textValue = re.sub(r"https?://\S+", " ", textValue)
    textValue = re.sub(r"(?i)http://\S+", " ", textValue)
    # Drop any residual URL-like patterns that survived decoding quirks.
    textValue = re.sub(r"\S{0,20}\s*:\s*//\s*\S+", " ", textValue)
    # Remove common CSS-like noise that leaks into snippets.
    textValue = re.sub(r"(?i)@font-face\s*\{[^}]{0,2000}\}", " ", textValue)
    textValue = re.sub(r"(?i)@media\s*\([^)]{0,200}\)\s*\{[^}]{0,2000}\}", " ", textValue)
    textValue = re.sub(r"(?i):root\s*\{[^}]{0,2000}\}", " ", textValue)
    textValue = re.sub(r"(?i)\S*font\S*face\S*", " ", textValue)
    textValue = re.sub(r"\{\s*[^}]{0,2000}\}", " ", textValue)
    textValue = re.sub(r"[\r\n\t]+", " ", textValue)
    textValue = re.sub(r"\s+", " ", textValue).strip()
    # If mostly mojibake/replacement chars, drop it.
    if textValue:
        badCount = textValue.count("�")
        if badCount / float(len(textValue)) > 0.15:
            textValue = ""
        if re.search(r"[�?]{12,}", textValue):
            textValue = ""
    ret = textValue
    return ret


def _extractTextFromPart(in_part: Message) -> str:
    ret: str
    try:
        content = in_part.get_content()
        ret = content if isinstance(content, str) else str(content)
    except Exception:
        try:
            payload = in_part.get_payload(decode=True) or b""
            charset = in_part.get_content_charset() or "utf-8"
            ret = payload.decode(charset, errors="replace")
        except Exception:
            ret = ""
    return ret


def _extractTextSnippet(in_msg: Message, in_maxChars: int) -> str:
    ret: str
    textParts: list[str] = []
    htmlParts: list[str] = []
    if in_msg.is_multipart():
        for part in in_msg.walk():
            contentType = str(part.get_content_type() or "")
            disp = str(part.get("Content-Disposition", "") or "").lower()
            if "attachment" in disp:
                continue
            if contentType == "text/plain":
                try:
                    textParts.append(_extractTextFromPart(in_part=part))
                except Exception:
                    continue
            if contentType == "text/html":
                try:
                    htmlParts.append(_extractTextFromPart(in_part=part))
                except Exception:
                    continue
    else:
        contentType = str(in_msg.get_content_type() or "")
        if contentType == "text/plain":
            try:
                textParts.append(_extractTextFromPart(in_part=in_msg))
            except Exception:
                textParts = []
        if contentType == "text/html":
            try:
                htmlParts.append(_extractTextFromPart(in_part=in_msg))
            except Exception:
                htmlParts = []
    combined = "\n".join(item.strip() for item in textParts if item and item.strip())
    if combined.strip() == "" and len(htmlParts) > 0:
        htmlText = "\n".join(item for item in htmlParts if item)
        htmlText = re.sub(r"(?is)<(script|style)[^>]*>.*?</\\1>", " ", htmlText)
        htmlText = re.sub(r"(?s)<!--.*?-->", " ", htmlText)
        htmlText = re.sub(r"(?s)<[^>]+>", " ", htmlText)
        htmlText = html.unescape(htmlText)
        combined = htmlText
    combined = _cleanPlainText(in_text=combined)
    ret = combined[: max(0, in_maxChars)]
    return ret


def _defaultImapClientFactory(in_settings: EmailReaderToolSettings) -> ImapClientProtocol:
    if in_settings.imapSsl is True:
        return imaplib.IMAP4_SSL(in_settings.imapHost, in_settings.imapPort)
    return imaplib.IMAP4(in_settings.imapHost, in_settings.imapPort)


@dataclass
class ReadEmailTool:
    in_emailSettings: EmailReaderToolSettings
    in_password: str
    in_imapClientFactory: Any = _defaultImapClientFactory

    def execute(self, in_args: dict[str, Any]) -> dict[str, Any]:
        ret: dict[str, Any]
        mailbox = str(in_args.get("mailbox", "INBOX"))
        unreadOnly = bool(in_args.get("unreadOnly", True)) is True
        markAsRead = bool(in_args.get("markAsRead", True)) is True
        sinceHours = int(in_args.get("sinceHours", 24))
        maxItems = int(in_args.get("maxItems", 10))
        snippetChars = int(in_args.get("snippetChars", 300))

        if maxItems < 1:
            maxItems = 1
        if maxItems > 50:
            maxItems = 50
        if sinceHours < 0:
            sinceHours = 0
        if sinceHours > 168:
            sinceHours = 168
        if snippetChars < 0:
            snippetChars = 0
        if snippetChars > 2000:
            snippetChars = 2000

        if not self.in_emailSettings.email:
            raise RuntimeError("EmailReader settings: email is empty")
        if not self.in_password:
            raise RuntimeError("EMAIL_APP_PASSWORD is not configured")

        nowUtc = datetime.now(timezone.utc)
        sinceTs = int((nowUtc - timedelta(hours=sinceHours)).timestamp())
        shouldMarkAsRead = unreadOnly is True and markAsRead is True

        imapClient = self.in_imapClientFactory(self.in_emailSettings)
        try:
            imapClient.login(self.in_emailSettings.email, self.in_password)
            imapClient.select(mailbox, readonly=not shouldMarkAsRead)
            criteria = "UNSEEN" if unreadOnly else "ALL"
            _status, data = imapClient.uid("SEARCH", None, criteria)
            uidBytes = data[0] if isinstance(data, list) and len(data) > 0 else b""
            uidList = [item for item in uidBytes.split() if item]
            # take recent UIDs from the end, fetch a bit more to allow filtering by sinceTs
            candidateUids = uidList[-min(len(uidList), maxItems * 5) :]
            candidateUids.reverse()

            items: list[dict[str, Any]] = []
            markedAsReadCount = 0
            for oneUid in candidateUids:
                if len(items) >= maxItems:
                    break
                _st, fetchData = imapClient.uid("FETCH", oneUid, "(RFC822)")
                raw = fetchData[0][1] if isinstance(fetchData, list) and len(fetchData) > 0 else b""
                if not isinstance(raw, (bytes, bytearray)) or len(raw) == 0:
                    continue
                msg = BytesParser(policy=default).parsebytes(raw)
                fromValue = _decodeHeaderValue(msg.get("From"))
                subjectValue = _decodeHeaderValue(msg.get("Subject"))
                dateHeader = _decodeHeaderValue(msg.get("Date"))
                dateUnixTs = _parseEmailDateToUnixTs(dateHeader) if dateHeader else None
                if dateUnixTs is not None and dateUnixTs < sinceTs:
                    continue
                snippet = _extractTextSnippet(in_msg=msg, in_maxChars=snippetChars)
                langHint = _detectLangHint(in_text=(subjectValue + " " + snippet).strip())
                items.append(
                    {
                        "uid": oneUid.decode("ascii", errors="replace"),
                        "from": fromValue,
                        "subject": subjectValue,
                        "date": dateHeader,
                        "dateUnixTs": dateUnixTs,
                        "snippet": snippet,
                        "langHint": langHint,
                    }
                )
                if shouldMarkAsRead is True:
                    try:
                        imapClient.uid("STORE", oneUid, "+FLAGS", "(\\Seen)")
                        markedAsReadCount += 1
                    except Exception:
                        pass

            ret = {
                "account": {
                    "name": self.in_emailSettings.accountName,
                    "email": self.in_emailSettings.email,
                    "imapHost": self.in_emailSettings.imapHost,
                },
                "mailbox": mailbox,
                "unreadOnly": unreadOnly,
                "markAsRead": markAsRead,
                "markedAsReadCount": markedAsReadCount,
                "sinceUnixTsUsed": sinceTs,
                "count": len(items),
                "items": items,
            }
        finally:
            try:
                imapClient.logout()
            except Exception:
                pass
        return ret

