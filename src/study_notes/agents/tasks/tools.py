"""예시 Agent의 업무 도구 (모두 조회).

이름: tasks_<동사>_<대상>. 첫 인자는 Pydantic 모델, 둘째는 ToolContext. 독스트링에 언제 쓰고 언제 쓰지 않는지.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from study_notes.tools.be_client.protocol import TaskItem
from study_notes.tools.registry import ToolContext, agent_tool


class SubjectArgs(BaseModel):
    subject_id: str = Field(description="대상 ID. 예: DEMO-001")


class NoArgs(BaseModel):
    pass


@agent_tool(agent="tasks", llm_selectable=True)
async def tasks_list_items(args: SubjectArgs, ctx: ToolContext) -> list[TaskItem]:
    """대상의 할 일 목록(열린 것·끝난 것 모두)을 가져온다.

    쓸 때: "할 일 보여줘", "이 할 일 왜 생겼어?"
    쓰지 않을 때: 여러 대상을 한꺼번에 볼 때 → 예약 실행(daily_check)이 한다.
    """
    return await ctx.be.list_tasks(args.subject_id, token=ctx.request.be_token)


@agent_tool(agent="tasks")
async def tasks_list_subjects(args: NoArgs, ctx: ToolContext) -> list[str]:
    """예약 실행이 점검할 대상 목록. 대화에서는 쓰지 않는다."""
    return await ctx.be.list_subjects(token=ctx.request.be_token)
