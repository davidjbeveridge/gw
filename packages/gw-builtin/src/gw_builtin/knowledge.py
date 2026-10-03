"""Thin optional GW bridge. All storage, retrieval and caching live in gw-knowledge.

Connection settings/principals are global-only, never read from a project file
or an agent request. No automatic transcript ingestion or prompt injection.
"""
from __future__ import annotations

import argparse
import contextlib
import pathlib
from gw_supervisor.api import canonical, digest, read_json, write_json

DEFAULT_KNOWLEDGE = {"enabled": False, "provider": "local", "options": {}, "tenant": "local",
                     "principal": "owner", "collections": {}, "allow_writes": False,
                     "cache": {"ttl_seconds": 300, "max_entries": 256, "max_bytes": 16777216,
                               "allow_unversioned": False}}


def validate_knowledge(config):
    if not isinstance(config, dict) or set(config) - set(DEFAULT_KNOWLEDGE):
        raise ValueError("Invalid knowledge configuration")
    for key in ("enabled", "allow_writes"):
        if type(config.get(key)) is not bool:
            raise ValueError(f"knowledge.{key} must be boolean")
    for key in ("provider", "tenant", "principal"):
        if not isinstance(config.get(key), str) or not config[key].strip() or config[key] == "*":
            raise ValueError(f"Invalid knowledge.{key}")
    if not isinstance(config.get("options"), dict) or not isinstance(config.get("collections"), dict):
        raise ValueError("Knowledge options and collections must be objects")
    if any(not isinstance(k, str) or not isinstance(v, str) or not v.strip() or v == "*" for k, v in config["collections"].items()):
        raise ValueError("Knowledge collections map canonical project paths to names")
    cache = config.get("cache", {})
    if not isinstance(cache, dict) or set(cache) - set(DEFAULT_KNOWLEDGE["cache"]):
        raise ValueError("Unknown knowledge cache setting")
    for key, low, high in (("ttl_seconds", 1, 86400), ("max_entries", 1, 100000), ("max_bytes", 1024, 1073741824)):
        if type(cache.get(key)) is not int or not low <= cache[key] <= high:
            raise ValueError(f"Invalid knowledge.cache.{key}")
    if type(cache.get("allow_unversioned")) is not bool:
        raise ValueError("knowledge.cache.allow_unversioned must be boolean")


def require_package():
    try:
        import gw_knowledge
        return gw_knowledge
    except ImportError as exc:
        raise ValueError("Knowledge is optional. Re-run the gw installer with --knowledge, or install the standalone gw-knowledge package into the same Python environment.") from exc


@contextlib.contextmanager
def open_service(home, project, client):
    require_package()
    from gw_knowledge import ContextCache, Scope
    from gw_knowledge.registry import open_provider
    from gw_knowledge.service import KnowledgeService
    from .host import project_root, resolve
    project = project_root(project)
    config, _ = resolve(home, project, client)
    c = config["knowledge"]
    if not c["enabled"]:
        raise ValueError("Knowledge is disabled; run gw knowledge init")
    options = dict(c["options"])
    if c["provider"] == "local":
        options.setdefault("directory", str(home / "knowledge" / "sources"))
    scope = Scope(c["tenant"], c["collections"].get(str(project), "project-" + digest(str(project))), c["principal"])
    provider = open_provider(c["provider"], options)
    with contextlib.ExitStack() as stack:
        if hasattr(provider, "close"):
            stack.callback(provider.close)
        cache = stack.enter_context(ContextCache(home / "knowledge" / "cache", **c["cache"]))
        from .ports import enabled, publish_component
        if enabled(config):
            try:
                from gw_observe.knowledge import ObservedKnowledgeProvider, ObservedContextCache
                import os,uuid
                identity={"client":client,"project":str(project),"session":os.environ.get("GW_SESSION") or "knowledge-"+uuid.uuid4().hex,
                          "run_id":os.environ.get("GW_RUN_ID")}
                def emit(kind,attrs,start,end):
                    publish_component(home,config,identity,kind,attrs,start_ns=start,end_ns=end)
                provider=ObservedKnowledgeProvider(provider,emit)
                cache=ObservedContextCache(cache,emit)
            except ImportError:
                import warnings
                warnings.warn("Knowledge tracing unavailable: optional gw-observe package is not installed",RuntimeWarning)
        yield KnowledgeService(provider, cache, scope=scope, writable=c["allow_writes"])


