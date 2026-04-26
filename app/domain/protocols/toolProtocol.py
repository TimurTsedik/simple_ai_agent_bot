from typing import Any, Protocol


class ToolProtocol(Protocol):
    def execute(self, in_args: dict[str, Any]) -> Any:
        ...
