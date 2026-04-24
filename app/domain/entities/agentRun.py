from pydantic import BaseModel


class AgentRunModel(BaseModel):
    traceId: str
    runId: str
    sessionId: str
    inputMessage: str
    runStatus: str
    completionReason: str | None
    finalAnswer: str | None
    selectedModel: str | None
