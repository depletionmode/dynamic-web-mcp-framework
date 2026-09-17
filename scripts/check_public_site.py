"""Paid, read-only Jev run against Wikipedia, exercising the extension example."""

import asyncio
import tempfile
from pathlib import Path

from website_mcp.browser import Browser
from website_mcp.load import load_site
from website_mcp.policy import JevPolicy
from website_mcp.runner import Runner

SITE = load_site(str(Path(__file__).resolve().parents[1] / "servers/wikipedia/site.py"))
Search = SITE.tools[0].arguments


async def main():
    with tempfile.TemporaryDirectory(prefix="jev-wiki-") as state:
        browser = Browser(SITE, Path(state))
        policy = JevPolicy()

        try:
            task = SITE.tools[0].task(Search(query="Ada Lovelace"))
            result = await Runner(browser, policy).run(task)
            print(
                {"status": result["status"], "url": result["page"]["url"], "steps": result["steps"]}
            )
            assert result["status"] == "verified", result["verification"]
        finally:
            await policy.close()
            await browser.close()


asyncio.run(main())
