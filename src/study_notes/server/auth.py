"""Aegra 인증 핸들러 (aegra.json의 auth.path).

ai-agent는 BE만 부른다 (FE → BE → ai-agent). 토큰 전달 방식은 프로젝트마다 정하므로 두 방식만 둔다.

- ``dev``: 개발 PC 전용. ``X-User-Id`` 헤더를 그대로 믿는다.
- ``trusted_be``: 내부망에서 BE만 부를 수 있다는 전제. ``X-Agent-Key``(공유 키)를 확인하고,
  BE가 보낸 사용자 헤더와 ``Authorization``(사용자 토큰, BE 도구 호출에 그대로 쓴다)을 받는다.

돌려준 dict는 그래프에서 ``config["configurable"]["langgraph_auth_user"]``로 읽는다 (core/context.py).

**주의 (Aegra 0.12에서 확인)**: 여기 넣은 be_token은 Aegra의 ``public.runs.execution_params``에
그대로 저장된다. 운영 전에 토큰 전달 방식을 바꿔야 한다(짧게 사는 위임 토큰, 또는 서비스 계정 + "누구 대신" 헤더).
"""

from __future__ import annotations

import hmac
from typing import Any
from urllib.parse import unquote

from langgraph_sdk import Auth

from study_notes.config import get_settings

auth = Auth()

# 헤더 이름. 프로젝트에서 BE와 맞춘다
USER_ID = "X-User-Id"
USER_NAME = "X-User-Name"  # 헤더는 ASCII만 되므로 한글 이름은 BE가 URL 인코딩해 보낸다
USER_ROLE = "X-User-Role"
AGENT_KEY = "X-Agent-Key"


def _header(headers: dict[Any, Any], name: str) -> str:
    for k, v in headers.items():
        key = k.decode() if isinstance(k, bytes) else str(k)
        if key.lower() == name.lower():
            return v.decode() if isinstance(v, bytes) else str(v)
    return ""


@auth.authenticate
async def authenticate(headers: dict[Any, Any]) -> dict[str, Any]:
    s = get_settings().auth
    user_id = _header(headers, USER_ID)
    if s.mode == "trusted_be":
        expected = s.shared_key.get_secret_value() if s.shared_key else ""
        given = _header(headers, AGENT_KEY)
        if not expected or not hmac.compare_digest(expected, given):
            raise Auth.exceptions.HTTPException(status_code=401, detail="BE 공유 키가 맞지 않습니다")
    if not user_id:
        raise Auth.exceptions.HTTPException(status_code=401, detail=f"{USER_ID} 헤더가 필요합니다")
    token = _header(headers, "Authorization").removeprefix("Bearer ").strip()
    return {
        "identity": user_id,
        "display_name": unquote(_header(headers, USER_NAME)),
        "role": _header(headers, USER_ROLE) or "user",
        "permissions": [],
        "is_authenticated": True,
        "be_token": token or None,
    }


@auth.on.threads
async def owner_only(ctx: Auth.types.AuthContext, value: dict[str, Any]) -> dict[str, Any]:
    """자기 thread만 보게 한다. thread metadata에 owner를 남기고 그것으로 거른다."""
    metadata = value.setdefault("metadata", {}) if isinstance(value, dict) else {}
    if isinstance(metadata, dict):
        metadata["owner"] = ctx.user.identity
    return {"owner": ctx.user.identity}
