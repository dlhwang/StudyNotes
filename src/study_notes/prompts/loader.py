"""프롬프트는 ``agents/<agent>/prompts/<agent>.<용도>.v<n>.md`` 파일로 둔다.

- 기본은 가장 높은 버전. 설정 ``prompt_pins``로 고정할 수 있다 (예: ``{"notes.summary": 1}``).
- 실행 기록에는 ``Prompt.id`` (예: ``notes.summary.v2``)를 남긴다.
- 본문의 ``{이름}`` 자리는 ``render(이름=값)``으로 채운다. 없는 이름은 그대로 둔다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from study_notes.config import get_settings

_AGENTS_DIR = Path(__file__).resolve().parent.parent / "agents"
_NAME = re.compile(r"^(?P<agent>[a-z_]+)\.(?P<purpose>[a-z_]+)\.v(?P<version>\d+)\.md$")


class _Keep(dict[str, object]):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


@dataclass(frozen=True)
class Prompt:
    agent: str
    purpose: str
    version: int
    text: str

    @property
    def id(self) -> str:
        return f"{self.agent}.{self.purpose}.v{self.version}"

    def render(self, **values: object) -> str:
        return self.text.format_map(_Keep(values))


@lru_cache(maxsize=256)
def _versions(agent: str, purpose: str, base: Path) -> dict[int, Path]:
    found: dict[int, Path] = {}
    folder = base / agent / "prompts"
    if folder.is_dir():
        for p in folder.iterdir():
            m = _NAME.match(p.name)
            if m and m["agent"] == agent and m["purpose"] == purpose:
                found[int(m["version"])] = p
    return found


def load_prompt(agent: str, purpose: str, version: int | None = None, base: Path | None = None) -> Prompt:
    versions = _versions(agent, purpose, base or _AGENTS_DIR)
    if not versions:
        raise FileNotFoundError(f"프롬프트 파일이 없습니다: agents/{agent}/prompts/{agent}.{purpose}.v<n>.md")
    pinned = version or get_settings().prompt_pins.get(f"{agent}.{purpose}")
    chosen = pinned if pinned is not None else max(versions)
    if chosen not in versions:
        raise FileNotFoundError(f"프롬프트 버전이 없습니다: {agent}.{purpose}.v{chosen}")
    text = versions[chosen].read_text(encoding="utf-8")
    return Prompt(agent=agent, purpose=purpose, version=chosen, text=text)
