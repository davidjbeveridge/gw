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
def gw_status(self) -> dict:
    """Inspect this project's GW configuration, pinned task and plugin availability."""
    from ..ports import Store
    with_store = Store(self.home)
    try:
        sessions = with_store.recent_sessions(str(self.project), 20)
        task = with_store.task(str(self.project))
    finally:
        with_store.close()
    packages = {}
    for name in ("gw-supervisor", "gw-builtin", "gw-context", "gw-knowledge", "gw-observe", "gw-learning", "gw-sync"):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = None
    return {"project": str(self.project), "client": self.client, "management_enabled": self.manage,
            "task": task, "sessions": [dict(r) for r in sessions], "configuration": redact(self.configuration()),
            "packages": packages, "setup": "Use configure_plan/apply for requested changes; credentials are references, never raw keys."}


def gw_setup_options(self) -> dict:
    """Read supported setup presets, decision strategies and context options. Makes no provider calls."""
    from gw_supervisor.api import optional_service
    inference = optional_service('inference')
    manifest = inference.setup_options if inference else lambda: {'available': False}
    context_service = optional_service('context')
    DEFAULT_CONTEXT = context_service.defaults() if context_service else {}
    try:
        from gw_context import installed_sources
        sources = installed_sources()
    except ModuleNotFoundError as exc:
        if exc.name != "gw_context":
            raise
        sources = []
    return {"runtime": plugin_inventory(self.home, self.client), "context_source_providers": sources, "decision": manifest(), "strategies": {
        "single": "One configured typed decision endpoint",
        "cascade": "One primary plus at most one configured fallback for exact uncertainty labels; errors opt-in",
        "managed": "One compatible endpoint that owns its own adaptive reasoning/model switching"},
        "fallback_shape": {"backend": {"provider": "openai", "endpoint": "https://YOUR_HOST/v1/chat/completions",
            "model": "YOUR_MODEL", "key_env": "GW_REASONING_API_KEY", "timeout_seconds": 5},
            "on_labels": {"*": ["uncertain", "unknown"]}, "on_error": False},
        "context_compiler": DEFAULT_CONTEXT,
        "credentials": "Reference names/paths only. Provision actual keys outside model context."}


def gw_configure_plan(self, patch: dict, scope: Literal["global", "client"] = "client") -> dict:
    """Prepare a reviewable configuration diff. Does not apply changes or call providers."""
    self.require_management()
    if not isinstance(patch, dict) or not patch or len(canonical(patch)) > 64000:
        raise ValueError("Unsupported configuration patch")
    if redact(patch) != patch:
        raise ValueError("Do not submit literal credentials; use environment-variable or private-file references")
    if scope not in {"global", "client"}:
        raise ValueError("Unknown configuration scope")
    old = read_json(self.home / "config.json", {"version": 1})
    overlay = patch if scope == "global" or self.client == "generic" else {"clients": {self.client: patch}}
    candidate = merge(old, overlay)
    from gw_supervisor.api import configuration
    configuration().validate_agent_patch(patch, candidate, self.client)
    for client in {self.client, "generic", *candidate.get("clients", {})}:
        configuration().validate_document(candidate, client)
    key = uuid.uuid4().hex
    plan = {"id": key, "project": str(self.project), "client": self.client, "scope": scope,
            "before_hash": digest(old), "after_hash": digest(candidate), "patch": patch,
            "candidate": candidate, "created_at": time.time(), "expires_at": time.time() + 1800,
            "status": "proposed"}
    write_json(self.home / "agent-plans" / (key + ".json"), plan)
    return {k: v for k, v in plan.items() if k != "candidate"} | {
        "network_check": "not performed", "applies_to": "new sessions; existing session policy stays pinned",
        "review": "Explain changes, data destinations and possible inference costs to the user before applying."}


def gw_configure_apply(self, plan_id: str) -> dict:
    """Apply a requested, reviewed setup plan with revision checks and backup. Requires managed tools."""
    self.require_management()
    if not isinstance(plan_id, str) or len(plan_id) != 32 or any(c not in "0123456789abcdef" for c in plan_id):
        raise ValueError("Invalid plan ID")
    path = self.home / "agent-plans" / (plan_id + ".json")
    plan = read_json(path)
    if not plan or plan["project"] != str(self.project) or plan["client"] != self.client:
        raise ValueError("Unknown plan for this agent workspace")
    if plan["expires_at"] < time.time():
        raise ValueError("Setup plan expired; prepare a fresh plan")
    lock = self.home / "agent-config.lock"
    fd = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        old = read_json(self.home / "config.json", {"version": 1})
        if digest(old) == plan["after_hash"]:
            return {"applied": True, "already_applied": True, "plan_id": plan_id}
        if digest(old) != plan["before_hash"] or digest(plan["candidate"]) != plan["after_hash"]:
            raise ValueError("Configuration changed after review; prepare another plan")
        candidate = plan["candidate"]
        from gw_supervisor.api import configuration
        configuration().validate_agent_patch(plan['patch'], candidate, self.client)
        for client in {self.client, "generic", *candidate.get("clients", {})}:
            configuration().validate_document(candidate, client)
        write_json(self.home / "backups" / ("agent-" + plan_id + ".json"), old)
        write_json(self.home / "config.json", candidate)
        plan["status"] = "applied"
        write_json(path, plan)
    finally:
        os.close(fd)
        lock.unlink()
    return {"applied": True, "plan_id": plan_id, "configuration_hash": plan["after_hash"],
            "next": "Start a fresh agent session for changed supervision policy. No provider call or permission grant was made."}


def gw_task_set(self, task: str) -> dict:
    """Pin the user-requested task for new sessions in this project. Never grants permissions."""
    self.require_management()
    from ..ports import Store
    store = Store(self.home)
    try:
        store.set_task(str(self.project), task)
    finally:
        store.close()
    return {"task_pinned": True, "applies_to": "new sessions"}




def gw_runtime_inspect(self) -> dict:
    """Inspect selected plugins, provider versions, registered tools and execution phases."""
    return plugin_inventory(self.home, self.client)
