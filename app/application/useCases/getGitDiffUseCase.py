from typing import Any

from app.integrations.git.gitService import GitService


class GetGitDiffUseCase:
    def __init__(self, in_gitService: GitService) -> None:
        self._gitService = in_gitService

    def execute(
        self,
        in_offset: int = 0,
        in_limit: int = 5,
        in_filePath: str = "",
        in_maxCharsPerFile: int = 30000,
    ) -> dict[str, Any]:
        ret = self._gitService.getDiff(
            in_offset=in_offset,
            in_limit=in_limit,
            in_filePath=in_filePath,
            in_maxCharsPerFile=in_maxCharsPerFile,
        )
        return ret
