"""quiz Agent의 업무 도구 (모두 조회). 카드 저장은 하지 않는다 — 제안 초안을 돌려주고 BE가 저장한다."""

from __future__ import annotations

from pydantic import BaseModel, Field

from study_notes.core.errors import ToolInputError
from study_notes.tools.be_client.protocol import Card, LearnerProfile, Note, NoteSummary
from study_notes.tools.registry import ToolContext, agent_tool


class QuizNotesArgs(BaseModel):
    notebook_id: str = Field(description="노트북 ID. 예: NB-1")
    limit: int = Field(default=20, ge=1, le=50)


class QuizNoteArgs(BaseModel):
    note_id: str = Field(description="노트 ID. 예: N-1")


class QuizCardsArgs(BaseModel):
    notebook_id: str = Field(description="노트북 ID")
    note_id: str = Field(description="이 노트의 카드만")


class QuizProfileArgs(BaseModel):
    base_date: str | None = None


@agent_tool(agent="quiz")
async def quiz_list_notes(args: QuizNotesArgs, ctx: ToolContext) -> list[NoteSummary]:
    """퀴즈를 만들 노트를 고르기 위해 노트 목록(제목)을 가져온다.

    쓸 때: 질문에 든 노트 제목을 찾을 때. 쓰지 않을 때: 내용 검색 → notes Agent의 일
    """
    return await ctx.be.list_notes(args.notebook_id, limit=args.limit, token=ctx.request.be_token)


@agent_tool(agent="quiz")
async def quiz_get_note(args: QuizNoteArgs, ctx: ToolContext) -> Note:
    """카드를 만들 노트 본문 전체. 카드의 근거는 이 본문에만 있어야 한다."""
    if not args.note_id:
        raise ToolInputError("노트 ID가 비어 있습니다", hint="노트 제목을 넣어 다시 물어 주세요")
    return await ctx.be.get_note(args.note_id, token=ctx.request.be_token)


@agent_tool(agent="quiz")
async def quiz_list_cards(args: QuizCardsArgs, ctx: ToolContext) -> list[Card]:
    """그 노트에 이미 있는 카드. 같은 질문을 다시 만들지 않으려고 본다."""
    return await ctx.be.list_cards(args.notebook_id, note_id=args.note_id, token=ctx.request.be_token)


@agent_tool(agent="quiz")
async def quiz_get_profile(args: QuizProfileArgs, ctx: ToolContext) -> LearnerProfile:
    """학습자 프로필(장기 메모리)의 퀴즈 난이도 선호를 읽는다."""
    return await ctx.be.get_learner_profile(token=ctx.request.be_token, base_date=args.base_date)
