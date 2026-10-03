"""Configured goals and deterministic policy; no runtime permission ownership."""
from __future__ import annotations
import copy
import fnmatch
import shutil
import time
from types import SimpleNamespace
from gw_supervisor.api import (Assessment, Advice, canonical, digest, finite, redact, service)
from .host import get_path

from .matching import matches

def _prepare(ctx):
    config, session, event = ctx.config, ctx.session, ctx.event
    config.setdefault("inference", {"models": {}, "policy": {}})
    action_hash = digest([event.get("tool", ""), redact(event.get("input", {}))])
    counts = ctx.repository.counts(session["id"], action_hash, session["project"])
    metrics = {**counts, "drift": session.get("drift", 0), "observations": session.get("observations", 0)}
    observation = ctx.services.optional('observation')
    tracking = observation is not None and observation.enabled(config)
    audit = {"event_type": event["type"], "event_id": event["id"], "mode": config["mode"],
             "proposal": observation.proposal(event, config), "rules": [], "goals": [],
             "classifier_calls": [], "source_coverage": "hook_or_proxy_projection"} if tracking else None
    goal_audits = {}
    if audit is not None:
        for gid, g in config['goals'].items():
            detail = {'id': gid, 'evaluator': g.get('evaluator'),
                      'status': 'disabled' if not g.get('enabled', True) else 'not_applicable', 'effect': None}
            audit['goals'].append(detail); goal_audits[gid] = detail
    return action_hash, counts, metrics, tracking, audit, goal_audits


def baseline(ctx):
    _, _, metrics, _, audit, _ = _prepare(ctx)
    if audit is not None:
        for g in audit['goals']:
            g['status'] = 'baseline_not_evaluated'
    return {'metrics': metrics, 'classifier_status': 'baseline', **({'audit': audit} if audit is not None else {})}


def assess(ctx):
    config, session, event = ctx.config, ctx.session, ctx.event
    config.setdefault("inference", {"models": {}, "policy": {}})
    policy_hash = ctx.result['policy_hash']
    action_hash, counts, metrics, tracking, audit, goal_audits = _prepare(ctx)
    result = {'labels': {}, 'advice': [], 'metrics': metrics}
    effects = []
    drift = candidate_at = None
    self = SimpleNamespace(home=ctx.home, store=ctx.repository, classifier=ctx.overrides.get('classifier'))
    inference = ctx.services.require('inference')
    make_decider, decision_config, append_calls = inference.create, inference.decision_config, inference.append_calls
    def apply(effect, reason):
        effects.append(Advice(effect, str(redact(reason))[:2000]))

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
            try:
                context_service = ctx.services.optional("context")
                supervisor_context = context_service.for_supervisor if context_service else lambda home, session, event, state, store: (state, None)
                state, context_id = supervisor_context(self.home, session, event, state, self.store)
                if context_id:
                    result["compiled_context_id"] = context_id
                cache_key = digest([policy_hash, session["task"], state, choices])
                labels = self.store.get_cache(cache_key)
                if labels is None:
                    provider = self.classifier or make_decider(decision_config(config))
                    call_start = time.perf_counter()
                    try:
                        labels = provider.decide(state, choices)
                    finally:
                        if tracking:
                            append_calls(audit, provider, "goals", round((time.perf_counter()-call_start)*1000,3), config["decision"].get("model"))
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

    for advice in result.pop('advice', []):
        effects.append(Advice('advise', advice))
    if audit is not None:
        audit['alignment_observation'] = drift
    return Assessment(tuple(effects), result, audit or {},
                      {'action_hash': action_hash, 'drift': drift, 'candidate_at': candidate_at})
