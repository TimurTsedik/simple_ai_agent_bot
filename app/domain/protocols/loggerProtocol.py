from typing import Protocol


class LoggerProtocol(Protocol):
    def info(self, in_message: str) -> None:
        ...

    def error(self, in_message: str) -> None:
        ...
