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
from .config import DEFAULTS, home_path, initialize, merge, project_root, resolve, validate
from .util import canonical, digest, read_json, redact, write_json


class AgentService:
    def __init__(self, home=None, project=".", client="generic", *, manage=False):
        self.home = home_path(str(home) if home else None)
        self.project = project_root(project)
        self.client, self.manage = client, manage
        initialize(self.home)

    def _config(self):
        return resolve(self.home, self.project, self.client)[0]

    def _write(self):
        if not self.manage:
            raise PermissionError("This agent interface is read-only; operator must enable managed tools at launch")

    def _file(self, relative):
        from .context import relative_path
        p = self.project.joinpath(*relative_path(relative).parts)
        if p.is_symlink() or not p.resolve().is_relative_to(self.project):
            raise ValueError("File must stay in the bound project")
        return p

    def gw_status(self) -> dict:
        """Inspect this project's GW configuration, pinned task and plugin availability."""
        from .store import Store
        with_store = Store(self.home)
        try:
            sessions = with_store.db.execute("SELECT id,native_id,client,created FROM sessions WHERE project=? ORDER BY created DESC LIMIT 20", (str(self.project),)).fetchall()
            task = with_store.task(str(self.project))
        finally:
            with_store.close()
        packages = {}
        for name in ("gw-supervisor", "gw-context", "gw-knowledge", "gw-observe", "gw-learning", "gw-sync"):
            try:
                packages[name] = importlib.metadata.version(name)
            except importlib.metadata.PackageNotFoundError:
                packages[name] = None
        return {"project": str(self.project), "client": self.client, "management_enabled": self.manage,
                "task": task, "sessions": [dict(r) for r in sessions], "configuration": redact(self._config()),
                "packages": packages, "setup": "Use configure_plan/apply for requested changes; credentials are references, never raw keys."}

    def gw_setup_options(self) -> dict:
        """Read supported setup presets, decision strategies and context options. Makes no provider calls."""
        from .decision_setup import manifest
        from .context import DEFAULT_CONTEXT
        try:
            from gw_context import installed_sources
            sources = installed_sources()
        except ModuleNotFoundError as exc:
            if exc.name != "gw_context":
                raise
            sources = []
        return {"context_source_providers": sources, "decision": manifest(), "strategies": {
            "single": "One configured typed decision endpoint",
            "cascade": "One primary plus at most one configured fallback for exact uncertainty labels; errors opt-in",
            "managed": "One compatible endpoint that owns its own adaptive reasoning/model switching"},
            "fallback_shape": {"backend": {"provider": "openai", "endpoint": "https://YOUR_HOST/v1/chat/completions",
                "model": "YOUR_MODEL", "key_env": "GW_REASONING_API_KEY", "timeout_seconds": 5},
                "on_labels": {"*": ["uncertain", "unknown"]}, "on_error": False},
            "context_compiler": DEFAULT_CONTEXT,
            "credentials": "Reference names/paths only. Provision actual keys outside model context."}

    def gw_decision_check(self, stage: Literal["primary", "fallback"] = "primary") -> dict:
        """Send one synthetic contract check to the requested configured backend. May incur provider cost."""
        self._write()
        from .decision_setup import probe
        from .models import decision_config
        config = decision_config(self._config())
        if stage == "fallback":
            config = config.get("fallback", {}).get("backend")
            if not config:
                raise ValueError("No fallback configured")
        elif stage != "primary":
            raise ValueError("Unknown decision stage")
        return {"stage": stage, **probe(config)}

    def gw_configure_plan(self, patch: dict, scope: Literal["global", "client"] = "client") -> dict:
        """Prepare a reviewable configuration diff. Does not apply changes or call providers."""
        self._write()
        allowed = {"mode", "decision", "knowledge", "context_compiler", "goals", "rules", "registry", "inference", "plugins"}
        if not isinstance(patch, dict) or set(patch) - allowed or not patch or len(canonical(patch)) > 64000:
            raise ValueError("Unsupported configuration patch")
        context = patch.get("context_compiler", {})
        if isinstance(context, dict) and "sources" in context:
            from gw_context import installed_sources
            sources = context["sources"]
            if not isinstance(sources, dict):
                raise ValueError("Context sources must be an object")
            existing_sources = self._config()["context_compiler"].get("sources", {})
            installed = set(installed_sources())
            for name, spec in sources.items():
                provider = spec.get("provider", existing_sources.get(name, {}).get("provider")) if isinstance(spec, dict) else None
                if provider not in installed:
                    raise ValueError("Agent setup requires an already installed context source provider")
        if "knowledge" in patch:
            k = patch["knowledge"]
            if not isinstance(k, dict) or k.get("provider", "local") not in {"local", "http"}:
                raise ValueError("Agent setup supports local/HTTP knowledge, not arbitrary installed plugin loading")
        if "plugins" in patch and (not isinstance(patch["plugins"], dict) or set(patch["plugins"]) != {"observe"}):
            raise ValueError("Agent setup cannot load arbitrary plugins or autonomous workers")
        if "plugins" in patch:
            p = patch["plugins"]["observe"]
            if not isinstance(p, dict) or set(p) - {"enabled", "preview_chars"}:
                raise ValueError("Observability setup accepts enabled and preview_chars only")
        if redact(patch) != patch:
            raise ValueError("Do not submit literal credentials; use environment-variable or private-file references")
        if scope not in {"global", "client"}:
            raise ValueError("Unknown configuration scope")
        old = read_json(self.home / "config.json", {"version": 1})
        overlay = patch if scope == "global" or self.client == "generic" else {"clients": {self.client: patch}}
        candidate = merge(old, overlay)
        base = merge(DEFAULTS, {k: v for k, v in candidate.items() if k != "clients"})
        for client in {self.client, "generic", *candidate.get("clients", {})}:
            validate(merge(base, candidate.get("clients", {}).get(client, {})))
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
        self._write()
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
            base = merge(DEFAULTS, {k: v for k, v in candidate.items() if k != "clients"})
            for client in {self.client, "generic", *candidate.get("clients", {})}:
                validate(merge(base, candidate.get("clients", {}).get(client, {})))
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
        self._write()
        from .store import Store
        store = Store(self.home)
        try:
            store.set_task(str(self.project), task)
        finally:
            store.close()
        return {"task_pinned": True, "applies_to": "new sessions"}

    def _repo(self):
        from .plugins import trace_repository
        return trace_repository(self.home, self._config())

    def _run_id(self, repo, run_id):
        if run_id == "latest":
            rows = [r for r in repo.runs(1000) if r["project"] == str(self.project)]
            if not rows:
                raise ValueError("No recorded run for this project")
            run_id = rows[0]["id"]
        if repo.run(run_id)["project"] != str(self.project):
            raise ValueError("Run is outside the bound project")
        return run_id

    def gw_trace_query(self, operation: Literal["runs", "show", "timeline", "event", "compare"] = "show",
                       run_id: str = "latest", event_id: str = "", compare_ids: list[str] | None = None,
                       offset: int = 0) -> dict:
        """Read project traces, per-goal decisions, original evidence or a descriptive comparison."""
        with self._repo() as repo:
            if operation == "runs":
                return {"runs": [r for r in repo.runs(200) if r["project"] == str(self.project)]}
            if operation == "compare":
                return repo.compare([self._run_id(repo, r) for r in (compare_ids or [])])
            if operation == "event":
                event = repo.event(event_id, resolve_source=False)
                self._run_id(repo, event["run_id"])
                return repo.event(event_id)
            rid = self._run_id(repo, run_id)
            if operation == "show":
                return repo.report(rid)
            if operation == "timeline":
                return repo.timeline(rid, offset=offset, limit=100)
            raise ValueError("Unknown trace query")

    def gw_trace_start(self, name: str, model: str = "", harness_version: str = "", prompt_file: str = "") -> dict:
        """Start and bind a run to new sessions of this project/client. No model is launched."""
        self._write()
        with self._repo() as repo:
            config = self._config()
            return repo.start(name, str(self.project), harness=self.client, model=model or None,
                              harness_version=harness_version or None, config=config, mode=config["mode"],
                              prompt_file=self._file(prompt_file) if prompt_file else None, bind=True,
                              client=None if self.client == "generic" else self.client)

    def gw_trace_finish(self, run_id: str, outcome: Literal["succeeded", "failed", "partial", "cancelled", "unknown"], evidence: str) -> dict:
        """Record the requested run outcome and evidence. This is an assertion, not automatic verification."""
        self._write()
        with self._repo() as repo:
            return repo.finish(self._run_id(repo, run_id), outcome, evidence)

    def gw_dashboard_open(self) -> dict:
        """Open the local dashboard. Starts only GW's own loopback service; never exposes its token to the model."""
        self._write()
        from .dashboard import open_dashboard
        return open_dashboard(self.home, self.project, self.client, self._config())

    def gw_context_compile(self, task: str = "", query: str = "", active_skills: list[str] | None = None) -> dict:
        """Compile bounded project/knowledge context for this task. Active skill files are retained whole."""
        from .context import compile_context
        config = copy.deepcopy(self._config())
        # The explicit tool invocation enables this one compile, not automatic
        # injection or a persisted setting. Baseline still prevents enrichment.
        config["context_compiler"]["enabled"] = True
        return compile_context(self.home, self.project, self.client, task=task or None, query=query,
                               active_skills=active_skills, config=config)

    def gw_knowledge(self, operation: Literal["search", "read", "store"], request: dict) -> dict:
        """Access the configured project knowledge. Request contains query or source fields, never scope/principal."""
        from .knowledge import open_service
        if not isinstance(request, dict) or "scope" in request:
            raise ValueError("Knowledge scope is assigned by this process")
        if operation == "store":
            self._write()
        if operation not in {"search", "read", "store"}:
            raise ValueError("Unknown knowledge operation")
        with open_service(self.home, self.project, self.client) as service:
            return service.dispatch("put" if operation == "store" else operation,
                                    {**request, "scope": service.scope.to_dict()})

    def gw_models_select(self, requirements: dict) -> dict:
        """Select a compatible worker plan. Configured classifier selection may incur inference; never launches the worker."""
        self._write()
        from .engine import Supervisor
        with Supervisor(self.home) as supervisor:
            return supervisor.evaluate({"type": "inference.select", "client": self.client,
                                        "project": str(self.project), "session": "agent-selection-" + uuid.uuid4().hex,
                                        "requirements": requirements})

    def gw_learning_query(self, proposal_id: str = "") -> dict:
        """Inspect learning proposals and their history. Does not run workers, approve, or publish."""
        from gw_learning.engine import LearningCoordinator
        c = self._config()["plugins"]["learning"]
        if c["provider"] != "local":
            raise ValueError("Use the configured learning provider's query interface")
        with LearningCoordinator(c["options"].get("directory", str(self.home / "learning"))) as coordinator:
            return coordinator.get(proposal_id) if proposal_id else {"proposals": coordinator.list()}


