import importlib

from ..spec import Site


def load_site(name: str) -> Site:
    """A module in jev_mcp.sites by short name, or any importable module exporting SITE."""
    module = f"jev_mcp.sites.{name}" if "." not in name else name
    try:
        site = importlib.import_module(module).SITE
    except ModuleNotFoundError:
        if "." in name:
            raise
        site = importlib.import_module(name).SITE
    if not isinstance(site, Site):
        raise TypeError(f"{module}.SITE must be a Site")
    return site
