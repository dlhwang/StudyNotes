"""모델 게이트웨이 약속과 안전장치.

- 모델 이름 대신 역할 키(``Role``)로 부른다.
- 안전장치(타임아웃·분당 상한·같은 요청 캐시)는 ``GuardedGateway``가 감싼다.
- 실패하면 ``LlmUnavailableError``를 던진다. 부른 쪽이 규칙 답으로 바꾼다 .
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from collections import OrderedDict, deque
from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field

from study_notes.core.errors import LlmUnavailableError

Role = Literal["router", "worker", "judge", "embedding"]


class ToolDef(BaseModel):
    """모델에게 보여 줄 도구 (Function Calling). parameters는 JSON 스키마."""

    name: str
    description: str
    parameters: dict[str, Any]


class ToolCall(BaseModel):
    """모델이 고른 도구 호출."""

    id: str
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ChatMessage(BaseModel):
    """``user`` 다음에 이어지는 대화 (ReAct 루프). tool 메시지는 tool_call_id로 호출과 잇는다."""

    role: Literal["user", "assistant", "tool"]
    content: str = ""
    tool_calls: list[ToolCall] = Field(default_factory=list)
    tool_call_id: str | None = None
    name: str | None = None


class LlmRequest(BaseModel):
    role: Role
    system: str
    user: str
    # 여러 단계 대화(ReAct). 있으면 user 뒤에 이어 붙는다
    messages: list[ChatMessage] | None = None
    # Function Calling: 모델이 고를 수 있는 도구. 결과는 LlmResult.tool_calls
    tools: list[ToolDef] | None = None
    # 구조화 출력이 필요하면 JSON 스키마를 넘긴다. 결과 검증은 부른 쪽이 Pydantic으로 한다
    json_schema: dict[str, object] | None = None
    max_tokens: int | None = None
    temperature: float = 0.2
    # 프롬프트 버전 (실행 기록용)
    prompt_id: str | None = None
    cacheable: bool = True


class LlmResult(BaseModel):
    text: str
    role: Role
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0
    cached: bool = False
    prompt_id: str | None = None
    raw_json: dict[str, object] | None = Field(default=None)
    # 모델이 도구를 부르기로 했으면 여기에 (text는 그때의 생각일 수 있다)
    tool_calls: list[ToolCall] = Field(default_factory=list)


class LlmGateway(Protocol):
    async def complete(self, req: LlmRequest) -> LlmResult: ...


class _MinuteLimiter:
    def __init__(self, per_minute: int) -> None:
        self.per_minute = per_minute
        self.calls: deque[float] = deque()

    def allow(self) -> bool:
        now = time.monotonic()
        while self.calls and now - self.calls[0] > 60:
            self.calls.popleft()
        if len(self.calls) >= self.per_minute:
            return False
        self.calls.append(now)
        return True


class GuardedGateway:
    """타임아웃·분당 상한·캐시를 붙인다. 프로세스 안 캐시라 Pod마다 따로다.

    여러 Pod가 상한을 함께 써야 하면 Valkey(``agent:`` 접두어 + TTL)로 바꾼다 (AGENTS.md §1-6).
    """

    def __init__(
        self,
        inner: LlmGateway,
        *,
        timeout_seconds: float,
        calls_per_minute: int,
        cache_ttl_seconds: int,
        cache_max_entries: int,
        default_max_tokens: int,
    ) -> None:
        self.inner = inner
        self.timeout = timeout_seconds
        self.limiter = _MinuteLimiter(calls_per_minute)
        self.cache_ttl = cache_ttl_seconds
        self.cache_max = cache_max_entries
        self.default_max_tokens = default_max_tokens
        self._cache: OrderedDict[str, tuple[float, LlmResult]] = OrderedDict()

    @staticmethod
    def _key(req: LlmRequest) -> str:
        body = json.dumps(req.model_dump(exclude={"cacheable"}), sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(body.encode("utf-8")).hexdigest()

    async def complete(self, req: LlmRequest) -> LlmResult:
        if req.max_tokens is None:
            req = req.model_copy(update={"max_tokens": self.default_max_tokens})
        key = self._key(req)
        if req.cacheable and key in self._cache:
            at, hit = self._cache[key]
            if time.monotonic() - at <= self.cache_ttl:
                return hit.model_copy(update={"cached": True})
            del self._cache[key]
        if not self.limiter.allow():
            raise LlmUnavailableError("분당 모델 호출 상한을 넘었습니다")
        started = time.monotonic()
        try:
            result = await asyncio.wait_for(self.inner.complete(req), timeout=self.timeout)
        except LlmUnavailableError:
            raise
        except TimeoutError as e:
            raise LlmUnavailableError("모델 응답 시간 초과") from e
        except Exception as e:  # 공급자 오류는 모두 '쓸 수 없음'으로 본다
            raise LlmUnavailableError(f"모델 호출 실패: {type(e).__name__}") from e
        result = result.model_copy(
            update={"latency_ms": int((time.monotonic() - started) * 1000), "prompt_id": req.prompt_id}
        )
        if req.cacheable:
            self._cache[key] = (time.monotonic(), result)
            while len(self._cache) > self.cache_max:
                self._cache.popitem(last=False)
        return result
