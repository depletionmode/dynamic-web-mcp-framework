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
        env=dict(os.environ),
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            names = {tool.name for tool in (await session.list_tools()).tools}
            assert {"outlook_search_mail", "outlook_send_mail", "browser_status"} <= names
            payload = base64.b64encode(b"attachment").decode()
            result = await session.call_tool(
                "files_put", {"filename": "a.pdf", "data_base64": payload}
            )
            assert not result.isError and json.loads(result.content[0].text)["size"] == 10
