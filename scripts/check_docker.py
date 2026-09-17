"""Container smoke, no model calls: start the site's container, handshake over HTTP, list its
tools, and read the public landing page.

Usage: uv run python scripts/check_docker.py servers/<site> [servers/<site> ...]
The containers keep running afterwards; stop with bin/site-mcp down <site>.
"""

import asyncio
import json
import sys
from pathlib import Path

from _client import session


async def check(target):
    async with session(target) as client:
        catalog = await client.list_tools()
        result = await client.call_tool("browser_status", {})
        assert not result.isError, result
        page = json.loads(result.content[0].text)
        assert page["frames"] and page["controls"], page  # the public page must be readable
        print(
            json.dumps(
                {
                    "site": Path(target).resolve().name,
                    "tools": sorted(t.name for t in catalog.tools if t.name != "browser_status"),
                    "url": page["url"].split("?")[0],
                    "controls": len(page["controls"]),
                    "blocked_navigation": page["blocked_navigation"],
                    "login": page["login"],
                }
            )
        )


async def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    for target in sys.argv[1:]:
        await check(target)


asyncio.run(main())
