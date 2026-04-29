from pathlib import Path
from tempfile import TemporaryDirectory

from app.application.useCases.getLogsUseCase import GetLogsUseCase
from app.config.settingsModels import LoggingSettings


def testGetLogsUseCaseReadsTailAndSkipsInvalidLines() -> None:
    with TemporaryDirectory() as tempDir:
        logsDirPath = Path(tempDir)
        runLogPath = logsDirPath / "run.jsonl"
        runLogPath.write_text(
            "\n".join(
                [
                    '{"eventType":"first","value":1}',
                    "not a json line",
                    '{"eventType":"second","value":2}',
                    '{"eventType":"third","value":3}',
                ]
            ),
            encoding="utf-8",
        )
        settings = LoggingSettings(
            logsDirPath=str(logsDirPath),
            runLogsFileName="run.jsonl",
            appLogsFileName="app.log",
            maxBytes=1024,
            backupCount=1,
        )
        useCase = GetLogsUseCase(in_loggingSettings=settings)

        result = useCase.execute(in_limit=3)

    assert len(result) == 2
    assert result[0]["eventType"] == "third"
    assert result[1]["eventType"] == "second"
