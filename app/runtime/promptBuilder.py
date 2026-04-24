from app.config.settingsModels import RuntimeSettings
from app.common.truncation import truncateText


class PromptBuilder:
    def __init__(self, in_runtimeSettings: RuntimeSettings) -> None:
        self._runtimeSettings = in_runtimeSettings

    def buildPrompt(self, in_userMessage: str, in_observations: list[str]) -> str:
        ret: str
        observationsBlock = "\n".join(in_observations)
        promptText = (
            "You are an AI runtime. Respond only with strict JSON.\n"
            "Allowed output types: tool_call, final, stop.\n"
            f"User message:\n{in_userMessage}\n"
            f"Observations:\n{observationsBlock}\n"
        )
        truncatedText, _isTruncated = truncateText(
            in_text=promptText,
            in_maxChars=self._runtimeSettings.maxPromptChars,
        )
        ret = truncatedText
        return ret
