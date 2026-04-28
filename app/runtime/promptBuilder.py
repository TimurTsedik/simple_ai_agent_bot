from app.config.settingsModels import RuntimeSettings
from app.common.truncation import truncateText
from datetime import datetime, timezone


class PromptBuilder:
    def __init__(self, in_runtimeSettings: RuntimeSettings) -> None:
        self._runtimeSettings = in_runtimeSettings

    def buildPrompt(
        self,
        in_userMessage: str,
        in_observations: list[str],
        in_toolsDescription: str,
        in_skillsBlock: str,
        in_memoryBlock: str,
    ) -> str:
        ret: str
        nowUtcText = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        observationsBlock = "\n".join(in_observations)
        promptText = (
            "You are an AI runtime. Respond ONLY with one valid JSON object.\n"
            "Do not include markdown fences or any text outside JSON.\n"
            f"Current date/time: {nowUtcText}\n"
            "IMPORTANT JSON rule: Do NOT use literal newline characters inside JSON strings. "
            "If you need line breaks in final_answer, use the two-character sequence \\n.\n"
            "Allowed output schemas only:\n"
            '1) {"type":"tool_call","reason":"short","action":"tool_name","args":{}}\n'
            '2) {"type":"final","reason":"short","final_answer":"text"}\n'
            '3) {"type":"stop","reason":"short","final_answer":"safe stop message"}\n'
            "Never use keys tool, response, text, or content instead of required schema keys.\n"
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

    def buildJsonRepairPrompt(
        self,
        in_previousRawOutput: str,
        in_parseErrorCode: str | None,
        in_parseErrorMessage: str | None,
    ) -> str:
        ret: str
        errorCodeText = in_parseErrorCode or "unknown"
        errorMessageText = in_parseErrorMessage or ""
        promptText = (
            "You are an AI runtime. Your previous output was INVALID.\n"
            "Respond ONLY with one valid JSON object. No markdown fences, no text outside JSON.\n"
            "IMPORTANT JSON rule: Do NOT use literal newline characters inside JSON strings. "
            "If you need line breaks in final_answer, use the two-character sequence \\n.\n"
            "Do NOT output meta-statements about correction process.\n"
            "Your final_answer must be user-facing and solve the original request.\n"
            "Allowed output schemas only:\n"
            '1) {"type":"tool_call","reason":"short","action":"tool_name","args":{}}\n'
            '2) {"type":"final","reason":"short","final_answer":"text"}\n'
            '3) {"type":"stop","reason":"short","final_answer":"safe stop message"}\n'
            f"Parse error code: {errorCodeText}\n"
            f"Parse error detail: {errorMessageText}\n"
            "Your previous invalid output was:\n"
            f"{in_previousRawOutput}\n"
            "Fix it and output a single valid JSON object now.\n"
        )
        truncatedText, _isTruncated = truncateText(
            in_text=promptText,
            in_maxChars=self._runtimeSettings.maxPromptChars,
        )
        ret = truncatedText
        return ret
