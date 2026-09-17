from __future__ import annotations

import base64
import json
import uuid
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool, ToolAnnotations
from pydantic import Field

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


BUILTINS = {
    "website_task": (
        WebsiteTask,
        "Run an explicit custom workflow on this website. Supply every needed input string in values. May modify data.",
    ),
    "browser_status": (
        Empty,
        "Observe the current browser page without a model call. Starts the isolated browser if needed.",
    ),
    "files_list": (
        Empty,
        "List uploaded and downloaded files in this server's private file store.",
    ),
    "files_put": (PutFile, "Upload a file for website attachment. Returns its isolated file name."),
    "files_read": (
        ReadFile,
        "Read a downloaded file as base64 in bounded chunks; returns next offset and EOF.",
    ),
}


def create_server(browser, policy=None):
    server = Server(f"jev-{browser.site.name}")
    runner = Runner(browser, policy or JevPolicy())
    specs = {spec.name: spec for spec in browser.site.tools}
    if len(specs) != len(browser.site.tools) or specs.keys() & BUILTINS.keys():
        raise ValueError("Tool names must be unique and cannot shadow framework tools")

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
                annotations=ToolAnnotations(readOnlyHint=name not in {"files_put", "website_task"}),
            )
            for name, (model, description) in BUILTINS.items()
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
            result = await runner.run(task)
        elif name in BUILTINS:
            args = BUILTINS[name][0].model_validate(arguments)
            if name == "website_task":
                for filename in args.uploads.values():
                    contained_file(browser.files, filename)
                result = await runner.run(
                    Task(args.goal, args.values, args.uploads, args.max_steps)
                )
                return [
                    TextContent(
                        type="text", text=json.dumps(result, ensure_ascii=False, default=str)
                    )
                ]
            async with browser.lock:
                if name == "browser_status":
                    await browser.start()
                    result = await browser.observe()
                else:
                    browser.files.mkdir(parents=True, exist_ok=True, mode=0o700)
                    if name == "files_list":
                        result = [
                            {"name": p.name, "size": p.stat().st_size}
                            for p in sorted(browser.files.iterdir())
                            if p.is_file() and not p.is_symlink()
                        ]
                    elif name == "files_put":
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


async def serve(browser):
    server, runner = create_server(browser)
    try:
        async with stdio_server() as (read, write):
            await server.run(read, write, server.create_initialization_options())
    finally:
        await runner.policy.close()
        await browser.close()
