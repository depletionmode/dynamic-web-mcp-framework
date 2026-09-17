from __future__ import annotations

import asyncio
import base64
import json
import os
import secrets
import sys
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import TextContent, Tool, ToolAnnotations
from pydantic import Field
from starlette.applications import Starlette
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from .auth import login_routes
from .policy import JevPolicy
from .runner import Runner
from .spec import Arguments, Task, contained_file


class Empty(Arguments):
    pass


class WebsiteTask(Arguments):
    goal: str = Field(
        min_length=1,
        max_length=10000,
        description="Exact requested website workflow and completion conditions",
    )
    values: dict[str, str] = Field(
        default_factory=dict,
        description="All exact text values that Jev may type, labeled by purpose",
    )
    uploads: dict[str, str] = Field(
        default_factory=dict, description="Purpose to existing private file name"
    )
    max_steps: int = Field(default=60, ge=1, le=150)


class PutFile(Arguments):
    filename: str = Field(min_length=1, max_length=200)
    data_base64: str = Field(
        max_length=14_000_000, description="Base64 file content; maximum decoded size 10 MiB"
    )


class ReadFile(Arguments):
    name: str
    offset: int = Field(default=0, ge=0)
    length: int = Field(default=262144, ge=1, le=1048576)


# browser_status exposes the raw page; it is for developers and the helper scripts only.
DEBUG_TOOLS_ENV = "WEBSITE_MCP_DEBUG_TOOLS"


def capability_tools(site):
    """Framework capabilities the site opted into, named for the site."""
    tools = {}
    if site.custom_task:
        tools[f"{site.name}_task"] = (
            WebsiteTask,
            f"Run any other {site.name} workflow, described in words with exact values to type. May modify data.",
            False,
        )
    if site.attachments:
        tools[f"{site.name}_list_files"] = (
            Empty,
            f"List files available to attach in {site.name} and files downloaded from it.",
            True,
        )
        tools[f"{site.name}_put_file"] = (
            PutFile,
            f"Upload a file so a {site.name} tool can attach it. Returns the name to pass as an attachment.",
            False,
        )
        tools[f"{site.name}_read_file"] = (
            ReadFile,
            f"Read a file downloaded from {site.name} as base64, in chunks; returns next offset and EOF.",
            True,
        )
    if os.getenv(DEBUG_TOOLS_ENV):
        tools["browser_status"] = (
            Empty,
            "Debug: observe the current browser page without a model call. Starts the browser if needed.",
            True,
        )
    return tools


def create_server(browser, policy=None, login_url=None):
    server = Server(f"jev-{browser.site.name}")
    runner = Runner(browser, policy or JevPolicy())

    def with_login(result):
        """Tell the agent whether a human must sign in, and where, before retrying."""
        result["login"] = {"required": browser.needs_login(), "url": login_url}
        return result

    specs = {spec.name: spec for spec in browser.site.tools}
    builtins = capability_tools(browser.site)
    if len(specs) != len(browser.site.tools) or specs.keys() & builtins.keys():
        raise ValueError("Tool names must be unique and cannot shadow capability tools")

    @server.list_tools()
    async def list_tools():
        result = [
            Tool(
                name=spec.name,
                description=spec.description,
                inputSchema=spec.arguments.model_json_schema(),
                annotations=ToolAnnotations(
                    readOnlyHint=spec.read_only,
                    destructiveHint=not spec.read_only,
                    idempotentHint=False,
                    openWorldHint=True,
                ),
            )
            for spec in browser.site.tools
        ]
        result.extend(
            Tool(
                name=name,
                description=description,
                inputSchema=model.model_json_schema(),
                annotations=ToolAnnotations(readOnlyHint=read_only),
            )
            for name, (model, description, read_only) in builtins.items()
        )
        return result

    @server.call_tool()
    async def call_tool(name, arguments):
        if name in specs:
            spec = specs[name]
            args = spec.arguments.model_validate(arguments)
            task = spec.task(args)
            for filename in task.uploads.values():
                contained_file(browser.files, filename)
            result = with_login(await runner.run(task))
        elif name in builtins:
            args = builtins[name][0].model_validate(arguments)
            if name.endswith("_task"):
                for filename in args.uploads.values():
                    contained_file(browser.files, filename)
                result = with_login(
                    await runner.run(Task(args.goal, args.values, args.uploads, args.max_steps))
                )
                return [
                    TextContent(
                        type="text", text=json.dumps(result, ensure_ascii=False, default=str)
                    )
                ]
            async with browser.lock:
                if name == "browser_status":
                    await browser.start()
                    result = with_login(await browser.observe())
                else:
                    browser.files.mkdir(parents=True, exist_ok=True, mode=0o700)
                    if name.endswith("_list_files"):
                        result = [
                            {"name": p.name, "size": p.stat().st_size}
                            for p in sorted(browser.files.iterdir())
                            if p.is_file() and not p.is_symlink()
                        ]
                    elif name.endswith("_put_file"):
                        data = base64.b64decode(args.data_base64, validate=True)
                        if len(data) > 10 * 1024 * 1024:
                            raise ValueError("File exceeds 10 MiB")
                        filename = uuid.uuid4().hex[:12] + "-" + Path(args.filename).name
                        path = browser.files / filename
                        with path.open("xb") as stream:
                            stream.write(data)
                        path.chmod(0o600)
                        result = {"name": filename, "size": len(data)}
                    else:
                        path = contained_file(browser.files, args.name)
                        with path.open("rb") as stream:
                            stream.seek(args.offset)
                            data = stream.read(args.length)
                        next_offset = args.offset + len(data)
                        result = {
                            "name": path.name,
                            "data_base64": base64.b64encode(data).decode(),
                            "next_offset": next_offset,
                            "eof": next_offset >= path.stat().st_size,
                        }
        else:
            raise ValueError("Unknown tool")
        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, default=str))]

    return server, runner


