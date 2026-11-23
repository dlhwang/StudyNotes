"""LiteLLM으로 실제 모델을 부른다. ``pip install -e .[llm]`` 이 필요하다.

LLM 경로와 인증 방식은 프로젝트마다 다르다. 역할 키 → 모델 ID 연결은 설정으로만 한다.
Function Calling은 OpenAI 형식(``tools``·``tool_calls``·``tool`` 메시지)으로 넘긴다. LiteLLM이 공급자 형식으로 바꾼다.
"""

from __future__ import annotations

import json
from typing import Any

from study_notes.core.errors import LlmUnavailableError
from study_notes.llm.gateway import LlmRequest, LlmResult, ToolCall


def to_openai_messages(req: LlmRequest) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = [{"role": "system", "content": req.system}, {"role": "user", "content": req.user}]
    for m in req.messages or []:
        if m.role == "tool":
            messages.append({"role": "tool", "tool_call_id": m.tool_call_id, "name": m.name, "content": m.content})
        elif m.role == "assistant" and m.tool_calls:
            messages.append(
                {
                    "role": "assistant",
                    "content": m.content or None,
                    "tool_calls": [
                        {
                            "id": c.id,
                            "type": "function",
                            "function": {"name": c.name, "arguments": json.dumps(c.arguments, ensure_ascii=False)},
                        }
                        for c in m.tool_calls
                    ],
                }
            )
        else:
            messages.append({"role": m.role, "content": m.content})
    return messages


def to_openai_tools(req: LlmRequest) -> list[dict[str, Any]] | None:
    if not req.tools:
        return None
    return [
        {"type": "function", "function": {"name": t.name, "description": t.description, "parameters": t.parameters}}
        for t in req.tools
    ]


def parse_tool_calls(message: Any) -> list[ToolCall]:
    """응답 메시지의 tool_calls → ToolCall. 인자 JSON이 깨졌으면 모델을 쓸 수 없는 것으로 본다."""
    raw = getattr(message, "tool_calls", None) or (message.get("tool_calls") if isinstance(message, dict) else None)
    calls: list[ToolCall] = []
    for i, c in enumerate(raw or []):
        fn = c["function"] if isinstance(c, dict) else c.function
        name = fn["name"] if isinstance(fn, dict) else fn.name
        args_raw = fn["arguments"] if isinstance(fn, dict) else fn.arguments
        try:
            args = json.loads(args_raw) if isinstance(args_raw, str) and args_raw else dict(args_raw or {})
        except json.JSONDecodeError as e:
            raise LlmUnavailableError(f"도구 호출 인자를 읽을 수 없습니다: {name}") from e
        cid = (c.get("id") if isinstance(c, dict) else getattr(c, "id", None)) or f"call_{i}"
        calls.append(ToolCall(id=str(cid), name=str(name), arguments=args))
    return calls


class LiteLlmGateway:
    def __init__(self, models: dict[str, str]) -> None:
        self.models = models

    async def complete(self, req: LlmRequest) -> LlmResult:
        model = self.models.get(req.role)
        if not model:
            raise LlmUnavailableError(f"역할 키 '{req.role}'에 연결된 모델이 없습니다 (STUDY_NOTES_LLM__MODELS)")
        try:
            import litellm  # 선택 의존성
        except ImportError as e:
            raise LlmUnavailableError("litellm이 설치되지 않았습니다: pip install -e .[llm]") from e

        kwargs: dict[str, Any] = {
            "model": model,
            "messages": to_openai_messages(req),
            "max_tokens": req.max_tokens,
            "temperature": req.temperature,
            "caching": False,  # 캐시는 GuardedGateway가 한다
        }
        tools = to_openai_tools(req)
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        elif req.json_schema is not None:
            kwargs["response_format"] = {"type": "json_object"}
        resp = await litellm.acompletion(**kwargs)
        message = resp.choices[0].message
        text = str(message.content or "")
        usage = getattr(resp, "usage", None)
        raw: dict[str, object] | None = None
        if req.json_schema is not None and not tools:
            try:
                raw = json.loads(text)
            except json.JSONDecodeError:
                raw = None
        return LlmResult(
            text=text,
            role=req.role,
            model=model,
            input_tokens=int(getattr(usage, "prompt_tokens", 0) or 0),
            output_tokens=int(getattr(usage, "completion_tokens", 0) or 0),
            raw_json=raw,
            tool_calls=parse_tool_calls(message) if tools else [],
        )
