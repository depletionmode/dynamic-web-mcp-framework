"""Read-only container smoke: real MCP handshake and the real public login page.

Usage: uv run python scripts/check_docker.py servers/<site> [servers/<site> ...]
"""

import asyncio
import json
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def check(target):
    directory = Path(target).resolve()
    site, service = directory.name, f"{directory.name}-mcp"
    params = StdioServerParameters(
        command="docker",
        args=["compose", "-f", str(directory / "compose.yaml"), "run", "--rm", "--no-deps"]
        + ["--name", f"{service}-smoke", "-T", service, "serve", "--site", "/site/site.py"]
        + ["--account", "container-smoke"],
        env=dict(os.environ),
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            catalog = await session.list_tools()
            result = await session.call_tool("browser_status", {})
            assert not result.isError, result
            page = json.loads(result.content[0].text)
            # A public app/login page must actually be readable.
            assert page["frames"], page
            assert page["controls"], page
            print(
                json.dumps(
                    {
                        "site": site,
                        "tools": len(catalog.tools),
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
