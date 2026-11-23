"""LiteLLM으로 실제 모델을 부른다. ``pip install -e .[llm]`` 이 필요하다.

LLM 경로와 인증 방식은 프로젝트마다 다르다. 역할 키 → 모델 ID 연결은 설정으로만 한다.
"""

from __future__ import annotations

import json
from typing import Any

from study_notes.core.errors import LlmUnavailableError
from study_notes.llm.gateway import LlmRequest, LlmResult


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
            "messages": [{"role": "system", "content": req.system}, {"role": "user", "content": req.user}],
            "max_tokens": req.max_tokens,
            "temperature": req.temperature,
            "caching": False,  # 캐시는 GuardedGateway가 한다
        }
        if req.json_schema is not None:
            kwargs["response_format"] = {"type": "json_object"}
        resp = await litellm.acompletion(**kwargs)
        text = str(resp.choices[0].message.content or "")
        usage = getattr(resp, "usage", None)
        raw: dict[str, object] | None = None
        if req.json_schema is not None:
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
        )
