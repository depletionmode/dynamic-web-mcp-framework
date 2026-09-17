"""Call one tool on a site's container through a real MCP stdio client.

Usage: uv run python scripts/mcp_call.py <site> <tool> ['<json arguments>'] [--local]
Prints the JSON result. --local runs the server from this checkout instead of Docker.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main(site, tool, arguments, local):
    root = Path(__file__).resolve().parents[1]
    if local:
        params = StdioServerParameters(
            command=str(root / ".venv/bin/jev-mcp"),
            args=["serve", "--site", site, "--state-dir", str(root / ".state")],
            env=dict(os.environ),
        )
    else:
        params = StdioServerParameters(
            command="docker",
            args=["compose", "-f", str(root / "compose.yaml"), "run", "--rm", "--no-deps"]
            + ["--service-ports", "-T", site],
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
