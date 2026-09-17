"""MCP over HTTP: bearer-protected /mcp beside the login view, usable by many clients."""

import asyncio
import os
import socket
import subprocess
import sys

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


async def test_http_transport_serves_site_tools_to_authorized_clients(tmp_path):
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    env = {k: v for k, v in os.environ.items() if k != "WEBSITE_MCP_DEBUG_TOOLS"}
    env["WEBSITE_MCP_TOKEN"] = "test-token"
    server = subprocess.Popen(
        [sys.executable, "-m", "website_mcp.cli", "serve", "--site", "servers/wikipedia/site.py"]
        + ["--state-dir", str(tmp_path), "--transport", "http", "--port", str(port)],
        env=env,
    )
    base = f"http://127.0.0.1:{port}"
    try:
        async with httpx.AsyncClient(base_url=base) as client:
            for _ in range(100):
                try:
                    if (await client.get("/health")).status_code == 200:
                        break
                except httpx.HTTPError:
                    pass
                await asyncio.sleep(0.1)
            assert (await client.get("/")).status_code == 200  # login view
            assert (await client.get("/screen")).status_code == 401
            assert (await client.post("/mcp", json={})).status_code == 401
        headers = {"Authorization": "Bearer test-token"}
        for _ in range(2):  # two independent clients, same server
            async with streamablehttp_client(f"{base}/mcp", headers=headers) as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    names = {tool.name for tool in (await session.list_tools()).tools}
                    assert names == {"wiki_search"}
    finally:
        server.terminate()
        server.wait(timeout=10)
