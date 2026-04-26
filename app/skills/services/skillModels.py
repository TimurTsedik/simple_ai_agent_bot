from dataclasses import dataclass


@dataclass(frozen=True)
class SkillModel:
    skillId: str
    title: str
    content: str
