from typing import Any

from app.integrations.git.gitService import GitService


class GetGitStatusUseCase:
    def __init__(self, in_gitService: GitService) -> None:
        self._gitService = in_gitService

    def execute(self, in_limit: int = 200) -> dict[str, Any]:
        ret = self._gitService.getStatus(in_limit=in_limit)
        return ret
