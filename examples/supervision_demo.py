"""Run an offline policy/state example. No shell tool or model is executed."""
from __future__ import annotations

import json
import pathlib
import tempfile
from gw_supervisor.engine import Supervisor
from gw_supervisor.util import write_json


def run() -> dict:
    with tempfile.TemporaryDirectory(prefix="gw-example-") as directory:
        root = pathlib.Path(directory)
        home, project = root / "state", root / "project"
        project.mkdir()
        write_json(home / "config.json", {
            "version": 1,
            "decision": {"provider": "off"},
            "rules": {"canary": {
                "when": {"input.command": "echo GW_CANARY_DENY"},
                "effect": "deny", "reason": "Offline fixture: must not execute",
            }},
            "goals": {"retry_limit": {"threshold": 2}},
        })
        identity = {"client": "example", "project": str(project), "session": "fixture-session"}
        with Supervisor(home) as supervisor:
            supervisor.evaluate({**identity, "type": "session.start", "id": "start", "task": "Exercise offline supervisor fixtures"})
            event = {**identity, "type": "tool.before", "id": "canary", "tool": "Bash", "input": {"command": "echo GW_CANARY_DENY"}}
            denied = supervisor.evaluate(event)
            repeated = supervisor.evaluate(event)
            # Supplied outcomes are test fixtures, not claims that pytest ran.
            for i in range(2):
                supervisor.evaluate({**identity, "type": "tool.after", "id": f"failed-{i}",
                                     "tool": "Bash", "input": {"command": "pytest"},
                                     "output": {"exit_code": 1}, "success": False})
            retry = supervisor.evaluate({**identity, "type": "tool.before", "id": "retry",
                                         "tool": "Bash", "input": {"command": "pytest"}})
            result = {"canary": denied["decision"], "duplicate": repeated.get("duplicate", False),
                      "retry": retry["decision"], "events": supervisor.store.report()["events"]}
            expected = {"canary": "deny", "duplicate": True, "retry": "approve", "events": 5}
            if result != expected:
                raise AssertionError(f"Unexpected fixture result: {result!r}")
            return result


if __name__ == "__main__":
    print(json.dumps(run(), separators=(",", ":")))
