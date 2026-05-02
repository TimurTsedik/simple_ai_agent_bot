"""Минимальное содержимое для автосоздания tools.yaml / schedules.yaml в каталоге сессии (без файлов-примеров в репозитории)."""

DEFAULT_TENANT_TOOLS_YAML_TEXT = (
    "emailReader:\n"
    '  accountName: "gmail"\n'
    '  email: ""\n'
    '  password: ""\n'
    '  imapHost: "imap.gmail.com"\n'
    "  imapPort: 993\n"
    "  imapSsl: true\n"
    '  smtpHost: "smtp.gmail.com"\n'
    "  smtpPort: 465\n"
    "  smtpSsl: true\n"
)

DEFAULT_TENANT_SCHEDULES_YAML_TEXT = "scheduledTasks: []\n"
