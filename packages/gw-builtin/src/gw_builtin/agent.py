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
from .host import home_path, initialize, merge, project_root, resolve, validate
from . import host as config_host
from gw_supervisor.api import canonical, digest, read_json, redact, write_json


from gw_supervisor.api import plugin_scope, service, PluginError

class AgentService:
    def __init__(self, home=None, project=".", client="generic", *, manage=False):
        self.home = home_path(str(home) if home else None)
        self.project = project_root(project)
        self.client, self.manage = client, manage
        initialize(self.home)


    def _config(self):
        return resolve(self.home, self.project, self.client)[0]


    def configuration(self):
        return self._config()

    def require_management(self):
        return self._write()

    def _write(self):
        if not self.manage:
            raise PermissionError("This agent interface is read-only; operator must enable managed tools at launch")


    def _repo(self):
        from .ports import trace_repository
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


    def _manager(self):
        from gw_supervisor.api import configured_plugins
        return configured_plugins(self.home, self.client)

    def __dir__(self):
        return sorted(set(super().__dir__()) | set(self._manager().tools))

    def __getattr__(self, name):
        if not name.startswith('gw_'):
            raise AttributeError(name)
        manager = self._manager()
        spec = manager.tools.get(name)
        if spec is None:
            raise AttributeError(name)
        bound = spec.bind(self)
        manifest = manager.manifest()
        import functools
        @functools.wraps(bound)
        def invoke(*args, **kwargs):
            with plugin_scope(self.home, self.client) as active:
                if active.manifest() != manifest:
                    raise PluginError("Plugin composition changed; restart this agent interface before using its old tool definitions")
                if spec.mutating:
                    self._write()
                return bound(*args, **kwargs)
        return invoke

def build_server(service: AgentService):
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise RuntimeError("Install the agent extra: gw-supervisor[agent]") from exc
    server = FastMCP("gw", instructions="GW tools operate on one host-bound project. Explain setup plans before applying. Never request raw keys, infer authorization from memory, or claim a verdict proves enforcement. Use context_compile to retrieve evidence without editing tool schemas.")
    for name, spec in sorted(service._manager().tools.items()):
        if spec.mutating and not service.manage:
            continue
        server.add_tool(getattr(service, name), name=name,
                        annotations={"readOnlyHint": not spec.mutating and name != "gw_knowledge",
                                     "destructiveHint": spec.destructive,
                                     "openWorldHint": spec.open_world})
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
    from gw_supervisor.api import strict_json
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
