from pathlib import Path


def testScheduleReminderSkillDeclaresSchemaFirstContract() -> None:
    repoRoot = Path(__file__).resolve().parent.parent
    skillPath = repoRoot / "app" / "skills" / "assets" / "schedule_reminder.md"
    text = skillPath.read_text(encoding="utf-8")

    assert "schedule_reminder" in text
    assert "строго структурированному JSON" in text
    assert "никакого разбора естественного языка" in text
    assert "weekdays" in text
    assert "timeLocal" in text

