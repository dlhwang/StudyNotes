"""데모용 합성 시드 데이터. 직접 쓴 짧은 학습 메모다(책·문서 본문 인용 없음).

``seed_demo(store, today)``는 노트북이 하나도 없을 때만 넣는다.
"""

from __future__ import annotations

from datetime import date, timedelta

from notes_api.store.models import Grade
from notes_api.store.store import Store

NOTEBOOKS: list[tuple[str, list[tuple[str, list[str], str]]]] = [
    (
        "LangGraph 공부",
        [
            (
                "StateGraph 기초",
                ["langgraph", "그래프"],
                """## 그래프를 만드는 순서
StateGraph는 상태 스키마를 먼저 정하고 노드와 엣지를 더한 뒤 compile 해서 실행 가능한 그래프를 얻는다.
노드는 상태를 받아 바뀐 부분만 dict로 돌려준다. 상태 객체를 직접 고치지 않는다.

- 상태 스키마: 그래프 전체가 공유하는 데이터 모양. 보통 TypedDict로 정의한다
- 노드: 상태를 받아 부분 업데이트를 돌려주는 함수
- 엣지: 노드 다음에 어느 노드로 갈지 정하는 연결
- 리듀서: 여러 노드가 같은 키를 갱신할 때 값을 합치는 규칙

## 조건 분기
add_conditional_edges로 상태를 보고 다음 노드를 고른다.
분기 함수는 모델의 자유 문장 대신 구조화된 필드를 보고 결정하는 편이 안정적이다.
START와 END는 그래프의 시작과 끝을 뜻하는 특별한 노드 이름이다.""",
            ),
            (
                "체크포인터와 메모리",
                ["langgraph", "메모리"],
                """## 체크포인터
체크포인터는 노드가 끝날 때마다 그래프 상태를 저장한다. 그래서 대화를 이어 가거나 실패한 지점부터 다시 실행할 수 있다.
같은 thread_id로 다시 부르면 이전 상태 위에서 이어서 실행된다.

- 체크포인터: 단계마다 상태 스냅숏을 저장하는 장치. 개발에는 InMemorySaver, 운영에는 PostgreSQL 저장소를 쓴다
- thread_id: 하나의 대화(실행 흐름)를 구분하는 키
- 단기 메모리: 한 thread 안에서 이어지는 대화 기록과 상태

## 장기 메모리
여러 thread를 넘어 기억할 정보는 따로 저장소에 둔다. 사용자 선호나 학습 이력이 그 예다.

- 장기 메모리: thread가 바뀌어도 남는 사용자별 정보
- durability: 체크포인트를 언제 디스크에 쓸지 정하는 옵션. sync는 매 단계 바로 쓴다""",
            ),
            (
                "도구 호출과 ReAct",
                ["agent", "도구"],
                """## Function Calling
모델에게 도구 이름, 설명, 인자 JSON 스키마를 알려 주면 모델이 어떤 도구를 어떤 인자로 부를지 구조화된 형태로 돌려준다.
실제 실행은 애플리케이션 코드가 하고 결과를 다시 모델에게 넘긴다.

- Function Calling: 모델이 도구 호출을 구조화된 JSON으로 내놓는 기능
- 도구 설명: 언제 쓰고 언제 쓰지 않는지를 적어야 모델이 도구를 잘 고른다

## ReAct
ReAct는 생각하고(Reason) 행동하고(Act) 관찰하는 과정을 반복하는 에이전트 실행 방식이다.
관찰 결과가 충분하면 최종 답을 내고, 부족하면 다른 도구를 다시 부른다.

- ReAct: 추론과 도구 실행을 번갈아 반복하는 패턴
- 관찰: 도구 실행 결과를 모델에게 돌려준 것
- 단계 상한: 무한 반복을 막기 위해 루프 횟수를 제한하는 장치""",
            ),
        ],
    ),
    (
        "파이썬 비동기",
        [
            (
                "asyncio 기초",
                ["python", "asyncio"],
                """## 코루틴과 이벤트 루프
async def로 만든 함수는 코루틴을 돌려준다. await를 만나면 제어권을 이벤트 루프에 넘기고, 루프는 다른 작업을 실행한다.

- 코루틴: async def로 정의한, 중간에 멈췄다 다시 이어지는 함수
- 이벤트 루프: 준비된 코루틴을 번갈아 실행하는 스케줄러
- await: 다른 코루틴이나 I/O가 끝날 때까지 기다리며 제어권을 넘기는 키워드

## 여러 작업 동시에 돌리기
asyncio.gather는 여러 코루틴을 동시에 실행하고 결과를 순서대로 모은다.
asyncio.wait_for로 시간 제한을 걸 수 있다. CPU를 오래 쓰는 일은 이벤트 루프를 막으므로 to_thread로 넘긴다.""",
            ),
            (
                "동시성과 병렬성",
                ["python", "동시성"],
                """## 차이
동시성은 여러 작업을 번갈아 진행해 함께 진행되는 것처럼 보이게 하는 것이고,
병렬성은 실제로 같은 순간에 여러 작업을 실행하는 것이다.

- 동시성: 하나의 실행 흐름이 작업을 번갈아 처리하는 구조
- 병렬성: 여러 코어에서 작업을 같은 순간에 실행하는 것
- GIL: CPython에서 한 번에 한 스레드만 파이썬 바이트코드를 실행하게 하는 잠금

## 언제 무엇을
I/O를 기다리는 일이 많으면 asyncio나 스레드가 맞고, 계산이 많으면 multiprocessing이 맞다.""",
            ),
        ],
    ),
]

