"""Human-operated login page served by the MCP process on its own browser; no model calls."""

from __future__ import annotations

import asyncio
import secrets
import sys
from pathlib import Path

import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, Response
from starlette.routing import Route

HTML = Path(__file__).with_name("auth.html").read_text()


def auth_app(browser, token):
    def authorized(request):
        return secrets.compare_digest(request.headers.get("authorization", ""), f"Bearer {token}")

    async def index(request):
        return HTMLResponse(
            HTML,
            headers={
                "Cache-Control": "no-store",
                "Referrer-Policy": "no-referrer",
                "X-Frame-Options": "DENY",
            },
        )

    async def screenshot(request):
        if not authorized(request):
            return Response(status_code=401)
        async with browser.lock:
            await browser.start()
            if browser.page.is_closed():
                await browser.observe()
            data = await browser.page.screenshot(type="jpeg", quality=80)
        return Response(data, media_type="image/jpeg", headers={"Cache-Control": "no-store"})

    async def action(request: Request):
        if not authorized(request):
            return Response(status_code=401)
        data = await request.json()
        async with browser.lock:
            await browser.start()
            op = data.get("op")
            if op == "click":
                x, y = float(data["x"]), float(data["y"])
                if not (0 <= x <= 1440 and 0 <= y <= 1000):
                    return JSONResponse({"error": "invalid coordinates"}, status_code=400)
                await browser.page.mouse.click(x, y)
            elif op == "text":
                text = str(data["text"])
                if len(text) > 10000:
                    return Response(status_code=400)
                await browser.page.keyboard.insert_text(text)
            elif op == "key" and data.get("key") in {
                "Enter",
                "Tab",
                "Escape",
                "Backspace",
                "ControlOrMeta+A",
                "ArrowDown",
                "ArrowUp",
            }:
                await browser.page.keyboard.press(data["key"])
            elif op == "scroll":
                await browser.page.mouse.wheel(0, max(-1000, min(1000, int(data["dy"]))))
            elif op == "home":
                await browser.page.goto(browser.site.start_url, wait_until="domcontentloaded")
            else:
                return JSONResponse({"error": "unknown operation"}, status_code=400)
        return JSONResponse({"ok": True})

    return Starlette(
        routes=[
            Route("/", index),
            Route("/screen", screenshot),
            Route("/action", action, methods=["POST"]),
        ]
    )


class LoginView:
    """Token-protected human login page running beside the MCP server."""

    def __init__(self, browser, host, port):
        self.token = secrets.token_urlsafe(32)
        self.url = f"http://127.0.0.1:{port}/#{self.token}"
        self.server = uvicorn.Server(
            uvicorn.Config(
                auth_app(browser, self.token),
                host=host,
                port=port,
                log_level="warning",
                access_log=False,
            )
        )

    async def serve_in_background(self):
        """Never lets a bind failure kill the MCP server; uvicorn raises SystemExit on it."""
        try:
            await self.server.serve()
        except asyncio.CancelledError:
            raise
        except BaseException as exc:
            print(f"Login view unavailable: {exc}", file=sys.stderr)

    def stop(self):
        self.server.should_exit = True
