"""Human-operated login in the same isolated headless profile; no model calls."""

from __future__ import annotations

import secrets
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, Response
from starlette.routing import Route

HTML = Path(__file__).with_name("auth.html").read_text()


def auth_app(browser, token):
    @asynccontextmanager
    async def lifespan(app):
        await browser.start()
        try:
            yield
        finally:
            await browser.close()

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
            if browser.page.is_closed():
                await browser.observe()
            data = await browser.page.screenshot(type="jpeg", quality=80)
        return Response(data, media_type="image/jpeg", headers={"Cache-Control": "no-store"})

    async def action(request: Request):
        if not authorized(request):
            return Response(status_code=401)
        data = await request.json()
        async with browser.lock:
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
        ],
        lifespan=lifespan,
    )


async def login(browser, host, port):
    token = secrets.token_urlsafe(32)
    print(
        f"Login URL: http://127.0.0.1:{port}/#{token}\nComplete login, then Ctrl-C to save/close the profile before starting MCP.",
        file=sys.stderr,
    )
    server = uvicorn.Server(
        uvicorn.Config(
            auth_app(browser, token), host=host, port=port, log_level="warning", access_log=False
        )
    )
    await server.serve()
