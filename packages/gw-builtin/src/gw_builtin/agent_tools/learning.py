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
def gw_learning_query(self, proposal_id: str = "") -> dict:
    """Inspect learning proposals through the configured learning service."""
    return service('learning').query(self.home, self.configuration(), proposal_id)


