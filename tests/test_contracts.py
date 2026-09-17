import os
import sys

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from pydantic import ValidationError

from website_mcp.spec import Site, contained_file


def test_validation_rejects_unknown_fields():
    from website_mcp.load import load_site

    site = load_site("servers/wikipedia/site.py")
    with pytest.raises(ValidationError):
        site.tools[0].arguments(query="x", selector="#evil")


def test_domains_and_path_boundary(tmp_path):
    site = Site("test", "https://example.com", ("example.com",), ())
    assert site.permits("https://app.example.com")
    assert not site.permits("https://example.com.evil.org")
    assert not site.permits("file:///etc/passwd")
    root = tmp_path / "files"
    root.mkdir()
    outside = tmp_path / "secret"
    outside.write_text("secret")
    (root / "symlink").symlink_to(outside)
    for name in ["../secret", "symlink", str(outside)]:
        with pytest.raises(ValueError):
            contained_file(root, name)


async def test_site_exposes_only_its_own_tools(tmp_path):
    params = StdioServerParameters(
        command=sys.executable,
        # --host '' : no login view, so parallel test runs never fight over a port.
        args=["-m", "website_mcp.cli", "serve", "--site", "servers/wikipedia/site.py"]
        + ["--state-dir", str(tmp_path), "--host", ""],
        env={k: v for k, v in os.environ.items() if k != "WEBSITE_MCP_DEBUG_TOOLS"},
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            names = {tool.name for tool in (await session.list_tools()).tools}
            assert names == {"wiki_search"}
            result = await session.call_tool("browser_status", {})
            assert result.isError


async def test_debug_tool_is_opt_in(tmp_path):
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "website_mcp.cli", "serve", "--site", "servers/wikipedia/site.py"]
        + ["--state-dir", str(tmp_path), "--host", ""],
        env=dict(os.environ) | {"WEBSITE_MCP_DEBUG_TOOLS": "1"},
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            names = {tool.name for tool in (await session.list_tools()).tools}
            assert names == {"wiki_search", "browser_status"}
