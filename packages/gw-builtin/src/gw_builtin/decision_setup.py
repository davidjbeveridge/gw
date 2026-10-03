"""Reviewable decision-backend setup for people and noninteractive agents."""
from __future__ import annotations

import copy
import os
import pathlib
import sys
import time
import urllib.error
import urllib.parse
from .host import merge, validate
from . import host as config_host
from .models import decision_config
from .providers import Classifier
from gw_supervisor.api import digest, read_json, write_json

PRESETS = {
    "glide": {"provider": "systemone", "endpoint": "https://api.fastino.ai/v1/systemone", "model": "fastino/GLiDE", "auth": "api_key", "key_env": "FASTINO_API_KEY", "strategy": "managed", "timeout_seconds": 5},
    "typesafe": {"provider": "systemone", "endpoint": "https://api.typesafe.ai/v1/systemone", "model": "jev-latest", "auth": "bearer", "key_env": "TYPESAFE_API_KEY"},
    "openrouter": {"provider": "systemone", "endpoint": "https://openrouter.ai/api/v1/systemone", "model": "jev-latest", "auth": "bearer", "key_env": "OPENROUTER_API_KEY"},
    "kev": {"provider": "systemone", "endpoint": "http://127.0.0.1:8009/v1/systemone", "model": "kev-latest", "auth": "none", "key_env": ""},
    "laya": {"provider": "systemone", "endpoint": "http://127.0.0.1:8000/v1/systemone", "model": "typed-decisions", "auth": "none", "key_env": "", "max_state_chars": 2000, "max_request_chars": 6000, "max_options": 16},
    "systemone": {"provider": "systemone", "endpoint": "", "model": "", "auth": "bearer", "key_env": "GW_DECISION_API_KEY"},
    "openai": {"provider": "openai", "endpoint": "", "model": "", "auth": "bearer", "key_env": "GW_DECISION_API_KEY"},
    "custom": {"provider": "http", "endpoint": "", "model": "", "auth": "bearer", "key_env": "GW_DECISION_API_KEY"},
    "cua": {"provider": "http", "endpoint": "", "model": "", "auth": "bearer", "key_env": "GW_DECISION_API_KEY"},
}
NOTES = {
    "glide": "Fastino GLiDE uses its documented System One endpoint with X-API-Key authentication and manages adaptive thinking internally. No additional GW fallback is configured; account access and quality need a live check.",
    "openrouter": "Uses OpenRouter's System One endpoint and key, not chat/completions or subscription tokens.",
    "kev": "Start and warm a Kev server separately. Setup does not install or download weights.",
    "laya": "Targets NandhaKishorM/laya's HTTP server, not the laya-mlx CLI. Small context limits require workload evaluation; reported truncation is rejected.",
    "openai": "Generative JSON classifier, not a System One model. Endpoint/model must support the selected JSON response format; no automatic schema downgrade.",
    "cua": "Requires YOUR evaluated general-choice bridge returning the gw HTTP contract. CUA-S1 forms/nano checkpoints are not generic supervisor classifiers; setup does not adapt or launch them.",
    "custom": "Requires the gw HTTP contract: version/model/state/goals in, decisions object out.",
    "systemone": "The proxy must actually forward the System One request/response contract. An OpenAI-compatible chat endpoint alone is insufficient.",
}
DOC = "https://github.com/davidjbeveridge/gw/blob/main/docs/DECISION_SETUP.md"
SMOKE_STATE = {"requested_label": "beta", "blocked": True}
SMOKE_GOALS = {
    "selection": {"question": "Select the exact value of requested_label in the state.", "choices": {"alpha": "The value is alpha", "beta": "The value is beta"}},
    "policy": {"question": "Return deny when blocked is true; otherwise return allow.", "choices": {"allow": "blocked is false", "deny": "blocked is true"}},
}


