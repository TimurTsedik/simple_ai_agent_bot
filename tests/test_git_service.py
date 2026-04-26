from app.integrations.git.gitService import GitService


class FakeGitRunner:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def __call__(self, in_args: list[str], in_workingDirectory: str) -> tuple[int, str, str]:
        ret: tuple[int, str, str]
        _ = in_workingDirectory
        self.calls.append(in_args)
        commandKey = " ".join(in_args)
        if commandKey == "git rev-parse --is-inside-work-tree":
            ret = (0, "true\n", "")
        elif commandKey == "git status --short --branch":
            ret = (0, "## main\n M app/main.py\n?? tests/new_test.py\n", "")
        elif commandKey == "git diff --name-only":
            ret = (0, "app/main.py\n", "")
        elif commandKey == "git diff --name-only --cached":
            ret = (0, "README.md\n", "")
        elif commandKey == "git diff -- app/main.py":
            ret = (0, "diff --git a/app/main.py b/app/main.py\n+line\n", "")
        elif commandKey == "git diff --cached -- app/main.py":
            ret = (0, "", "")
        elif commandKey == "git diff -- README.md":
            ret = (0, "", "")
        elif commandKey == "git diff --cached -- README.md":
            ret = (0, "diff --git a/README.md b/README.md\n+doc\n", "")
        else:
            ret = (1, "", "unknown command")
        return ret


def testGitServiceStatusAndDiff() -> None:
    runner = FakeGitRunner()
    service = GitService(
        in_repoRootPath=".",
        in_commandRunner=runner,
    )

    status = service.getStatus(in_limit=10)
    diff = service.getDiff(in_offset=0, in_limit=10)

    assert status["isGitRepo"] is True
    assert status["branch"] == "main"
    assert len(status["items"]) == 2
    assert diff["isGitRepo"] is True
    assert diff["totalFiles"] == 2
    assert len(diff["files"]) == 2


def testGitServiceNonGitRepo() -> None:
    def runner(in_args: list[str], in_workingDirectory: str) -> tuple[int, str, str]:
        ret: tuple[int, str, str]
        _ = in_args
        _ = in_workingDirectory
        ret = (1, "", "not a git repository")
        return ret

    service = GitService(
        in_repoRootPath=".",
        in_commandRunner=runner,
    )

    status = service.getStatus()
    diff = service.getDiff()

    assert status["isGitRepo"] is False
    assert diff["isGitRepo"] is False
