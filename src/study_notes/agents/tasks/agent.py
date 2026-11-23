"""예시 하위 Agent — 할 일. 새 프로젝트는 이 폴더를 지우거나 바꿔 자기 Agent를 만든다.

보여 주는 것
- 의도 선언(``intents``)과 규칙 분류 정규식
- 조회 도구 부르기(``self.tool``)
- 규칙 답(``task_list``)과 모델 답 + 실패 시 규칙 답(``task_explain``)
- 버튼(``UiAction``)과 근거(``Citation``)
"""

from __future__ import annotations

from typing import cast

from study_notes.agents.base import AgentRequest, BaseAgent
from study_notes.agents.tasks import rules
from study_notes.agents.tasks.tools import SubjectArgs
from study_notes.core.errors import LlmUnavailableError
from study_notes.core.reply import AgentResult, Citation, UiAction
from study_notes.orchestrator.intents import IntentSpec
from study_notes.tools.be_client.protocol import TaskItem

TASK_EXPLAIN = IntentSpec(
    "task_explain",
    "할 일이 왜 생겼는지 설명",
    (r"(왜|이유|근거).*(할일|생겼)", r"(할일|생긴).*(왜|이유|근거)"),
)
TASK_LIST = IntentSpec(
    "task_list",
    "할 일 목록 보기",
    (r"^(?!.*(왜|이유|근거)).*(할일|해야할|todo)",),
)


class TasksAgent(BaseAgent):
    name = "tasks"
    title = "할 일 Agent"
    intents = (TASK_EXPLAIN, TASK_LIST)

    async def run(self, req: AgentRequest) -> AgentResult:
        tasks = cast(list[TaskItem], await self.tool("tasks_list_items", SubjectArgs(subject_id=self.subject_id())))
        if req.intent == TASK_EXPLAIN.name:
            return await self._explain(req, tasks)
        return self._list(tasks)

    def _list(self, tasks: list[TaskItem]) -> AgentResult:
        opened = rules.open_tasks(tasks)
        if not opened:
            return AgentResult(reply=self.reply("열린 할 일이 없습니다."))
        lines = [f"{t.title}(마감 {t.due_date}, {t.owner})" for t in opened]
        return AgentResult(
            reply=self.reply(
                f"열린 할 일 {len(opened)}건입니다. " + " / ".join(lines),
                actions=[UiAction(kind="ask", label="왜 생겼는지", text=f"{opened[0].title} 할 일 왜 생겼어?")],
                data={"tasks": [t.model_dump(include={"id", "title", "due_date", "owner"}) for t in opened]},
            )
        )

    async def _explain(self, req: AgentRequest, tasks: list[TaskItem]) -> AgentResult:
        task = rules.find_task(tasks, req.text)
        if task is None:
            return AgentResult(reply=self.reply("설명할 할 일을 찾지 못했습니다."))
        citation = Citation(title=f"할 일 {task.id}", location="BE tasks")
        facts = f"{task.title} / 마감 {task.due_date} / 담당 {task.owner} / 근거: {task.note or '없음'}"
        try:
            # 모델은 문장만 다듬는다. 사실은 facts에 있는 것만 쓰게 프롬프트에 적어 둔다
            text, pid = await self.ask_llm("worker", self.prompt("explain"), req.text, task=facts)
            return AgentResult(reply=self.reply(text, source="ai", citations=[citation], prompt_version=pid))
        except LlmUnavailableError:
            reason = task.note or "근거가 적혀 있지 않습니다"
            text = (
                f"'{task.title}'은 {reason} 때문에 생긴 할 일입니다. 마감은 {task.due_date}, 담당은 {task.owner}입니다."
            )
            return AgentResult(reply=self.reply(text, citations=[citation]))
