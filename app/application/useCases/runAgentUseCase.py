from app.common.ids import generateId
from app.domain.entities.agentRun import AgentRunModel
from app.memory.services.memoryService import MemoryService
from app.runtime.agentLoop import AgentLoop
from app.skills.services.skillService import SkillService


class RunAgentUseCase:
    def __init__(
        self,
        in_agentLoop: AgentLoop,
        in_skillService: SkillService,
        in_memoryService: MemoryService,
    ) -> None:
        self._agentLoop = in_agentLoop
        self._skillService = in_skillService
        self._memoryService = in_memoryService

    def execute(self, in_sessionId: str, in_inputMessage: str) -> AgentRunModel:
        ret: AgentRunModel
        traceId = generateId()
        runId = generateId()
        skillsBlock = self._skillService.buildSkillsBlock(in_userMessage=in_inputMessage)
        memoryBlock = self._memoryService.buildMemoryBlock(in_sessionId=in_sessionId)
        loopResult = self._agentLoop.run(
            in_userMessage=in_inputMessage,
            in_skillsBlock=skillsBlock,
            in_memoryBlock=memoryBlock,
        )
        self._memoryService.updateAfterRun(
            in_sessionId=in_sessionId,
            in_userMessage=in_inputMessage,
            in_finalAnswer=loopResult.finalAnswer,
            in_memoryCandidates=loopResult.memoryCandidates,
        )
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
