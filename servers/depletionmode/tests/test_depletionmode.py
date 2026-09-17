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


def test_year_range_validation_and_phrasing():
    IndexQuery = TOOLS["depletionmode_list_index"].arguments
    with pytest.raises(ValidationError):
        IndexQuery(year_from=2020, year_to=2015)
    with pytest.raises(ValidationError):
        IndexQuery(section="blog")
    with pytest.raises(ValidationError):
        IndexQuery(limit=0)
    with pytest.raises(ValidationError):
        IndexQuery(query="themida")  # extra fields are rejected
    assert IndexQuery(year_from=2015, year_to=2019).span() == "entries dated 2015 to 2019 inclusive"
    assert IndexQuery(year_to=2012).span() == "entries dated 2012 or earlier"
    assert IndexQuery().span() == "entries from every year"
    assert IndexQuery(year_from=2019).enough("the footer").startswith("Entries run newest first")
    assert IndexQuery().enough("the footer") == "Finish once the footer is on screen. "
    assert (
        IndexQuery(section="poc").heading()
        == "the 'poc' section, in the top of the short right-hand column"
    )
    assert IndexQuery().heading() == "every section"


def test_the_catalog_is_the_four_read_only_tools():
    assert set(TOOLS) == {
        "depletionmode_list_index",
        "depletionmode_list_archive",
        "depletionmode_find",
        "depletionmode_read_post",
    }


def test_find_and_post_goals_carry_the_callers_strings():
    find = TOOLS["depletionmode_find"]
    task = find.task(find.arguments(query="themida", include_archive=False))
    assert task.values == {"query": "themida"}
    assert "do not open the archive page" in task.goal
    assert "/archive/" in find.task(find.arguments(query="themida")).goal

    read = TOOLS["depletionmode_read_post"]
    task = read.task(read.arguments(title="Unpacking Themida #1"))
    assert task.values == {"title": "Unpacking Themida #1"}
    assert "'Unpacking Themida #1'" in task.goal
    assert "Stop if two entries share that title" in task.goal


def test_every_tool_is_read_only():
    assert all(tool.read_only for tool in SITE.tools)


def test_domains_cover_the_off_site_entry_targets():
    for url in (
        "https://depletionmode.com/unpacking-themida-1/",
        "https://www.originhq.com/research/a-pdf-picked-my-model",
        "https://cloudblogs.microsoft.com/microsoftsecure/2018/04/19/introducing-windows-defender-system-guard-runtime-attestation/",
        "https://github.com/originsec/praxis",
        "https://patents.google.com/patent/US10366213B2",
        "https://pagedout.institute/download/PagedOut_003_beta1.pdf",
        "https://exchange.xforce.ibmcloud.com/collection/aabb53f56644710abdb147d9a0adb57b",
    ):
        assert SITE.permits(url), url
    assert not SITE.permits("https://www.linkedin.com/in/davkaps/")
    # A public site: nothing is ever a sign-in redirect.
    assert SITE.login_domains == ()
    assert not SITE.is_login_url("https://depletionmode.com/")


async def test_stdio_handshake_lists_depletionmode_tools(tmp_path):
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
            assert set(TOOLS) <= names
            # No file store: the site has no downloadable artifact, and no custom_task.
            assert not any(
                n.startswith(("depletionmode_put_file", "depletionmode_read_file"))
                or n == "depletionmode_list_files"
                or n == "depletionmode_task"
                for n in names
            )
            assert not any(n.startswith(("files_", "website_", "browser_")) for n in names)
