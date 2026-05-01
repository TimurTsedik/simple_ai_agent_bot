from app.config.settingsModels import RuntimeSettings
from app.common.truncation import truncateText
from datetime import datetime, timezone
from typing import Callable
from zoneinfo import ZoneInfo


class PromptBuilder:
    def __init__(
        self,
        in_runtimeSettings: RuntimeSettings,
        in_displayTimeZoneName: str = "UTC",
        in_nowUtcProvider: Callable[[], datetime] | None = None,
    ) -> None:
        self._runtimeSettings = in_runtimeSettings
        self._displayTimeZoneName = str(in_displayTimeZoneName or "UTC").strip() or "UTC"
        self._nowUtcProvider = in_nowUtcProvider or (lambda: datetime.now(timezone.utc))

    def _buildTimeContextBlock(self) -> str:
        ret: str
        nowUtcValue = self._nowUtcProvider()
        if nowUtcValue.tzinfo is None:
            nowUtcValue = nowUtcValue.replace(tzinfo=timezone.utc)
        nowUtcValue = nowUtcValue.astimezone(timezone.utc)
        configuredTimeZoneName = self._displayTimeZoneName
        effectiveTimeZoneName = configuredTimeZoneName
        try:
            configuredZone = ZoneInfo(configuredTimeZoneName)
        except Exception:
            configuredZone = ZoneInfo("UTC")
            effectiveTimeZoneName = "UTC"
        configuredLocalNow = nowUtcValue.astimezone(configuredZone)
        ret = (
            f"Server current UTC time: {nowUtcValue.strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
            f"Configured business timezone: {configuredTimeZoneName}\n"
            f"Current time in configured timezone ({effectiveTimeZoneName}): "
            f"{configuredLocalNow.strftime('%Y-%m-%d %H:%M:%S')}\n"
        )
        return ret

    def buildPrompt(
        self,
        in_userMessage: str,
        in_observations: list[str],
        in_toolsDescription: str,
        in_skillsBlock: str,
        in_memoryBlock: str,
    ) -> str:
        ret: str
        timeContextBlock = self._buildTimeContextBlock()
        observationsBlock = "\n".join(in_observations)
        promptText = (
            "You are an AI runtime. Respond ONLY with one valid YAML document (a single mapping).\n"
            "Do not wrap in markdown fences. Do not add any prose before or after the YAML.\n"
            f"{timeContextBlock}"
            "YAML rule for multi-line user-visible text: use a literal block scalar for final_answer, e.g.\n"
            "final_answer: |\n"
            "  line one\n"
            "  line two\n"
            "Or keep final_answer on one line; escape quotes inside double-quoted strings as needed.\n"
            "Allowed shapes only:\n"
            "1)\n"
            "type: tool_call\n"
            "reason: short\n"
            "action: tool_name\n"
            "args: {}\n"
            "2)\n"
            "type: final\n"
            "reason: short\n"
            "final_answer: \"text or block\"\n"
            "3)\n"
            "type: stop\n"
            "reason: short\n"
            "final_answer: safe stop message\n"
            "Never use keys tool, response, text, or content instead of required schema keys.\n"
            "For digest_telegram_news: pass channels/topics/keywords in args when the user names "
            "channels (@handle), themes (AI/economy/etc.), or filter words; empty channels means "
            "use configured defaults when the server has defaults. If observation JSON includes "
            "data_preview.digest_followup_hint.suggest_configure_named_topic_digest=true, do NOT answer "
            "final with only «nothing found»; immediately tool_call user_topic_telegram_digest with "
            "fetchUnread=false and topic derived from the user message (e.g. economy/экономика), then "
            "follow user_topic statuses (needs_channels/needs_keywords). If observation has digest "
            "data_preview.count=0 and data_preview.filteredOutByTime>0, retry digest_telegram_news with "
            "broader sinceHours (72 then 168). For user_topic_telegram_digest: use fetchUnread=false "
            "to configure/check "
            "(merge channels/keywords); put Telegram channels only as @username or t.me/name in channels "
            "(bare Latin tickers like POSI belong in keywords, not channels); follow status "
            "needs_channels/needs_keywords with a user-facing "
            "final question; only call fetchUnread=true after status=ready; deleteTopic=true removes saved "
            "topic settings from long-term memory. For user feedback on liked digest items, follow the "
            "active skill: ask a short clarifying question first, then call save_digest_preference "
            "only after the user confirms what to remember.\n"
            "For schedule_reminder: NEVER use scheduleType=once. Allowed values are daily|weekly only. "
            "If user asks one-time reminder, map it to scheduleType=daily with remainingRuns=1 and weekdays=[]. "
            "If user asks relative time like 'in N minutes/hours', compute absolute HH:MM using "
            "Current time in configured timezone and call schedule_reminder immediately; do not ask extra clarification. "
            "Do not claim reminder is set until schedule_reminder tool returns ok=true. "
            "If previous observation contains schedule_reminder VALIDATION_ERROR, immediately retry "
            "with corrected args in the next tool_call.\n"
            f"Available tools:\n{in_toolsDescription}\n"
            f"Relevant skills:\n{in_skillsBlock}\n"
            f"Memory block:\n{in_memoryBlock}\n"
            f"User message:\n{in_userMessage}\n"
            f"Observations:\n{observationsBlock}\n"
        )
        truncatedText, _isTruncated = truncateText(
            in_text=promptText,
            in_maxChars=self._runtimeSettings.maxPromptChars,
        )
        ret = truncatedText
        return ret

    def buildRoutingPrompt(
        self,
        in_userMessage: str,
        in_registeredToolBulletList: str,
        in_skillsCatalogBlock: str,
    ) -> str:
        ret: str
        timeContextBlockText = self._buildTimeContextBlock()
        routingContractText = (
            "You are a routing classifier for this AI agent runtime.\n"
            "Return ONLY one valid YAML document (single mapping). "
            "No markdown fences and no prose before or after YAML.\n"
            "Exactly this shape:\n"
            "type: route_plan\n"
            "selected_skill_ids:\n"
            "  - skill_id_from_catalog\n"
            "allow_tool_calls: true|false\n"
            "required_first_successful_tool_name: \"\"|registered_tool_name\n"
            "memory_mode: full|long_term_only\n"
            "Rules:\n"
            "- `selected_skill_ids` MUST be copied from Known skills catalog ids only "
            "(multi-select, ordering preserved).\n"
            "- Always include skill `default_assistant` unless strictly impossible "
            "(if unsure, include it).\n"
            "- `allow_tool_calls` is false only for greeting/small-talk/clarifying question "
            "without tools, or purely conversational requests that need no integrations.\n"
            "- When `allow_tool_calls` is false, set `required_first_successful_tool_name` to \"\".\n"
            "- Feedback-only preference skills MUST NOT force a tool-call gate: "
            "if ids include telegram_digest_feedback or email_preference_feedback, "
            "`required_first_successful_tool_name` MUST be \"\".\n"
            "- `required_first_successful_tool_name` must be \"\" or "
            "one of Registered tool names. It is enforced before the assistant may answer:\n"
            "  compose_digest AND read_and_analyze_email activated together → "
            "`read_email`;\n"
            "  read_and_analyze_email without compose_digest digest intent → "
            "`read_email`;\n"
            "  user_topic_telegram_digest → `user_topic_telegram_digest`;\n"
            "  telegram_news_digest → `digest_telegram_news`;\n"
            "  otherwise → \"\" unless user clearly needs another registered tool immediately.\n"
            "- Thematic digest wording (economics/markets/Tech topic area / naming a SUBJECT AREA) "
            "without listing @channels and WITHOUT an explicit time-window phrase "
            "(e.g. «за последний час», «за день», «за час», «сегодня» in the NEWS digest sense) "
            "→ prefer skill `user_topic_telegram_digest` and "
            "`required_first_successful_tool_name: user_topic_telegram_digest`. "
            "Topic-level digests need per-user channels/keywords; use `telegram_news_digest` when the "
            "user wants preset/default channels snapshot or names a rolling time window "
            "(or lists @handles for one-off fetch).\n"
            "- Follow-up Telegram topic digest configuration (only channel handles / "
            "only keyword lists) still needs tools: "
            "`allow_tool_calls: true`, skill `user_topic_telegram_digest`, "
            "required_first_successful_tool_name: `user_topic_telegram_digest`. "
            "If the message is mainly comma-separated "
            "`@channel` / `t.me/...` handles (digest setup follow-up), never set "
            "`allow_tool_calls: false`.\n"
            "- Email digest wording (письма/писем/inbox/email/почта/непрочитанн) → activate "
            "read_and_analyze_email (+ compose_digest if user asks explicitly for compose digest), "
            "required_first_successful_tool_name: `read_email` when почта должна быть прочитана.\n"
            "- `memory_mode` is long_term_only when scheduled email compose digest pipelines "
            "need fresh mailbox reads without session chatter; typical when BOTH "
            "`compose_digest` and `read_and_analyze_email` are selected for digest composition. "
            "Otherwise prefer full.\n"
            "Known skills catalog:\n"
            f"{in_skillsCatalogBlock}\n"
            "Registered tool names:\n"
            f"{in_registeredToolBulletList}\n"
            f"{timeContextBlockText}"
            f"User message:\n{in_userMessage}\n"
        )
        truncatedRoutingText, _routingTruncated = truncateText(
            in_text=routingContractText,
            in_maxChars=self._runtimeSettings.maxPromptChars,
        )
        ret = truncatedRoutingText
        return ret

    def buildYamlRepairPrompt(
        self,
        in_previousRawOutput: str,
        in_parseErrorCode: str | None,
        in_parseErrorMessage: str | None,
        in_attemptIndexOneBased: int,
        in_maxAttempts: int,
    ) -> str:
        ret: str
        errorCodeText = in_parseErrorCode or "unknown"
        errorMessageText = in_parseErrorMessage or ""
        promptText = (
            "You are an AI runtime. Your previous output was INVALID for this runtime.\n"
            f"Repair attempt {in_attemptIndexOneBased} of {in_maxAttempts}.\n"
            "Respond ONLY with one valid YAML document (single mapping). "
            "No markdown fences, no commentary outside YAML.\n"
            "Use a literal block (|) for final_answer if the answer is long.\n"
            "Do NOT output meta-statements about correction process.\n"
            "Your final_answer must be user-facing and solve the original request.\n"
            "Important: for schedule_reminder use only scheduleType=daily|weekly (never once). "
            "If a one-time reminder is needed, use daily + remainingRuns=1.\n"
            "Allowed shapes only:\n"
            "1)\n"
            "type: tool_call\n"
            "reason: short\n"
            "action: tool_name\n"
            "args: {}\n"
            "2)\n"
            "type: final\n"
            "reason: short\n"
            "final_answer: |\n"
            "  ...\n"
            "3)\n"
            "type: stop\n"
            "reason: short\n"
            "final_answer: ...\n"
            f"Parse error code: {errorCodeText}\n"
            f"Parse error detail: {errorMessageText}\n"
            "Your previous invalid output was:\n"
            f"{in_previousRawOutput}\n"
            "Fix it and output a single valid YAML document now.\n"
        )
        truncatedText, _isTruncated = truncateText(
            in_text=promptText,
            in_maxChars=self._runtimeSettings.maxPromptChars,
        )
        ret = truncatedText
        return ret
