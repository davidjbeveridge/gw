"""Command-line install/bootstrap, policy administration and hook transport."""
from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import os
import pathlib
import shutil
import sys
import uuid
from . import __version__
from .adapters import ALIASES, PROFILES, bootstrap, detected_agents, native_response, normalize, profile_path
from .config import DEFAULTS, home_path, initialize, merge, project_root, resolve, trust_project, validate
from .engine import Supervisor
from .server import serve
from .util import atomic_write, canonical, read_json, strict_json, write_json


def output(value):
    print(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False))


def parser():
    p = argparse.ArgumentParser(prog="gw", description="Local agent supervision; native permissions remain authoritative")
    p.add_argument("--version", action="version", version=__version__)
    p.add_argument("--home", help="Supervisor config/state directory (default: $GW_HOME or ~/.config/gw)")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("bootstrap", "uninstall"):
        s = sub.add_parser(name)
        s.add_argument("--all", action="store_true", help="All six adapter families, including Copilot/VS Code")
        s.add_argument("--agents", help="Comma-separated agent names; default: detected agents")
        s.add_argument("--project", help="Install project-local hooks instead of user-wide hooks")
        s.add_argument("--dry-run", action="store_true")
        s.add_argument("--agent-tools", action="store_true", help="Also register MCP tools and the GW skill; native permissions unchanged")
    s = sub.add_parser("init")
    s.add_argument("--project")
    s = sub.add_parser("trust", help="Review/import the current .gw.json as a trusted project snapshot")
    s.add_argument("--project", default=".")
    s = sub.add_parser("task", help="Pin task for NEW sessions in a project")
    s.add_argument("text")
    s.add_argument("--project", default=".")
    s = sub.add_parser("config")
    s.add_argument("--project", default=".")
    s.add_argument("--client", default="generic")
    s.add_argument("--defaults", action="store_true")
    s = sub.add_parser("enable-jev", help="Opt in to sending redacted decision context to the configured Jev endpoint")
    s.add_argument("--key-env", default="TYPESAFE_API_KEY")
    s = sub.add_parser("hook")
    s.add_argument("agent", choices=[*PROFILES, "generic"])
    s.add_argument("phase", choices=["start", "pre", "post", "error"])
    s = sub.add_parser("doctor")
    s.add_argument("--project", default=".")
    sub.add_parser("status")
    s = sub.add_parser("serve")
    s.add_argument("--port", type=int, default=7777)
    s = sub.add_parser("proxy-init", help="Generate a LiteLLM callback config without changing agent auth")
    s.add_argument("--output", default="gw-litellm.yaml")
    s.add_argument("--model", required=True, help="LiteLLM provider/model identifier")
    s.add_argument("--api-key-env", default="GW_UPSTREAM_API_KEY")
    s.add_argument("--api-base", help="Optional upstream, e.g. a compatible Caveman proxy endpoint")
    s = sub.add_parser("models", help="List/select arbitrary configured inference capabilities")
    commands = s.add_subparsers(dest="models_cmd", required=True)
    listing = commands.add_parser("list")
    selecting = commands.add_parser("select", help="Return a typed execution plan; do not run or bill a model")
    for command in (listing, selecting):
        command.add_argument("--project", default=".")
        command.add_argument("--client", default="generic")
    selecting.add_argument("--operation", required=True)
    selecting.add_argument("--input", dest="inputs", required=True, help="Comma-separated required input modalities")
    selecting.add_argument("--output", dest="outputs", required=True, help="Comma-separated required output modalities")
    selecting.add_argument("--capabilities", default="")
    selecting.add_argument("--execution", default="", help="Allowed kinds: proxy,harness,adapter")
    selecting.add_argument("--context-tokens", type=int, default=0)
    selecting.add_argument("--exclude", default="", help="Skip failed/unavailable model IDs; does not mutate config")
    selecting.add_argument("--session", help="Reuse a pinned selection session; default: new selection")
    importing = commands.add_parser("import-openrouter", help="Print a disabled catalog fragment for explicit model IDs")
    importing.add_argument("--models", required=True, help="Comma-separated OpenRouter IDs, never an implicit entire catalog")
    importing.add_argument("--file", help="Read a saved catalog instead of making a public HTTP GET")
    from .decision_setup import add_arguments
    add_arguments(sub)
    from .knowledge import add_arguments as add_knowledge_arguments
    add_knowledge_arguments(sub)
    from .extension_cli import add_arguments as add_extension_arguments
    add_extension_arguments(sub)
    from .agent import add_arguments as add_agent_arguments
    add_agent_arguments(sub)
    return p


