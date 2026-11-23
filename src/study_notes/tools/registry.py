"""업무 도구 등록 (AGENTS.md §4.2).

사용법::

    class ChunkSearchArgs(BaseModel):
        query: str

    @agent_tool(agent="notes", llm_selectable=True)
    async def notes_search_chunks(args: ChunkSearchArgs, ctx: ToolContext) -> list[ChunkHit]:
        \"\"\"언제 쓰는지 / 언제 쓰지 않는지 / 예시\"\"\"

- 이름은 ``{도메인}_{동사}_{대상}``이고, 도메인은 ``agent``와 같아야 한다.
- 첫 인자는 Pydantic 모델, 둘째는 ``ToolContext``.
- **도구는 모두 조회다.** ai-agent는 BE에 쓰지 않는다. BE 클라이언트 약속(BeClient)에 쓰기 메서드가 없다 (docs/01 §5).
"""

from __future__ import annotations

import inspect
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, TypeVar, get_type_hints

from pydantic import BaseModel

from study_notes.core.context import RequestInfo
from study_notes.tools.be_client.protocol import BeClient

_NAME = re.compile(r"^[a-z]+_[a-z]+_[a-z0-9_]+$")


@dataclass(frozen=True)
class ToolContext:
    """도구가 받는 것. 토큰은 ``request.be_token``에만 있고 도구는 BE 클라이언트에 넘기기만 한다."""

    request: RequestInfo
    be: BeClient


ToolFunc = Callable[[Any, ToolContext], Awaitable[Any]]


@dataclass(frozen=True)
class ToolSpec:
    name: str
    agent: str
    args_model: type[BaseModel]
    func: ToolFunc
    description: str
    # LLM에게 도구 목록으로 보여 줄 것인가
    llm_selectable: bool


TOOLS: dict[str, ToolSpec] = {}

F = TypeVar("F", bound=ToolFunc)


def agent_tool(agent: str, *, llm_selectable: bool = False) -> Callable[[F], F]:
    def deco(func: F) -> F:
        original = func  # 아래 iscoroutinefunction이 타입을 좁히므로 원래 타입을 남겨 둔다
        name = func.__name__
        if not _NAME.match(name) or not name.startswith(f"{agent}_"):
            raise ValueError(f"도구 이름은 '{agent}_<동사>_<대상>' 형식이어야 합니다: {name}")
        if not inspect.iscoroutinefunction(func):
            raise TypeError(f"도구는 async 함수여야 합니다: {name}")
        hints = get_type_hints(func)
        params = list(inspect.signature(func).parameters)
        args_model = hints.get(params[0]) if params else None
        if not (isinstance(args_model, type) and issubclass(args_model, BaseModel)):
            raise TypeError(f"도구의 첫 인자는 Pydantic 모델이어야 합니다: {name}")
        doc = inspect.getdoc(func) or ""
        if not doc:
            raise ValueError(f"도구 독스트링이 필요합니다(언제 쓰고 언제 쓰지 않는지): {name}")
        if name in TOOLS and TOOLS[name].func is not func:
            raise ValueError(f"같은 이름의 도구가 이미 있습니다: {name}")
        TOOLS[name] = ToolSpec(
            name=name,
            agent=agent,
            args_model=args_model,
            func=func,
            description=doc,
            llm_selectable=llm_selectable,
        )
        return original

    return deco
