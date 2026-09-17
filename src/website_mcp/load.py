"""Load a Site from a Python file path or an importable module; the framework ships no sites."""

from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path

from .spec import Site


def load_site(target: str) -> Site:
    if target.endswith(".py"):
        path = Path(target).resolve()
        spec = importlib.util.spec_from_file_location(path.stem, path)
        if spec is None or spec.loader is None:
            raise FileNotFoundError(target)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    else:
        module = importlib.import_module(target)
    site = getattr(module, "SITE", None)
    if not isinstance(site, Site):
        raise TypeError(f"{target} must export SITE: Site")
    return site
