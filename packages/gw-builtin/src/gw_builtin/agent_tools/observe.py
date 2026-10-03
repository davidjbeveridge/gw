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
def gw_trace_query(self, operation: Literal["runs", "show", "timeline", "event", "compare"] = "show",
                   run_id: str = "latest", event_id: str = "", compare_ids: list[str] | None = None,
                   offset: int = 0) -> dict:
    """Read project traces, per-goal decisions, original evidence or a descriptive comparison."""
    with service('observation').repository(self.home, self.configuration()) as repo:
        if operation == "runs":
            return {"runs": [r for r in repo.runs(200) if r["project"] == str(self.project)]}
        if operation == "compare":
            return repo.compare([_run_id(self, repo, r) for r in (compare_ids or [])])
        if operation == "event":
            event = repo.event(event_id, resolve_source=False)
            _run_id(self, repo, event["run_id"])
            return repo.event(event_id)
        rid = _run_id(self, repo, run_id)
        if operation == "show":
            return repo.report(rid)
        if operation == "timeline":
            return repo.timeline(rid, offset=offset, limit=100)
        raise ValueError("Unknown trace query")


def gw_trace_start(self, name: str, model: str = "", harness_version: str = "", prompt_file: str = "") -> dict:
    """Start and bind a run to new sessions of this project/client. No model is launched."""
    self.require_management()
    with service('observation').repository(self.home, self.configuration()) as repo:
        config = self.configuration()
        return repo.start(name, str(self.project), harness=self.client, model=model or None,
                          harness_version=harness_version or None, config=config, mode=config["mode"],
                          prompt_file=_file(self, prompt_file) if prompt_file else None, bind=True,
                          client=None if self.client == "generic" else self.client)


def gw_trace_finish(self, run_id: str, outcome: Literal["succeeded", "failed", "partial", "cancelled", "unknown"], evidence: str) -> dict:
    """Record the requested run outcome and evidence. This is an assertion, not automatic verification."""
    self.require_management()
    with service('observation').repository(self.home, self.configuration()) as repo:
        return repo.finish(_run_id(self, repo, run_id), outcome, evidence)


def gw_dashboard_open(self) -> dict:
    """Open the local dashboard. Starts only GW's own loopback service; never exposes its token to the model."""
    self.require_management()
    open_dashboard = service("observation").dashboard
    return open_dashboard(self.home, self.project, self.client, self.configuration())




def _run_id(host, repo, run_id):
    if run_id == 'latest':
        rows = [r for r in repo.runs(1000) if r['project'] == str(host.project)]
        if not rows: raise ValueError('No recorded run for this project')
        run_id = rows[0]['id']
    if repo.run(run_id)['project'] != str(host.project):
        raise ValueError('Run is outside the bound project')
    return run_id


def _file(host, relative):
    path = pathlib.PurePosixPath(relative)
    if path.is_absolute() or '..' in path.parts or '\\' in relative or ':' in relative:
        raise ValueError('File must stay in the bound project')
    candidate = host.project.joinpath(*path.parts)
    if candidate.is_symlink() or not candidate.resolve().is_relative_to(host.project):
        raise ValueError('File must stay in the bound project')
    return candidate
