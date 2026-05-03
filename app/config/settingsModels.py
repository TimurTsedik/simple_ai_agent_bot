from pydantic import BaseModel, ConfigDict, Field


class AppSettings(BaseModel):
    appName: str
    environment: str
    dataRootPath: str
    displayTimeZone: str = Field(
        default="UTC",
        min_length=1,
        description="IANA time zone name for web admin display only (e.g. Europe/Moscow).",
    )
    usersRegistryPath: str = Field(
        default="./data/users/registry.yaml",
        min_length=1,
        description="Общий YAML: разрешённые пользователи Telegram и метаданные (единственный источник whitelist).",
    )


class TelegramSettings(BaseModel):
    pollingTimeoutSeconds: int = Field(ge=1, le=60)
    denyMessageText: str
    digestChannelUsernames: list[str] = Field(default_factory=list)
    portfolioTickers: list[str] = Field(default_factory=list)
    digestSemanticKeywords: list[str] = Field(default_factory=list)
    outboundHttpMaxConcurrent: int = Field(default=2, ge=1, le=32)
    outboundHttpMaxRetries: int = Field(default=2, ge=0, le=8)
    outboundHttpDefaultTimeoutSeconds: int = Field(default=45, ge=5, le=180)
    voiceLanguage: str = Field(
        default="",
        description="Optional language hint for voice transcription (e.g. ru, en). Empty = auto.",
    )
    voiceModelName: str = Field(
        default="small",
        description="faster-whisper model name (e.g. tiny, base, small, medium, large-v3).",
    )
    voiceComputeType: str = Field(
        default="int8",
        description="CTranslate2 compute type for CPU (e.g. int8, int8_float16, float16).",
    )
    voiceMaxSeconds: int = Field(
        default=60,
        ge=1,
        le=600,
        description="Max allowed voice duration (seconds) for synchronous transcription.",
    )
    voiceMaxBytes: int = Field(
        default=5_000_000,
        ge=50_000,
        le=50_000_000,
        description="Max allowed file size (bytes) for voice/audio download.",
    )


class ModelSettings(BaseModel):
    openRouterBaseUrl: str
    primaryModel: str
    secondaryModel: str
    tertiaryModel: str
    requestTimeoutSeconds: int = Field(ge=5, le=300)
    formatRepairRequestTimeoutSeconds: int = Field(
        default=45,
        ge=5,
        le=300,
        description="HTTP timeout for format-repair prompts (YAML remediation).",
    )
    retryCountBeforeFallback: int = Field(ge=0, le=5)
    returnToPrimaryCooldownSeconds: int = Field(ge=60, le=86400)


class RuntimeSettings(BaseModel):
    maxSteps: int = Field(ge=1, le=50)
    maxToolCalls: int = Field(ge=0, le=100)
    maxExecutionSeconds: int = Field(ge=1, le=1800)
    maxToolOutputChars: int = Field(ge=256, le=200000)
    maxPromptChars: int = Field(ge=1024, le=500000)
    recentMessagesLimit: int = Field(ge=1, le=50)
    sessionSummaryMaxChars: int = Field(ge=256, le=10000)
    skillSelectionMaxCount: int = Field(ge=1, le=4)
    toolCallHistoryWindowSize: int = Field(default=8, ge=2, le=30)
    maxSameToolSignatureInWindow: int = Field(default=3, ge=2, le=10)
    maxToolCallBlockedIterations: int = Field(default=3, ge=1, le=10)
    extraSecondsPerLlmError: int = Field(default=45, ge=0, le=600)
    extraSecondsPerFormatFailureStep: int = Field(
        default=30,
        ge=0,
        le=600,
        description="Extra execution budget per step where YAML/format repair was exhausted.",
    )
    maxExtraSecondsTotal: int = Field(default=180, ge=0, le=1800)
    maxFormatRepairAttempts: int = Field(
        default=4,
        ge=1,
        le=10,
        description="LLM repair calls after an invalid runtime response in one agent step.",
    )
    maxConsecutiveFormatFailureSteps: int = Field(
        default=3,
        ge=1,
        le=20,
        description="Stop after this many consecutive steps with exhausted format repair.",
    )


class SecuritySettings(BaseModel):
    webSessionCookieTtlSeconds: int = Field(ge=300, le=604800)
    maxAdminTokens: int = Field(ge=1, le=10)
    allowedReadOnlyPaths: list[str]
    adminWritesEnabled: bool = False
    bindSessionToIp: bool = Field(
        default=False,
        description="If true, web session cookie is bound to client IP (helps against stolen cookies).",
    )
    trustProxyHeaders: bool = Field(
        default=False,
        description="If true, X-Forwarded-For may be used to resolve client IP (only when request comes from a trusted proxy).",
    )
    trustedProxyIps: list[str] = Field(
        default_factory=list,
        description="Trusted proxy IPs allowed to set X-Forwarded-For when trustProxyHeaders=true.",
    )


class LoggingSettings(BaseModel):
    logsDirPath: str
    runLogsFileName: str
    appLogsFileName: str
    maxBytes: int = Field(ge=1024, le=104857600)
    backupCount: int = Field(ge=1, le=20)


