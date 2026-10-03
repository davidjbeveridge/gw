"""Agent-facing operations shared by MCP and the deterministic CLI interface.

The process is bound to one project/client. Management is an explicit launch-time
capability; native tool approvals and immutable config locks still apply.
"""
from __future__ import annotations

import copy
import importlib.metadata
import os
import pathlib
import time
import uuid
from typing import Literal
from ..host import home_path, initialize, merge, project_root, resolve, validate
from .. import host as config_host
from gw_supervisor.api import canonical, digest, read_json, redact, write_json


from gw_supervisor.api import service, plugin_inventory
def gw_context_compile(self, task: str = "", query: str = "", active_skills: list[str] | None = None) -> dict:
    """Compile bounded project/knowledge context for this task. Active skill files are retained whole."""
    from ..ports import compile_context
    config = copy.deepcopy(self.configuration())
    # The explicit tool invocation enables this one compile, not automatic
    # injection or a persisted setting. Baseline still prevents enrichment.
    config["context_compiler"]["enabled"] = True
    return compile_context(self.home, self.project, self.client, task=task or None, query=query,
                           active_skills=active_skills, config=config)


