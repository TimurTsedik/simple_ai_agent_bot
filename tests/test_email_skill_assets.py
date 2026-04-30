from pathlib import Path


def _readSkillFile(in_relativePath: str) -> str:
    ret: str
    repoRoot = Path(__file__).resolve().parent.parent
    skillPath = repoRoot / in_relativePath
    ret = skillPath.read_text(encoding="utf-8")
    return ret


def testReadAndAnalyzeEmailSkillDeclaresThreeCategories() -> None:
    text = _readSkillFile(
        in_relativePath="app/skills/assets/read_and_analyze_email.md"
    )

    assert "Требуют ответа/действия или предпочтительные отправители" in text
    assert "Важные" in text
    assert "Остальное/мусор" in text


def testReadAndAnalyzeEmailSkillReferencesEmailPreferenceHintsBlock() -> None:
    text = _readSkillFile(
        in_relativePath="app/skills/assets/read_and_analyze_email.md"
    )

    assert "Email preference hints" in text


def testComposeDigestSkillReferencesThreeCategoryFormatForEmail() -> None:
    text = _readSkillFile(in_relativePath="app/skills/assets/compose_digest.md")

    assert "ровно 3 категории" in text
    assert "save_email_preference" in text


def testEmailPreferenceFeedbackSkillIsPresent() -> None:
    text = _readSkillFile(
        in_relativePath="app/skills/assets/email_preference_feedback.md"
    )

    assert "save_email_preference" in text
    assert "preferredSenders" in text
