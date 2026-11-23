"""평가 질문이 가짜 BE·가짜 모델로 모두 통과하는지."""

from __future__ import annotations

from study_notes.eval.runner import run_all
from tests.conftest import Env


async def test_eval_cases_pass(env: Env) -> None:
    results = await run_all()
    failed = [(r.case.id, r.intents, r.missing) for r in results if not r.passed]
    assert results and not failed
    assert len(env.recorder.of("eval")) == len(results)