def add_arguments(sub):
    p = sub.add_parser("setup", help="Guided core decision-provider setup; no network unless --check")
    p.add_argument("--preset", choices=PRESETS)
    p.add_argument("--describe", action="store_true", help="Machine-readable setup manifest; no prompts, writes or inference")
    p.add_argument("--endpoint", help="Complete inference endpoint URL (including /v1/systemone or /chat/completions)")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--model", help="Exact served model ID or proxy alias")
    g.add_argument("--model-ref", help="Existing compatible decision entry in the inference registry")
    p.add_argument("--key-env", help="Credential environment-variable NAME, never the token")
    p.add_argument("--key-file", help="Existing private token file, never copied into config; environment takes precedence")
    p.add_argument("--no-auth", action="store_true", help="Explicitly send no credentials")
    p.add_argument("--client", help="Global client override, e.g. codex; otherwise configure all clients")
    p.add_argument("--timeout", type=float, help="Warm inference timeout, 0.1..5 seconds")
    p.add_argument("--max-state-chars", type=int)
    p.add_argument("--response-format", choices=["json_schema", "json_object"])
    p.add_argument("--token-parameter", choices=["max_tokens", "max_completion_tokens"])
    p.add_argument("--check", action="store_true", help="Send one synthetic two-question request BEFORE saving; may incur API cost")
    p.add_argument("--dry-run", action="store_true", help="Print the candidate config, never save; --check still makes its explicit request")
    p.add_argument("--yes", action="store_true", help="Apply without an interactive confirmation")
    p = sub.add_parser("decision", help="Inspect or test the core supervisor classifier, independently of worker models")
    commands = p.add_subparsers(dest="decision_cmd", required=True)
    for name in ("status", "check"):
        c = commands.add_parser(name)
        c.add_argument("--project", default=".")
        c.add_argument("--client", default="generic")
    return p


def manifest():
    return {"version": 1, "purpose": "Configure the supervisor classifier, not the worker model registry",
            "presets": {name: {**config, "note": NOTES.get(name, "TypeSafe direct System One access")} for name, config in PRESETS.items()},
            "credential_inputs": ["environment variable name", "existing private file path"],
            "workflow": ["Choose protocol and served model", "Provide credentials outside chat", "Preview with --dry-run", "Run --check to test with synthetic data", "Apply with --yes", "Start a new agent session and verify a deny canary"],
            "documentation": DOC, "live_test": "one synthetic request; not an accuracy benchmark; no project data", "local_runtime_installation": False}


def effective(global_config, client=None):
    config = merge(config_host.DEFAULTS, {k: v for k, v in global_config.items() if k != "clients"})
    if client:
        config = merge(config, global_config.get("clients", {}).get(client, {}))
    validate(config)
    return config


def description(c):
    return {"protocol": c["provider"], "endpoint": c.get("endpoint"), "model": c.get("model"),
            "model_ref": c.get("model_ref"), "auth": c.get("auth", "legacy"), "key_env": c.get("key_env"),
            "environment_key_present": bool(os.environ.get(c.get("key_env", ""))),
            "key_file_configured": bool(c.get("key_file")), "timeout_seconds": c.get("timeout_seconds"),
            "live_verified": False}


def probe(c):
    """A bounded synthetic contract smoke, no user data, no fallback, no raw error log."""
    started = time.monotonic()
    report = {"ok": False, "kind": "synthetic_contract_smoke", "accuracy_benchmark": False}
    try:
        labels = Classifier(c).decide(SMOKE_STATE, SMOKE_GOALS)
        if labels != {"selection": "beta", "policy": "deny"}:
            report.update(error="unexpected_labels", hint="The endpoint is reachable but failed the synthetic choice check; do not treat it as ready.")
        else:
            report.update(ok=True, protocol=c["provider"], model=c["model"])
    except urllib.error.HTTPError as exc:
        hints = {400: "Check wire protocol, model ID and JSON-schema support.", 401: "Check the credential in the environment or private file.",
                 403: "Check account/model access and key permissions.", 404: "Use the complete supported inference endpoint, not just its base URL.",
                 429: "Check provider rate limits or balance; no fallback or retry was attempted."}
        report.update(error="http_error", http_status=exc.code, hint=hints.get(exc.code, "Provider failed; no alternate endpoint or model was tried."))
    except Exception as exc:
        known = {
            "decision_key_missing": "Set the configured API key environment variable in the agent process, or use --key-file pointing to an existing private token file.",
            "decision_context_truncated": "The model/server truncated input. Reduce context/options or choose a larger-context decision model; gw will not silently use a partial judgment.",
            "decision_provider_disabled": "No decision backend is enabled. Run gw setup first.",
            "decision_too_many_options": "Reduce candidate choices or raise max_options only after verifying the model's supported limit.",
        }
        code = str(exc).split(":", 1)[0]
        report.update(error=code if code in known else type(exc).__name__, hint=known.get(code, "Check configuration, credential presence/file permissions, warm server readiness, protocol and context limits. Raw provider errors are suppressed."))
    report["elapsed_ms"] = round((time.monotonic() - started) * 1000)
    return report


