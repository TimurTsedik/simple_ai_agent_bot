from datetime import datetime, timezone

from app.config.settingsModels import RuntimeSettings
from app.runtime.promptBuilder import PromptBuilder


def _buildRuntimeSettings() -> RuntimeSettings:
    ret = RuntimeSettings(
        maxSteps=5,
        maxToolCalls=5,
        maxExecutionSeconds=30,
        maxToolOutputChars=1000,
        maxPromptChars=20000,
        recentMessagesLimit=12,
        sessionSummaryMaxChars=2000,
        skillSelectionMaxCount=4,
        extraSecondsPerLlmError=0,
        maxExtraSecondsTotal=0,
    )
    return ret


def testPromptBuilderIncludesUtcAndConfiguredTimeZoneContext() -> None:
    runtimeSettings = _buildRuntimeSettings()
    promptBuilder = PromptBuilder(
        in_runtimeSettings=runtimeSettings,
        in_displayTimeZoneName="Europe/Moscow",
        in_nowUtcProvider=lambda: datetime(2026, 4, 30, 12, 34, 56, tzinfo=timezone.utc),
    )

    prompt = promptBuilder.buildPrompt(
        in_userMessage="поставь напоминание",
        in_observations=[],
        in_toolsDescription="tools",
        in_skillsBlock="skills",
        in_memoryBlock="memory",
    )

    assert "Server current UTC time: 2026-04-30 12:34:56 UTC" in prompt
    assert "Configured business timezone: Europe/Moscow" in prompt
    assert "Current time in configured timezone (Europe/Moscow):" in prompt
    assert "If user asks relative time like 'in N minutes/hours'" in prompt

