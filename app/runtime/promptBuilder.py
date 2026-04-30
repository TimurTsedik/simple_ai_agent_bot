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
            "use configured defaults. If observation has digest data_preview.count=0 and "
            "data_preview.filteredOutByTime>0, perform one more digest call with broader sinceHours "
            "(72 then 168). For user feedback on liked digest items, follow the "
            "active skill: ask a short clarifying question first, then call save_digest_preference "
            "only after the user confirms what to remember.\n"
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
