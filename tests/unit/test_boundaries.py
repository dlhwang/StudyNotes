"""패키지 경계 (AGENTS.md §0-4): Agent 패키지는 BE·화면 패키지를 import하지 않는다."""

from __future__ import annotations

import re
from pathlib import Path

AGENT_SRC = Path(__file__).resolve().parents[2] / "src" / "study_notes"
_FORBIDDEN = re.compile(r"^\s*(from|import)\s+(notes_api|notes_ui|notes_mcp)\b", re.M)


def test_agent_does_not_import_be_or_ui() -> None:
    offenders = [
        str(p.relative_to(AGENT_SRC))
        for p in AGENT_SRC.rglob("*.py")
        if _FORBIDDEN.search(p.read_text(encoding="utf-8"))
    ]
    assert offenders == [], f"Agent는 BE를 HttpBeClient로만 부릅니다: {offenders}"