def candidate(args, existing):
    c = {**copy.deepcopy(config_host.DEFAULTS["decision"]), **PRESETS[args.preset], "model_ref": None, "key_file": ""}
    for flag, key in (("endpoint", "endpoint"), ("model", "model"), ("model_ref", "model_ref"), ("key_env", "key_env"),
                      ("timeout", "timeout_seconds"), ("max_state_chars", "max_state_chars"), ("response_format", "response_format"), ("token_parameter", "token_parameter")):
        if getattr(args, flag) is not None:
            c[key] = getattr(args, flag)
    if args.model_ref and not c["model"]:
        c["model"] = "registry-model"
    if args.key_file:
        c["key_file"] = str(pathlib.Path(args.key_file).expanduser().absolute())
    if args.no_auth and (args.key_env or args.key_file):
        raise ValueError("Use --no-auth or a credential reference, not both")
    # Never send a TypeSafe/OpenRouter key accidentally to a new host.
    if args.endpoint and c["auth"] == "none" and urllib.parse.urlsplit(c["endpoint"]).hostname not in {"localhost", "127.0.0.1", "::1"}:
        c["auth"], c["key_env"] = "bearer", args.key_env or "GW_DECISION_API_KEY"
    if args.key_env or args.key_file:
        c["auth"] = "api_key" if c["auth"] == "api_key" else "bearer"
    if args.no_auth:
        c.update(auth="none", key_env="", key_file="")
    if not c["endpoint"] or not c["model"]:
        raise ValueError("This preset requires --endpoint FULL_INFERENCE_URL and --model SERVED_ID (or --model-ref)")
    new = copy.deepcopy(existing)
    layer = new.setdefault("clients", {}).setdefault(args.client, {}) if args.client else new
    layer["decision"] = c
    # Validate every global client override and its locks before any write.
    for client in [None, *new.get("clients", {})]:
        effective(new, client)
    decision_config(effective(new, args.client))
    return new


def wizard(args):
    def ask(prompt, default=""):
        print(f"{prompt}" + (f" [{default}]" if default else "") + ": ", end="", file=sys.stderr, flush=True)
        answer = input().strip()
        return answer or default
    if not args.preset:
        print("Core decision model setup. Worker models/authentication are unchanged.\nPresets: " + ", ".join(PRESETS), file=sys.stderr)
        args.preset = ask("Preset", "openrouter")
        if args.preset not in PRESETS:
            raise ValueError("Unknown setup preset")
    p = PRESETS[args.preset]
    args.endpoint = args.endpoint or ask("Complete endpoint", p["endpoint"])
    if not args.model_ref:
        args.model = args.model or ask("Served model ID", p["model"])
    print(NOTES.get(args.preset, "Use your TypeSafe API key."), file=sys.stderr)
    if p["auth"] != "none" and not (args.no_auth or args.key_file):
        args.key_env = args.key_env or ask("API key environment variable NAME (not the secret)", p["key_env"])
    if not args.check:
        args.check = ask("Send one synthetic test request? May incur API cost", "n").lower() in {"y", "yes"}


def run_setup(args, home, output):
    if args.describe:
        output(manifest())
        return
    interactive = sys.stdin.isatty() and not args.yes and not args.dry_run
    if interactive:
        wizard(args)
    if not args.preset:
        raise ValueError("Noninteractive setup needs --preset; run gw setup --describe for the agent-readable guide")
    if not (interactive or args.yes or args.dry_run):
        raise ValueError("Use --dry-run to preview or --yes to apply noninteractively")
    path = home / "config.json"
    existing = read_json(path, {"version": 1})
    new = candidate(args, existing)
    c = decision_config(effective(new, args.client))
    result = {"applied": False, "scope": args.client or "global", "decision": description(c),
              "configuration": new.get("clients", {}).get(args.client, {}).get("decision") if args.client else new["decision"],
              "note": NOTES.get(args.preset, "TypeSafe direct API"), "documentation": DOC}
    if args.check:
        result["check"] = probe(c)
        result["decision"]["live_verified"] = result["check"]["ok"]
        if not result["check"]["ok"]:
            output(result)
            raise SystemExit(2)
    if not args.dry_run:
        if interactive:
            output(result)
            print("Apply this configuration for new sessions? [y/N]: ", end="", file=sys.stderr, flush=True)
            if input().strip().lower() not in {"y", "yes"}:
                return
        # Do not overwrite changes made by another setup process during the probe.
        if read_json(path, {"version": 1}) != existing:
            raise ValueError("Configuration changed during setup; rerun and review it")
        if path.exists():
            backup = home / "backups" / ("decision-" + digest(existing) + ".json")
            if not backup.exists():
                write_json(backup, existing)
            result["backup"] = str(backup)
        write_json(path, new)
        result["applied"] = True
    result["next"] = "Start a new agent session. Run gw decision check in the same environment as the agent, then verify a native deny canary."
    output(result)