class SentrySettings(BaseModel):
    enabled: bool = False
    dsn: str = ""
    environment: str = ""
    release: str = ""
    tracesSampleRate: float = Field(default=0.0, ge=0.0, le=1.0)
    profilesSampleRate: float = Field(default=0.0, ge=0.0, le=1.0)
    sendDefaultPii: bool = False


class SkillsSettings(BaseModel):
    # In production containers, code directories are typically read-only.
    # Default to a writable data directory (mounted volume) so admin skill editing works.
    skillsDirPath: str = "./data/skills"


class MemorySettings(BaseModel):
    memoryRootPath: str = "./data/memory"
    longTermFileName: str = "long_term.md"
    sessionSummaryFileName: str = "summary.md"
    recentMessagesFileName: str = "recent.md"


class SchedulerJobInternalRunAction(BaseModel):
    sessionId: str = "scheduler:default"
    message: str = ""


class SchedulerJobSchedule(BaseModel):
    intervalSeconds: int = Field(default=3600, ge=5, le=604800)
    allowedHourStart: int | None = Field(default=None, ge=0, le=23)
    allowedHourEnd: int | None = Field(default=None, ge=0, le=23)


class SchedulerJobSettings(BaseModel):
    jobId: str
    enabled: bool = True
    schedule: SchedulerJobSchedule = Field(default_factory=SchedulerJobSchedule)
    actionInternalRun: SchedulerJobInternalRunAction = Field(
        default_factory=SchedulerJobInternalRunAction
    )


class SchedulerSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    tickSeconds: int = Field(default=1, ge=1, le=30)


class ReminderScheduleModel(BaseModel):
    kind: str = Field(
        default="daily",
        description='Schedule kind: "daily" or "weekly".',
    )
    weekdays: list[int] = Field(
        default_factory=list,
        description="0=Mon..6=Sun. Used only when kind=weekly.",
    )
    timeLocal: str = Field(
        default="09:00",
        min_length=4,
        max_length=5,
        description='Local time "HH:MM".',
    )
    timeZone: str = Field(
        default="",
        description="IANA time zone name. Empty means use app.displayTimeZone.",
    )
    remainingRuns: int | None = Field(
        default=None,
        ge=1,
        description="If set, decremented on each fire; reminder disables when reaches 0.",
    )


class ReminderModel(BaseModel):
    reminderId: str = Field(min_length=1)
    enabled: bool = True
    message: str = Field(default="", max_length=4000)
    schedule: ReminderScheduleModel = Field(default_factory=ReminderScheduleModel)
    ownerMemoryPrincipalId: str = Field(
        default="",
        description='Tenant key, напр. telegramUser:123. Пусто = без привязки к tenant (только admin-контекст).',
    )
    createdAtUnixTs: int | None = Field(default=None, ge=0)
    lastFiredAtUnixTs: int | None = Field(default=None, ge=0)
    nextFireAtUnixTs: int | None = Field(default=None, ge=0)


class TelegramNewsDigestToolSettings(BaseModel):
    digestChannelUsernames: list[str] = Field(default_factory=list)
    portfolioTickers: list[str] = Field(default_factory=list)
    digestSemanticKeywords: list[str] = Field(default_factory=list)


class EmailReaderToolSettings(BaseModel):
    accountName: str = "gmail"
    email: str = ""
    password: str = ""
    imapHost: str = "imap.gmail.com"
    imapPort: int = Field(default=993, ge=1, le=65535)
    imapSsl: bool = True
    smtpHost: str = "smtp.gmail.com"
    smtpPort: int = Field(default=465, ge=1, le=65535)
    smtpSsl: bool = True


class ToolsSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    telegramNewsDigest: TelegramNewsDigestToolSettings = Field(
        default_factory=TelegramNewsDigestToolSettings
    )
    emailReader: EmailReaderToolSettings = Field(default_factory=EmailReaderToolSettings)


class SettingsModel(BaseModel):
    app: AppSettings
    telegram: TelegramSettings
    models: ModelSettings
    runtime: RuntimeSettings
    tools: ToolsSettings = Field(default_factory=ToolsSettings)
    security: SecuritySettings
    logging: LoggingSettings
    sentry: SentrySettings = Field(default_factory=SentrySettings)
    skills: SkillsSettings = Field(default_factory=SkillsSettings)
    memory: MemorySettings = Field(default_factory=MemorySettings)
    scheduler: SchedulerSettings = Field(default_factory=SchedulerSettings)
    adminTenantToolsYamlPath: str = Field(
        default="",
        description=(
            "Абсолютный путь к tenant tools.yaml администратора; выставляется только в loadSettings."
        ),
    )
    adminTenantSchedulesYamlPath: str = Field(
        default="",
        description=(
            "Абсолютный путь к tenant schedules.yaml администратора; выставляется только в loadSettings."
        ),
    )

    telegramBotToken: str = Field(min_length=1)
    openRouterApiKey: str = Field(min_length=1)
    sessionCookieSecret: str = Field(min_length=32)
    emailAppPassword: str = Field(default="")
    adminRawTokens: list[str] = Field(default_factory=list)
    adminTelegramUserId: int = Field(
        default=16739703,
        ge=1,
        description="Telegram user id владельца админки / дефолтного tenant для scoped UI.",
    )
