# Unit 06: Function Calling 게이트웨이와 ReAct 루프

## Goal (목표)

모델 게이트웨이가 도구 정의(Function Calling)·도구 호출 결과·여러 메시지를 주고받을 수 있고, `BaseAgent.react()`가 "모델 판단 → 조회 도구 실행 → 관찰을 돌려줌"을 정해진 단계 안에서 반복해 최종 답과 실행 흔적(trace)을 돌려주는 상태가 된다. 가짜 모델 시나리오 시험으로 확인된다.

## 배경 / 컨텍스트

- 과제 필수: Tool Calling, ReAct 기반 실행. 선택 A: Function Calling, Reasoning 흐름.
- 지금 `LlmRequest`는 `system`+`user` 한 쌍만 있고 `LlmResult`는 글자만 돌려준다(`src/study_notes/llm/gateway.py`). `LiteLlmGateway`는 `messages`를 두 줄로 만든다.
- 템플릿 안전장치를 그대로 쓴다: 모델이 고를 수 있는 도구는 그 Agent의 `llm_selectable=True` 도구뿐(`ToolRunner.llm_tools()`), 실행당 호출 상한, 호출 기록.
- `langgraph.prebuilt.create_react_agent`는 템플릿 도구 실행기·기록을 우회하므로 쓰지 않는다.

## 선행 조건 (Dependencies)

- Unit 01
- 참고: `src/study_notes/llm/{gateway,fake,litellm_gateway}.py`, `src/study_notes/agents/base.py`, `src/study_notes/tools/{registry,guards}.py`, `tests/unit/test_platform.py`

## 작업 범위 (Scope)

### 한다

- `llm/gateway.py`
  - `ToolDef(name, description, parameters: dict)`
  - `ToolCall(id: str, name: str, arguments: dict[str, Any])`
  - `ChatMessage(role: Literal["user","assistant","tool"], content: str = "", tool_calls: list[ToolCall] = [], tool_call_id: str | None = None, name: str | None = None)`
  - `LlmRequest`에 `messages: list[ChatMessage] | None = None`(있으면 `user` 뒤에 이어 붙는 대화), `tools: list[ToolDef] | None = None` 추가
  - `LlmResult`에 `tool_calls: list[ToolCall] = []` 추가
- `llm/litellm_gateway.py`: OpenAI 형식으로 `tools`(`{"type":"function","function":{...}}`)·`tool_calls`·`tool` 메시지 변환, 응답의 `tool_calls` 읽기(arguments JSON 파싱 실패 → `LlmUnavailableError`)
- `llm/fake.py`: 응답 함수가 `str | LlmResult | None`을 돌려줄 수 있게. 도우미 `script(role: str, results: list[LlmResult | str])` — 그 역할의 호출마다 차례로 돌려줌
- `agents/base.py`
  - `ReactStep(thought: str, tool: str, args: dict, observation_summary: str)`, `ReactOutcome(answer: str, steps: list[ReactStep], observations: list[Any], prompt_id: str)`
  - `async def react(self, role, prompt, user_text, *, tools: list[str] | None = None, max_steps: int = 4, **values) -> ReactOutcome`
    1. 도구 정의 = `self.runner.llm_tools()` 중 `tools`에 든 것(없으면 전부). parameters = `args_model.model_json_schema()`, description = 독스트링
    2. 대화: user_text로 시작 → 모델 호출(`cacheable=False`) → `tool_calls`가 있으면 각 호출을 `self.tool(name, args)`로 실행(허용 목록·상한·기록 적용), 결과를 JSON(최대 2,000자)으로 `tool` 메시지에 붙임 → 반복
    3. `tool_calls`가 없으면 그 글자가 최종 답. `max_steps`를 넘으면 `LlmUnavailableError("ReAct 단계 상한")`
    4. 도구 오류(`ToolInputError`)는 관찰로 모델에 돌려준다(고칠 기회). `ToolPermissionError`·`ToolLimitError`는 그대로 올린다
    5. 각 모델 호출은 `llm_call` 기록(템플릿 `ask_llm`과 같은 필드 + `step`)
- `tests/unit/test_react.py`

### 하지 않는다

- 실제 Agent에 적용(Unit 07), 병렬 도구 호출 최적화, 스트리밍 토큰

## 상세 작업 단계

1. 모델 추가와 캐시 키 확인(`GuardedGateway._key`가 messages·tools를 포함해 다른 대화를 같은 캐시로 보지 않게)
2. LiteLLM 변환 함수는 순수 함수로 분리해 시험(`to_openai_messages(req) -> list[dict]`, `parse_tool_calls(message) -> list[ToolCall]`)
3. FakeLlm 확장, 기존 `reply_for`·`when` 동작 유지
4. `react()` 구현
5. 시험(시험용 더미 Agent와 더미 도구를 `agent_tool(agent="dummy", llm_selectable=True)`로 등록)
   - 1단계: 모델이 도구 호출 → 도구 실행 → 2단계 최종 답. steps 1개, 도구 기록 1개
   - 모델이 허용되지 않은 도구를 부름 → `ToolPermissionError`
   - 잘못된 인자 → 관찰에 hint가 들어가고 다음 단계에서 회복
   - 단계 상한 → `LlmUnavailableError`
   - LiteLLM 변환 함수 왕복

## 사용할 수 있는 SKILL / 참고 자료

- OpenAI Chat Completions의 tools/tool_calls 형식(LiteLLM이 같은 형식을 쓴다)
- 기존 `ask_llm`, `ask_llm_json` 구현

## 완료 조건 (Definition of Done)

- [ ] `.\.venv\Scripts\python.exe -m pytest -q` 전체 통과
- [ ] `ruff check`·`ruff format --check`·`mypy` 통과
- [ ] react 시나리오 시험 4개 이상

## 산출물 (Output)

- `src/study_notes/llm/{gateway,fake,litellm_gateway}.py`, `src/study_notes/agents/base.py`
- `tests/unit/test_react.py`
