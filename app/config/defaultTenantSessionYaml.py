"""Минимальное содержимое для автосоздания tools.yaml / schedules.yaml в каталоге сессии (без файлов-примеров в репозитории)."""

DEFAULT_TENANT_TOOLS_YAML_TEXT = (
    "telegramNewsDigest:\n"
    "  digestChannelUsernames: []\n"
    "  portfolioTickers: []\n"
    "  digestSemanticKeywords: []\n"
    "\n"
    "emailReader:\n"
    '  accountName: "gmail"\n'
    '  email: ""\n'
    '  imapHost: "imap.gmail.com"\n'
    "  imapPort: 993\n"
    "  imapSsl: true\n"
    '  smtpHost: "smtp.gmail.com"\n'
    "  smtpPort: 465\n"
    "  smtpSsl: true\n"
)

DEFAULT_TENANT_SCHEDULES_YAML_TEXT = "jobs: []\nreminders: []\n"
