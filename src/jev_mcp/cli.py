import argparse
import asyncio
import os
from pathlib import Path

from .browser import Browser
from .server import serve
from .sites import load_site


def main():
    parser = argparse.ArgumentParser(description="Jev-driven website MCP server")
    parser.add_argument("command", choices=["serve", "tools"])
    parser.add_argument(
        "--site", required=True, help="outlook, or an importable module exporting SITE"
    )
    parser.add_argument("--account", default=os.getenv("JEV_ACCOUNT", "default"))
    parser.add_argument(
        "--state-dir", type=Path, default=Path(os.getenv("JEV_STATE_DIR", ".state"))
    )
    parser.add_argument(
        "--host", default="127.0.0.1", help="Login view bind address; '' disables it for serve"
    )
    parser.add_argument("--port", type=int, default=8765, help="Login view port")
    args = parser.parse_args()
    os.umask(0o077)
    site = load_site(args.site)
    if args.command == "tools":
        for tool in site.tools:
            print(f"{tool.name}: {tool.description}")
        return
    browser = Browser(site, args.state_dir, args.account)
    try:
        asyncio.run(serve(browser, args.host, args.port))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
