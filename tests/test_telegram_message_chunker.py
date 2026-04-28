from app.integrations.telegram.telegramMessageChunker import splitTelegramMessage


def testSplitTelegramMessagePrefersSeparator() -> None:
    header = "H\n"
    block1 = "A" * 1000
    block2 = "B" * 1000
    block3 = "C" * 1000
    text = header + "\n---\n".join([block1, block2, block3])

    chunks = splitTelegramMessage(in_text=text, in_maxChars=2100, in_preferSeparator="\n---\n")

    assert len(chunks) == 2
    assert block1 in chunks[0]
    assert block2 in chunks[0]
    assert block3 in chunks[1]


def testSplitTelegramMessageHardSplitsLongPart() -> None:
    text = "X" * 5000
    chunks = splitTelegramMessage(in_text=text, in_maxChars=2000, in_preferSeparator="\n---\n")

    assert len(chunks) == 3
    assert sum(len(c) for c in chunks) == 5000

