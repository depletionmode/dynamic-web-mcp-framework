import base64
import json
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


async def test_stdio_handshake_tools_and_file_roundtrip(tmp_path):
    site, expected = "servers/wikipedia/site.py", "wiki_search"
    params = StdioServerParameters(
        command=sys.executable,
        # --host '' : no login view, so parallel test runs never fight over a port.
        args=[
            "-m",
            "website_mcp.cli",
            "serve",
            "--site",
            site,
            "--state-dir",
            str(tmp_path),
            "--host",
            "",
        ],
        env=dict(os.environ),
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            names = {tool.name for tool in tools.tools}
            assert expected in names
            assert {"files_put", "files_read", "browser_status"} <= names
            payload = base64.b64encode(b"binary attachment\x00\xff").decode()
            result = await session.call_tool(
                "files_put", {"filename": "../receipt.pdf", "data_base64": payload}
            )
            assert not result.isError
            uploaded = json.loads(result.content[0].text)
            assert "/" not in uploaded["name"]
            result = await session.call_tool("files_read", {"name": uploaded["name"], "length": 5})
            first = json.loads(result.content[0].text)
            assert not first["eof"] and first["next_offset"] == 5
            result = await session.call_tool("files_read", {"name": uploaded["name"], "offset": 5})
            second = json.loads(result.content[0].text)
            assert first["data_base64"] != payload
            assert base64.b64decode(first["data_base64"]) + base64.b64decode(
                second["data_base64"]
            ) == base64.b64decode(payload)
            assert second["eof"]
            result = await session.call_tool("files_read", {"name": "../../etc/passwd"})
            assert result.isError
