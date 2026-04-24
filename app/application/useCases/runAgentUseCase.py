from app.common.ids import generateId
from app.domain.entities.agentRun import AgentRunModel
from app.runtime.agentLoop import AgentLoop


class RunAgentUseCase:
    def __init__(self, in_agentLoop: AgentLoop) -> None:
        self._agentLoop = in_agentLoop

    def execute(self, in_sessionId: str, in_inputMessage: str) -> AgentRunModel:
        ret: AgentRunModel
        traceId = generateId()
        runId = generateId()
        loopResult = self._agentLoop.run(in_userMessage=in_inputMessage)
        ret = AgentRunModel(
            traceId=traceId,
            runId=runId,
            sessionId=in_sessionId,
            inputMessage=in_inputMessage,
            runStatus="completed",
            completionReason=loopResult.completionReason,
            finalAnswer=loopResult.finalAnswer,
            selectedModel=loopResult.selectedModel,
        )
        return ret
