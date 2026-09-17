from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict


class Arguments(BaseModel):
    model_config = ConfigDict(extra="forbid")


@dataclass(frozen=True)
class Task:
    goal: str
    values: dict[str, str] = field(default_factory=dict)
    uploads: dict[str, str] = field(default_factory=dict)
    max_steps: int = 60
    # A site-specific deterministic verifier may inspect the browser and result.
    verifier: Callable | None = None


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    arguments: type[BaseModel]
    task: Callable[[Any], Task]
    read_only: bool = False


@dataclass(frozen=True)
class Site:
    name: str
    start_url: str
    domains: tuple[str, ...]
    tools: tuple[ToolSpec, ...]
    guidance: str = ""
    # Hosts that mean there is no authenticated session (login pages, logged-out landing pages).
    login_domains: tuple[str, ...] = ()
    # Opt-in capabilities, exposed as <name>_* tools. A site's MCP surface is its own
    # functionality only; the browser and file store are inner workings.
    attachments: bool = False  # <name>_put_file / <name>_read_file / <name>_list_files
    custom_task: bool = False  # <name>_task: any workflow on this site described in words

    def permits(self, url: str) -> bool:
        parsed = urlparse(url)
        return parsed.scheme in {"https", "http"} and _host_in(parsed.hostname, self.domains)

    def is_login_url(self, url: str) -> bool:
        return _host_in(urlparse(url).hostname, self.login_domains)


def _host_in(host, domains):
    host = host or ""
    return any(host == domain or host.endswith("." + domain) for domain in domains)


def contained_file(root: Path, name: str) -> Path:
    path = (root / name).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError("File must exist inside this server's file directory")
    return path
