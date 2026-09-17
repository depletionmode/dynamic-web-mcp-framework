import base64
import json
import os
import sys
from pathlib import Path

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from pydantic import ValidationError

from website_mcp.load import load_site

SITE_FILE = str(Path(__file__).resolve().parents[1] / "site.py")
SITE = load_site(SITE_FILE)
TOOLS = {tool.name: tool for tool in SITE.tools}


def test_search_syntax_and_validation():
    MailQuery = TOOLS["outlook_search_mail"].arguments
    ChangeMessages = TOOLS["outlook_manage_mail"].arguments
    with pytest.raises(ValidationError):
        ChangeMessages(messages=["test"], action="move")
    with pytest.raises(ValidationError):
        MailQuery(after="2026-09-17", before="2026-01-01")
    query = MailQuery(
        sender="ada@example.com", unread=True, has_attachments=True, after="2026-09-01"
    )
    assert (
        query.search()
        == 'from:"ada@example.com" received:>=2026-09-01 isread:no hasattachments:yes'
    )


def test_login_domains_cover_the_sign_in_chain():
    assert SITE.is_login_url("https://login.live.com/oauth20_authorize.srf?x=1")
    assert SITE.is_login_url("https://www.microsoft.com/en-us/microsoft-365/outlook/")
    assert not SITE.is_login_url("https://outlook.live.com/mail/0/")


async def test_stdio_handshake_lists_outlook_tools(tmp_path):
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "website_mcp.cli", "serve", "--site", SITE_FILE, "--state-dir", str(tmp_path)]
        + ["--host", ""],
        env={k: v for k, v in os.environ.items() if k != "WEBSITE_MCP_DEBUG_TOOLS"},
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            names = {tool.name for tool in (await session.list_tools()).tools}
            assert {"outlook_search_mail", "outlook_send_mail"} <= names
            capabilities = {"outlook_put_file", "outlook_read_file", "outlook_list_files"}
            assert capabilities | {"outlook_task"} <= names
            assert not any(n.startswith(("files_", "website_", "browser_")) for n in names)
            payload = base64.b64encode(b"attachment").decode()
            result = await session.call_tool(
                "outlook_put_file", {"filename": "../a.pdf", "data_base64": payload}
            )
            uploaded = json.loads(result.content[0].text)
            assert not result.isError and uploaded["size"] == 10 and "/" not in uploaded["name"]
            result = await session.call_tool(
                "outlook_read_file", {"name": uploaded["name"], "length": 4}
            )
            first = json.loads(result.content[0].text)
            assert not first["eof"] and first["next_offset"] == 4
