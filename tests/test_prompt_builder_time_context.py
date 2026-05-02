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


def testPromptBuilderPreservesUserMessageWhenPromptIsTruncated() -> None:
    runtimeSettings = RuntimeSettings(
        maxSteps=5,
        maxToolCalls=5,
        maxExecutionSeconds=30,
        maxToolOutputChars=1000,
        maxPromptChars=5000,
        recentMessagesLimit=12,
        sessionSummaryMaxChars=2000,
        skillSelectionMaxCount=4,
        extraSecondsPerLlmError=0,
        maxExtraSecondsTotal=0,
    )
    promptBuilder = PromptBuilder(
        in_runtimeSettings=runtimeSettings,
        in_displayTimeZoneName="Asia/Jerusalem",
        in_nowUtcProvider=lambda: datetime(2026, 5, 2, 12, 49, 16, tzinfo=timezone.utc),
    )
    userMessageText = (
        "создай повторяющееся событие - каждый день в 10 утра - "
        "дайджест постов в телеграм по теме AI"
    )
    oversizedSkillsBlock = "skills\n" + ("x" * 20000)
    oversizedMemoryBlock = "memory\n" + ("y" * 20000)
    oversizedToolsBlock = "tools\n" + ("z" * 20000)
    prompt = promptBuilder.buildPrompt(
        in_userMessage=userMessageText,
        in_observations=[],
        in_toolsDescription=oversizedToolsBlock,
        in_skillsBlock=oversizedSkillsBlock,
        in_memoryBlock=oversizedMemoryBlock,
    )
    assert len(prompt) <= runtimeSettings.maxPromptChars
    assert f"User message:\n{userMessageText}" in prompt
