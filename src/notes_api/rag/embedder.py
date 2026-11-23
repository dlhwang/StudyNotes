"""임베딩. 모델 이름은 설정으로만 정한다.

- ``HashEmbedder``: 모델 없이 도는 결정적 임베딩. 문자 2·3-gram을 해시해 칸에 더하고 L2 정규화한다.
  의미 검색은 못 하지만 단어가 겹치는 청크를 찾는다. 시험과 키 없는 데모용.
- ``LiteLlmEmbedder``: LiteLLM ``embedding()``으로 실제 임베딩 모델을 부른다.

청크마다 ``name``·``version``을 메타데이터에 남긴다(AGENTS.md §3.2). 임베딩을 바꾸면 다시 적재한다.
"""

from __future__ import annotations

import hashlib
import math
import re
from typing import Any, Literal, Protocol


class Embedder(Protocol):
    name: str
    version: str

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class HashEmbedder:
    version = "1"

    def __init__(self, dim: int = 512) -> None:
        self.dim = dim
        self.name = "hash-ngram"

    def _vector(self, text: str) -> list[float]:
        s = re.sub(r"\s+", "", text).lower()
        vec = [0.0] * self.dim
        for n in (2, 3):
            for i in range(len(s) - n + 1):
                h = hashlib.md5(s[i : i + n].encode("utf-8")).digest()  # noqa: S324 — 보안 용도가 아님
                idx = int.from_bytes(h[:4], "little") % self.dim
                vec[idx] += 1.0 if h[4] & 1 else -1.0
        norm = math.sqrt(sum(v * v for v in vec))
        return [v / norm for v in vec] if norm else vec

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(t) for t in texts]


class LiteLlmEmbedder:
    version = "1"

    def __init__(self, model: str) -> None:
        self.model = model
        self.name = f"litellm:{model}"

    def embed(self, texts: list[str]) -> list[list[float]]:
        try:
            import litellm
        except ImportError as e:
            raise RuntimeError("litellm이 설치되지 않았습니다: pip install -e .[llm]") from e
        try:
            resp: Any = litellm.embedding(model=self.model, input=texts)
        except Exception as e:
            raise RuntimeError(f"임베딩 호출 실패: {type(e).__name__}") from e
        return [list(map(float, item["embedding"])) for item in resp.data]


def build_embedder(mode: Literal["hash", "litellm"], model: str | None = None) -> Embedder:
    if mode == "litellm":
        if not model:
            raise ValueError("임베딩 모델이 설정되지 않았습니다 (NOTES_API_EMBEDDING_MODEL)")
        return LiteLlmEmbedder(model)
    return HashEmbedder()
