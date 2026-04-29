from app.domain.entities.llmCompletionResult import LlmCompletionResultModel
from app.domain.protocols.llmClientProtocol import LlmClientProtocol


class StaticLlmClient(LlmClientProtocol):
    def complete(
        self,
        in_modelName: str,
        in_promptText: str,
        *,
        in_timeoutSeconds: int | None = None,
        in_useJsonObjectResponseFormat: bool = False,
    ) -> LlmCompletionResultModel:
        ret: LlmCompletionResultModel
        _ = (in_promptText, in_timeoutSeconds, in_useJsonObjectResponseFormat)
        contentValue = (
            '{"type":"stop","reason":"stage2_stub","final_answer":"'
            "Остановка: LLM provider будет подключен на следующем этапе."
            '"}'
        )
        ret = LlmCompletionResultModel(
            content=contentValue,
            selectedModel=in_modelName,
            fallbackEvents=(),
        )
        return ret
