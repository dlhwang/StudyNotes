"""도구 계층 (AGENTS.md §4). 도구는 모두 조회다.

| 단계 | 위치 | 누가 고르나 |
| BE 클라이언트 | tools/be_client/ | 아무도 직접 고르지 않음 (도구 안에서만) |
| 업무 도구 | agents/<도메인>/tools.py | 하위 Agent 코드, llm_selectable이면 LLM도 |
| 안전장치 | tools/guards.py | 모든 도구 호출이 거친다 |
"""
