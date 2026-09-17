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
