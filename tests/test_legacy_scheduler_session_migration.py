from pathlib import Path
from tempfile import TemporaryDirectory

from app.memory.services.legacySchedulerSessionMigration import (
    ensureLegacySchedulerSessionDirsMigrated,
)


def testMigratesLegacySchedulerEmailDirToTenantNamespacedFolder() -> None:
    with TemporaryDirectory() as tempDir:
        root = Path(tempDir)
        memoryRoot = root / "memory"
        legacyDir = memoryRoot / "sessions" / "scheduler_email"
        legacyDir.mkdir(parents=True)
        (legacyDir / "summary.md").write_text("x", encoding="utf-8")

        ensureLegacySchedulerSessionDirsMigrated(
            in_memoryRootPath=str(memoryRoot),
            in_adminTelegramUserId=16739703,
        )

        tenantDir = memoryRoot / "sessions" / "telegramUser_16739703_scheduler_email"
        assert tenantDir.is_dir()
        assert (tenantDir / "summary.md").read_text(encoding="utf-8") == "x"
        assert legacyDir.exists() is False
