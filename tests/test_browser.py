import asyncio

import pytest

from jev_mcp.browser import Browser
from jev_mcp.spec import Site


def target(observation, name):
    return next(c["id"] for c in observation["controls"] if c["name"] == name)


@pytest.fixture
async def browser(website, tmp_path):
    browser = Browser(Site("fixture", website, ("127.0.0.1",), ()), tmp_path)
    await browser.start()
    yield browser
    await browser.close()


async def test_real_controls_frames_shadow_upload_download(browser):
    observation = await browser.observe()
    assert target(observation, "Frame action")
    assert target(observation, "Shadow action")
    await browser.act("fill", target(observation, "Subject"), "Test invoice")
    observation = await browser.observe()
    await browser.act("select", target(observation, "Priority"), "high")
    assert await browser.page.locator("#priority").input_value() == "high"
    (browser.files / "receipt.txt").write_text("receipt")
    observation = await browser.observe()
    await browser.act("upload", target(observation, "Attachment"), "receipt.txt")
    assert await browser.page.locator("#uploaded").inner_text() == "receipt.txt"
    observation = await browser.observe()
    await browser.act("click", target(observation, "Save draft"))
    assert await browser.page.locator("#saved").inner_text() == "Draft saved: Test invoice"
    observation = await browser.observe()
    await browser.act("click", target(observation, "Download invoice"))
    await browser.flush_downloads()
    assert len(browser.downloads) == 1
    assert (
        browser.files / browser.downloads[0]["name"]
    ).read_text() == "Invoice 42: total 123.45 ILS"


async def test_stale_target_and_unknown_target_rejected(browser):
    observation = await browser.observe()
    await browser.page.locator("#save").evaluate("el => el.textContent='Delete everything'")
    with pytest.raises(RuntimeError, match="Stale"):
        await browser.act("click", target(observation, "Save draft"))
    with pytest.raises(ValueError, match="Unobserved"):
        await browser.act("click", "9999")


async def test_navigation_allowlist(browser):
    observation = await browser.observe()
    await browser.act("click", target(observation, "Outside domain"))
    await asyncio.sleep(0.1)
    assert browser.blocked_navigation == "https://example.org/forbidden"


async def test_profile_persistence_isolation_and_lock(website, tmp_path):
    site = Site("fixture", website, ("127.0.0.1",), ())
    first = Browser(site, tmp_path, "first")
    second = Browser(site, tmp_path, "second")
    try:
        await first.start()
        await first.page.evaluate("localStorage.setItem('secret','private')")
        collision = Browser(site, tmp_path, "first")
        with pytest.raises(RuntimeError, match="already in use"):
            await collision.start()
        await second.start()
        assert await second.page.evaluate("localStorage.getItem('secret')") is None
        await first.close()
        await first.start()
        assert await first.page.evaluate("localStorage.getItem('secret')") == "private"
    finally:
        await first.close()
        await second.close()


async def test_changed_form_rejects_unchanged_submit_button(browser):
    observation = await browser.observe()
    await browser.page.locator("#to").fill("wrong@example.com")
    with pytest.raises(RuntimeError, match="Stale"):
        await browser.act("click", target(observation, "Save draft"))


async def test_strict_csp_allows_snapshot_and_input(website, tmp_path):
    browser = Browser(Site("strict", website + "strict", ("127.0.0.1",), ()), tmp_path)
    try:
        await browser.start()
        observation = await browser.observe()
        await browser.act("fill", target(observation, "Strict field"), "works with CSP")
        assert await browser.page.locator("input").input_value() == "works with CSP"
    finally:
        await browser.close()