def build_server(service: AgentService):
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise RuntimeError("Install the agent extra: gw-supervisor[agent]") from exc
    server = FastMCP("gw", instructions="GW tools operate on one host-bound project. Explain setup plans before applying. Never request raw keys, infer authorization from memory, or claim a verdict proves enforcement. Use context_compile to retrieve evidence without editing tool schemas.")
    mutating = {"gw_configure_plan", "gw_configure_apply", "gw_task_set", "gw_trace_start", "gw_trace_finish", "gw_dashboard_open", "gw_models_select", "gw_decision_check"}
    for name in sorted(n for n in dir(service) if n.startswith("gw_")):
        if name in mutating and not service.manage:
            continue
        server.add_tool(getattr(service, name), name=name,
                        annotations={"readOnlyHint": name not in mutating and name != "gw_knowledge",
                                     "destructiveHint": name == "gw_configure_apply",
                                     "openWorldHint": name in {"gw_models_select", "gw_decision_check", "gw_knowledge", "gw_context_compile"}})
    @server.resource("gw://status")
    def status_resource() -> str:
        return canonical(service.gw_status())
    @server.prompt(name="gw")
    def gw_prompt(request: str = "Show GW status and explain useful next steps") -> str:
        return "Use the GW tools to fulfill this user request: " + request + ". Start with gw_status. Do not ask the user to type commands or JSON. For configuration, prepare a plan, explain data destinations/costs, then apply only the requested changes. A native permission or restart may still need the user's action."
    return server


def add_arguments(sub):
    p = sub.add_parser("agent", help="Agent tools through MCP or deterministic CLI calls")
    commands = p.add_subparsers(dest="agent_command", required=True)
    for name in ("serve", "call"):
        c = commands.add_parser(name)
        c.add_argument("--project", default=None)
        c.add_argument("--client", default="generic")
        c.add_argument("--manage", action="store_true")
        if name == "call":
            c.add_argument("tool")
            c.add_argument("--json", default="{}")
    sub.add_parser("agent-guide", help="Print the agent operations guide; no inference")


def run(args, home, output):
    from .util import strict_json
    project = args.project or os.environ.get("CLAUDE_PROJECT_DIR") or os.environ.get("GW_PROJECT") or "."
    service = AgentService(home, project, args.client, manage=args.manage)
    if args.agent_command == "serve":
        build_server(service).run(transport="stdio")
    else:
        if not args.tool.startswith("gw_") or not callable(getattr(service, args.tool, None)):
            raise ValueError("Unknown agent operation")
        request = strict_json(args.json)
        if not isinstance(request, dict):
            raise ValueError("Operation arguments must be an object")
        output(getattr(service, args.tool)(**request))
