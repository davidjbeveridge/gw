"""Agent-facing operations shared by MCP and the deterministic CLI interface.

The process is bound to one project/client. Management is an explicit launch-time
capability; native tool approvals and immutable config locks still apply.
"""
from __future__ import annotations

import copy


def gw_context_compile(self, task: str = "", query: str = "", active_skills: list[str] | None = None, diagnostics: bool = False) -> dict:
    """Compile source-backed context, returning content once. diagnostics adds full omission details.

    The SDK budget bounds payload characters, not transport framing. Diagnostic
    requests compile current sources again; they are not historical packet reads.
    """
    if type(diagnostics) is not bool:
        raise ValueError("diagnostics must be boolean")
    from ..ports import compile_context
    config = copy.deepcopy(self.configuration())
    # The explicit tool invocation enables this one compile, not automatic
    # injection or a persisted setting. Baseline still prevents enrichment.
    config["context_compiler"]["enabled"] = True
    packet = compile_context(self.home, self.project, self.client, task=task or None, query=query,
                           active_skills=active_skills, config=config)

    # The SDK/proxy still supports both representations. Do not send both to a
    # model or imply that duplicating serialization provides extra evidence.
    result = {key: value for key, value in packet.items() if key != "text"}
    if not diagnostics:
        result["omitted_count"] = len(result.pop("omitted", []))
    result["representation"] = "structured_once"
    return result
