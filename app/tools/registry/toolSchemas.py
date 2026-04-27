from pydantic import BaseModel, ConfigDict, Field


class DigestTelegramNewsArgsModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    keywords: list[str] = Field(default_factory=list)
    sinceUnixTs: int = Field(default=0, ge=0)
    sinceHours: int = Field(default=0, ge=0, le=168)
    maxItems: int = Field(default=10, ge=1, le=50)


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
    sinceHours: int = Field(default=24, ge=0, le=168)
    maxItems: int = Field(default=10, ge=1, le=50)
    snippetChars: int = Field(default=300, ge=0, le=2000)
