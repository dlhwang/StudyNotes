"""도구 실행기 — 모든 도구 호출이 거치는 안전장치 (AGENTS.md §4.1).

1. 허용 목록: Agent는 자기 도메인 도구만 부른다.
2. 실행당 호출 상한.
3. 실행 기록: 도구명, 인자 해시, 걸린 시간, 결과.
4. 오류는 그대로 올리되, ToolInputError는 고칠 방법(hint)을 담는다.

쓰기 등급·승인은 없다. ai-agent의 도구는 모두 조회이고, 쓰기·승인은 BE가 한다 (docs/01 §5).
"""

from __future__ import annotations

import time
from typing import Any

from pydantic import BaseModel, ValidationError

from study_notes.core.context import RequestInfo
from study_notes.core.errors import ToolInputError, ToolLimitError, ToolPermissionError
from study_notes.core.ids import args_hash
from study_notes.observability.recorder import Record, RunRecorder, safe_record
from study_notes.tools.be_client.protocol import BeClient
from study_notes.tools.registry import TOOLS, ToolContext, ToolSpec


class ToolRunner:
    def __init__(
        self,
        *,
        agent: str,
        request: RequestInfo,
        be: BeClient,
        recorder: RunRecorder,
        max_calls: int,
    ) -> None:
        self.agent = agent
        self.request = request
        self.be = be
        self.recorder = recorder
        self.max_calls = max_calls
        self.calls = 0

    def spec(self, name: str) -> ToolSpec:
        spec = TOOLS.get(name)
        if spec is None or spec.agent != self.agent:
            raise ToolPermissionError(f"'{self.agent}' Agent에 허용되지 않은 도구입니다: {name}")
        return spec

    def llm_tools(self) -> list[ToolSpec]:
        """LLM에 보여 줄 도구 목록. 이 Agent의 도구 중 llm_selectable인 것만."""
        return [s for s in TOOLS.values() if s.agent == self.agent and s.llm_selectable]

    async def call(self, name: str, args: BaseModel | dict[str, Any]) -> Any:
        spec = self.spec(name)
        self.calls += 1
        if self.calls > self.max_calls:
            raise ToolLimitError(f"한 실행에서 도구를 {self.max_calls}번 넘게 부를 수 없습니다")
        try:
            parsed = (
                args
                if isinstance(args, spec.args_model)
                else spec.args_model.model_validate(args.model_dump() if isinstance(args, BaseModel) else args)
            )
        except ValidationError as e:
            raise ToolInputError(f"{name} 인자가 올바르지 않습니다", hint=str(e.errors()[:3])) from e

        ctx = ToolContext(request=self.request, be=self.be)
        started = time.monotonic()
        outcome = "ok"
        try:
            return await spec.func(parsed, ctx)
        except Exception as e:
            outcome = type(e).__name__
            raise
        finally:
            await safe_record(
                self.recorder,
                Record(
                    kind="tool_call",
                    run_id=self.request.run_id,
                    thread_id=self.request.thread_id,
                    data={
                        "agent": self.agent,
                        "tool": name,
                        "args_hash": args_hash(parsed.model_dump()),
                        "outcome": outcome,
                        "latency_ms": int((time.monotonic() - started) * 1000),
                    },
                ),
            )
