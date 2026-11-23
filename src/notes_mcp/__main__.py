"""MCP 서버를 stdio로 띄운다: ``python -m notes_mcp``. BE(``NOTES_MCP_BE_URL``)가 떠 있어야 한다."""

from __future__ import annotations

import anyio
import httpx

from notes_mcp.config import McpSettings
from notes_mcp.server import build_server


async def _main() -> None:
    settings = McpSettings()
    async with httpx.AsyncClient(base_url=settings.be_url, timeout=settings.timeout_seconds) as http:
        await build_server(http).run_stdio_async()


if __name__ == "__main__":
    anyio.run(_main)
