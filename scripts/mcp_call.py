"""Call one tool on a site's running MCP container (starting it if needed).

Usage: uv run python scripts/mcp_call.py <servers/site-dir> <tool> ['<json arguments>']
Prints the JSON result. The container keeps running; stop it with bin/site-mcp down <site>.
"""

import asyncio
import json
import sys

from _client import session


async def main(target, tool, arguments):
    async with session(target) as client:
        result = await client.call_tool(tool, arguments)
        for item in result.content:
            print(item.text if hasattr(item, "text") else item)
        return 1 if result.isError else 0


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    sys.exit(
        asyncio.run(
            main(sys.argv[1], sys.argv[2], json.loads(sys.argv[3]) if len(sys.argv) > 3 else {})
        )
    )
