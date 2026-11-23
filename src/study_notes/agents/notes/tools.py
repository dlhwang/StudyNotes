"""notes Agent의 업무 도구 (모두 조회).

이름: notes_<동사>_<대상>. ``llm_selectable=True``인 도구는 ReAct 루프에서 모델이 직접 고른다.
노트북 ID를 비우면 지금 대화의 노트북(``request.subject_id``)을 쓴다 — 모델이 ID를 몰라도 된다.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from study_notes.core.errors import ToolInputError
from study_notes.tools.be_client.protocol import ChunkHit, LearnerProfile, Note, NoteSummary
from study_notes.tools.registry import ToolContext, agent_tool


class NoteListArgs(BaseModel):
    notebook_id: str | None = Field(default=None, description="노트북 ID. 비우면 지금 노트북")
    query: str | None = Field(default=None, description="제목·태그·본문 키워드. 비우면 최근 노트")
    limit: int = Field(default=10, ge=1, le=20)


class NoteIdArgs(BaseModel):
    note_id: str = Field(description="노트 ID. 예: N-1")


class ChunkSearchArgs(BaseModel):
    query: str = Field(description="찾을 내용. 질문 문장 그대로 또는 핵심 용어", min_length=1)
    notebook_id: str | None = Field(default=None, description="노트북 ID. 비우면 지금 노트북")
    k: int = Field(default=4, ge=1, le=8, description="가져올 조각 수")


class ProfileArgs(BaseModel):
    base_date: str | None = Field(default=None, description="기준일 YYYY-MM-DD")


def notebook_of(ctx: ToolContext, notebook_id: str | None) -> str:
    nb = notebook_id or ctx.request.subject_id
    if not nb:
        raise ToolInputError("노트북을 알 수 없습니다", hint="화면에서 노트북을 고른 뒤 다시 물어 주세요")
    return nb


@agent_tool(agent="notes")
async def notes_list_items(args: NoteListArgs, ctx: ToolContext) -> list[NoteSummary]:
    """노트 목록(제목·태그·앞부분)을 가져온다. 키워드를 주면 제목·태그·본문에 든 노트만 점수순.

    쓸 때: "노트 목록 보여줘", "LangGraph 노트 찾아줘", 질문에 나온 노트 제목 확인
    쓰지 않을 때: 노트 내용으로 질문에 답할 때 → notes_search_chunks
    """
    return await ctx.be.list_notes(
        notebook_of(ctx, args.notebook_id), query=args.query, limit=args.limit, token=ctx.request.be_token
    )


@agent_tool(agent="notes", llm_selectable=True)
async def notes_get_item(args: NoteIdArgs, ctx: ToolContext) -> Note:
    """노트 한 개의 본문 전체를 가져온다.

    쓸 때: 검색 조각만으로 답이 부족해 노트 전체 맥락이 필요할 때, 특정 노트를 요약할 때
    쓰지 않을 때: 어느 노트에 있는지 모를 때 → 먼저 notes_search_chunks
    """
    return await ctx.be.get_note(args.note_id, token=ctx.request.be_token)


@agent_tool(agent="notes", llm_selectable=True)
async def notes_search_chunks(args: ChunkSearchArgs, ctx: ToolContext) -> list[ChunkHit]:
    """노트 조각을 의미 검색(RAG)한다. 결과마다 노트 ID·제목·소제목·본문 조각·점수(0~1)를 준다.

    쓸 때: 사용자의 질문에 답할 근거를 노트에서 찾을 때. 질문 문장이나 핵심 용어로 검색한다
    쓰지 않을 때: 노트 목록만 필요할 때 → notes_list_items
    점수가 0.15보다 낮은 조각은 관련이 약하다. 근거가 없으면 없다고 답한다.
    """
    return await ctx.be.search_chunks(
        notebook_of(ctx, args.notebook_id), args.query, k=args.k, token=ctx.request.be_token
    )


@agent_tool(agent="notes")
async def notes_get_profile(args: ProfileArgs, ctx: ToolContext) -> LearnerProfile:
    """학습자 프로필(장기 메모리): 선호 요약 길이·퀴즈 난이도·약한 노트. 요약 길이를 정할 때 쓴다."""
    return await ctx.be.get_learner_profile(token=ctx.request.be_token, base_date=args.base_date)
