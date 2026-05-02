from app.common.adminTenantConfigPaths import (
    resolveAdminTenantSchedulesYamlPath,
    resolveAdminTenantSessionDirectoryPath,
    resolveAdminTenantToolsYamlPath,
)


def testResolveAdminTenantPathsUseAdminSessionSegment() -> None:
    session_dir = resolveAdminTenantSessionDirectoryPath(
        in_memoryRootPath="/data/mem",
        in_adminTelegramUserId=16739703,
    )
    assert session_dir.name == "telegramUser_16739703"
    tools_path = resolveAdminTenantToolsYamlPath(
        in_memoryRootPath="/data/mem",
        in_adminTelegramUserId=16739703,
    )
    assert tools_path.name == "tools.yaml"
    assert tools_path.parent.name == "telegramUser_16739703"
    schedules_path = resolveAdminTenantSchedulesYamlPath(
        in_memoryRootPath="/data/mem",
        in_adminTelegramUserId=16739703,
    )
    assert schedules_path.name == "schedules.yaml"
