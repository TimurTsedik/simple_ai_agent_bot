from app.domain.protocols.llmClientProtocol import LlmClientProtocol


class StaticLlmClient(LlmClientProtocol):
    def complete(self, in_modelName: str, in_promptText: str) -> str:
        ret: str
        _ = in_modelName
        _ = in_promptText
        ret = (
            '{"type":"stop","reason":"stage2_stub","final_answer":"'
            "Остановка: LLM provider будет подключен на следующем этапе."
            '"}'
        )
        return ret
