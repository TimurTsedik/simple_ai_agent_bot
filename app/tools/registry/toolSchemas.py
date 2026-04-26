from pydantic import BaseModel, ConfigDict, Field


class DigestTelegramNewsArgsModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    keywords: list[str] = Field(default_factory=list)
    sinceUnixTs: int = Field(ge=0)
    maxItems: int = Field(default=10, ge=1, le=50)


class ReadMemoryFileArgsModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    relativePath: str = Field(min_length=1)
    maxChars: int = Field(default=4000, ge=256, le=200000)
