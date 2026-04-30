from pathlib import Path
from tempfile import TemporaryDirectory

from app.bootstrap.container import _ensureSkillsDirInitialized


def testEnsureSkillsDirInitializedCopiesDefaultSkillsIfMissing() -> None:
    with TemporaryDirectory() as tempDir:
        targetDir = Path(tempDir) / "skills"
        _ensureSkillsDirInitialized(in_skillsDirPath=str(targetDir))

        # We rely on repo-shipped default skills existing.
        expectedSkill = targetDir / "default_assistant.md"
        assert expectedSkill.exists() is True
        assert expectedSkill.read_text(encoding="utf-8").strip() != ""


def testEnsureSkillsDirInitializedDoesNotOverwriteExistingSkill() -> None:
    with TemporaryDirectory() as tempDir:
        targetDir = Path(tempDir) / "skills"
        targetDir.mkdir(parents=True, exist_ok=True)
        preExistingPath = targetDir / "default_assistant.md"
        preExistingPath.write_text("custom", encoding="utf-8")

        _ensureSkillsDirInitialized(in_skillsDirPath=str(targetDir))

        assert preExistingPath.read_text(encoding="utf-8") == "custom"
