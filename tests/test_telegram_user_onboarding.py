from pathlib import Path
from tempfile import TemporaryDirectory

from app.application.useCases.createTelegramUserUseCase import CreateTelegramUserUseCase
from app.config.defaultTenantSessionYaml import DEFAULT_TENANT_TOOLS_YAML_TEXT
from app.config.settingsModels import MemorySettings
from app.users.provisionTelegramUserWorkspace import provisionTelegramUserWorkspaceIfNeeded
from app.users.telegramUserRegistryStore import TelegramUserRegistryStore


def testRegistryStoreRoundTripAndAddUser() -> None:
    with TemporaryDirectory() as tmp:
        reg_path = Path(tmp) / "registry.yaml"
        store = TelegramUserRegistryStore(in_registryFilePath=str(reg_path))
        assert len(store.listUsers()) == 0
        record_one, was_new_one = store.addOrTouchUser(
            in_telegramUserId=555,
            in_displayName="Tester",
            in_note="",
            in_createdAtUnixTs=1700000000,
        )
        assert was_new_one is True
        assert record_one.telegramUserId == 555
        record_two, was_new_two = store.addOrTouchUser(
            in_telegramUserId=555,
            in_displayName="",
            in_note="x",
            in_createdAtUnixTs=1700000001,
        )
        assert was_new_two is False
        assert len(store.listUsers()) == 1
        assert store.listRegisteredTelegramUserIds() == {555}


def testProvisionCreatesSessionFiles() -> None:
    with TemporaryDirectory() as tmp:
        memory_root = Path(tmp) / "memory"
        settings = MemorySettings(memoryRootPath=str(memory_root))
        provisionTelegramUserWorkspaceIfNeeded(in_telegramUserId=999, in_memorySettings=settings)
        session_dir = memory_root / "sessions" / "telegramUser_999"
        assert (session_dir / "long_term.md").exists()
        assert (session_dir / "summary.md").exists()
        assert (session_dir / "recent.md").exists()
        assert (session_dir / "tools.yaml").exists()
        assert (session_dir / "tools.yaml").read_text(encoding="utf-8") == DEFAULT_TENANT_TOOLS_YAML_TEXT
        assert (session_dir / "schedules.yaml").exists()


def testProvisionRepairsToolsYamlWhenPathWasDirectory() -> None:
    with TemporaryDirectory() as tmp:
        memory_root = Path(tmp) / "memory"
        session_dir = memory_root / "sessions" / "telegramUser_1000"
        session_dir.mkdir(parents=True)
        bogus_tools = session_dir / "tools.yaml"
        bogus_tools.mkdir()
        settings = MemorySettings(memoryRootPath=str(memory_root))
        provisionTelegramUserWorkspaceIfNeeded(in_telegramUserId=1000, in_memorySettings=settings)
        assert bogus_tools.is_file()
        assert bogus_tools.read_text(encoding="utf-8") == DEFAULT_TENANT_TOOLS_YAML_TEXT


def testCreateUserUseCaseAddsToRegistryAndDisk() -> None:
    with TemporaryDirectory() as tmp:
        memory_root = Path(tmp) / "memory"
        reg_path = Path(tmp) / "registry.yaml"
        registry = TelegramUserRegistryStore(in_registryFilePath=str(reg_path))
        memory_settings = MemorySettings(memoryRootPath=str(memory_root))
        use_case = CreateTelegramUserUseCase(
            in_registry_store=registry,
            in_memorySettings=memory_settings,
        )
        result = use_case.execute(in_telegramUserId=888, in_displayName="u", in_note="")
        assert result.ok is True
        assert registry.listRegisteredTelegramUserIds() == {888}
        session_dir = memory_root / "sessions" / "telegramUser_888"
        assert session_dir.is_dir()
        assert (session_dir / "tools.yaml").is_file()
        assert (session_dir / "schedules.yaml").is_file()
