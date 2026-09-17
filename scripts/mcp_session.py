"""Keep one MCP client session open on a site's container and run tool calls from a file.

Usage: uv run python scripts/mcp_session.py <servers/site-dir> <workdir>

Starts the container if needed, writes <workdir>/status.json (login URL and state), then executes
each new line of <workdir>/commands.jsonl ({"tool": ..., "arguments": {...}}) and writes
<workdir>/results/<n>.json. A line {"tool": "exit"} or a file <workdir>/stop ends the session.
"""

import asyncio
import json
import sys
from pathlib import Path

from _client import session


async def main(target, workdir):
    workdir.mkdir(parents=True, exist_ok=True)
    (workdir / "results").mkdir(exist_ok=True)
    commands = workdir / "commands.jsonl"
    commands.touch()
    done = 0
    async with session(target) as client:
        status = await client.call_tool("browser_status", {})
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
            result = await client.call_tool(call["tool"], call.get("arguments", {}))
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
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    asyncio.run(main(sys.argv[1], Path(sys.argv[2])))
