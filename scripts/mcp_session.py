"""Keep one MCP client session open on a site's container and run tool calls from a file.

Usage: uv run python scripts/mcp_session.py <servers/site-dir> <workdir> [--local]

Writes <workdir>/status.json (login URL and state) after connecting, then executes each new
line of <workdir>/commands.jsonl ({"tool": ..., "arguments": {...}}) and writes
<workdir>/results/<n>.json. A line {"tool": "exit"} or a file <workdir>/stop ends the session.
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


def params(target, local):
    root = Path(__file__).resolve().parents[1]
    site = site_name(target)
    if local:
        command = str(root / ".venv/bin/website-mcp")
        args = ["serve", "--site", str(Path(target) / "site.py")]
        args += ["--state-dir", str(root / ".state")]
    else:
        command, args = str(root / "bin/site-mcp"), [site]
    return StdioServerParameters(
        command=command, args=args, env=dict(os.environ) | {"WEBSITE_MCP_DEBUG_TOOLS": "1"}
    )


async def main(site, workdir, local):
    workdir.mkdir(parents=True, exist_ok=True)
    (workdir / "results").mkdir(exist_ok=True)
    commands = workdir / "commands.jsonl"
    commands.touch()
    done = 0
    async with stdio_client(params(site, local)) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            status = await session.call_tool("browser_status", {})
            page = json.loads(status.content[0].text)
            (workdir / "status.json").write_text(
                json.dumps({"url": page["url"], "login": page["login"]}, indent=2)
            )
            print(f"Connected. Login: {page['login']}", file=sys.stderr)
            while not (workdir / "stop").exists():
                lines = commands.read_text().splitlines()
                if len(lines) <= done:
                    await asyncio.sleep(0.5)
                    continue
                call = json.loads(lines[done])
                done += 1
                if call.get("tool") == "exit":
                    break
                result = await session.call_tool(call["tool"], call.get("arguments", {}))
                text = "\n".join(getattr(item, "text", str(item)) for item in result.content)
                try:
                    payload = json.loads(text)
                except ValueError:
                    payload = text
                out = workdir / "results" / f"{done}.json"
                out.write_text(
                    json.dumps(
                        {"call": call, "error": result.isError, "result": payload},
                        indent=2,
                        ensure_ascii=False,
                    )
                )
                print(f"[{done}] {call['tool']} -> {out}", file=sys.stderr)


if __name__ == "__main__":
    argv = [a for a in sys.argv[1:] if a != "--local"]
    if len(argv) != 2:
        sys.exit(__doc__)
    asyncio.run(main(argv[0], Path(argv[1]), "--local" in sys.argv))