def web_app(browser, token, mcp_server=None):
    """Login view, /health, and (for HTTP transport) the bearer-protected MCP endpoint at /mcp."""
    routes = login_routes(browser, token)
    routes.append(Route("/health", lambda request: JSONResponse({"site": browser.site.name})))
    lifespan = None
    if mcp_server is not None:
        manager = StreamableHTTPSessionManager(
            app=mcp_server,
            stateless=True,
            json_response=True,
            security_settings=TransportSecuritySettings(
                enable_dns_rebinding_protection=True,
                allowed_hosts=["127.0.0.1", "127.0.0.1:*", "localhost", "localhost:*"],
                allowed_origins=["http://127.0.0.1:*", "http://localhost:*"],
            ),
        )
        expected = f"Bearer {token}".encode()

        class McpEndpoint:
            """Raw ASGI app on an exact path; a Mount would 307-redirect /mcp to /mcp/."""

            async def __call__(self, scope, receive, send):
                headers = dict(scope.get("headers") or [])
                if not secrets.compare_digest(headers.get(b"authorization", b""), expected):
                    await Response(status_code=401)(scope, receive, send)
                    return
                await manager.handle_request(scope, receive, send)

        routes.append(Route("/mcp", McpEndpoint(), methods=["GET", "POST", "DELETE"]))

        @asynccontextmanager
        async def lifespan(app):
            async with manager.run():
                yield

    return Starlette(routes=routes, lifespan=lifespan)


async def serve(browser, host, port, transport="stdio"):
    """MCP over stdio (with the login view beside it) or over HTTP on host:port.

    One token protects both the login view and the MCP endpoint. Set WEBSITE_MCP_TOKEN for a
    stable token that clients can be configured with; otherwise one is generated per run.
    """
    token = os.getenv("WEBSITE_MCP_TOKEN") or secrets.token_urlsafe(32)
    login_url = f"http://127.0.0.1:{port}/#{token}" if host else None
    server, runner = create_server(browser, login_url=login_url)
    view_task = None
    try:
        if transport == "http":
            print(
                f"MCP endpoint: http://127.0.0.1:{port}/mcp\nLogin view: {login_url}",
                file=sys.stderr,
            )
            await _uvicorn(web_app(browser, token, server), host, port).serve()
        else:
            if host:
                print(f"Login view: {login_url}", file=sys.stderr)
                view = _uvicorn(web_app(browser, token), host, port)
                view_task = asyncio.create_task(_serve_quietly(view))
            async with stdio_server() as (read, write):
                await server.run(read, write, server.create_initialization_options())
    finally:
        if view_task:
            view.should_exit = True
            await view_task
        await runner.policy.close()
        await browser.close()


def _uvicorn(app, host, port):
    return uvicorn.Server(
        uvicorn.Config(app, host=host, port=port, log_level="warning", access_log=False)
    )


async def _serve_quietly(view):
    """A login-view bind failure must not kill the stdio server; uvicorn raises SystemExit on it."""
    try:
        await view.serve()
    except asyncio.CancelledError:
        raise
    except BaseException as exc:
        print(f"Login view unavailable: {exc}", file=sys.stderr)
