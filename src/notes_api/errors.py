"""오류 → RFC 9457 Problem Details. Agent의 ``HttpBeClient``가 ``detail``을 읽어 고칠 방법으로 쓴다."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from notes_api.store import InvalidInputError, NotFoundError


def problem(status: int, title: str, detail: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"type": "about:blank", "title": title, "status": status, "detail": detail},
        media_type="application/problem+json",
    )


def install_handlers(app: FastAPI) -> None:
    @app.exception_handler(NotFoundError)
    async def _not_found(_: Request, e: NotFoundError) -> JSONResponse:
        return problem(404, "찾을 수 없음", str(e))

    @app.exception_handler(InvalidInputError)
    async def _invalid(_: Request, e: InvalidInputError) -> JSONResponse:
        return problem(400, "잘못된 입력", str(e))
