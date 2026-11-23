"""공통 오류. 도구 실행기가 이 오류를 사람이 읽을 문장으로 바꾼다 (AGENTS.md §4.3)."""

from __future__ import annotations


class AgentError(Exception):
    """ai-agent 안에서 난 오류의 바탕."""


class ToolInputError(AgentError):
    """입력이 잘못됨. ``hint``에 고칠 방법을 담는다. LLM·사용자에게 그대로 보여 줄 수 있다."""

    def __init__(self, message: str, hint: str = "") -> None:
        super().__init__(message)
        self.hint = hint


class ToolPermissionError(AgentError):
    """권한 없음(BE 401/403) 또는 이 Agent에 허용되지 않은 도구. 즉시 멈추고 우회하지 않는다."""


class ToolLimitError(AgentError):
    """한 실행에서 도구 호출 상한을 넘음."""


class BeUnavailableError(AgentError):
    """BE가 응답하지 않음(타임아웃·5xx)."""


class LlmUnavailableError(AgentError):
    """모델을 쓸 수 없음(미설정·실패·상한 초과). 호출한 쪽이 규칙 답으로 바꾼다."""
