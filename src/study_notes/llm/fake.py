"""가짜 모델. LLM 경로가 정해지기 전 개발과 단위·그래프 시험에 쓴다 (AGENTS.md §8).

규칙: 등록된 응답이 없으면 ``LlmUnavailableError``를 던진다.
그래서 가짜 모델로 돌리면 모든 답이 '규칙 답'으로 나온다 — 모델 없이도 기능이 돌아야 한다는 뜻이다.
"""

from __future__ import annotations

from collections.abc import Callable

from study_notes.core.errors import LlmUnavailableError
from study_notes.llm.gateway import LlmRequest, LlmResult

Responder = Callable[[LlmRequest], str | None]


class FakeLlm:
    def __init__(self) -> None:
        self._responders: list[Responder] = []
        self.calls: list[LlmRequest] = []

    def when(self, responder: Responder) -> FakeLlm:
        """요청을 보고 답할 문자열을 돌려주는 함수를 등록한다. None이면 다음 함수로 넘긴다."""
        self._responders.append(responder)
        return self

    def reply_for(self, role: str, contains: str, text: str) -> FakeLlm:
        """역할과 사용자 문장에 특정 글자가 있으면 이 답을 준다."""
        return self.when(lambda r: text if r.role == role and contains in r.user else None)

    async def complete(self, req: LlmRequest) -> LlmResult:
        self.calls.append(req)
        for responder in self._responders:
            out = responder(req)
            if out is not None:
                return LlmResult(text=out, role=req.role, model=f"fake-{req.role}")
        raise LlmUnavailableError("가짜 모델: 등록된 응답 없음")
