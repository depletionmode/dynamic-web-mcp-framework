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

    def permits(self, url: str) -> bool:
        parsed = urlparse(url)
        host = parsed.hostname or ""
        return parsed.scheme in {"https", "http"} and any(
            host == domain or host.endswith("." + domain) for domain in self.domains
        )


def contained_file(root: Path, name: str) -> Path:
    path = (root / name).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError("File must exist inside this server's file directory")
    return path