# (노트 순번, 질문, 답) — 노트 순번은 위 목록 전체에서 0부터
CARDS: list[tuple[int, str, str]] = [
    (0, "StateGraph에서 노드는 무엇을 돌려주는가?", "상태의 바뀐 부분만 담은 dict"),
    (0, "리듀서란 무엇인가?", "여러 노드가 같은 키를 갱신할 때 값을 합치는 규칙"),
    (0, "조건 분기는 어떤 메서드로 만드는가?", "add_conditional_edges"),
    (0, "START와 END는 무엇인가?", "그래프의 시작과 끝을 뜻하는 특별한 노드 이름"),
    (1, "체크포인터란 무엇인가?", "단계마다 상태 스냅숏을 저장하는 장치"),
    (1, "thread_id란 무엇인가?", "하나의 대화(실행 흐름)를 구분하는 키"),
    (1, "durability sync는 무엇을 뜻하는가?", "체크포인트를 매 단계 바로 디스크에 쓴다"),
    (3, "이벤트 루프란 무엇인가?", "준비된 코루틴을 번갈아 실행하는 스케줄러"),
]

# (카드 순번, 며칠 전, 등급)
REVIEWS: list[tuple[int, int, Grade]] = [
    (0, 4, "good"),
    (1, 4, "again"),
    (4, 3, "again"),
    (5, 3, "good"),
    (4, 2, "again"),
    (6, 2, "hard"),
    (0, 1, "good"),
    (4, 1, "again"),
    (5, 1, "easy"),
]


def seed_demo(store: Store, today: str) -> bool:
    """비어 있으면 데모 데이터를 넣고 True."""
    if store.list_notebooks():
        return False
    base = date.fromisoformat(today)
    start = (base - timedelta(days=5)).isoformat()
    note_ids: list[str] = []
    for nb_name, notes in NOTEBOOKS:
        nb = store.create_notebook(nb_name)
        for title, tags, body in notes:
            note_ids.append(store.create_note(nb.id, title, body, tags, source="직접 정리").id)
    card_ids: list[str] = []
    for note_idx, q, a in CARDS:
        card_ids += [c.id for c in store.add_cards(note_ids[note_idx], [(q, a)], start)]
    for card_idx, days_ago, grade in REVIEWS:
        store.record_review(card_ids[card_idx], grade, (base - timedelta(days=days_ago)).isoformat())
    return True
