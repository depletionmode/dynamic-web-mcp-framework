"""Paid, read-only Jev run against Wikipedia, exercising the extension example."""

import asyncio
import sys
import tempfile
from dataclasses import replace
from pathlib import Path

from jev_mcp.browser import Browser
from jev_mcp.policy import JevPolicy
from jev_mcp.runner import Runner

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "examples"))
from wiki_site import SITE, Search  # noqa: E402


async def main():
    with tempfile.TemporaryDirectory(prefix="jev-wiki-") as state:
        browser = Browser(SITE, Path(state))
        policy = JevPolicy()

        async def verify(b):
            return (
                "/wiki/Ada_Lovelace" in b.page.url
                and await b.page.locator("#firstHeading").inner_text() == "Ada Lovelace"
                and "mathematician" in await b.page.locator("body").inner_text()
            )

        try:
            task = replace(SITE.tools[0].task(Search(query="Ada Lovelace")), verifier=verify)
            result = await Runner(browser, policy).run(task)
            print(
                {"status": result["status"], "url": result["page"]["url"], "steps": result["steps"]}
            )
            assert result["status"] == "verified", result["verification"]
        finally:
            await policy.close()
            await browser.close()


asyncio.run(main())
