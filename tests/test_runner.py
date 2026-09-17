from unittest.mock import AsyncMock

from jev_mcp.browser import Browser
from jev_mcp.policy import Decision
from jev_mcp.runner import Runner
from jev_mcp.spec import Site, Task


async def test_done_does_not_imply_verified(website, tmp_path):
    browser = Browser(Site("fixture", website, ("127.0.0.1",), ()), tmp_path)
    policy = AsyncMock()
    policy.decide.return_value = Decision("done")
    policy.verify.return_value = 0.3
    try:
        result = await Runner(browser, policy).run(Task("Send an email"))
        assert result["status"] == "unverified"
        assert result["verification"] == {"kind": "model", "probability": 0.3}
    finally:
        await browser.close()


async def test_error_never_replays_action(website, tmp_path):
    browser = Browser(Site("fixture", website, ("127.0.0.1",), ()), tmp_path)
    policy = AsyncMock()
    policy.decide.return_value = Decision("click", "not-real")
    try:
        result = await Runner(browser, policy).run(Task("Send an email"))
        assert result["status"] == "action_error"
        assert policy.decide.await_count == 1
        assert len(result["steps"]) == 1
    finally:
        await browser.close()


async def test_stale_preflight_reobserves_without_duplicate_click(website, tmp_path):
    browser = Browser(Site("fixture", website, ("127.0.0.1",), ()), tmp_path)
    await browser.start()
    await browser.page.evaluate(
        "window.clicks=0;document.querySelector('#save').addEventListener('click',()=>window.clicks++)"
    )
    calls = 0

    async def decide(task, observation, history, guidance):
        nonlocal calls
        calls += 1
        if calls == 1:
            await browser.page.locator("#subject").fill("changed before input")
        if calls < 3:
            control = next(c for c in observation["controls"] if c["name"] == "Save draft")
            return Decision("click", control["id"])
        return Decision("done")

    policy = AsyncMock()
    policy.decide.side_effect = decide
    policy.verify.return_value = 0.99
    try:
        result = await Runner(browser, policy).run(Task("Save current form once"))
        assert result["status"] == "model_complete"
        assert result["steps"][0]["executed"] is False
        assert result["steps"][1]["executed"] is True
        assert await browser.page.evaluate("window.clicks") == 1
    finally:
        await browser.close()
