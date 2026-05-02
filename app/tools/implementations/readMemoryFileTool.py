from pathlib import Path


class ReadMemoryFileTool:
    def __init__(
        self,
        in_memoryRootPath: str,
        in_allowedReadOnlyPaths: list[str],
    ) -> None:
        self._memoryRootPath = Path(in_memoryRootPath).resolve()
        self._sessionsRootPath = (self._memoryRootPath / "sessions").resolve()
        self._allowedRoots = [Path(item).resolve() for item in in_allowedReadOnlyPaths]

    def execute(
        self,
        in_args: dict,
        *,
        in_memoryPrincipalId: str,
    ) -> dict[str, str]:
        ret: dict[str, str]
        relativePath = str(in_args.get("relativePath", ""))
        maxChars = int(in_args.get("maxChars", 4000))
        targetPath = Path(relativePath)
        resolvedPath = targetPath.resolve()

        sanitizedPrincipal = str(in_memoryPrincipalId or "").strip().replace(":", "_")
        allowedSessionDir = (self._sessionsRootPath / sanitizedPrincipal).resolve()
        try:
            if resolvedPath.is_relative_to(self._sessionsRootPath) is True:
                if resolvedPath.is_relative_to(allowedSessionDir) is False:
                    raise PermissionError(
                        "Requested session memory path is outside of current tenant directory."
                    )
        except ValueError:
            pass

        isAllowed = False
        for rootPath in self._allowedRoots:
            try:
                if resolvedPath.is_relative_to(rootPath) is True:
                    isAllowed = True
                    break
            except ValueError:
                continue
        if isAllowed is False:
            raise PermissionError("Requested path is outside of read-only whitelist.")
        if resolvedPath.exists() is False:
            raise FileNotFoundError("Requested file is not found.")
        if resolvedPath.is_file() is False:
            raise FileNotFoundError("Requested path is not a file.")
        content = resolvedPath.read_text(encoding="utf-8")
        ret = {"content": content[:maxChars], "path": str(resolvedPath)}
        return ret
