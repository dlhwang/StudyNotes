"""BeClient의 HTTP 구현.

**경로는 예시다.** BE와 합의되면 경로만 바꾸거나, OpenAPI에서 만든 클라이언트로 갈아 끼운다.
- 조회만 있다. 타임아웃·5xx는 간격을 늘려 가며 다시 부른다.
- 401/403 → ToolPermissionError, 그 밖의 4xx → ToolInputError(BE가 준 문장), 5xx·타임아웃 → BeUnavailableError.
- 오류 본문은 RFC 9457 Problem Details(``detail``)를 기대한다.
- 계산을 맡기는 조회(시뮬레이션 등)는 본문이 길어 POST일 수 있다 → ``_post_query``. 저장에는 쓰지 않는다.
"""

from __future__ import annotations

import asyncio
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, SecretStr, TypeAdapter

from study_notes.config import BeSettings
from study_notes.core.errors import BeUnavailableError, ToolInputError, ToolPermissionError
from study_notes.tools.be_client.protocol import TaskItem

T = TypeVar("T")


class HttpBeClient:
    def __init__(self, settings: BeSettings, client: httpx.AsyncClient | None = None) -> None:
        self.settings = settings
        self._client = client or httpx.AsyncClient(
            base_url=settings.base_url.rstrip("/") + settings.path_prefix,
            timeout=settings.timeout_seconds,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    def _headers(self, token: SecretStr | None) -> dict[str, str]:
        tok = token or self.settings.service_token
        headers: dict[str, str] = {"Accept": "application/json"}
        if tok is not None:
            headers["Authorization"] = f"Bearer {tok.get_secret_value()}"
        return headers

    @staticmethod
    def _raise_for(resp: httpx.Response) -> None:
        if resp.status_code < 400:
            return
        detail = ""
        try:
            body = resp.json()
            detail = str(body.get("detail") or body.get("title") or "") if isinstance(body, dict) else ""
        except ValueError:
            detail = ""
        if resp.status_code in (401, 403):
            raise ToolPermissionError(detail or "BE 권한이 없습니다")
        if resp.status_code < 500:
            raise ToolInputError(detail or f"BE가 요청을 거절했습니다 ({resp.status_code})", hint=detail)
        raise BeUnavailableError(f"BE 오류 {resp.status_code}")

    async def _retry(self, send: Any, adapter: TypeAdapter[T]) -> T:
        last: Exception | None = None
        for attempt in range(self.settings.read_retries + 1):
            try:
                resp = await send()
                self._raise_for(resp)
                return adapter.validate_python(resp.json())
            except (httpx.TimeoutException, httpx.TransportError, BeUnavailableError) as e:
                last = e
                await asyncio.sleep(0.2 * (2**attempt))
        raise BeUnavailableError("BE 응답 없음") from last

    async def _get(self, path: str, adapter: TypeAdapter[T], *, token: SecretStr | None, **params: Any) -> T:
        query = {k: v for k, v in params.items() if v is not None}
        return await self._retry(lambda: self._client.get(path, params=query, headers=self._headers(token)), adapter)

    async def _post_query(
        self, path: str, body: BaseModel | dict[str, Any], adapter: TypeAdapter[T], *, token: SecretStr | None
    ) -> T:
        """계산을 맡기는 조회. BE 상태를 바꾸지 않는 API에만 쓴다."""
        payload = body.model_dump(mode="json") if isinstance(body, BaseModel) else body
        return await self._retry(lambda: self._client.post(path, json=payload, headers=self._headers(token)), adapter)

    # ── 예시 업무: 할 일 ───────────────────────────────────────────────

    async def list_tasks(self, subject_id: str, *, token: SecretStr | None) -> list[TaskItem]:
        return await self._get(f"/subjects/{subject_id}/tasks", TypeAdapter(list[TaskItem]), token=token)

    async def list_subjects(self, *, token: SecretStr | None) -> list[str]:
        return await self._get("/subjects/active", TypeAdapter(list[str]), token=token)
