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
def gw_knowledge(self, operation: Literal["search", "read", "store"], request: dict) -> dict:
    """Access the configured project knowledge. Request contains query or source fields, never scope/principal."""
    from ..ports import open_service
    if not isinstance(request, dict) or "scope" in request:
        raise ValueError("Knowledge scope is assigned by this process")
    if operation == "store":
        self.require_management()
    if operation not in {"search", "read", "store"}:
        raise ValueError("Unknown knowledge operation")
    with open_service(self.home, self.project, self.client) as service:
        return service.dispatch("put" if operation == "store" else operation,
                                {**request, "scope": service.scope.to_dict()})


