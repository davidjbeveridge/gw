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
def gw_decision_check(self, stage: Literal["primary", "fallback"] = "primary") -> dict:
    """Send one synthetic contract check to the requested configured backend. May incur provider cost."""
    self.require_management()
    probe = service("inference").probe
    decision_config = service("inference").decision_config
    config = decision_config(self.configuration())
    if stage == "fallback":
        config = config.get("fallback", {}).get("backend")
        if not config:
            raise ValueError("No fallback configured")
    elif stage != "primary":
        raise ValueError("Unknown decision stage")
    return {"stage": stage, **probe(config)}


def gw_models_select(self, requirements: dict) -> dict:
    """Select a compatible worker plan. Configured classifier selection may incur inference; never launches the worker."""
    self.require_management()
    from gw_supervisor.api import runtime as Supervisor
    with Supervisor(self.home) as supervisor:
        return supervisor.evaluate({"type": "inference.select", "client": self.client,
                                    "project": str(self.project), "session": "agent-selection-" + uuid.uuid4().hex,
                                    "requirements": requirements})


