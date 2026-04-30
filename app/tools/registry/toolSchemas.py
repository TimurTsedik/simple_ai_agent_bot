from pydantic import BaseModel, ConfigDict, Field


class DigestTelegramNewsArgsModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    keywords: list[str] = Field(default_factory=list, max_length=40)
    channels: list[str] = Field(
        default_factory=list,
        max_length=30,
        description="Public channel usernames (with or without @). Empty = use configured default channels.",
    )
    topics: list[str] = Field(
        default_factory=list,
        max_length=12,
        description="Topic ids (e.g. ai, economy, crypto). Adds seed keywords before config defaults.",
    )
    sinceUnixTs: int = Field(default=0, ge=0)
    sinceHours: int = Field(default=0, ge=0, le=168)
    maxItems: int = Field(default=10, ge=1, le=50)


class SaveDigestPreferenceArgsModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    likedTopics: list[str] = Field(default_factory=list, max_length=12)
    likedChannels: list[str] = Field(default_factory=list, max_length=30)
    likedKeywords: list[str] = Field(default_factory=list, max_length=30)
    userNote: str = Field(default="", max_length=800)


class SaveEmailPreferenceArgsModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    preferredSenders: list[str] = Field(default_factory=list, max_length=50)
    preferredKeywords: list[str] = Field(default_factory=list, max_length=30)
    userNote: str = Field(default="", max_length=800)


class ReadMemoryFileArgsModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    relativePath: str = Field(min_length=1)
    maxChars: int = Field(default=4000, ge=256, le=200000)


class WebSearchArgsModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=1)
    maxResults: int = Field(default=10, ge=1, le=10)
    fetchTopN: int = Field(default=5, ge=0, le=5)
    maxCharsPerPage: int = Field(default=8000, ge=256, le=200000)


class ReadEmailArgsModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mailbox: str = Field(default="INBOX", min_length=1)
    unreadOnly: bool = True
    markAsRead: bool = True
    sinceHours: int = Field(default=24, ge=0, le=168)
    maxItems: int = Field(default=10, ge=1, le=50)
    snippetChars: int = Field(default=300, ge=0, le=2000)
