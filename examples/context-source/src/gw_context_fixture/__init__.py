"""An installable external source fixture. No GW, knowledge store or network."""
from gw_context import ContextItem, ContextRequest, SourceResult


class FixtureSource:
    def __init__(self, options):
        self.text = options.get("text", "Use the vendor fixture to check login validation.")
        self.revision = options.get("revision", "fixture-v1")

    def collect(self, request: ContextRequest) -> SourceResult:
        return SourceResult((ContextItem(
            id="document", kind="knowledge", content=self.text,
            source="vendor:document", revision=self.revision,
        ),), scope=request.scope, revision=self.revision)


def from_options(options):
    return FixtureSource(options)
