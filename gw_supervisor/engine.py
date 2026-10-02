"""One decision engine used by CLI hooks, the optional HTTP API and LiteLLM."""
from __future__ import annotations

import fnmatch
import pathlib
import shutil
import uuid
import time
from typing import Any
from .config import EVENTS, get_path, home_path, initialize, project_root, resolve
from .providers import Classifier, HttpAuthority
from .models import select as select_model, requirements, decision_config
from .store import Store
from .util import canonical, digest, finite, redact
from .plugins import enabled as tracing_enabled, proposal, publish_intercept, usage_metadata

RANK = {"allow": 0, "advise": 1, "approve": 2, "deny": 3}


def matches(event: dict, conditions: dict) -> bool:
    """Conjunctive, literal/glob matching; never eval arbitrary policy code."""
    for path, pattern in conditions.items():
        value = canonical(redact(event)) if path == "text" else get_path(event, path)
        if isinstance(pattern, list):
            if value not in pattern:
                return False
        elif isinstance(pattern, str):
            if not isinstance(value, str) or not fnmatch.fnmatchcase(value, pattern):
                return False
        elif value != pattern:
            return False
    return True


def validate_event(event: dict) -> dict:
    if not isinstance(event, dict) or event.get("type") not in EVENTS:
        raise ValueError("Unknown supervisor event")
    out = dict(event)
    for key in ("client", "session", "project"):
        if not isinstance(out.get(key), str) or not out[key].strip() or len(out[key]) > 4096:
            raise ValueError(f"Event needs a nonempty {key}")
    out["project"] = str(project_root(out["project"]))
    out.setdefault("id", str(uuid.uuid4()))
    if not isinstance(out["id"], str) or not out["id"] or len(out["id"]) > 4096:
        raise ValueError("Invalid event id")
    if out["type"].startswith("tool."):
        if not isinstance(out.get("tool"), str) or not out["tool"]:
            raise ValueError("Tool event has no tool name")
        if not isinstance(out.get("input", {}), dict):
            raise ValueError("Tool input must be an object")
    if "success" in out and out["success"] is not None and not isinstance(out["success"], bool):
        raise ValueError("success must be true, false, or null")
    if out["type"] == "inference.select" or "requirements" in out:
        out["requirements"] = requirements(out.get("requirements"))
    canonical(out)  # Reject unsupported/non-finite data before scoring or persisting.
    return out


