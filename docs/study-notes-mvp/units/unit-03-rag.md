# Unit 03: RAG 적재·검색(전처리·임베딩·Chroma)

## Goal (목표)

BE에 노트 본문을 청크로 나누고(전처리), 임베딩해(`Embedder`), Chroma 컬렉션에 적재·삭제·검색하는 `NoteIndex`가 있고, 모델 없이도 결정적 해시 임베딩으로 "질문과 관련된 노트 청크 top-k(출처 포함)"를 돌려주는 상태가 된다.

## 배경 / 컨텍스트

- 과제 필수 요소: 데이터 전처리, 임베딩, Vector DB(FAISS/Chroma), 검색 기반 지식 보강.
- AGENTS.md §3.2: 적재와 검색을 나눈다(적재는 대화 중에 하지 않는다 → 노트 저장 때 BE가 한다). 원본과 조각을 나눠 저장하고, 조각마다 임베딩 이름·버전을 남긴다. 검색 결과는 출처(노트 제목·위치)를 함께 준다.
- Agent는 BE 내부 API(Unit 04)로 이 검색을 부른다.

## 선행 조건 (Dependencies)

- Unit 01: `chromadb` 설치
- Unit 02: `src/notes_api/store/models.py`의 `Note`(id, notebook_id, title, body, tags …)
- 참고: `AGENTS.md` §3.2

## 작업 범위 (Scope)

### 한다

- `src/notes_api/rag/__init__.py`, `chunking.py`, `embedder.py`, `index.py`
- `tests/api/test_rag.py`

### 하지 않는다

- HTTP 연결(Unit 04), 재순위(rerank), 하이브리드 검색

## 상세 작업 단계

1. `chunking.py`
   - `Chunk(id: str, note_id: str, position: int, heading: str, text: str)` (dataclass 또는 Pydantic)
   - `normalize(text) -> str`: 줄 끝 공백 제거, 3줄 이상 빈 줄 → 1줄, 탭→공백
   - `split_note(note_id, title, body, max_chars=400, overlap=50) -> list[Chunk]`
     - `## 소제목` 단위로 묶음 → 문단(빈 줄) 단위 → 짧은 문단은 max_chars까지 합침 → 그래도 긴 문단은 max_chars 창을 overlap만큼 겹쳐 자름
     - 각 청크 text 앞에 `"{title} > {heading}\n"`을 붙여 맥락을 준다(heading 없으면 title만)
     - id = `f"{note_id}#{position}"`
2. `embedder.py`
   - `class Embedder(Protocol)`: `name: str`, `version: str`, `dim: int | None`, `def embed(self, texts: list[str]) -> list[list[float]]`
   - `HashEmbedder(dim=512)`: name `"hash-ngram"`, version `"1"`. 공백 제거·소문자 문자열의 2-gram·3-gram을 `hashlib.md5`로 칸 번호와 부호를 정해 더하고 L2 정규화. 결정적이어야 한다.
   - `LiteLlmEmbedder(model: str)`: name `f"litellm:{model}"`, `litellm.embedding(model=..., input=texts)` 사용. 임포트 실패·호출 실패는 `RuntimeError`로 올린다.
   - `build_embedder(mode: Literal["hash","litellm"], model: str | None) -> Embedder`
3. `index.py`
   - `ChunkHit(note_id, chunk_id, notebook_id, title, heading, text, position, score: float)` (Pydantic, API 응답에 그대로)
   - `class NoteIndex`
     - `__init__(self, client: chromadb.api.ClientAPI, embedder: Embedder, collection: str = "note_chunks")` — 컬렉션은 `metadata={"hnsw:space": "cosine"}`, `embedding_function=None`, 임베딩은 직접 넘긴다
     - `upsert_note(note: Note) -> int`: 그 노트의 기존 청크 삭제 후 새로 적재. 메타데이터: `note_id, notebook_id, title, heading, position, embedder, embedder_version`. 돌려주는 값은 청크 수
     - `delete_note(note_id) -> None`
     - `search(notebook_id: str, query: str, k: int = 5) -> list[ChunkHit]`: `where={"notebook_id": ...}`, score = `1 - distance`(소수 넷째 자리 반올림), 점수 높은 순
     - `count(notebook_id: str | None = None) -> int`
   - `make_client(path: str | None) -> ClientAPI`: path가 None이면 `chromadb.EphemeralClient`, 있으면 `PersistentClient(path)`. 둘 다 `Settings(anonymized_telemetry=False, allow_reset=True)`
   - `reindex_all(index, notes: Iterable[Note]) -> int`
4. 시험(`tests/api/test_rag.py`) — 메모리 클라이언트, `HashEmbedder`
   - 청크 분할: 소제목 경계, 길이 상한, 겹침, id 형식
   - HashEmbedder 결정성(같은 입력 → 같은 벡터), 정규화(노름 1)
   - 적재 후 질의 "체크포인터"가 "체크포인터와 메모리" 노트 청크를 1위로
   - 다른 노트북 청크는 결과에 없음
   - 노트 수정 후 upsert → 예전 청크 사라짐, delete_note → 0건
   - 메타데이터에 embedder 이름·버전
   - 시험 데이터는 Unit 02의 `seed_demo`를 메모리 `Store`에 넣어 쓴다
5. 시험이 서로 간섭하지 않도록 컬렉션 이름을 시험마다 다르게(uuid) 하거나 `client.reset()`.

## 사용할 수 있는 SKILL / 참고 자료

- chromadb 문서: `get_or_create_collection`, `upsert/add(ids, embeddings, documents, metadatas)`, `query(query_embeddings, n_results, where)`, `delete(where=...)`
- chromadb 설치가 안 되면(Unit 01 기록) FAISS(`faiss-cpu`) + SQLite 메타데이터로 같은 `NoteIndex` 약속을 구현하고 개요의 설계 결정 표를 고친다

## 완료 조건 (Definition of Done)

- [ ] `.\.venv\Scripts\python.exe -m pytest -q tests/api/test_rag.py` 통과
- [ ] `ruff check`·`ruff format --check`·`mypy` 통과
- [ ] 해시 임베딩으로 seed 노트에 "체크포인터"·"ReAct"·"이벤트 루프" 질의가 각각 해당 노트를 1위로 찾음(시험)

## 산출물 (Output)

- `src/notes_api/rag/{__init__,chunking,embedder,index}.py`
- `tests/api/test_rag.py`
