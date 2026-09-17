"""Shared helper: connect to a site's running MCP container over HTTP (bin/site-mcp up <site>)."""

import re
import subprocess
from contextlib import asynccontextmanager
from pathlib import Path

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

ROOT = Path(__file__).resolve().parents[1]


def endpoint(target, debug=True):
    """Ensure servers/<site> is up (with the debug tool when asked); return (url, headers)."""
    directory = Path(target).resolve()
    site = directory.name
    args = [str(ROOT / "bin/site-mcp"), "up", site] + (["--debug"] if debug else [])
    subprocess.run(args, check=True, stdout=subprocess.DEVNULL)
    env = dict(
        line.split("=", 1) for line in (directory / ".env").read_text().splitlines() if "=" in line
    )
    port = re.search(r"127\.0\.0\.1:(\d+)", (directory / "compose.yaml").read_text()).group(1)
    token = env.get("WEBSITE_MCP_TOKEN", "")
    return f"http://127.0.0.1:{port}/mcp", ({"Authorization": f"Bearer {token}"} if token else {})


@asynccontextmanager
async def session(target, debug=True):
    url, headers = endpoint(target, debug)
    async with streamablehttp_client(url, headers=headers, timeout=300, sse_read_timeout=300) as (
        read,
        write,
        _,
    ):
        async with ClientSession(read, write) as client:
            await client.initialize()
            yield client
