"""chat 그래프 — BE가 사용자 질문을 넘기는 진입점 (docs/01 §3).

classify_intent → run_agents → 끝

SSE: BE는 ``stream_mode=["custom", "values"]``로 부른다. custom 이벤트 형식은 core/reply.py.
멈춤(interrupt)·승인·실행은 없다. 하위 Agent 답에 제안 초안(``proposals``)과 버튼(``actions``)이 담겨 오면
FE가 버튼을 그리고, 사용자가 누르면 FE→BE가 저장·승인한다. ai-agent는 BE에 쓰지 않는다 (docs/01 §5).
"""

from __future__ import annotations

from typing import Annotated, Any, TypedDict

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage
from langgraph.config import get_config, get_stream_writer
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.runtime import Runtime
from langgraph.types import Checkpointer

from study_notes.agents.base import AgentRequest
from study_notes.agents.registry import agent_for, all_intents
from study_notes.config import get_settings
from study_notes.core.context import AgentContext, RequestInfo, request_info
from study_notes.core.errors import BeUnavailableError, ToolInputError, ToolLimitError, ToolPermissionError
from study_notes.core.reply import AgentReply, AgentReplyEvent, OrchestratorEvent, UiAction
from study_notes.deps import get_deps
from study_notes.observability.logging import get_logger, log_context
from study_notes.orchestrator.classify import classify

GRAPH = "chat"
ORCHESTRATOR = "orchestrator"
log = get_logger("graphs.chat")


class ChatState(TypedDict, total=False):
    messages: Annotated[list[AnyMessage], add_messages]
    intents: list[str]
    replies: list[dict[str, Any]]  # 이번 질문의 하위 Agent 답(요약). 제안 초안도 여기에 있다


def _req(runtime: Runtime[AgentContext]) -> RequestInfo:
    return request_info(get_config(), runtime.context, GRAPH)


def _last_user_text(state: ChatState) -> str:
    for m in reversed(state.get("messages") or []):
        if isinstance(m, HumanMessage) or getattr(m, "type", "") == "human":
            return str(m.content)
    return ""


def _history(state: ChatState, limit: int = 6) -> list[str]:
    msgs = (state.get("messages") or [])[-limit - 1 : -1]
    return [f"{getattr(m, 'type', '')}: {str(m.content)[:200]}" for m in msgs]


def _emit(event: dict[str, Any]) -> None:
    try:
        get_stream_writer()(event)
    except RuntimeError:  # 스트림 밖(invoke)에서 부를 때
        pass


async def classify_intent(state: ChatState, runtime: Runtime[AgentContext]) -> dict[str, Any]:
    req = _req(runtime)
    deps = get_deps()
    text = _last_user_text(state)
    with log_context(run_id=req.run_id, thread_id=req.thread_id, graph=GRAPH, node="classify_intent"):
        intents, how = await classify(text, all_intents(), deps.llm, deps.settings.guard.max_intents_per_message)
        names: list[str] = []
        for i in intents:
            cls = agent_for(i)
            if cls.title not in names:
                names.append(cls.title)
        if names:
            verb = "담당합니다" if len(names) == 1 else "함께 답합니다"
            _emit(OrchestratorEvent(agents=names, text=f"이 질문은 {' · '.join(names)}가 {verb}.").model_dump())
        log.info("의도 판정", extra={"fields": {"intents": intents, "how": how}})
    return {"intents": intents, "replies": []}


def _error_reply(agent: str, e: Exception) -> AgentReply:
    if isinstance(e, ToolInputError):
        text = str(e) + (f" ({e.hint})" if e.hint else "")
    elif isinstance(e, ToolPermissionError):
        text = "이 요청을 처리할 권한이 없습니다."
    elif isinstance(e, ToolLimitError):
        text = "한 번에 처리할 수 있는 양을 넘었습니다. 질문을 나눠 주세요."
    elif isinstance(e, BeUnavailableError):
        text = "업무 시스템이 지금 응답하지 않습니다. 잠시 뒤 다시 물어 주세요."
    else:
        text = "처리 중 문제가 생겼습니다."
    return AgentReply(agent=agent, text=text, source="rule")


def _help_reply() -> AgentReply:
    """의도를 못 찾았을 때. 물어볼 수 있는 것을 보여 준다."""
    specs = all_intents()
    lines = " / ".join(s.help for s in specs)
    return AgentReply(
        agent=ORCHESTRATOR,
        text=f"질문을 이해하지 못했습니다. 이런 것을 물어볼 수 있습니다: {lines}",
        source="rule",
        actions=[UiAction(kind="ask", label=s.help, text=s.help) for s in specs[:3]],
    )


async def run_agents(state: ChatState, runtime: Runtime[AgentContext]) -> dict[str, Any]:
    req = _req(runtime)
    deps = get_deps()
    text = _last_user_text(state)
    replies: list[AgentReply] = []
    for intent in state.get("intents") or []:
        cls = agent_for(intent)
        stop = False
        with log_context(run_id=req.run_id, thread_id=req.thread_id, graph=GRAPH, node="run_agents", agent=cls.name):
            try:
                result = await cls(req, deps).run(AgentRequest(intent=intent, text=text, history=_history(state)))
                reply = result.reply
            except (ToolInputError, ToolPermissionError, ToolLimitError, BeUnavailableError) as e:
                reply = _error_reply(cls.name, e)
                # 권한 오류는 즉시 멈추고 우회하지 않는다 (AGENTS.md §4.3)
                stop = isinstance(e, ToolPermissionError)
            except Exception as e:
                log.exception("하위 Agent 실패")
                reply = _error_reply(cls.name, e)
        replies.append(reply)
        _emit(AgentReplyEvent(reply=reply).model_dump())
        if stop:
            break
    if not replies:
        reply = _help_reply()
        replies.append(reply)
        _emit(AgentReplyEvent(reply=reply).model_dump())
    messages = [AIMessage(content=r.text, name=r.agent) for r in replies]
    return {"replies": [r.model_dump() for r in replies], "messages": messages}


def build_chat_graph(checkpointer: Checkpointer = None) -> Any:
    g = StateGraph(ChatState, context_schema=AgentContext)
    g.add_node("classify_intent", classify_intent)
    g.add_node("run_agents", run_agents)
    g.add_edge(START, "classify_intent")
    g.add_edge("classify_intent", "run_agents")
    g.add_edge("run_agents", END)
    compiled = g.compile(checkpointer=checkpointer, name=GRAPH)
    return compiled.with_config(recursion_limit=get_settings().guard.recursion_limit)


# Aegra가 읽는 그래프 (aegra.json). 체크포인터는 Aegra가 붙인다
graph = build_chat_graph()
