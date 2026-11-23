"""의도와 규칙 분류기.

의도는 각 하위 Agent가 ``intents``로 내놓는다(``IntentSpec``). 오케스트레이터는 그것을 모아 쓴다.
그래서 새 기능을 넣을 때 이 파일을 고치지 않고, 자기 Agent 폴더만 고친다.

규칙 분류
- 질문에서 공백을 지우고 소문자로 바꾼 뒤, 등록 순서대로 ``patterns``(정규식)를 건다.
- 여러 의도가 걸리면 최대 ``max_intents``개를 순서대로 돌려준다.
- 하나도 안 걸리면 빈 목록 → 모델 분류로 넘어간다 (classify.py).
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from functools import cache

_NAME = re.compile(r"^[a-z][a-z0-9_]*$")


@dataclass(frozen=True)
class IntentSpec:
    """의도 하나.

    - name: 의도 이름. 평가 질문의 expected_intent와 같은 값. 예: ``task_list``
    - help: 모델 분류에 보여 줄 한 줄 설명. 예: "할 일 목록 보기"
    - patterns: 규칙 분류 정규식. 공백을 지우고 소문자로 바꾼 질문에 건다
    """

    name: str
    help: str
    patterns: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not _NAME.match(self.name):
            raise ValueError(f"의도 이름은 영문 소문자·숫자·밑줄만 씁니다: {self.name}")


def compact(text: str) -> str:
    return re.sub(r"\s", "", text).lower()


@cache
def _compiled(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern)


def classify_by_rules(text: str, specs: Iterable[IntentSpec], max_intents: int = 3) -> list[str]:
    """규칙으로 의도를 고른다. 아무것도 걸리지 않으면 빈 목록(모델 분류로 넘김)."""
    t = compact(text)
    found: list[str] = []
    for spec in specs:
        if spec.name not in found and any(_compiled(p).search(t) for p in spec.patterns):
            found.append(spec.name)
    return found[:max_intents]
