import importlib

from ..spec import Site


def load_site(name: str) -> Site:
    """Built-in name, or an installed Python module exporting a Site as SITE."""
    module = f"jev_mcp.sites.{name}" if name in {"outlook", "morning"} else name
    site = importlib.import_module(module).SITE
    if not isinstance(site, Site):
        raise TypeError(f"{module}.SITE must be a Site")
    return site
