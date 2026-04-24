from app.config.settingsModels import RuntimeSettings
from app.common.truncation import truncateText


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
        observationsBlock = "\n".join(in_observations)
        promptText = (
            "You are an AI runtime. Respond ONLY with one valid JSON object.\n"
            "Do not include markdown fences or any text outside JSON.\n"
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
