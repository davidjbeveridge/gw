"""Native hook boundary. Can encode failure before the runtime is available."""
import argparse
import os
import pathlib
import sys
from gw_supervisor.api import runtime as Supervisor, strict_json, configuration, canonical
from .adapters import normalize, native_response, PROFILES
from .ports import enabled, publish_component


def output(value):
    print(canonical(value))


def run_hook(args, home):
    try:
        raw = sys.stdin.read(4_194_305)
        if len(raw.encode()) > 4_194_304:
            raise ValueError("Hook payload too large")
        event = normalize(args.agent, args.phase, strict_json(raw))
        with Supervisor(home, client=args.agent) as supervisor, supervisor.scope(args.agent):
            result = supervisor.evaluate(event)
            native = native_response(args.agent, args.phase, result)
            from .ports import enabled, publish_component
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
            from .ports import publish_component
            from .host import resolve,project_root
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
    parser = argparse.ArgumentParser(prog='gw hook')
    parser.add_argument('--home')
    parser.add_argument('command', choices=['hook'])
    parser.add_argument('agent', choices=[*PROFILES, 'generic'])
    parser.add_argument('phase', choices=['start', 'pre', 'post', 'error'])
    args = parser.parse_args(argv)
    return run_hook(args, configuration().home_path(args.home))
