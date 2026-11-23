"""하위 Agent 목록. 새 Agent는 여기에 한 줄 추가하면 오케스트레이터가 의도로 찾아 부른다 (docs/01 §4)."""

from __future__ import annotations

from study_notes.agents.base import BaseAgent
from study_notes.agents.tasks import TasksAgent
from study_notes.orchestrator.intents import IntentSpec

# 앞에 둔 Agent의 의도 규칙부터 건다
AGENTS: list[type[BaseAgent]] = [
    TasksAgent,
]


def all_intents() -> list[IntentSpec]:
    return [spec for cls in AGENTS for spec in cls.intents]


def agent_for(intent: str) -> type[BaseAgent]:
    for cls in AGENTS:
        if any(spec.name == intent for spec in cls.intents):
            return cls
    raise KeyError(f"의도를 맡을 Agent가 없습니다: {intent}")


def check_registry() -> list[str]:
    """Agent 이름과 의도 이름이 겹치지 않는지. 문제 목록을 돌려준다(시험이 부른다)."""
    problems: list[str] = []
    names = [c.name for c in AGENTS]
    if len(names) != len(set(names)):
        problems.append(f"Agent 이름 중복: {names}")
    seen: dict[str, str] = {}
    for cls in AGENTS:
        if not cls.intents:
            problems.append(f"{cls.name}: 맡은 의도가 없습니다")
        for spec in cls.intents:
            if spec.name in seen:
                problems.append(f"의도 {spec.name}을 {seen[spec.name]}와 {cls.name}가 함께 맡고 있습니다")
            seen[spec.name] = cls.name
    return problems
