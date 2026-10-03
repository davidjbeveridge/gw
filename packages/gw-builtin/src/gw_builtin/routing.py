"""Capability-aware execution plans. The runtime owns final verdict precedence."""
from __future__ import annotations
import copy
import time
from types import SimpleNamespace
from gw_supervisor.api import Advice, Assessment


def assess(ctx):
    config, session, event = ctx.config, ctx.session, ctx.event
    config.setdefault("inference", {"models": {}, "policy": {}})
    result = copy.deepcopy(ctx.result)
    metrics = result.get('metrics', {})
    effects = []
    observation = ctx.services.optional('observation')
    tracking = observation is not None and observation.enabled(config)
    audit = {'classifier_calls': []}
    inference = ctx.services.require('inference')
    make_decider, decision_config = inference.create, inference.decision_config
    select_model, append_calls = inference.select, inference.append_calls
    self = SimpleNamespace(classifier=ctx.overrides.get('classifier'))
    def apply(effect, reason):
        effects.append(Advice(effect, reason))
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
                        selector = make_decider(decision_config(config))
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
                                append_calls(audit, inner_selector, "model_selection", round((time.perf_counter()-t)*1000,3), config["decision"].get("model"))
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

    details = {k: v for k, v in result.items() if k not in ctx.result or v != ctx.result[k]}
    return Assessment(tuple(effects), details, audit if tracking else {})
