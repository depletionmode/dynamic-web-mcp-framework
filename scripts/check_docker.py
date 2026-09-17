"""Read-only container smoke: real MCP handshakes and real public login pages.

Usage: uv run python scripts/check_docker.py [site ...]
"""

import asyncio
import json
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    compose = str(Path(__file__).resolve().parents[1] / "compose.yaml")
    for site in sys.argv[1:] or ("outlook",):
        params = StdioServerParameters(
            command="docker",
            args=[
                "compose",
                "-f",
                compose,
                "run",
                "--rm",
                "--no-deps",
                "--name",
                f"{site}-mcp-smoke",
                "-T",
                f"{site}-mcp",
                "serve",
                "--site",
                site,
                "--account",
                "container-smoke",
            ],
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


asyncio.run(main())
