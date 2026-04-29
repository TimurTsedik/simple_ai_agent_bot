import time

from pydantic import BaseModel, ConfigDict, Field

from app.runtime.toolExecutionCoordinator import ToolExecutionCoordinator
from app.tools.registry.toolRegistry import ToolDefinitionModel, ToolRegistry


class EmptyArgsModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PositiveNumberArgsModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: int = Field(ge=1)


def _successTool(in_args: dict) -> dict:
    ret = {"ok": True, "args": in_args}
    return ret


def _slowTool(in_args: dict) -> dict:
    _ = in_args
    time.sleep(0.05)
    ret = {"ok": True}
    return ret


def _errorTool(in_args: dict) -> dict:
    _ = in_args
    raise RuntimeError("boom")


def testCoordinatorReturnsSuccessEnvelope() -> None:
    registry = ToolRegistry(
        in_toolDefinitions=[
            ToolDefinitionModel(
                name="success_tool",
                description="test",
                argsModel=EmptyArgsModel,
                timeoutSeconds=1,
                executeCallable=_successTool,
            )
        ]
    )
    coordinator = ToolExecutionCoordinator(
        in_toolRegistry=registry,
        in_maxToolOutputChars=1000,
    )

    result = coordinator.execute(in_toolName="success_tool", in_rawArgs={})

    assert result.ok is True
    assert result.tool_name == "success_tool"
    assert result.error is None


def testCoordinatorReturnsValidationError() -> None:
    registry = ToolRegistry(
        in_toolDefinitions=[
            ToolDefinitionModel(
                name="validation_tool",
                description="test",
                argsModel=PositiveNumberArgsModel,
                timeoutSeconds=1,
                executeCallable=_successTool,
            )
        ]
    )
    coordinator = ToolExecutionCoordinator(
        in_toolRegistry=registry,
        in_maxToolOutputChars=1000,
    )

    result = coordinator.execute(
        in_toolName="validation_tool",
        in_rawArgs={"value": 0},
    )

    assert result.ok is False
    assert result.error is not None
    assert result.error["code"] == "VALIDATION_ERROR"


def testCoordinatorReturnsTimeout() -> None:
    registry = ToolRegistry(
        in_toolDefinitions=[
            ToolDefinitionModel(
                name="slow_tool",
                description="test",
                argsModel=EmptyArgsModel,
                timeoutSeconds=0,
                executeCallable=_slowTool,
            )
        ]
    )
    coordinator = ToolExecutionCoordinator(
        in_toolRegistry=registry,
        in_maxToolOutputChars=1000,
    )

    result = coordinator.execute(in_toolName="slow_tool", in_rawArgs={})

    assert result.ok is False
    assert result.error is not None
    assert result.error["code"] == "TIMEOUT"


def testCoordinatorReturnsExecutionError() -> None:
    registry = ToolRegistry(
        in_toolDefinitions=[
            ToolDefinitionModel(
                name="error_tool",
                description="test",
                argsModel=EmptyArgsModel,
                timeoutSeconds=1,
                executeCallable=_errorTool,
            )
        ]
    )
    coordinator = ToolExecutionCoordinator(
        in_toolRegistry=registry,
        in_maxToolOutputChars=1000,
    )

    result = coordinator.execute(in_toolName="error_tool", in_rawArgs={})

    assert result.ok is False
    assert result.error is not None
    assert result.error["code"] == "EXECUTION_ERROR"


def testCoordinatorShutdownIsIdempotent() -> None:
    registry = ToolRegistry(
        in_toolDefinitions=[
            ToolDefinitionModel(
                name="success_tool",
                description="test",
                argsModel=EmptyArgsModel,
                timeoutSeconds=1,
                executeCallable=_successTool,
            )
        ]
    )
    coordinator = ToolExecutionCoordinator(
        in_toolRegistry=registry,
        in_maxToolOutputChars=1000,
    )
    coordinator.shutdown(in_wait=True)
    coordinator.shutdown(in_wait=True)
