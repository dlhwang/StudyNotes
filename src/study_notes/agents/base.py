"""하위 Agent 약속 (docs/01 §4).

새 Agent를 만들 때::

    class NotesAgent(BaseAgent):
        name = "notes"
        title = "노트 Agent"
        intents = (IntentSpec("note_search", "노트 찾기", (r"노트.*찾아",)),)

        async def run(self, req: AgentRequest) -> AgentResult:
            notes = await self.tool("notes_list_items", {"notebook_id": self.subject_id()})
            return AgentResult(reply=self.reply(f"노트 {len(notes)}개입니다."))

규칙
- 하위 Agent는 요약된 결과만 돌려준다. 다른 하위 Agent를 부르지 않는다 (AGENTS.md §2).
- **BE에 쓰지 않는다.** 무언가를 바꿔야 하면 제안 초안(``self.proposal()``)을 답에 담고 버튼을 붙인다.
  저장·승인·반영은 사용자가 버튼을 누른 뒤 BE가 한다 (docs/01 §5).
- 모델이 실패하면 ``LlmUnavailableError``가 난다. 규칙 답(``source="rule"``)으로 바꿔 답한다.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any, ClassVar, TypeVar

from pydantic import BaseModel, Field, ValidationError
from pydantic_core import to_jsonable_python

from study_notes.core.context import RequestInfo
from study_notes.core.errors import LlmUnavailableError, ToolInputError, ToolPermissionError
from study_notes.core.ids import args_hash, dedupe_key
from study_notes.core.proposal import ProposalDraft
from study_notes.core.reply import AgentReply, AgentResult, Citation, UiAction
from study_notes.deps import Deps
from study_notes.llm.gateway import ChatMessage, LlmRequest, LlmResult, Role, ToolDef
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
    # 대화 메모리: 최근에 다룬 노트 ID (최신 먼저). "그 노트"를 이어 받는다
    focus_note_ids: list[str] = Field(default_factory=list)


class ReactStep(BaseModel):
    """ReAct 한 단계의 흔적. 화면의 '실행 흔적'으로 보여 줄 수 있다(관찰은 앞부분만)."""

    step: int
    thought: str = ""
    tool: str
    args: dict[str, Any] = Field(default_factory=dict)
    observation: str = ""


class ReactOutcome(BaseModel):
    answer: str
    steps: list[ReactStep] = Field(default_factory=list)
    # 도구가 돌려준 원래 값(근거 만들기용). State에 넣지 않는다
    observations: list[Any] = Field(default_factory=list)
    prompt_id: str


_OBS_MAX = 2000


def _to_json(value: Any) -> str:
    text = json.dumps(to_jsonable_python(value), ensure_ascii=False)
    return text if len(text) <= _OBS_MAX else text[:_OBS_MAX] + "…(잘림)"


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

    def screen_note_id(self) -> str | None:
        """화면에서 보고 있는 노트 ID (context.screen.note_id)."""
        value = self.request.screen.get("note_id")
        return str(value) if value else None

    def base_date(self) -> str:
        """기준일. 화면이 넘긴 screen.base_date, 없으면 오늘."""
        value = self.request.screen.get("base_date")
        return str(value) if value else date.today().isoformat()

    async def tool(self, name: str, args: BaseModel | dict[str, Any]) -> Any:
        """도구를 부른다(모두 조회). 허용 목록·호출 상한·기록은 도구 실행기가 맡는다."""
        return await self.runner.call(name, args)

    def prompt(self, purpose: str) -> Prompt:
        return load_prompt(self.name, purpose)

    async def _record_llm(self, role: Role, prompt_id: str, result: LlmResult, **extra: object) -> None:
        await safe_record(
            self.deps.recorder,
            Record(
                kind="llm_call",
                run_id=self.request.run_id,
                thread_id=self.request.thread_id,
                data={
                    "agent": self.name,
                    "role": role,
                    "prompt_id": prompt_id,
                    "model": result.model,
                    "input_tokens": result.input_tokens,
                    "output_tokens": result.output_tokens,
                    "latency_ms": result.latency_ms,
                    "cached": result.cached,
                    "tool_calls": [c.name for c in result.tool_calls],
                    **extra,
                },
            ),
        )

    async def ask_llm(self, role: Role, prompt: Prompt, user_text: str, **values: object) -> tuple[str, str]:
        """(답, 프롬프트 ID). 실패하면 LlmUnavailableError."""
        req = LlmRequest(role=role, system=prompt.render(**values), user=user_text, prompt_id=prompt.id)
        result = await self.deps.llm.complete(req)
        await self._record_llm(role, prompt.id, result)
        return result.text, prompt.id

    async def react(
        self,
        role: Role,
        prompt: Prompt,
        user_text: str,
        *,
        tools: list[str] | None = None,
        max_steps: int = 4,
        **values: object,
    ) -> ReactOutcome:
        """ReAct 루프: 모델 판단(Function Calling) → 조회 도구 실행 → 관찰을 돌려줌 → … → 최종 답.

        - 모델이 고를 수 있는 도구는 이 Agent의 ``llm_selectable`` 도구 중 ``tools``에 든 것뿐이다.
        - 도구 실행은 ``self.tool``(허용 목록·호출 상한·기록)을 거친다.
        - 입력 오류(``ToolInputError``)는 관찰로 돌려줘 모델이 고치게 한다. 권한·상한 오류는 그대로 올린다.
        - ``max_steps`` 안에 최종 답이 없거나 모델을 쓸 수 없으면 ``LlmUnavailableError`` → 부른 쪽이 규칙 답으로.
        """
        specs = [s for s in self.runner.llm_tools() if tools is None or s.name in tools]
        if not specs:
            raise LlmUnavailableError("모델이 고를 수 있는 도구가 없습니다")
        allowed = {s.name for s in specs}
        defs = [
            ToolDef(name=s.name, description=s.description, parameters=s.args_model.model_json_schema()) for s in specs
        ]
        system = prompt.render(**values)
        convo: list[ChatMessage] = []
        steps: list[ReactStep] = []
        observations: list[Any] = []
        for step in range(1, max_steps + 1):
            req = LlmRequest(
                role=role,
                system=system,
                user=user_text,
                messages=list(convo) or None,
                tools=defs,
                prompt_id=prompt.id,
                cacheable=False,
            )
            result = await self.deps.llm.complete(req)
            await self._record_llm(role, prompt.id, result, step=step)
            if not result.tool_calls:
                if not result.text.strip():
                    raise LlmUnavailableError("모델이 빈 답을 냈습니다")
                return ReactOutcome(
                    answer=result.text.strip(), steps=steps, observations=observations, prompt_id=prompt.id
                )
            convo.append(ChatMessage(role="assistant", content=result.text, tool_calls=result.tool_calls))
            for call in result.tool_calls:
                if call.name not in allowed:
                    raise ToolPermissionError(f"모델이 허용되지 않은 도구를 골랐습니다: {call.name}")
                try:
                    out = await self.tool(call.name, call.arguments)
                    observations.append(out)
                    obs = _to_json(out)
                except ToolInputError as e:
                    obs = json.dumps({"error": str(e), "hint": e.hint}, ensure_ascii=False)
                convo.append(ChatMessage(role="tool", content=obs, tool_call_id=call.id, name=call.name))
                steps.append(
                    ReactStep(
                        step=step, thought=result.text, tool=call.name, args=call.arguments, observation=obs[:200]
                    )
                )
        raise LlmUnavailableError(f"ReAct 단계 상한({max_steps})을 넘었습니다")

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
        await self._record_llm(role, prompt.id, result)
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