def run_hook(args, home):
    try:
        raw = sys.stdin.read(4_194_305)
        if len(raw.encode()) > 4_194_304:
            raise ValueError("Hook payload too large")
        event = normalize(args.agent, args.phase, strict_json(raw))
        with Supervisor(home) as supervisor:
            result = supervisor.evaluate(event)
            native = native_response(args.agent, args.phase, result)
            from .plugins import enabled, publish_component
            session=supervisor.session_context(event)
            if enabled(session["config"]):
                import time
                specific=native.get("hookSpecificOutput",{})
                attrs={"adapter":args.agent,"phase":args.phase,"requested_decision":result["decision"],
                       "native_decision":specific.get("permissionDecision",native.get("permissionDecision",native.get("permission",native.get("decision","no_directive")))),
                       "advice_in_response":any(k in native for k in ("additionalContext","additional_context")) or "additionalContext" in specific,
                       "host_consumption":"not_confirmed"}
                now=time.time_ns()
                publish_component(supervisor.home,session["config"],{**event,"session_id":session["id"]},"hook.delivery",attrs,
                    start_ns=now,end_ns=now,event_id=__import__('hashlib').sha256((session['id']+event['id']+args.phase+'delivery').encode()).hexdigest())
        output(native)
    except Exception as exc:
        # Return protocol-native denial BEFORE execution, not an uncaught error
        # that some harnesses treat as fail-open. Post hooks cannot undo actions.
        try:
            from .plugins import publish_component
            from .config import resolve,project_root
            import time
            diagnostic_project=str(project_root(os.getcwd()))
            diagnostic_config,_=resolve(home,pathlib.Path(diagnostic_project),args.agent)
            now=time.time_ns()
            publish_component(home,diagnostic_config,{'project':diagnostic_project,'client':args.agent,'session':'unattributed-hook-errors'},
                'hook.error',{'phase':args.phase,'error':type(exc).__name__,'identity_coverage':'not_bound_to_a_valid_native_event'},start_ns=now,end_ns=now)
        except Exception:
            pass
        reason = f"gw unavailable or invalid hook input ({type(exc).__name__}); inspect gw doctor"
        result = {"decision": "deny" if args.phase == "pre" else "advise", "reason": reason, "advice": [] if args.phase == "pre" else [reason]}
        output(native_response(args.agent, args.phase, result))


