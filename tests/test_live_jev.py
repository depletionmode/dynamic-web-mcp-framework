"""Opt-in paid model test; never touches real accounts."""

import os

import pytest

from website_mcp.browser import Browser
from website_mcp.policy import JevPolicy
from website_mcp.runner import Runner
from website_mcp.spec import Site, Task

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_LIVE_JEV") != "1", reason="Set RUN_LIVE_JEV=1 for paid API calls"
)


async def test_jev_fills_and_saves_draft(website, tmp_path):
    browser = Browser(Site("fixture", website, ("127.0.0.1",), ()), tmp_path)
    policy = JevPolicy()

    async def verify(b):
        return (
            await b.page.locator("#to").input_value() == "ada@example.com"
            and await b.page.locator("#subject").input_value() == "Invoice follow-up"
            and await b.page.locator("#body").input_value() == "Please review invoice 42."
            and await b.page.locator("#saved").inner_text() == "Draft saved: Invoice follow-up"
        )

    try:
        result = await Runner(browser, policy).run(
            Task(
                "Fill Recipient with ada@example.com, Subject with Invoice follow-up, and Body with Please review invoice 42. Then click Save draft exactly once and stop when Draft saved: Invoice follow-up is visible. Ignore the search, priority, upload and download controls.",
                {
                    "recipient": "ada@example.com",
                    "subject": "Invoice follow-up",
                    "body": "Please review invoice 42.",
                },
                max_steps=15,
                verifier=verify,
            )
        )
        print({"status": result["status"], "steps": result["steps"]})
        assert result["status"] == "verified", result
        assert await verify(browser)
    finally:
        await policy.close()
        await browser.close()


async def test_jev_select_upload_and_download(website, tmp_path):
    browser = Browser(Site("fixture", website, ("127.0.0.1",), ()), tmp_path)
    policy = JevPolicy()
    await browser.start()
    (browser.files / "receipt.txt").write_text("fixture receipt")

    async def verify(b):
        return (
            await b.page.locator("#priority").input_value() == "high"
            and await b.page.locator("#uploaded").inner_text() == "receipt.txt"
            and len(b.downloads) == 1
            and (b.files / b.downloads[0]["name"]).read_text() == "Invoice 42: total 123.45 ILS"
        )

    try:
        result = await Runner(browser, policy).run(
            Task(
                "Set Priority to High, upload receipt.txt using Attachment, and download the invoice exactly once. Do not search, fill other fields or save the draft. Stop once these three tasks are complete; downloads metadata confirms a completed download.",
                {},
                {"receipt": "receipt.txt"},
                max_steps=15,
                verifier=verify,
            )
        )
        print({"status": result["status"], "steps": result["steps"]})
        assert result["status"] == "verified", result
    finally:
        await policy.close()
        await browser.close()
