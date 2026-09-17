import asyncio

from website_mcp.browser import Browser
from website_mcp.spec import Site


async def test_idle_browser_closes_and_reopens_with_profile_state(website, tmp_path):
    browser = Browser(Site("fixture", website, ("127.0.0.1",), ()), tmp_path)
    watcher = asyncio.create_task(browser.close_when_idle(0.5, poll_seconds=0.1))
    try:
        await browser.start()
        await browser.page.evaluate("localStorage.setItem('session', 'kept')")
        await asyncio.sleep(1.2)
        assert browser.context is None  # closed while idle
        await browser.start()  # next use relaunches the same profile
        assert await browser.page.evaluate("localStorage.getItem('session')") == "kept"
    finally:
        watcher.cancel()
        await browser.close()


async def test_busy_browser_is_not_closed(website, tmp_path):
    browser = Browser(Site("fixture", website, ("127.0.0.1",), ()), tmp_path)
    watcher = asyncio.create_task(browser.close_when_idle(0.3, poll_seconds=0.05))
    try:
        await browser.start()
        async with browser.lock:  # a run in progress
            await asyncio.sleep(0.8)
            assert browser.context is not None
    finally:
        watcher.cancel()
        await browser.close()


async def test_zero_disables_idle_close(website, tmp_path):
    browser = Browser(Site("fixture", website, ("127.0.0.1",), ()), tmp_path)
    await asyncio.wait_for(browser.close_when_idle(0), timeout=1)  # returns immediately