def call(home, context, method, request):
    """GW API bridge fixes the scope; arbitrary request scopes are refused."""
    from .host import project_root
    if not isinstance(context, dict) or set(context) - {"project", "client"} or not isinstance(context.get("project"), str):
        raise ValueError("Knowledge context needs a project and optional client")
    if not isinstance(request, dict) or "scope" in request:
        raise ValueError("Knowledge request scope is assigned by the GW host")
    client = context.get("client", "generic")
    if not isinstance(client, str) or not client:
        raise ValueError("Invalid knowledge client")
    with open_service(home, context["project"], client) as service:
        body = dict(request)
        if method != "capabilities":
            body["scope"] = service.scope.to_dict()
        result = service.dispatch(method, body)
    return {"protocol": "gw.knowledge/1", "result": result}


def add_arguments(sub):
    parser = sub.add_parser("knowledge", help="Optional standalone knowledge layer; run 'gw knowledge help' for commands")
    parser.add_argument("--project", default=".")
    parser.add_argument("--client", default="generic")
    parser.add_argument("arguments", nargs=argparse.REMAINDER)


def run(args, home, output):
    require_package()
    from gw_knowledge.cli import add_operations, run_operation, emit_json
    from gw_knowledge.contract import KnowledgeError, loads
    from .host import DEFAULTS, merge, project_root, validate
    parser = argparse.ArgumentParser(prog="gw knowledge", description="Set --project/--client before the operation. No automatic context injection.")
    sub = parser.add_subparsers(dest="operation", required=True)
    init = sub.add_parser("init", help="Explicitly enable and configure knowledge; no remote requests")
    init.add_argument("--provider", default="local")
    init.add_argument("--options", help="File containing provider options; credential references, not keys")
    init.add_argument("--collection", help="Stable collection name for this project (otherwise isolated path hash)")
    init.add_argument("--read-only", action="store_true")
    init.add_argument("--allow-writes", action="store_true", help="Explicitly enable writes for a remote provider")
    add_operations(sub)
    parsed = parser.parse_args(["--help"] if args.arguments == ["help"] else args.arguments)
    project = project_root(args.project)
    try:
        if parsed.operation == "init":
            if args.client != "generic":
                raise ValueError("knowledge init configures the global backend; configure client overrides explicitly in global config")
            path = home / "config.json"
            existing = read_json(path, {"version": 1})
            options = loads(pathlib.Path(parsed.options).read_text(encoding="utf-8")) if parsed.options else {}
            if parsed.provider != "local" and not parsed.options:
                raise ValueError("Remote/plugin providers require an explicit --options file")
            if parsed.read_only and parsed.allow_writes:
                raise ValueError("Choose --read-only or --allow-writes")
            # Treat init as global administration; respect existing client locks.
            c = merge(DEFAULT_KNOWLEDGE, existing.get("knowledge", {}))
            c.update(enabled=True, provider=parsed.provider, options=options,
                     allow_writes=not parsed.read_only and (parsed.provider == "local" or parsed.allow_writes))
            if parsed.collection:
                c["collections"][str(project)] = parsed.collection
            candidate = merge(existing, {"knowledge": c})
            for client in {"generic", *candidate.get("clients", {})}:
                resolved = merge(DEFAULTS, {k: v for k, v in candidate.items() if k != "clients"})
                validate(merge(resolved, candidate.get("clients", {}).get(client, {})))
            if path.exists():
                write_json(home / "backups" / ("knowledge-" + digest(existing) + ".json"), existing)
            write_json(path, candidate)
            output({"enabled": True, "provider": c["provider"], "network_verified": False,
                    "automatic_ingestion": False, "automatic_injection": False,
                    "next": "gw knowledge ingest FILE --id ID; gw knowledge context QUERY"})
            return
        with open_service(home, project, args.client) as service:
            if parsed.operation in {"mcp", "serve"}:
                # A CLI switch can narrow host policy but cannot grant new access.
                service.writable = service.writable and parsed.writable
            run_operation(parsed, service, emit_json)
    except KnowledgeError as exc:
        raise ValueError("Knowledge operation failed: " + exc.code) from None


def validate_agent_patch(patch, config):
    if not isinstance(patch, dict) or patch.get('provider', 'local') not in {'local', 'http'}:
        raise ValueError('Agent knowledge setup supports local/HTTP providers; configure other adapters as operator')
