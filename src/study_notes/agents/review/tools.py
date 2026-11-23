"""review Agent의 업무 도구 (모두 조회). 숫자(복습 대상·통계·약한 노트)는 BE가 계산해 준다."""

from __future__ import annotations

from pydantic import BaseModel, Field

from study_notes.tools.be_client.protocol import Card, LearnerProfile, ReviewStats
from study_notes.tools.registry import ToolContext, agent_tool


class NoArgs(BaseModel):
    pass


class DueArgs(BaseModel):
    notebook_id: str = Field(description="노트북 ID")
    base_date: str = Field(description="기준일 YYYY-MM-DD")
    limit: int = Field(default=20, ge=1, le=100)


class StatsArgs(BaseModel):
    notebook_id: str = Field(description="노트북 ID")
    base_date: str = Field(description="기준일 YYYY-MM-DD")


class ReviewProfileArgs(BaseModel):
    base_date: str | None = None


@agent_tool(agent="review")
async def review_list_notebooks(args: NoArgs, ctx: ToolContext) -> list[str]:
    """예약 실행(daily_review)이 돌 노트북 목록. 대화에서는 쓰지 않는다."""
    return await ctx.be.list_subjects(token=ctx.request.be_token)


@agent_tool(agent="review")
async def review_list_due(args: DueArgs, ctx: ToolContext) -> list[Card]:
    """기준일에 복습할 카드(다음 복습일이 기준일 이전·당일), 오래 밀린 순.

    쓸 때: "오늘 뭐 복습해?", 예약 실행의 오늘 계획. 쓰지 않을 때: 통계 → review_get_stats
    """
    return await ctx.be.list_due_cards(args.notebook_id, args.base_date, limit=args.limit, token=ctx.request.be_token)


@agent_tool(agent="review")
async def review_get_stats(args: StatsArgs, ctx: ToolContext) -> ReviewStats:
    """BE가 계산한 학습 통계(복습 대상 수, 최근 7일 복습 수·정답률, 연속 학습일). 숫자를 다시 계산하지 않는다."""
    return await ctx.be.get_review_stats(args.notebook_id, args.base_date, token=ctx.request.be_token)


@agent_tool(agent="review")
async def review_get_profile(args: ReviewProfileArgs, ctx: ToolContext) -> LearnerProfile:
    """학습자 프로필(장기 메모리): 선호와 BE가 계산한 약한 노트(최근 2주 자주 틀림)."""
    return await ctx.be.get_learner_profile(token=ctx.request.be_token, base_date=args.base_date)
