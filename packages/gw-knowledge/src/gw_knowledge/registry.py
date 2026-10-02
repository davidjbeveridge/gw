"""Explicit installed-plugin loading, independent of GW's configuration system."""
from importlib.metadata import entry_points
from .contract import KnowledgeProvider, InvalidRequest, validate_capabilities


def open_provider(name: str, options: dict) -> KnowledgeProvider:
    if name == "local":
        from .local import from_options
        provider = from_options(options)
    elif name == "http":
        from .http import from_options
        provider = from_options(options)
    else:
        matches = list(entry_points(group="gw_knowledge.providers", name=name))
        if len(matches) != 1:
            raise InvalidRequest("Expected exactly one explicitly installed knowledge provider")
        provider = matches[0].load()(options)
    if not isinstance(provider, KnowledgeProvider):
        raise InvalidRequest("Provider does not implement the knowledge read contract")
    # Network discovery remains explicit, not an import-time or setup side effect.
    return provider
