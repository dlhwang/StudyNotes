"""평가 질문을 chat 그래프에 넣어 의도와 핵심 말을 판정한다.

지금 deps(설정: 가짜 BE·가짜 모델이 기본)로 돌린다. 실제 모델로 재려면 STUDY_NOTES_LLM__MODE=litellm.
결과는 실행 기록(kind="eval")에도 남긴다.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from langgraph.checkpoint.memory import InMemorySaver

from study_notes.core.context import AgentContext
from study_notes.deps import get_deps
from study_notes.graphs.chat import build_chat_graph
from study_notes.observability.recorder import Record, safe_record

CASES_DIR = Path(__file__).resolve().parent / "cases"


@dataclass
class Case:
    id: str
    question: str
    expected_intent: str
    must_include: list[str]
    subject_id: str
    enabled: bool = True
    # 화면 정보(예: base_date, note_id). 파일 머리의 screen과 합친다
    screen: dict[str, Any] = field(default_factory=dict)
    # 다중 의도: 있으면 의도 목록 전체가 같아야 통과
    expected_intents: list[str] | None = None


@dataclass
class CaseResult:
    case: Case
    passed: bool
    intents: list[str]
    answer: str
    missing: list[str] = field(default_factory=list)


def load_cases(folder: Path = CASES_DIR) -> list[Case]:
    cases: list[Case] = []
    for path in sorted(folder.glob("*.yaml")):
        doc: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        default_subject = str(doc.get("subject_id") or "")
        default_screen: dict[str, Any] = {k: str(v) for k, v in (doc.get("screen") or {}).items()}
        for c in doc.get("cases") or []:
            cases.append(
                Case(
                    id=str(c["id"]),
                    question=str(c["question"]),
                    expected_intent=str(c["expected_intent"]),
                    must_include=[str(x) for x in c.get("must_include") or []],
                    subject_id=str(c.get("subject_id") or default_subject),
                    enabled=bool(c.get("enabled", True)),
                    screen={**default_screen, **{k: str(v) for k, v in (c.get("screen") or {}).items()}},
                    expected_intents=[str(x) for x in c["expected_intents"]] if c.get("expected_intents") else None,
                )
            )
    return cases


async def run_case(case: Case) -> CaseResult:
    graph = build_chat_graph(checkpointer=InMemorySaver())
    thread_id = f"eval:{case.id}:{uuid.uuid4()}"
    config: dict[str, Any] = {"configurable": {"thread_id": thread_id, "user_id": "eval"}}
    out = await graph.ainvoke(
        {"messages": [{"role": "user", "content": case.question}]},
        config=config,
        context=AgentContext(subject_id=case.subject_id, screen=dict(case.screen)),
    )
    intents = list(out.get("intents") or [])
    answer = " ".join(str(r.get("text", "")) for r in out.get("replies") or [])
    missing = [m for m in case.must_include if m not in answer]
    passed = bool(intents) and intents[0] == case.expected_intent and not missing
    if case.expected_intents is not None:
        passed = passed and intents == case.expected_intents
    await safe_record(
        get_deps().recorder,
        Record(
            kind="eval",
            run_id=thread_id,
            thread_id=thread_id,
            data={"case": case.id, "passed": passed, "intents": intents, "missing": missing},
        ),
    )
    return CaseResult(case=case, passed=passed, intents=intents, answer=answer, missing=missing)


async def run_all(only: str | None = None) -> list[CaseResult]:
    results = []
    for case in load_cases():
        if not case.enabled or (only and case.id != only):
            continue
        results.append(await run_case(case))
    return results