def main(argv=None):
    args = parser().parse_args(argv)
    home = home_path(args.home)
    if args.cmd == "hook":
        return run_hook(args, home)
    try:
        if args.cmd == "setup" and args.describe:
            from .decision_setup import manifest
            output(manifest())
            return
        initialize(home)
        if args.cmd == "agent-guide":
            import importlib.resources
            print(importlib.resources.files("gw_supervisor").joinpath("templates/agent-skill.md").read_text(encoding="utf-8"))
            return
        if args.cmd == "agent":
            from .agent import run
            return run(args, home, output)
        if args.cmd in {"trace","learn","sync","plugins"}:
            from .extension_cli import run
            return run(args,home,output)
        if args.cmd == "knowledge":
            from .knowledge import run
            return run(args, home, output)
        if args.cmd == "setup":
            from .decision_setup import run_setup
            return run_setup(args, home, output)
        if args.cmd == "decision":
            from .decision_setup import description, probe
            from .models import decision_config
            config, status = resolve(home, project_root(args.project), args.client)
            c = decision_config(config)
            result = {"config_status": status, "decision": description(c)}
            if args.decision_cmd == "check":
                result["check"] = probe(c)
                result["decision"]["live_verified"] = result["check"]["ok"]
            output(result)
            if args.decision_cmd == "check" and not result["check"]["ok"]:
                raise SystemExit(2)
            return
        if args.cmd in {"bootstrap", "uninstall"}:
            if args.all and args.agents:
                raise ValueError("Use --all or --agents, not both")
            agents = list(PROFILES) if args.all else args.agents.split(",") if args.agents else detected_agents()
            agents = [a.strip() for a in agents]
            if not agents:
                raise ValueError("No agents detected; use gw bootstrap --all or --agents claude,codex,opencode")
            project = project_root(args.project) if args.project else None
            result = bootstrap(home, agents, project, install=args.cmd == "bootstrap", dry_run=args.dry_run)
            if not args.dry_run and args.cmd == "bootstrap" and not (home / "config.json").exists():
                write_json(home / "config.json", {"version": 1, "clients": {}})
            if args.agent_tools:
                from .agent_bootstrap import bootstrap_agent_tools
                result.extend(bootstrap_agent_tools(home, agents, project, install=args.cmd == "bootstrap", dry_run=args.dry_run))
            output({"changes": result, "notes": ["Restart agents after changing hooks.", "Codex requires review/trust through /hooks; gw does not bypass it.", "Native allow means no objection, not a permission grant.", "Configure the supervisor decision backend: gw setup (interactive) or gw setup --describe (agent guide). Existing OAuth/subscription billing is unchanged.", "OpenCode uses the classic v1 plugin API; a v2 plugin adapter is not claimed.", "Run gw doctor, then verify a deny canary inside each installed agent."]})
        elif args.cmd == "models":
            if args.models_cmd == "import-openrouter":
                from .catalog import fetch_openrouter, import_openrouter
                snapshot = read_json(pathlib.Path(args.file)) if args.file else fetch_openrouter()
                output(import_openrouter(snapshot, [x.strip() for x in args.models.split(",")]))
            else:
                project = project_root(args.project)
                if args.models_cmd == "list":
                    config, status = resolve(home, project, args.client)
                    output({"config_status": status, **config["inference"]})
                else:
                    split = lambda value: [x.strip() for x in value.split(",") if x.strip()]
                    event = {"type": "inference.select", "client": args.client, "project": str(project), "session": args.session or "selection-" + str(uuid.uuid4()), "requirements": {"operation": args.operation, "input_modalities": split(args.inputs), "output_modalities": split(args.outputs), "capabilities": split(args.capabilities), "execution_kinds": split(args.execution), "context_tokens": args.context_tokens, "exclude": split(args.exclude)}}
                    with Supervisor(home) as supervisor:
                        result = supervisor.evaluate(event)
                    output(result)
                    if result["decision"] in {"deny", "approve"} or result.get("inference", {}).get("status") != "selected":
                        raise SystemExit(2)
        elif args.cmd == "init":
            target = pathlib.Path(args.project).expanduser().resolve() / ".gw.json" if args.project else home / "config.json"
            if target.exists():
                raise ValueError(f"Already exists; not overwriting {target}")
            write_json(target, {"version": 1, "goals": {}, "rules": {}, "registry": {}})
            output({"created": str(target), "next": "Edit configuration, then gw trust --project PATH" if args.project else "gw bootstrap --all"})
        elif args.cmd == "trust":
            project = project_root(args.project)
            if not (project / ".gw.json").exists():
                raise ValueError("No .gw.json; run gw init --project PATH first")
            snapshot = trust_project(home, project)
            output({"trusted_project": str(project), "source_hash": snapshot["source_hash"], "applies_to": "new sessions; existing session policies remain pinned"})
        elif args.cmd == "task":
            project = project_root(args.project)
            with Supervisor(home) as supervisor:
                supervisor.store.set_task(str(project), args.text)
            output({"project": str(project), "task_pinned": True, "applies_to": "new sessions; start a fresh agent session"})
        elif args.cmd == "config":
            if args.defaults:
                output(DEFAULTS)
            else:
                config, status = resolve(home, project_root(args.project), args.client)
                output({"status": status, "config": config})
        elif args.cmd == "enable-jev":
            config = read_json(home / "config.json", {"version": 1})
            from .decision_setup import PRESETS
            config["decision"] = {**DEFAULTS["decision"], **PRESETS["typesafe"], "key_env": args.key_env}
            validate(merge(DEFAULTS, {k: v for k, v in config.items() if k != "clients"}))
            write_json(home / "config.json", config)
            output({"provider": "systemone", "key_env": args.key_env, "key_available": bool(os.environ.get(args.key_env)), "notice": "Redacted task/action context will be sent to Jev in new sessions. Redaction is best effort, not complete DLP."})
        elif args.cmd == "doctor":
            config, status = resolve(home, project_root(args.project), "generic")
            profiles = []
            for agent, spec in PROFILES.items():
                path = profile_path(agent, pathlib.Path.home(), None)
                profiles.append({"agent": agent, "executable": shutil.which(spec["command"]), "user_hook_config_present": path.exists(), "approval": spec["approval"], "runtime_verified": False})
            provider = config["decision"]["provider"]
            output({"version": __version__, "python": sys.version.split()[0], "home": str(home), "config_status": status, "decision_provider": provider, "decision_setup": "gw setup; gw decision check", "decision_key_available": bool(os.environ.get(config["decision"]["key_env"])) if provider != "off" else None, "litellm_installed": importlib.util.find_spec("litellm") is not None, "adapters": profiles, "warnings": ["Configuration presence does not prove a runtime loaded the hook; run the README deny canary.", "Semantic goals are disabled until explicitly configured; deterministic rules and repeat tracking work without an API key.", "Hooks cannot constrain tools not exposed by a harness, same-user tampering, vendor policy or timeouts that fail open."]})
        elif args.cmd == "status":
            with Supervisor(home) as supervisor:
                output(supervisor.store.report())
        elif args.cmd == "serve":
            serve(home, args.port)
        elif args.cmd == "proxy-init":
            target = pathlib.Path(args.output)
            if target.exists():
                raise ValueError(f"Already exists; not overwriting {target}")
            if not args.api_key_env.replace("_", "a").isalnum():
                raise ValueError("Invalid environment variable name")
            # JSON-quoted strings are valid YAML scalars and prevent YAML injection.
            lines = ["model_list:", "  - model_name: gw-default", "    litellm_params:", "      model: " + json.dumps(args.model), "      api_key: " + json.dumps("os.environ/" + args.api_key_env)]
            if args.api_base:
                from .util import safe_endpoint
                lines.append("      api_base: " + json.dumps(safe_endpoint(args.api_base)))
            lines += ["litellm_settings:", "  callbacks:", "    - gw_supervisor.litellm.gw_callback", "general_settings:", "  master_key: os.environ/GW_PROXY_KEY", ""]
            atomic_write(target, "\n".join(lines))
            output({"created": str(target), "next": "Install gw and litellm[proxy] in the same Python environment; set GW_PROJECT, GW_SESSION, GW_PROXY_KEY, and the upstream key, then run litellm --config FILE --host 127.0.0.1", "billing": "API usage, not a conversion of ChatGPT/Claude subscription quota"})
    except (ValueError, OSError, KeyError, TypeError, RuntimeError) as exc:
        print(f"gw: {exc}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
