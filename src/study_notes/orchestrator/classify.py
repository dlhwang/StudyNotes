"""의도 판정: 규칙 먼저, 걸리는 것이 없으면 모델(역할 키 router). 둘 다 안 되면 빈 목록.

빈 목록이면 chat 그래프가 "이런 것을 물어볼 수 있습니다" 안내로 답한다.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError

from study_notes.core.errors import LlmUnavailableError
from study_notes.llm.gateway import LlmGateway, LlmRequest
from study_notes.orchestrator.intents import IntentSpec, classify_by_rules
from study_notes.prompts.loader import load_prompt

_BASE = Path(__file__).resolve().parent.parent  # src/study_notes → orchestrator/prompts


class _Out(BaseModel):
    intents: list[str] = Field(default_factory=list)


async def classify(text: str, specs: Sequence[IntentSpec], llm: LlmGateway, max_intents: int) -> tuple[list[str], str]:
    """(의도 목록, 판정 방식: rule | ai | none)."""
    found = classify_by_rules(text, specs, max_intents)
    if found:
        return found, "rule"
    prompt = load_prompt("orchestrator", "classify", base=_BASE)
    catalog = "\n".join(f"{s.name}: {s.help}" for s in specs)
    known = {s.name for s in specs}
    try:
        result = await llm.complete(
            LlmRequest(
                role="router",
                system=prompt.render(intents=catalog),
                user=text,
                prompt_id=prompt.id,
                json_schema=_Out.model_json_schema(),
                temperature=0.0,
            )
        )
        raw = result.raw_json if result.raw_json is not None else json.loads(result.text)
        out = _Out.model_validate(raw)
        valid = [v for v in out.intents if v in known]
        if valid:
            return valid[:max_intents], "ai"
    except (LlmUnavailableError, ValidationError, ValueError):
        pass
    return [], "none"
