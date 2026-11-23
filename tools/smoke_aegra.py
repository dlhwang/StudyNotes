"""떠 있는 Aegra에 BE처럼 붙어 본다: 질문 → SSE(custom) 이벤트 확인.

    python tools/smoke_aegra.py [--url http://127.0.0.1:2026]

BE 개발자가 붙는 방법을 확인할 때도 이 파일을 보면 된다 (docs/01 §3.3).
멈춤(interrupt)·재개는 없다. 버튼을 누른 뒤의 저장·승인은 BE가 한다 (docs/01 §5).
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from typing import Any
from urllib.parse import quote

import httpx
from langgraph_sdk import get_client

HEADERS = {
    "X-User-Id": "user-001",
    "X-User-Name": quote("김가람"),
    "X-User-Role": "user",
}  # 헤더는 ASCII만 → 한글은 URL 인코딩
CONTEXT = {"subject_id": "NB-1", "screen": {"screen_id": "home"}}


def out(text: str) -> None:
    sys.stdout.write(text + "\n")
    sys.stdout.flush()


async def wait_ready(url: str, seconds: int = 90) -> None:
    deadline = time.monotonic() + seconds
    async with httpx.AsyncClient() as http:
        while time.monotonic() < deadline:
            try:
                if (await http.get(f"{url}/ok", timeout=2)).status_code < 500:
                    return
            except httpx.HTTPError:
                pass
            await asyncio.sleep(1)
    raise SystemExit(f"Aegra가 {seconds}초 안에 뜨지 않았습니다: {url}")


async def stream(client: Any, thread_id: str, **kw: Any) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    async for part in client.runs.stream(thread_id, "chat", stream_mode=["custom", "values"], context=CONTEXT, **kw):
        if part.event == "custom":
            events.append(part.data)
            out(f"  [custom] {part.data.get('type')}: {str(part.data)[:160]}")
    return events


async def main(url: str) -> int:
    await wait_ready(url)
    client = get_client(url=url, headers=HEADERS)
    thread = await client.threads.create(metadata={"subject_id": CONTEXT["subject_id"]})
    tid = thread["thread_id"]
    out(f"thread {tid}")

    out("1) 노트 목록 보여줘")
    ev = await stream(client, tid, input={"messages": [{"role": "user", "content": "노트 목록 보여줘"}]})
    assert [e["type"] for e in ev] == ["orchestrator", "agent_reply"], ev
    assert "노트" in ev[-1]["reply"]["text"], ev[-1]

    out("2) 체크포인터가 뭐야? (RAG 질의 — BE가 떠 있어야 근거가 나온다)")
    ev = await stream(client, tid, input={"messages": [{"role": "user", "content": "체크포인터가 뭐야?"}]})
    assert ev[-1]["reply"]["agent"] == "notes", ev[-1]

    out("3) 멈추지 않고 끝났는지 · 대화 메모리가 thread에 남았는지")
    state = await client.threads.get_state(tid)
    assert not state["next"], state["next"]
    assert state["values"].get("focus_note_ids"), state["values"]

    out("4) daily_review 예약 그래프")
    job = await client.threads.create(metadata={"entry": "daily_review"})
    result = await client.runs.wait(job["thread_id"], "daily_review", input={"base_date": "2026-11-23"})
    out(f"  제안 {len(result.get('proposals') or [])}건")
    out("통과")
    return 0


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--url", default="http://127.0.0.1:2026")
    raise SystemExit(asyncio.run(main(p.parse_args().url)))
