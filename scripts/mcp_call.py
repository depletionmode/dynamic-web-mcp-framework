"""Call one tool on a site's container through a real MCP stdio client.

Usage: uv run python scripts/mcp_call.py <servers/site-dir> <tool> ['<json arguments>'] [--local]
Prints the JSON result. --local runs <site-dir>/site.py from this checkout instead of Docker.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def site_name(target):
    """servers/<site> directory -> site; bin/site-mcp runs it as container <site>-mcp."""
    return Path(target).resolve().name


async def main(target, tool, arguments, local):
    root = Path(__file__).resolve().parents[1]
    site = site_name(target)
    if local:
        params = StdioServerParameters(
            command=str(root / ".venv/bin/website-mcp"),
            args=["serve", "--site", str(Path(target) / "site.py")]
            + ["--state-dir", str(root / ".state")],
            env=dict(os.environ) | {"WEBSITE_MCP_DEBUG_TOOLS": "1"},
        )
    else:
        params = StdioServerParameters(
            command=str(root / "bin/site-mcp"),
            args=[site],
            # The MCP SDK strips the environment by default; Compose needs TYPESAFE_API_KEY.
            env=dict(os.environ) | {"WEBSITE_MCP_DEBUG_TOOLS": "1"},
        )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool, arguments)
            for item in result.content:
                print(item.text if hasattr(item, "text") else item)
            return 1 if result.isError else 0


if __name__ == "__main__":
    argv = [a for a in sys.argv[1:] if a != "--local"]
    if len(argv) < 2:
        sys.exit(__doc__)
    sys.exit(
        asyncio.run(
            main(
                argv[0],
                argv[1],
                json.loads(argv[2]) if len(argv) > 2 else {},
                "--local" in sys.argv,
            )
        )
    )
