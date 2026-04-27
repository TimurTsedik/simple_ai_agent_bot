from pydantic import BaseModel, Field


class AppSettings(BaseModel):
    appName: str
    environment: str
    dataRootPath: str


class TelegramSettings(BaseModel):
    pollingTimeoutSeconds: int = Field(ge=1, le=60)
    allowedUserIds: list[int]
    denyMessageText: str
    digestChannelUsernames: list[str] = Field(default_factory=list)
    portfolioTickers: list[str] = Field(default_factory=list)
    digestSemanticKeywords: list[str] = Field(default_factory=list)


class ModelSettings(BaseModel):
    openRouterBaseUrl: str
    primaryModel: str
    secondaryModel: str
    tertiaryModel: str
    requestTimeoutSeconds: int = Field(ge=5, le=300)
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
    maxExtraSecondsTotal: int = Field(default=180, ge=0, le=1800)


class SecuritySettings(BaseModel):
    webSessionCookieTtlSeconds: int = Field(ge=300, le=604800)
    maxAdminTokens: int = Field(ge=1, le=10)
    allowedReadOnlyPaths: list[str]
    adminWritesEnabled: bool = False


class LoggingSettings(BaseModel):
    logsDirPath: str
    runLogsFileName: str
    appLogsFileName: str
    maxBytes: int = Field(ge=1024, le=104857600)
    backupCount: int = Field(ge=1, le=20)


class SkillsSettings(BaseModel):
    skillsDirPath: str = "./app/skills/assets"


class MemorySettings(BaseModel):
    memoryRootPath: str = "./data/memory"
    longTermFileName: str = "long_term.md"
    sessionSummaryFileName: str = "summary.md"
    recentMessagesFileName: str = "recent.md"


class TelegramNewsDigestToolSettings(BaseModel):
    digestChannelUsernames: list[str] = Field(default_factory=list)
    portfolioTickers: list[str] = Field(default_factory=list)
    digestSemanticKeywords: list[str] = Field(default_factory=list)


class ToolsSettings(BaseModel):
    toolsConfigPath: str = "./app/config/tools.yaml"
    telegramNewsDigest: TelegramNewsDigestToolSettings = Field(
        default_factory=TelegramNewsDigestToolSettings
    )


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

    telegramBotToken: str = Field(min_length=1)
    openRouterApiKey: str = Field(min_length=1)
    sessionCookieSecret: str = Field(min_length=32)
    adminRawTokens: list[str] = Field(default_factory=list)
