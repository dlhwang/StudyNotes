"""예시 Agent의 규칙. 모델 없이 시험할 수 있는 순수 함수만 둔다."""

from __future__ import annotations

from study_notes.core.ids import dedupe_key
from study_notes.core.proposal import ProposalDraft
from study_notes.orchestrator.intents import compact
from study_notes.tools.be_client.protocol import TaskItem


def open_tasks(tasks: list[TaskItem]) -> list[TaskItem]:
    return sorted((t for t in tasks if t.status == "open"), key=lambda t: t.due_date)


def find_task(tasks: list[TaskItem], text: str) -> TaskItem | None:
    """질문에 제목이 들어 있는 할 일. 없으면 가장 급한 열린 할 일."""
    t = compact(text)
    for task in tasks:
        if compact(task.title) in t:
            return task
    opened = open_tasks(tasks)
    return opened[0] if opened else None


def overdue_notices(tasks: list[TaskItem], base_date: str) -> list[ProposalDraft]:
    """마감이 지난 열린 할 일 → 알림 제안 초안. 예약 실행(daily_check)이 쓴다.

    중복 방지 키 = 대상·할 일·기준일. 같은 날 두 번 돌아도 키가 같아 BE가 한 번만 저장한다.
    """
    out: list[ProposalDraft] = []
    for t in open_tasks(tasks):
        if t.due_date >= base_date:
            continue
        out.append(
            ProposalDraft(
                kind="task.overdue_notice",
                subject_id=t.subject_id,
                title=f"'{t.title}' 마감({t.due_date})이 지났습니다",
                payload={"task_id": t.id, "due_date": t.due_date, "owner": t.owner},
                reasons=[f"기준일 {base_date}에 아직 열려 있음"],
                source="agent",
                source_ref=t.id,
                dedupe_key=dedupe_key("overdue", t.subject_id, t.id, base_date),
            )
        )
    return out
