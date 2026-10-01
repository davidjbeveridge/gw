"""SQLite/WAL trace store. No raw prompts, tool arguments, or responses in events."""
from __future__ import annotations

import json
import os
import pathlib
import sqlite3
import time
from .util import canonical, digest, redact

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
 id TEXT PRIMARY KEY, native_id TEXT NOT NULL, client TEXT NOT NULL,
 project TEXT NOT NULL, task TEXT NOT NULL, config TEXT NOT NULL,
 created REAL NOT NULL, drift REAL NOT NULL DEFAULT 0,
 observations INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS events (
 session TEXT NOT NULL, event_id TEXT NOT NULL, kind TEXT NOT NULL,
 action_hash TEXT NOT NULL, tool TEXT NOT NULL, success INTEGER,
 result TEXT NOT NULL, created REAL NOT NULL,
 PRIMARY KEY(session,event_id,kind));
CREATE INDEX IF NOT EXISTS event_action ON events(session,action_hash,kind);
CREATE TABLE IF NOT EXISTS candidates (
 project TEXT NOT NULL, action_hash TEXT NOT NULL, tool TEXT NOT NULL,
 successes INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'proposed',
 created REAL NOT NULL, PRIMARY KEY(project,action_hash));
CREATE TABLE IF NOT EXISTS tasks (project TEXT PRIMARY KEY, task TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, result TEXT NOT NULL, expires REAL NOT NULL);
CREATE TABLE IF NOT EXISTS usage (
 session TEXT NOT NULL, event_id TEXT NOT NULL, model TEXT NOT NULL,
 input_tokens INTEGER, output_tokens INTEGER, created REAL NOT NULL,
 PRIMARY KEY(session,event_id));
"""


class Store:
    def __init__(self, home: pathlib.Path):
        home.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(home / "state.sqlite3", timeout=5)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA busy_timeout=5000")
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript(SCHEMA)
        os.chmod(home / "state.sqlite3", 0o600)

    def close(self):
        self.db.close()

    def task(self, project: str) -> str:
        row = self.db.execute("SELECT task FROM tasks WHERE project=?", (project,)).fetchone()
        return row[0] if row else ""

    def set_task(self, project: str, task: str):
        if not task.strip():
            raise ValueError("Task must not be empty")
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO tasks VALUES (?,?)", (project, redact(task.strip())))

    def session(self, event: dict, config: dict) -> dict:
        key = digest([event["client"], event["project"], event["session"]])
        row = self.db.execute("SELECT * FROM sessions WHERE id=?", (key,)).fetchone()
        if not row:
            task = self.task(event["project"]) or (redact(event.get("task", "")) if event["type"] == "session.start" else "")
            with self.db:
                self.db.execute("INSERT OR IGNORE INTO sessions(id,native_id,client,project,task,config,created) VALUES (?,?,?,?,?,?,?)", (key, event["session"], event["client"], event["project"], task, canonical(config), time.time()))
            row = self.db.execute("SELECT * FROM sessions WHERE id=?", (key,)).fetchone()
        if not row["task"] and event["type"] == "session.start" and event.get("task"):
            with self.db:
                self.db.execute("UPDATE sessions SET task=? WHERE id=? AND task=''", (redact(event["task"]), key))
            row = self.db.execute("SELECT * FROM sessions WHERE id=?", (key,)).fetchone()
        result = dict(row)
        result["config"] = json.loads(result["config"])
        return result

    def cached_event(self, sid: str, event: dict):
        row = self.db.execute("SELECT result FROM events WHERE session=? AND event_id=? AND kind=?", (sid, event["id"], event["type"])).fetchone()
        return json.loads(row[0]) if row else None

    def counts(self, sid: str, action_hash: str, project: str) -> dict:
        recent = self.db.execute("SELECT success FROM events WHERE session=? AND action_hash=? AND kind='tool.after' ORDER BY created DESC LIMIT 20", (sid, action_hash)).fetchall()
        failures = 0
        for row in recent:
            if row[0] != 0:
                break
            failures += 1
        successes = self.db.execute("SELECT COUNT(*) FROM events e JOIN sessions s ON s.id=e.session WHERE s.project=? AND e.action_hash=? AND e.kind='tool.after' AND e.success=1", (project, action_hash)).fetchone()[0]
        return {"failures": failures, "successes": successes}

    def record(self, session: dict, event: dict, action_hash: str, result: dict, drift: float | None, candidate_at: int | None) -> dict:
        # Return the first decision for a duplicated delivery, without double-counting.
        with self.db:
            inserted = self.db.execute("INSERT OR IGNORE INTO events VALUES (?,?,?,?,?,?,?,?)", (session["id"], event["id"], event["type"], action_hash, event.get("tool", ""), event.get("success"), canonical(result), time.time())).rowcount
            if not inserted:
                return self.cached_event(session["id"], event)
            if drift is not None:
                self.db.execute("UPDATE sessions SET drift=CASE WHEN observations=0 THEN ? ELSE 0.7*drift+0.3*? END, observations=observations+1 WHERE id=?", (drift, drift, session["id"]))
            if candidate_at and event["type"] == "tool.after" and event.get("success") is True:
                count = self.counts(session["id"], action_hash, session["project"])["successes"]
                if count >= candidate_at:
                    self.db.execute("INSERT INTO candidates VALUES (?,?,?,?,'proposed',?) ON CONFLICT(project,action_hash) DO UPDATE SET successes=excluded.successes", (session["project"], action_hash, event.get("tool", ""), count, time.time()))
            if event["type"] == "model.response":
                u = event.get("usage", {})
                def integer(key):
                    value = u.get(key)
                    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None
                self.db.execute("INSERT OR IGNORE INTO usage VALUES (?,?,?,?,?,?)", (session["id"], event["id"], event.get("model", ""), integer("input_tokens"), integer("output_tokens"), time.time()))
        return result

    def get_cache(self, key: str):
        row = self.db.execute("SELECT result FROM cache WHERE key=? AND expires>?", (key, time.time())).fetchone()
        return json.loads(row[0]) if row else None

    def put_cache(self, key: str, result: dict, ttl: float):
        with self.db:
            self.db.execute("DELETE FROM cache WHERE expires<?", (time.time(),))
            self.db.execute("INSERT OR REPLACE INTO cache VALUES (?,?,?)", (key, canonical(result), time.time() + ttl))

    def report(self) -> dict:
        sessions = [dict(r) for r in self.db.execute("SELECT id,native_id,client,project,created,drift,observations FROM sessions ORDER BY created DESC LIMIT 100")]
        candidates = [dict(r) for r in self.db.execute("SELECT * FROM candidates ORDER BY created DESC LIMIT 100")]
        usage = dict(self.db.execute("SELECT COUNT(*) AS calls,SUM(input_tokens) AS input_tokens,SUM(output_tokens) AS output_tokens FROM usage").fetchone())
        return {"sessions": sessions, "automation_candidates": candidates, "usage": usage, "events": self.db.execute("SELECT COUNT(*) FROM events").fetchone()[0]}
