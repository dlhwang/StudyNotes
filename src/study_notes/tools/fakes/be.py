"""가짜 BE. BE 없이 끝까지 돌려 보고 시험하기 위한 것 (AGENTS.md §4.6).

데이터는 모두 합성이다. 실데이터를 넣지 않는다.
"""

from __future__ import annotations

from pydantic import SecretStr

from study_notes.tools.be_client.protocol import TaskItem

DEMO_SUBJECT = "DEMO-001"


def _demo_tasks() -> list[TaskItem]:
    return [
        TaskItem(
            id="T-1",
            subject_id=DEMO_SUBJECT,
            title="견적서 검토",
            status="open",
            due_date="2026-11-20",
            owner="김가람",
            note="협력사 견적이 새로 들어왔다",
        ),
        TaskItem(
            id="T-2",
            subject_id=DEMO_SUBJECT,
            title="월간 보고서 작성",
            status="open",
            due_date="2026-11-30",
            owner="이나래",
            note="월 마감 일정",
        ),
        TaskItem(
            id="T-3",
            subject_id=DEMO_SUBJECT,
            title="회의록 공유",
            status="done",
            due_date="2026-11-10",
            owner="김가람",
        ),
    ]


class FakeBeClient:
    """시험에서 데이터를 바꿔 끼울 수 있게 ``tasks``를 그대로 연다."""

    def __init__(self) -> None:
        self.tasks: dict[str, list[TaskItem]] = {DEMO_SUBJECT: _demo_tasks()}

    async def list_tasks(self, subject_id: str, *, token: SecretStr | None) -> list[TaskItem]:
        return [t.model_copy() for t in self.tasks.get(subject_id, [])]

    async def list_subjects(self, *, token: SecretStr | None) -> list[str]:
        return list(self.tasks)
