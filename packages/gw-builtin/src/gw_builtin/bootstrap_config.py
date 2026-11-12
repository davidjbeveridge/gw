"""Operator choices for a new native harness and additive bootstrap opt-ins."""
from __future__ import annotations

from gw_supervisor.api import configuration, read_json


NATIVE_PLUGINS = ("gw.state", "gw.policy", "gw.inference", "gw.governance", "gw.harness")
OPTIONAL_PLUGINS = ("gw.observe", "gw.learning", "gw.sync")


def plan(home, args, clients):
    requested = set()
    if args.context or args.knowledge or args.agent_tools:
        requested.add("gw.context")
    if args.knowledge:
        requested.add("gw.knowledge")
    if args.agent_tools:
        requested.add("gw.agent")
    if args.plugins:
        requested.update(OPTIONAL_PLUGINS)

    config = configuration()
    path = home / "config.json"
    previous = read_json(path, {})
    if not isinstance(previous, dict):
        raise ValueError("Global config must be an object")
    if not path.exists() and not any((home / name).exists() for name in ("state.sqlite3", "projects")):
        # Keep the existing reference rubrics available for deliberate opt-in.
        # Only the exact retry rule is active in a fresh native policy.
        from .defaults import REFERENCE_DEFAULTS
        candidate = {
            "version": 1,
            "runtime": {"profile": "minimal", "enable": sorted(set(NATIVE_PLUGINS) | requested)},
            "goals": {goal: {"enabled": False} for goal in REFERENCE_DEFAULTS["goals"] if goal != "retry_limit"},
        }
    elif not requested:
        return previous, previous
    elif previous.get("runtime", {}).get("profile") == "minimal":
        enabled = set(previous["runtime"].get("enable", [])) | requested
        candidate = config.merge(previous, {"runtime": {"enable": sorted(enabled)}})
    else:
        candidate = previous

    for client in {"generic", *clients, *candidate.get("clients", {})}:
        effective = config.validate_document(candidate, client)
        runtime = effective["runtime"]
        available = requested if runtime["profile"] == "standard" else set(runtime["enable"])
        missing = requested - (available - set(runtime["disable"]))
        if missing:
            raise ValueError(f"Requested plugins are not selected for {client}: " + ", ".join(sorted(missing)))
    return previous, candidate
