from unittest.mock import AsyncMock

from starlette.testclient import TestClient

from jev_mcp.auth import auth_app


def test_login_requires_token():
    browser = AsyncMock()
    with TestClient(auth_app(browser, "secret-token")) as client:
        assert client.get("/").status_code == 200
        assert client.get("/screen").status_code == 401
        assert client.post("/action", json={"op": "text", "text": "password"}).status_code == 401
        browser.page.keyboard.insert_text.assert_not_called()
        assert "secret-token" not in client.get("/").text


async def test_headless_login_view_controls_real_browser(website, tmp_path):
    from httpx import ASGITransport, AsyncClient

    from jev_mcp.browser import Browser
    from jev_mcp.spec import Site

    browser = Browser(Site("fixture", website, ("127.0.0.1",), ()), tmp_path)
    await browser.start()
    try:
        async with AsyncClient(
            transport=ASGITransport(app=auth_app(browser, "test-token")),
            base_url="http://localhost",
            headers={"Authorization": "Bearer test-token"},
        ) as client:
            screenshot = await client.get("/screen")
            assert screenshot.status_code == 200
            assert screenshot.content[:2] == b"\xff\xd8"
            box = await browser.page.locator("#to").bounding_box()
            response = await client.post(
                "/action", json={"op": "click", "x": box["x"] + 10, "y": box["y"] + 10}
            )
            assert response.status_code == 200
            response = await client.post(
                "/action", json={"op": "text", "text": "human-typed-value"}
            )
            assert response.status_code == 200
            assert await browser.page.locator("#to").input_value() == "human-typed-value"
    finally:
        await browser.close()


async def test_logged_out_page_short_circuits_without_model_call(website, tmp_path):
    from unittest.mock import AsyncMock

    from jev_mcp.browser import Browser
    from jev_mcp.runner import Runner
    from jev_mcp.spec import Site, Task

    site = Site("fixture", website, ("127.0.0.1",), (), login_domains=("127.0.0.1",))
    browser = Browser(site, tmp_path)
    policy = AsyncMock()
    try:
        result = await Runner(browser, policy).run(Task("Search mail"))
    finally:
        await browser.close()
    assert result["status"] == "login_required"
    policy.decide.assert_not_called()


async def test_serve_hosts_login_view_and_reports_it(tmp_path):
    import json
    import os
    import socket
    import sys

    import httpx
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "jev_mcp.cli", "serve", "--site", "outlook", "--state-dir", str(tmp_path)]
        + ["--host", "127.0.0.1", "--port", str(port)],
        env=dict(os.environ),
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            # No browser needed to learn where login lives; files_list carries no login block.
            result = await session.call_tool("files_list", {})
            assert not result.isError
            async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}") as client:
                page = await client.get("/")
                assert page.status_code == 200
                assert (await client.get("/screen")).status_code == 401
            assert "login" not in json.loads(result.content[0].text)
