from app.domain.entities.llmCompletionResult import LlmCompletionResultModel
from app.domain.protocols.llmClientProtocol import LlmClientProtocol


class StaticLlmClient(LlmClientProtocol):
    def complete(
        self, in_modelName: str, in_promptText: str
    ) -> LlmCompletionResultModel:
        ret: LlmCompletionResultModel
        _ = in_promptText
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