class Supervisor:
    def __init__(self, home: str | pathlib.Path | None = None, classifier=None, authority=None):
        self.home = home_path(str(home) if home is not None else None)
        initialize(self.home)
        self.store = Store(self.home)
        self.classifier = classifier
        self.authority = authority

    def close(self):
        self.store.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def evaluate(self, source: dict) -> dict:
        began_ns = time.time_ns()
        began_clock = time.perf_counter()
        event = validate_event(source)
        current, config_status = resolve(self.home, pathlib.Path(event["project"]), event["client"])
        session = self.store.session(event, current)
        previous = self.store.cached_event(session["id"], event)
        if previous:
            return {**previous, "duplicate": True}
        config = session["config"]
        # Pre-v0.2 sessions keep their original policy; the new registry is empty.
        config.setdefault("inference", {"models": {}, "policy": {}})
        policy_hash = digest(config)
        # Fingerprints are only for repetition, NEVER reusable consent.
        action_hash = digest([event.get("tool", ""), redact(event.get("input", {}))])
        counts = self.store.counts(session["id"], action_hash, session["project"])
        metrics = {**counts, "drift": session["drift"], "observations": session["observations"]}
        result = {"version": 1, "decision": "allow", "reasons": [], "advice": [], "labels": {}, "session_id": session["id"], "policy_hash": policy_hash, "config_status": config_status, "metrics": metrics}
        drift = None
        candidate_at = None
        tracking = tracing_enabled(config)
        audit = {"event_type":event["type"], "event_id":event["id"], "mode":config["mode"],
                 "start_ns":began_ns, "proposal":proposal(event,config), "rules":[], "goals":[],
                 "classifier_calls":[], "source_coverage":"hook_or_proxy_projection"} if tracking else None
        goal_audits = {}
        if tracking:
            result["audit"] = audit
            for gid,g in config["goals"].items():
                record = {"id":gid,"evaluator":g.get("evaluator"),"status":"disabled" if not g.get("enabled",True) else "not_applicable","effect":None}
                audit["goals"].append(record); goal_audits[gid]=record

        def save():
            if tracking:
                audit.update(end_ns=time.time_ns(), evaluation_ms=round((time.perf_counter()-began_clock)*1000,3), alignment_observation=drift)
            saved = self.store.record(session,event,action_hash,result,drift,candidate_at)
            publish_intercept(self.home,session,event,saved)
            return saved

        if config["mode"] == "baseline":
            if self.authority:
                raise ValueError("Baseline cannot bypass an injected authority")
            result.update(reason="Measurement-only baseline; GW did not evaluate policy or change the action",classifier_status="baseline")
            if tracking:
                for g in audit["goals"]: g["status"]="baseline_not_evaluated"
            return save()


        def apply(effect: str, reason: str):
            reason = str(redact(reason))[:2000]
            if RANK[effect] > RANK[result["decision"]]:
                result["decision"] = effect
            if effect != "allow":
                result["reasons"].append(reason)
            if effect == "advise":
                result["advice"].append(reason)

        if event.get("preflight_denial"):
            apply("deny",str(event["preflight_denial"]))
            if tracking:audit["rules"].append({"id":"proxy_preflight","matched":True,"effect":"deny"})

        for rule_id, rule in config["rules"].items():
            matched = rule.get("enabled", True) and event["type"] in rule.get("on", ["tool.before"]) and matches(event, rule["when"])
            if tracking:
                audit["rules"].append({"id":rule_id,"matched":bool(matched),"effect":rule["effect"] if matched else None})
            if matched:
                apply(rule["effect"], f"{rule_id}: {rule.get('reason', 'Configured rule matched')}")
        active = {key: g for key, g in config["goals"].items() if g.get("enabled", True) and event["type"] in g["on"]}
        choices = {}
        for goal_id, goal in active.items():
            evaluator = goal["evaluator"]
            detail = goal_audits.get(goal_id,{})
            detail["status"]="evaluated"
            if evaluator == "choice":
                choices[goal_id] = goal
                detail["status"]="pending"
            elif evaluator == "metric":
                metric = goal["metric"]
                if metric not in metrics:
                    raise ValueError(f"Unknown metric: {metric}")
                detail.update(metric=metric,value=metrics.get(metric),threshold=goal["threshold"],effect="allow")
                if metrics[metric] >= goal["threshold"] and session["observations"] >= goal.get("min_observations", 0):
                    detail["effect"]=goal["effect"]
                    apply(goal["effect"], goal.get("message", f"{goal_id}: threshold exceeded"))
            elif evaluator == "repetition" and event.get("success") is True:
                candidate_at = int(goal.get("threshold", 3))
                detail.update(value=counts["successes"]+1,threshold=candidate_at,effect="allow")
                if counts["successes"] + 1 == candidate_at:
                    apply("advise", goal.get("message", "Automation candidate identified"))
                    result["automation_candidate"] = action_hash
                    detail.update(effect="advise",candidate=action_hash)
            elif evaluator == "repetition":
                detail.update(status="outcome_not_success",effect=None)
            elif evaluator == "registry":
                preference = goal.get("preference", [])
                candidates = []
                for tool_id, tool in config["registry"].items():
                    executable = tool.get("executable")
                    if tool.get("enabled", True) and matches(event, tool.get("when", {})) and executable and shutil.which(executable):
                        candidates.append((preference.index(tool.get("kind")) if tool.get("kind") in preference else 999, tool_id, tool))
                if candidates:
                    _, tool_id, tool = sorted(candidates, key=lambda t: (t[0], t[1]))[0]
                    apply("advise", f"Consider registered tool {tool_id}: {tool.get('description', '')}. {tool.get('example', '')}")
                    result["recommended_tool"] = tool_id
                    detail.update(effect="advise",recommended_tool=tool_id)
                else:
                    detail.update(effect="allow",status="no_matching_installed_tool")

        if choices and (config["decision"]["provider"] != "off" or self.classifier):
            # Root-task-dependent goals abstain if no task was pinned.
            if not session["task"] and event["type"].startswith("tool."):
                result["classifier_status"] = "no_pinned_task"
            else:
                state = {"task": session["task"], "event": redact({k: v for k, v in event.items() if k not in {"project", "session", "id", "task", "native_trace_hint"}}), "metrics": metrics}
                cache_key = digest([policy_hash, session["task"], state, choices])
                try:
                    labels = self.store.get_cache(cache_key)
                    if labels is None:
                        provider = self.classifier or Classifier(decision_config(config))
                        call_start = time.perf_counter()
                        try:
                            labels = provider.decide(state, choices)
                        finally:
                            if tracking:
                                audit["classifier_calls"].append({"purpose":"goals","elapsed_ms":round((time.perf_counter()-call_start)*1000,3),
                                    "model":config["decision"].get("model"),"usage":usage_metadata(getattr(provider,"last_usage",None))})
                        if not isinstance(labels, dict) or any(labels.get(k) not in g["choices"] for k, g in choices.items()):
                            raise ValueError("Invalid classification")
                        self.store.put_cache(cache_key, labels, config["decision"].get("cache_seconds", 60))
                    else:
                        result["classifier_cached"] = True
                    result["labels"] = labels
                    result["classifier_status"] = "scored"
                    for goal_id, label in labels.items():
                        goal = choices[goal_id]
                        if tracking:goal_audits[goal_id].update(status="evaluated",label=label,effect=goal.get("effects",{}).get(label,"allow"))
                        apply(goal.get("effects", {}).get(label, "allow"), f"{goal_id}: {goal['choices'][label]}")
                        if goal.get("metric") == "drift" and label in goal.get("scores", {}):
                            drift = finite(goal["scores"][label])
                        route = goal.get("route", {}).get(label)
                        if event["type"] == "model.request" and route and not config["inference"]["models"] and event.get("requirements", {}).get("operation", "chat") in {"chat", "responses", "messages"}:
                            model = config["proxy"].get("models", {}).get(route)
                            required = event.get("capabilities", [])
                            if model and all(cap in model.get("capabilities", []) for cap in required):
                                result["model"] = model["alias"]
                            else:
                                result["advice"].append("Requested route unavailable or missing required capabilities; retaining current model")
                except Exception as exc:
                    # Do not include third-party exception messages (may contain payloads/secrets).
                    result["classifier_status"] = "unavailable"
                    result["classifier_error"] = type(exc).__name__
                    for goal_id, goal in choices.items():
                        if tracking:goal_audits[goal_id].update(status="unavailable",effect=goal.get("on_error","advise"))
                        apply(goal.get("on_error", "advise"), f"{goal_id}: classifier unavailable; no semantic verdict")
        elif choices:
            result["classifier_status"] = "disabled"

        if tracking:
            for gid in choices:
                if goal_audits[gid]["status"]=="pending":
                    goal_audits[gid]["status"]=result.get("classifier_status","not_evaluated")

        # A general selection is a plan, not an execution. A proxy may only
        # replace an alias when the selected operation/transport is compatible.
        if event["type"] in {"inference.select", "model.request"} and (config["inference"]["models"] or event["type"] == "inference.select"):
            if result["decision"] in {"deny", "approve"}:
                result["inference"] = {"status": "blocked_by_policy", "selection_only": True}
            else:
                req = event.get("requirements")
                if not req:
                    apply("deny", "Explicit operation and modality requirements are required for model selection")
                else:
                    selector = self.classifier
                    if selector is None and config["decision"]["provider"] != "off":
                        try:
                            selector = Classifier(decision_config(config))
                        except ValueError:
                            pass  # select() reports classifier_unavailable, never assumes success.
                    if tracking and selector is not None:
                        inner_selector = selector
                        class MeasuredSelector:
                            def decide(self, state, questions):
                                t = time.perf_counter()
                                try:
                                    return inner_selector.decide(state, questions)
                                finally:
                                    audit["classifier_calls"].append({"purpose":"model_selection", "elapsed_ms":round((time.perf_counter()-t)*1000,3),
                                        "model":config["decision"].get("model"), "usage":usage_metadata(getattr(inner_selector,"last_usage",None))})
                        selector = MeasuredSelector()
                    selection = select_model(config["inference"], req, selector, {"task": session["task"], "request": event.get("latest_user_excerpt", ""), "metrics": metrics})
                    result["inference"] = selection
                    if selection["status"] != "selected":
                        apply(config["inference"]["policy"].get("on_unavailable", "approve"), "No admissible model selected: " + selection["status"])
                    elif event["type"] == "model.request":
                        plan = selection["plan"]
                        if plan["execution"]["kind"] != "proxy":
                            apply("deny", "A harness/adapter plan requires its executor; it cannot rewrite a proxy model alias")
                        else:
                            result["model"] = plan["execution"]["target"]

        would = result["decision"]
        if config["mode"] == "observe" and would in {"approve", "deny"}:
            result["would_decision"] = would
            result["decision"] = "advise"
            result["advice"].extend(result["reasons"])

        if event["type"] in {"tool.before", "model.request", "inference.select"} and (config["authority"].get("endpoint") or self.authority):
            try:
                authority = (self.authority or HttpAuthority(config["authority"])).authorize({"session": session["id"], "task": session["task"], "policy_hash": policy_hash, "event": redact(event), "inference_plan": result.get("inference", {}).get("plan")})
                if authority.get("decision") not in {"allow", "deny", "approve"}:
                    raise ValueError("Invalid authority decision")
                result["authority"] = redact(authority)
                # External allow can never relax a local deny, nor vice versa.
                apply(authority["decision"], authority.get("reason", "External authority"))
            except Exception as exc:
                apply("deny", f"Authority unavailable ({type(exc).__name__}); refusing to proceed")

        # Post-action decisions are advice, never a claim to undo an action.
        if event["type"] in {"tool.after", "model.response"} and result["decision"] in {"deny", "approve"}:
            result["would_decision"] = result["decision"]
            result["decision"] = "advise"
            result["advice"].extend(result["reasons"])
        result["reason"] = "; ".join(dict.fromkeys(result["reasons"])) or "No supervisor objection; native permissions still apply"
        return save()

    def session_context(self, event: dict) -> dict:
        event = validate_event(event)
        config, _ = resolve(self.home, pathlib.Path(event["project"]), event["client"])
        return self.store.session(event, config)
