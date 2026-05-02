from dataclasses import dataclass
from typing import Any, Callable

from pydantic import BaseModel


@dataclass(frozen=True)
class ToolDefinitionModel:
    name: str
    description: str
    argsModel: type[BaseModel]
    timeoutSeconds: int
    executeCallable: Callable[..., Any]


class ToolRegistry:
    def __init__(self, in_toolDefinitions: list[ToolDefinitionModel]) -> None:
        self._toolByName = {item.name: item for item in in_toolDefinitions}

    def getTool(self, in_toolName: str) -> ToolDefinitionModel | None:
        ret = self._toolByName.get(in_toolName)
        return ret

    def listTools(self) -> list[ToolDefinitionModel]:
        ret = list(self._toolByName.values())
        return ret
