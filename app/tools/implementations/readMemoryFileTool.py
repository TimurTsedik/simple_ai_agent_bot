from pathlib import Path


class ReadMemoryFileTool:
    def __init__(self, in_allowedReadOnlyPaths: list[str]) -> None:
        self._allowedRoots = [Path(item).resolve() for item in in_allowedReadOnlyPaths]

    def execute(self, in_args: dict) -> dict[str, str]:
        ret: dict[str, str]
        relativePath = str(in_args.get("relativePath", ""))
        maxChars = int(in_args.get("maxChars", 4000))
        targetPath = Path(relativePath)
        resolvedPath = targetPath.resolve()

        isAllowed = False
        for rootPath in self._allowedRoots:
            if resolvedPath.is_relative_to(rootPath):
                isAllowed = True
                break
        if isAllowed is False:
            raise PermissionError("Requested path is outside of read-only whitelist.")
        if resolvedPath.exists() is False:
            raise FileNotFoundError("Requested file is not found.")
        if resolvedPath.is_file() is False:
            raise FileNotFoundError("Requested path is not a file.")
        content = resolvedPath.read_text(encoding="utf-8")
        ret = {"content": content[:maxChars], "path": str(resolvedPath)}
        return ret
