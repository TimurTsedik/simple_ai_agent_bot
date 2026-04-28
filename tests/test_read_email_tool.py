from datetime import datetime, timezone
from email.message import EmailMessage

import pytest

from app.config.settingsModels import EmailReaderToolSettings
from app.tools.implementations.readEmailTool import ReadEmailTool


class FakeImapClient:
    def __init__(self, in_messagesByUid: dict[bytes, bytes]) -> None:
        self._messagesByUid = dict(in_messagesByUid)
        self.loggedOut = False
        self.selectedReadonly: bool | None = None
        self.storedSeenUids: list[str] = []

    def login(self, user: str, password: str):
        return "OK", [b"logged_in"]

    def select(self, mailbox: str, readonly: bool = True):
        self.selectedReadonly = readonly
        return "OK", [b"selected"]

    def uid(self, command: str, *args):
        cmd = command.upper()
        if cmd == "SEARCH":
            uids = b" ".join(sorted(self._messagesByUid.keys()))
            return "OK", [uids]
        if cmd == "FETCH":
            uid = args[0]
            msg = self._messagesByUid.get(uid, b"")
            return "OK", [(b"RFC822", msg)]
        if cmd == "STORE":
            uid = args[0]
            self.storedSeenUids.append(uid.decode("ascii", errors="replace"))
            return "OK", [b"stored"]
        raise RuntimeError(f"unsupported command: {command}")

    def logout(self):
        self.loggedOut = True
        return "OK", [b"bye"]


def _makeRfc822Bytes(in_from: str, in_subject: str, in_body: str, in_dt: datetime) -> bytes:
    msg = EmailMessage()
    msg["From"] = in_from
    msg["To"] = "me@example.com"
    msg["Subject"] = in_subject
    msg["Date"] = in_dt.astimezone(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
    msg.set_content(in_body)
    return msg.as_bytes()


def _makeHtmlOnlyRfc822Bytes(in_from: str, in_subject: str, in_htmlBody: str, in_dt: datetime) -> bytes:
    msg = EmailMessage()
    msg["From"] = in_from
    msg["To"] = "me@example.com"
    msg["Subject"] = in_subject
    msg["Date"] = in_dt.astimezone(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
    msg.add_alternative(in_htmlBody, subtype="html")
    return msg.as_bytes()


def testReadEmailToolReturnsItemsAndSnippets():
    settings = EmailReaderToolSettings(email="me@example.com")
    now = datetime.now(timezone.utc)
    m1 = _makeRfc822Bytes("Alice <a@example.com>", "Hello", "Body one", now)
    m2 = _makeRfc822Bytes("Bob <b@example.com>", "Hi", "Body two", now)
    fake = FakeImapClient({b"10": m1, b"11": m2})

    tool = ReadEmailTool(
        in_emailSettings=settings,
        in_password="app_password",
        in_imapClientFactory=lambda _s: fake,
    )
    result = tool.execute(
        {"mailbox": "INBOX", "unreadOnly": True, "sinceHours": 24, "maxItems": 10, "snippetChars": 50}
    )

    assert result["count"] == 2
    assert len(result["items"]) == 2
    assert result["items"][0]["uid"] in {"10", "11"}
    assert isinstance(result["items"][0]["snippet"], str)
    assert fake.loggedOut is True
    assert fake.selectedReadonly is False
    assert sorted(fake.storedSeenUids) == ["10", "11"]
    assert result["markedAsReadCount"] == 2


def testReadEmailToolExtractsSnippetFromHtml():
    settings = EmailReaderToolSettings(email="me@example.com")
    now = datetime.now(timezone.utc)
    htmlMsg = _makeHtmlOnlyRfc822Bytes(
        "News <n@example.com>",
        "HTML only",
        "<html><body><h1>Hello</h1><p>World&nbsp;AI</p></body></html>",
        now,
    )
    fake = FakeImapClient({b"5": htmlMsg})
    tool = ReadEmailTool(
        in_emailSettings=settings,
        in_password="app_password",
        in_imapClientFactory=lambda _s: fake,
    )
    result = tool.execute({"maxItems": 1, "snippetChars": 100, "unreadOnly": False})
    assert result["count"] == 1
    assert "Hello" in result["items"][0]["snippet"]
    assert "AI" in result["items"][0]["snippet"]


def testReadEmailToolCleansUrlsAndCssNoise():
    settings = EmailReaderToolSettings(email="me@example.com")
    now = datetime.now(timezone.utc)
    htmlMsg = _makeHtmlOnlyRfc822Bytes(
        "Noise <n@example.com>",
        "Tracking",
        "<html><body>"
        "<style>@font-face{font-family:'Inter';src:url('https://example.com/a.woff2');}</style>"
        "<p>Hi Timur</p>"
        "<p>Click https://tracker.example.com/abc?x=1</p>"
        "</body></html>",
        now,
    )
    fake = FakeImapClient({b"7": htmlMsg})
    tool = ReadEmailTool(
        in_emailSettings=settings,
        in_password="app_password",
        in_imapClientFactory=lambda _s: fake,
    )
    result = tool.execute({"maxItems": 1, "snippetChars": 300, "unreadOnly": False})
    snippet = result["items"][0]["snippet"]
    assert "Hi" in snippet
    assert "Click" in snippet
    assert "://" not in snippet
    assert "font" not in snippet.lower()


def testReadEmailToolFiltersBySinceHours():
    settings = EmailReaderToolSettings(email="me@example.com")
    now = datetime.now(timezone.utc)
    old = now.replace(year=now.year - 1)
    m1 = _makeRfc822Bytes("Alice <a@example.com>", "Old", "Old body", old)
    m2 = _makeRfc822Bytes("Bob <b@example.com>", "New", "New body", now)
    fake = FakeImapClient({b"1": m1, b"2": m2})
    tool = ReadEmailTool(
        in_emailSettings=settings,
        in_password="app_password",
        in_imapClientFactory=lambda _s: fake,
    )
    result = tool.execute({"sinceHours": 1, "maxItems": 10})
    assert result["count"] == 1
    assert result["items"][0]["subject"] == "New"


def testReadEmailToolRequiresPassword():
    settings = EmailReaderToolSettings(email="me@example.com")
    tool = ReadEmailTool(
        in_emailSettings=settings,
        in_password="",
        in_imapClientFactory=lambda _s: FakeImapClient({}),
    )
    with pytest.raises(RuntimeError):
        _ = tool.execute({})


def testReadEmailToolCanKeepUnreadWithoutSeenFlag() -> None:
    settings = EmailReaderToolSettings(email="me@example.com")
    now = datetime.now(timezone.utc)
    oneMessage = _makeRfc822Bytes("Alice <a@example.com>", "Hello", "Body one", now)
    fake = FakeImapClient({b"10": oneMessage})
    tool = ReadEmailTool(
        in_emailSettings=settings,
        in_password="app_password",
        in_imapClientFactory=lambda _s: fake,
    )
    result = tool.execute(
        {"unreadOnly": True, "markAsRead": False, "sinceHours": 24, "maxItems": 10}
    )
    assert result["count"] == 1
    assert result["markedAsReadCount"] == 0
    assert fake.selectedReadonly is True
    assert fake.storedSeenUids == []

