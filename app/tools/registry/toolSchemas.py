from pydantic import BaseModel, ConfigDict, Field, model_validator


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


class ScheduleReminderArgsModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reminderId: str = Field(
        default="",
        description="Optional id for update. Empty = create new reminder id.",
    )
    enabled: bool = True
    message: str = Field(min_length=1, max_length=4000)
    scheduleType: str = Field(
        default="daily",
        description='Reminder schedule kind: "daily" or "weekly".',
    )
    weekdays: list[int] = Field(
        default_factory=list,
        description="0=Mon..6=Sun. Required for scheduleType=weekly.",
    )
    timeLocal: str = Field(
        min_length=4,
        max_length=5,
        description='Local time in "HH:MM".',
    )
    timeZone: str = Field(
        default="",
        description="IANA time zone name. Empty = use app.displayTimeZone.",
    )
    remainingRuns: int | None = Field(
        default=None,
        ge=1,
        description="Optional run limit. Null means unlimited.",
    )

    @model_validator(mode="after")
    def _validateSchedulePayload(self):
        ret = self
        scheduleTypeValue = str(self.scheduleType or "").strip().lower()
        if scheduleTypeValue == "once":
            self.scheduleType = "daily"
            self.weekdays = []
            if self.remainingRuns is None:
                self.remainingRuns = 1
            scheduleTypeValue = "daily"
        if scheduleTypeValue not in {"daily", "weekly"}:
            raise ValueError('scheduleType must be either "daily" or "weekly".')
        if scheduleTypeValue == "weekly" and len(self.weekdays) == 0:
            raise ValueError("weekdays must be provided for weekly schedule.")
        if scheduleTypeValue == "daily" and len(self.weekdays) > 0:
            raise ValueError("weekdays must be empty for daily schedule.")
        for weekdayItem in self.weekdays:
            if int(weekdayItem) < 0 or int(weekdayItem) > 6:
                raise ValueError("weekdays must contain values in range 0..6.")
        return ret


class ListRemindersArgsModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DeleteReminderArgsModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reminderId: str = Field(min_length=1)
