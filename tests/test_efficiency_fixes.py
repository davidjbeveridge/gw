"""Regression checks for cache semantics, one-copy delivery and warm dispatch.

No model requests. A fixed classifier measures cache scheduling, not accuracy.
"""
from __future__ import annotations

import copy
import importlib.util
import json
import pathlib
import tempfile
import unittest
from unittest.mock import Mock, PropertyMock, patch

from gw_supervisor.engine import Supervisor
from gw_supervisor.api import PluginError
from gw_supervisor.util import canonical, write_json
from gw_builtin.decision_cache import evaluate_goals, projected_state, validate_inputs


def goal(inputs=None):
    out = {"on": ["tool.before"], "evaluator": "choice", "question": "Judge evidence only",
           "choices": {"ready": "Ready", "unknown": "Insufficient evidence"}}
    if inputs is not None:
        out["inputs"] = inputs
    return out


class CacheTests(unittest.TestCase):
    def setUp(self):
        self.data, self.calls = {}, []
        self.store = Mock()
        self.store.get_cache.side_effect = lambda key: copy.deepcopy(self.data.get(key))
        self.store.put_cache.side_effect = lambda key, result, ttl: self.data.__setitem__(key, copy.deepcopy(result))
        self.provider = Mock()
        def answer(state, goals):
            self.calls.append((copy.deepcopy(state), copy.deepcopy(goals)))
            return {gid: "ready" for gid in goals}
        self.provider.decide.side_effect = answer
        self.state = {"task": "Fix parser", "event": {"type": "tool.before", "tool": "Read", "input": {"file": "parser.py"}},
                      "metrics": {"failures": 0, "observations": 2, "successes": 1},
                      "compiled_context": {"id": "evidence-v1"}}
        self.scope = {"policy": "p", "session": "s", "project": "a", "client": "fixture"}

    def run_goals(self, goals, ttl=60):
        return evaluate_goals(self.store, scope=self.scope, state=self.state, goals=goals, ttl=ttl,
                              provider_factory=lambda: self.provider)

    def test_projected_request_matches_key_and_ignores_only_declared_omissions(self):
        goals = {"alignment": goal(["event", "metrics.failures"])}
        self.run_goals(goals)
        self.state["metrics"].update(observations=100, successes=99)
        labels, errors, audit = self.run_goals(goals)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(audit["alignment"]["status"], "hit")
        self.assertEqual(self.calls[0][0]["metrics"], {"failures": 0})
        self.assertIn("compiled_context", self.calls[0][0])
        self.assertEqual(labels, {"alignment": "ready"}); self.assertFalse(errors)
        self.state["metrics"]["failures"] = 1
        self.run_goals(goals)
        self.assertEqual(len(self.calls), 2)

    def test_custom_goals_default_to_full_state(self):
        goals = {"progress": goal()}
        self.run_goals(goals); self.state["metrics"]["observations"] += 1; self.run_goals(goals)
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(self.calls[-1][0], self.state)

    def test_only_misses_are_batched_and_cached_siblings_survive_errors(self):
        goals = {"a": goal(["event"]), "b": goal(["event"])}
        _, _, audit = self.run_goals(goals)
        self.assertEqual(set(self.calls[0][1]), {"a", "b"})
        del self.data[audit["b"]["key"]]
        def fail(state, pending):
            self.assertEqual(set(pending), {"b"})
            raise RuntimeError("private provider diagnostic")
        self.provider.decide.side_effect = fail
        labels, errors, details = self.run_goals(goals)
        self.assertEqual(labels, {"a": "ready"}); self.assertEqual(errors, {"b": "RuntimeError"})
        self.assertEqual(details["a"]["status"], "hit")
        self.assertNotIn("private", canonical(details))
        self.assertNotIn(audit["b"]["key"], self.data)

    def test_incompatible_dependency_sets_do_not_share_model_state(self):
        self.run_goals({"static": goal(["event"]), "dynamic": goal()})
        self.assertEqual(len(self.calls), 2)
        self.assertNotIn("metrics", self.calls[0][0]); self.assertIn("metrics", self.calls[1][0])

    def test_input_and_scope_changes_invalidate_exactly(self):
        goals = {"a": goal(["event"])}
        changes = [lambda: self.state.update(task="New task"),
                   lambda: self.state["compiled_context"].update(id="evidence-v2"),
                   lambda: self.state["event"]["input"].update(file="other.py"),
                   lambda: self.scope.update(session="new-session"),
                   lambda: self.scope.update(project="other-project"),
                   lambda: self.scope.update(policy="new-rubric-model-or-policy")]
        self.run_goals(goals)
        for change in changes:
            before = len(self.calls); change(); self.run_goals(goals)
            self.assertEqual(len(self.calls), before + 1)

    def test_missing_null_and_different_rubrics_remain_distinct(self):
        goals = {"a": goal(["event.optional"])}
        self.run_goals(goals); self.state["event"]["optional"] = None; self.run_goals(goals)
        goals["a"]["question"] = "A different question"; self.run_goals(goals)
        self.assertEqual(len(self.calls), 3)

    def test_zero_ttl_is_no_cache_and_invalid_labels_are_not_saved(self):
        goals = {"a": goal(["event"])}
        self.run_goals(goals, 0); _, _, audit = self.run_goals(goals, 0)
        self.assertEqual(len(self.calls), 2); self.assertEqual(audit["a"]["status"], "disabled")
        self.assertEqual(self.data, {})
        for answer in ({}, {"a": "ready", "extra": "ready"}, {"a": "invented"}, {"a": []}):
            self.provider.decide.side_effect = None; self.provider.decide.return_value = answer
            labels, errors, _ = self.run_goals(goals)
            self.assertFalse(labels); self.assertEqual(errors, {"a": "ValueError"}); self.assertEqual(self.data, {})

    def test_expired_entries_and_model_change_do_not_reuse_labels(self):
        goals = {"a": goal(["event"])}
        self.run_goals(goals); self.data.clear(); self.run_goals(goals)
        self.scope["model_version"] = "new-pinned-version"; self.run_goals(goals)
        self.assertEqual(len(self.calls), 3)

    def test_input_contract_validation(self):
        for inputs in ([], "event", ["task"], ["event", "event.input"], ["metrics", "metrics"], ["event..x"], ["event[0]"]):
            with self.subTest(inputs=inputs), self.assertRaises(ValueError): validate_inputs(goal(inputs))
        validate_inputs(goal()); validate_inputs(goal(["event.input", "metrics.failures"]))


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name).resolve(); self.home = self.root / "state"
        self.project = self.root / "project"; self.project.mkdir(); (self.project / ".git").mkdir()

    def event(self, i, kind="tool.before", success=True):
        return {"client": "fixture", "project": str(self.project), "session": "s", "id": str(i),
                "type": kind, "tool": "Read", "input": {"path": "parser.py"},
                **({"success": success, "output": "unchanged fixture"} if kind == "tool.after" else {})}

    def test_twenty_repeated_successful_actions_make_two_calls_not_forty(self):
        calls = []
        class Fixture:
            def decide(self, state, goals):
                calls.append((copy.deepcopy(state), set(goals)))
                return {k: {"task_alignment": "direct", "research_first": "ready", "inbound_redirect": "data"}[k] for k in goals}
        with Supervisor(self.home, classifier=Fixture()) as supervisor:
            supervisor.store.set_task(str(self.project), "Inspect parser")
            hits = 0
            for i in range(20):
                for kind in ("tool.before", "tool.after"):
                    result = supervisor.evaluate(self.event(i, kind))
                    self.assertNotEqual(result["decision"], "deny")
                    self.assertNotIn("plugin_errors", result)
                    hits += sum(v["status"] == "hit" for v in result["decision_cache"].values())
            self.assertEqual(len(calls), 2)
            self.assertEqual(hits, 57)  # 19*(two pre-goals + one post-goal)
            self.assertTrue(supervisor.evaluate(self.event(19, "tool.after"))["duplicate"])
            self.assertEqual(len(calls), 2)

    def test_customizing_shipped_rubric_does_not_inherit_unsafe_projection(self):
        write_json(self.home / "config.json", {"goals": {"task_alignment": {"question": "Is observation count odd?"}}})
        states = []
        class Fixture:
            def decide(self, state, goals):
                if "task_alignment" in goals: states.append(copy.deepcopy(state))
                return {k: {"task_alignment": "direct", "research_first": "ready"}[k] for k in goals}
        with Supervisor(self.home, classifier=Fixture()) as s:
            s.store.set_task(str(self.project), "Inspect parser")
            s.evaluate(self.event(1)); s.evaluate(self.event(2))
        self.assertEqual(len(states), 2)
        self.assertIn("observations", states[0]["metrics"])

    def test_failed_outcomes_recompute_and_retry_control_still_runs(self):
        classifier = Mock(); classifier.decide.side_effect = lambda state, goals: {k: {"task_alignment": "direct", "research_first": "ready", "inbound_redirect": "data"}[k] for k in goals}
        with Supervisor(self.home, classifier=classifier) as s:
            s.store.set_task(str(self.project), "Inspect parser")
            for i in range(3):
                s.evaluate(self.event(i)); s.evaluate(self.event(i, "tool.after", False))
            result = s.evaluate(self.event(4))
            self.assertEqual(result["decision"], "approve")
            self.assertTrue(all(d["status"] == "miss" for d in result["decision_cache"].values()))
            self.assertEqual(result["metrics"]["failures"], 3)

    def test_cached_labels_never_cache_external_authority(self):
        classifier = Mock(); classifier.decide.side_effect = lambda state, goals: {k: {"task_alignment": "direct", "research_first": "ready"}[k] for k in goals}
        authority = Mock(); authority.authorize.side_effect = [{"decision": "allow"}, {"decision": "deny"}]
        with Supervisor(self.home, classifier=classifier, authority=authority) as s:
            s.store.set_task(str(self.project), "Inspect parser")
            self.assertEqual(s.evaluate(self.event(1))["decision"], "allow")
            r = s.evaluate(self.event(2))
            self.assertTrue(r["classifier_cached"]); self.assertEqual(r["decision"], "deny")
            self.assertEqual(authority.authorize.call_count, 2)

    def test_warm_runtime_reuses_discovery_but_checks_config_changes(self):
        from gw_supervisor.registry import discover
        with Supervisor(self.home) as s:
            with patch("gw_supervisor.registry.discover", wraps=discover) as called:
                for i in range(4): s.evaluate(self.event(i))
                called.assert_not_called()
            write_json(self.home / "config.json", {"rules": {"stop": {"when": {"tool": "Read"}, "effect": "deny"}}})
            self.assertEqual(s.evaluate(self.event(10))["decision"], "allow")  # pinned session
            self.assertEqual(s.evaluate({**self.event(11), "session": "fresh"})["decision"], "deny")
            write_json(self.home / "config.json", {"runtime": {"disable": ["gw.learning"]}})
            with self.assertRaises(PluginError): s.evaluate(self.event(12))

    def test_distribution_metadata_is_parsed_once_per_discovery(self):
        from gw_supervisor.api import Plugin
        from gw_supervisor.registry import discover
        class Distribution:
            reads = 0
            @property
            def metadata(self):
                self.reads += 1
                return {"Name": "fixture-distribution", "Version": "1"}
        dist = Distribution()
        from types import SimpleNamespace
        entries = {key: [SimpleNamespace(dist=dist, value=key, load=lambda k=key: lambda: Plugin(k, "1"))]
                   for key in ("fixture.one", "fixture.two")}
        with patch("gw_supervisor.registry.installed", return_value=entries):
            manager = discover(tuple(entries))
        self.assertEqual(dist.reads, 1)
        self.assertEqual(manager.manifest()[0]["origin"]["distribution"], "fixture-distribution")
        manager.close()

    def test_history_query_uses_added_indices_and_preserves_counts(self):
        with Supervisor(self.home) as s:
            for i in range(5): s.evaluate(self.event(i, "tool.after", i != 4))
            session = s.session_context(self.event(10))
            from gw_supervisor.util import digest
            counts = s.store.counts(session["id"], digest(["Read", {"path": "parser.py"}]), str(self.project))
            self.assertEqual(counts, {"successes": 4, "failures": 1})
            plan = s.store.db.execute("EXPLAIN QUERY PLAN SELECT COUNT(*) FROM events e JOIN sessions s ON s.id=e.session WHERE s.project=? AND e.action_hash=? AND e.kind='tool.after' AND e.success=1", (str(self.project), "hash")).fetchall()
            self.assertTrue(any("event_success_scope" in row[3] for row in plan), str([tuple(r) for r in plan]))

    @unittest.skipUnless(importlib.util.find_spec("gw_context"), "Optional context compiler")
    def test_agent_content_once_sdk_unchanged_and_diagnostics_explicit(self):
        from gw_builtin.agent import AgentService
        from gw_builtin.context import compile_context
        (self.project / "README.md").write_text("Fixture parser evidence.\n" * 400)
        agent = AgentService(self.home, self.project)
        compact = agent.gw_context_compile(task="Repair parser")
        detailed = agent.gw_context_compile(task="Repair parser", diagnostics=True)
        self.assertNotIn("text", compact); self.assertNotIn("text", detailed)
        self.assertNotIn("omitted", compact); self.assertIn("omitted", detailed)
        self.assertEqual(compact["payload"], detailed["payload"])
        config = agent.configuration(); config["context_compiler"]["enabled"] = True
        sdk = compile_context(self.home, self.project, "generic", task="Repair parser", config=config)
        self.assertEqual(canonical(sdk["payload"]), sdk["text"])
        self.assertEqual(compact["payload"], sdk["payload"])
        self.assertLess(len(canonical(compact)), 0.60 * len(canonical(sdk)))
        with self.assertRaises(ValueError): agent.gw_context_compile(task="Task", diagnostics="yes")


if __name__ == "__main__":
    unittest.main()
