from pydantic import BaseModel, Field


class AppSettings(BaseModel):
    appName: str
    environment: str
    dataRootPath: str
    displayTimeZone: str = Field(
        default="UTC",
        min_length=1,
        description="IANA time zone name for web admin display only (e.g. Europe/Moscow).",
    )


class TelegramSettings(BaseModel):
    pollingTimeoutSeconds: int = Field(ge=1, le=60)
    allowedUserIds: list[int]
    denyMessageText: str
    digestChannelUsernames: list[str] = Field(default_factory=list)
    portfolioTickers: list[str] = Field(default_factory=list)
    digestSemanticKeywords: list[str] = Field(default_factory=list)
    outboundHttpMaxConcurrent: int = Field(default=2, ge=1, le=32)
    outboundHttpMaxRetries: int = Field(default=2, ge=0, le=8)
    outboundHttpDefaultTimeoutSeconds: int = Field(default=45, ge=5, le=180)


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
    enabled: bool = False
    schedulesConfigPath: str = "./app/config/schedules.yaml"
    tickSeconds: int = Field(default=1, ge=1, le=30)
    jobs: list[SchedulerJobSettings] = Field(default_factory=list)


class TelegramNewsDigestToolSettings(BaseModel):
    digestChannelUsernames: list[str] = Field(default_factory=list)
    portfolioTickers: list[str] = Field(default_factory=list)
    digestSemanticKeywords: list[str] = Field(default_factory=list)


class EmailReaderToolSettings(BaseModel):
    accountName: str = "gmail"
    email: str = ""
    imapHost: str = "imap.gmail.com"
    imapPort: int = Field(default=993, ge=1, le=65535)
    imapSsl: bool = True
    smtpHost: str = "smtp.gmail.com"
    smtpPort: int = Field(default=465, ge=1, le=65535)
    smtpSsl: bool = True


class ToolsSettings(BaseModel):
    toolsConfigPath: str = "./app/config/tools.yaml"
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
    skills: SkillsSettings = Field(default_factory=SkillsSettings)
    memory: MemorySettings = Field(default_factory=MemorySettings)
    scheduler: SchedulerSettings = Field(default_factory=SchedulerSettings)

    telegramBotToken: str = Field(min_length=1)
    openRouterApiKey: str = Field(min_length=1)
    sessionCookieSecret: str = Field(min_length=32)
    emailAppPassword: str = Field(default="")
    adminRawTokens: list[str] = Field(default_factory=list)
