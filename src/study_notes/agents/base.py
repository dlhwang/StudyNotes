"""하위 Agent 약속 (docs/01 §4).

새 Agent를 만들 때::

    class TasksAgent(BaseAgent):
        name = "tasks"
        title = "할 일 Agent"
        intents = (IntentSpec("task_list", "할 일 목록 보기", (r"할일",)),)

        async def run(self, req: AgentRequest) -> AgentResult:
            items = await self.tool("tasks_list_items", {"subject_id": self.subject_id()})
            return AgentResult(reply=self.reply(f"할 일 {len(items)}건입니다."))

규칙
- 하위 Agent는 요약된 결과만 돌려준다. 다른 하위 Agent를 부르지 않는다 (AGENTS.md §2).
- **BE에 쓰지 않는다.** 무언가를 바꿔야 하면 제안 초안(``self.proposal()``)을 답에 담고 버튼을 붙인다.
  저장·승인·반영은 사용자가 버튼을 누른 뒤 BE가 한다 (docs/01 §5).
- 모델이 실패하면 ``LlmUnavailableError``가 난다. 규칙 답(``source="rule"``)으로 바꿔 답한다.
"""

from __future__ import annotations

import json
from typing import Any, ClassVar, TypeVar

from pydantic import BaseModel, Field, ValidationError

from study_notes.core.context import RequestInfo
from study_notes.core.errors import LlmUnavailableError, ToolInputError
from study_notes.core.ids import args_hash, dedupe_key
from study_notes.core.proposal import ProposalDraft
from study_notes.core.reply import AgentReply, AgentResult, Citation, UiAction
from study_notes.deps import Deps
from study_notes.llm.gateway import LlmRequest, Role
from study_notes.observability.recorder import Record, safe_record
from study_notes.orchestrator.intents import IntentSpec
from study_notes.prompts.loader import Prompt, load_prompt
from study_notes.tools.guards import ToolRunner

M = TypeVar("M", bound=BaseModel)


class AgentRequest(BaseModel):
    intent: str
    text: str
    # 최근 대화 몇 줄의 요약 (원문 전체를 넘기지 않는다)
    history: list[str] = Field(default_factory=list)


class BaseAgent:
    name: ClassVar[str]
    title: ClassVar[str]
    # 이 Agent가 맡는 의도. 앞에 둔 것부터 규칙을 건다
    intents: ClassVar[tuple[IntentSpec, ...]]

    def __init__(self, request: RequestInfo, deps: Deps) -> None:
        self.request = request
        self.deps = deps
        self.runner = ToolRunner(
            agent=self.name,
            request=request,
            be=deps.be,
            recorder=deps.recorder,
            max_calls=deps.settings.guard.max_tool_calls_per_run,
        )

    async def run(self, req: AgentRequest) -> AgentResult:
        raise NotImplementedError

    # ── 도우미 ────────────────────────────────────────────────────────

    def subject_id(self) -> str:
        if not self.request.subject_id:
            raise ToolInputError("무엇에 대한 질문인지 알 수 없습니다", hint="대상을 고른 뒤 다시 물어 주세요")
        return self.request.subject_id

    async def tool(self, name: str, args: BaseModel | dict[str, Any]) -> Any:
        """도구를 부른다(모두 조회). 허용 목록·호출 상한·기록은 도구 실행기가 맡는다."""
        return await self.runner.call(name, args)

    def prompt(self, purpose: str) -> Prompt:
        return load_prompt(self.name, purpose)

    async def ask_llm(self, role: Role, prompt: Prompt, user_text: str, **values: object) -> tuple[str, str]:
        """(답, 프롬프트 ID). 실패하면 LlmUnavailableError."""
        req = LlmRequest(role=role, system=prompt.render(**values), user=user_text, prompt_id=prompt.id)
        result = await self.deps.llm.complete(req)
        await safe_record(
            self.deps.recorder,
            Record(
                kind="llm_call",
                run_id=self.request.run_id,
                thread_id=self.request.thread_id,
                data={
                    "agent": self.name,
                    "role": role,
                    "prompt_id": prompt.id,
                    "model": result.model,
                    "input_tokens": result.input_tokens,
                    "output_tokens": result.output_tokens,
                    "latency_ms": result.latency_ms,
                    "cached": result.cached,
                },
            ),
        )
        return result.text, prompt.id

    async def ask_llm_json(self, model: type[M], role: Role, prompt: Prompt, user_text: str, **values: object) -> M:
        """구조화 출력. 형식이 틀리면 LlmUnavailableError로 본다(규칙 답으로 바꾸게)."""
        req = LlmRequest(
            role=role,
            system=prompt.render(**values),
            user=user_text,
            prompt_id=prompt.id,
            json_schema=model.model_json_schema(),
            temperature=0.1,
        )
        result = await self.deps.llm.complete(req)
        raw = result.raw_json if result.raw_json is not None else _extract_json(result.text)
        try:
            return model.model_validate(raw)
        except ValidationError as e:
            raise LlmUnavailableError("모델 출력 형식이 맞지 않습니다") from e

    def reply(
        self,
        text: str,
        *,
        source: str = "rule",
        actions: list[UiAction] | None = None,
        citations: list[Citation] | None = None,
        proposals: list[ProposalDraft] | None = None,
        data: dict[str, Any] | None = None,
        prompt_version: str | None = None,
    ) -> AgentReply:
        return AgentReply(
            agent=self.name,
            text=text,
            source="ai" if source == "ai" else "rule",
            actions=actions or [],
            citations=citations or [],
            proposals=proposals or [],
            data=data or {},
            prompt_version=prompt_version,
        )

    def proposal(
        self,
        *,
        kind: str,
        title: str,
        payload: dict[str, Any],
        reasons: list[str],
        source: str = "chat",
        source_ref: str | None = None,
    ) -> ProposalDraft:
        """제안 초안을 만든다. 저장은 BE가 한다.

        중복 방지 키: 같은 대화(thread)·같은 내용이면 같은 값 → BE가 같은 제안을 두 번 만들지 않는다.
        """
        key = dedupe_key(
            self.request.thread_id or self.request.run_id or "no-thread",
            self.name,
            args_hash([kind, title, payload]),
        )
        return ProposalDraft(
            kind=kind,
            subject_id=self.subject_id(),
            title=title,
            payload=payload,
            reasons=reasons,
            source="agent" if source == "agent" else "chat",
            source_ref=source_ref,
            dedupe_key=key,
        )


def _extract_json(text: str) -> object:
    s = text.strip()
    if s.startswith("```"):
        s = s.strip("`")
        s = s[s.find("\n") + 1 :] if "\n" in s else s
    start, end = s.find("{"), s.rfind("}")
    if start < 0 or end < start:
        raise LlmUnavailableError("모델 출력에 JSON이 없습니다")
    try:
        return json.loads(s[start : end + 1])
    except json.JSONDecodeError as e:
        raise LlmUnavailableError("모델 출력 JSON을 읽을 수 없습니다") from e
