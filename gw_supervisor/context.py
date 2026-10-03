"""GW adapter for the independent context compiler. Source text is never policy.

Project file access is explicit, bounded and root-confined. Native history stays
in its owner; only recent verdict/outcome metadata is projected here.
"""
from __future__ import annotations

import copy
import json
import pathlib
import time
from .util import canonical, digest, redact

DEFAULT_CONTEXT = {"enabled": False, "max_chars": 12000, "project_files": ["README.md"],
                   "required_files": [], "constraints": [], "history_limit": 6,
                   "knowledge": True, "knowledge_mode": "keyword", "knowledge_limit": 4,
                   "delivery": "tools", "supervisor": False, "sources": {}}


def validate_context(c):
    if not isinstance(c, dict) or set(c) - set(DEFAULT_CONTEXT):
        raise ValueError("Unknown context compiler option")
    for key in ("enabled", "knowledge", "supervisor"):
        if type(c.get(key)) is not bool:
            raise ValueError("Invalid context boolean: " + key)
    for key, low, high in (("max_chars", 512, 250000), ("history_limit", 0, 20), ("knowledge_limit", 1, 20)):
        if type(c.get(key)) is not int or not low <= c[key] <= high:
            raise ValueError("Invalid context limit: " + key)
    if c.get("delivery") not in {"tools", "proxy"} or c.get("knowledge_mode") not in {"keyword", "structured", "semantic", "hybrid"}:
        raise ValueError("Invalid context delivery or retrieval mode")
    sources = c.get("sources", {})
    if not isinstance(sources, dict) or len(sources) > 16:
        raise ValueError("Context sources must be a bounded mapping")
    for name, spec in sources.items():
        if not isinstance(name, str) or not name or len(name) > 128 or name == "gw-knowledge":
            raise ValueError("Invalid context source name")
        if not isinstance(spec, dict) or set(spec) - {"provider", "options", "enabled", "limit", "on_error"}:
            raise ValueError("Unknown context source option")
        if not isinstance(spec.get("provider"), str) or not spec["provider"] or len(spec["provider"]) > 128:
            raise ValueError("Context source requires an installed provider name")
        if type(spec.get("enabled", True)) is not bool or type(spec.get("limit", 16)) is not int or not 1 <= spec.get("limit", 16) <= 256:
            raise ValueError("Invalid context source enablement or limit")
        if spec.get("on_error", "error") not in {"error", "omit"}:
            raise ValueError("Context source on_error must be error or omit")
        options = spec.get("options", {})
        if not isinstance(options, dict) or len(canonical(options)) > 16000 or redact(options) != options:
            raise ValueError("Context source options need bounded JSON with credential references, not secrets")
    for key in ("project_files", "required_files", "constraints"):
        values = c.get(key)
        if not isinstance(values, list) or len(values) > 32 or any(not isinstance(v, str) or not v or len(v) > 8192 for v in values):
            raise ValueError("Invalid context list: " + key)
        if key.endswith("files"):
            for path in values:
                relative_path(path)


def relative_path(value):
    if not isinstance(value, str) or not value or "\\" in value or ":" in value or "\0" in value:
        raise ValueError("Context files need portable relative paths")
    p = pathlib.PurePosixPath(value)
    if p.is_absolute() or any(x in {"", ".", ".."} for x in value.split("/")):
        raise ValueError("Context path escapes the project")
    if any(x.startswith(".env") or x in {".git", ".ssh", "node_modules"} for x in p.parts) or p.suffix.lower() not in {".md", ".txt", ".rst", ".py", ".js", ".ts", ".tsx", ".jsx", ".rs", ".json", ".yaml", ".yml"}:
        raise ValueError("Context file type or path is excluded")
    return p


def read_project(root, relative):
    p = root.joinpath(*relative_path(relative).parts)
    if any(part.is_symlink() for part in (p, *[x for x in p.parents if x != root and root in x.parents])):
        raise ValueError("Context file symlinks are not followed")
    if not p.resolve().is_relative_to(root):
        raise ValueError("Context path escapes the project")
    if not p.exists():
        return None
    if not p.is_file() or p.stat().st_size > 256000:
        raise ValueError("Context file is not bounded text")
    with p.open("r", encoding="utf-8", newline="") as stream:
        content = stream.read(256001)
    if len(content) > 256000:
        raise ValueError("Context file exceeds size budget")
    if redact(content) != content:
        raise ValueError("Potential secret in context source; do not inject it")
    return content


def compile_context(home, project, client, *, task=None, query="", session_id=None, active_skills=None, config=None, store=None, max_chars=None):
    try:
        from gw_context import ContextItem, DeterministicContextCompiler
        from gw_context.text import chunks
    except ModuleNotFoundError as exc:
        if exc.name != "gw_context":
            raise
        raise ValueError("Install gw-context with the GW installer --context or --agent-tools; knowledge storage is not required") from exc
    from .config import project_root, resolve
    from .store import Store
    root = project_root(project)
    config = config or resolve(home, root, client)[0]
    c = config["context_compiler"]
    validate_context(c)
    if not c["enabled"]:
        raise ValueError("Context compiler is disabled; configure it through GW agent tools")
    if config["mode"] == "baseline":
        raise ValueError("Context compilation is disabled in a measurement-only baseline")
    started = time.time_ns()
    owned = store is None
    store = store or Store(home)
    try:
        if session_id:
            row = store.db.execute("SELECT task,project,client FROM sessions WHERE id=?", (session_id,)).fetchone()
            if row is None or row["project"] != str(root) or row["client"] != client:
                raise ValueError("Context session belongs to another project or client")
            pinned = row["task"]
        else:
            pinned = store.task(str(root))
        task = task or pinned
        if not task:
            raise ValueError("Supply the task or pin one before compiling context")
        task, query = redact(task), redact(query)
        items, unavailable, project_revisions = [], [], {}
        for n, constraint in enumerate(c["constraints"]):
            items.append(ContextItem("constraint-" + str(n), "constraint", redact(constraint), "gw-config:constraint/" + str(n), digest(constraint), True, 0, trust="host_instruction"))
        skills = active_skills or []
        if not isinstance(skills, list) or len(skills) > 16:
            raise ValueError("At most sixteen active skill paths")
        required = set(c["required_files"]) | set(skills)
        for relative in dict.fromkeys([*sorted(required), *c["project_files"]]):
            content = read_project(root, relative)
            if content is None:
                if relative in required:
                    raise ValueError("Required context file is missing: " + relative)
                unavailable.append({"source": relative, "reason": "missing"})
                continue
            source, revision = "project:" + relative, digest(content)
            project_revisions[relative] = revision
            if relative in required:
                items.append(ContextItem(relative, "skill" if relative in skills else "project", content, source, revision, True, 10))
            else:
                for ordinal, part, a, b, la, lb in chunks(content, width=1600):
                    items.append(ContextItem(relative + ":" + str(ordinal), "project", part, source, revision, False, 100, a))
        if session_id and c["history_limit"]:
            rows = store.db.execute("SELECT event_id,kind,tool,success,result FROM events WHERE session=? AND kind IN ('tool.before','tool.after') ORDER BY created DESC LIMIT ?", (session_id, c["history_limit"])).fetchall()
            for row in reversed(rows):
                result = json.loads(row["result"])
                evidence = {"event": row["event_id"], "kind": row["kind"], "tool": row["tool"], "success": row["success"], "decision": result["decision"], "advice": result.get("advice", [])[:3]}
                content = canonical(redact(evidence))
                items.append(ContextItem("history:" + row["event_id"] + ":" + row["kind"], "history", content, "gw-event:" + digest([session_id, row["event_id"], row["kind"]]), digest(content), False, 50))
        from .context_sources import gather_sources
        extra, missing, retrieval, sources, scope = gather_sources(
            home, root, client, config, task, query, session_id=session_id,
            max_chars=min(max_chars or c["max_chars"], c["max_chars"]))
        items.extend(extra)
        unavailable.extend(missing)
        if len(items) > 256:
            raise ValueError("Context candidate limit exceeded; narrow the configured file set")
        packet = DeterministicContextCompiler().compile(task, items, query=query, max_chars=min(max_chars or c["max_chars"], c["max_chars"]), scope=scope)
        # File reads are not a filesystem snapshot. Detect edits made during
        # compilation instead of presenting mixed source versions as current.
        for relative, revision in project_revisions.items():
            current = read_project(root, relative)
            if current is None or digest(current) != revision:
                raise ValueError("Project context changed during compilation; retry with fresh evidence")
        packet.update(unavailable=unavailable, retrieval=retrieval, sources=sources, scope=scope)
        from .plugins import publish_component
        identity = {"project": str(root), "client": client, "session": "context", "session_id": session_id}
        publish_component(home, config, identity, "context.compile", {"packet_id": packet["id"], "compiled_chars": packet["compiled_chars"],
                          "max_chars": packet["max_chars"], "selected": packet["selected"], "omitted": packet["omitted"], "unavailable": unavailable,
                          "model_calls": 0, "sources": sources, "scope": scope}, start_ns=started, end_ns=time.time_ns())
        return packet
    except Exception as exc:
        from .plugins import publish_component
        publish_component(home, config, {"project": str(root), "client": client, "session": "context", "session_id": session_id},
                          "context.error", {"error": type(exc).__name__, "model_calls": 0}, start_ns=started, end_ns=time.time_ns())
        raise
    finally:
        if owned:
            store.close()


def inject_context(payload, wire, packet):
    """Append evidence in a user message. Never rewrite tools, arguments or system policy."""
    out = copy.deepcopy(payload)
    block = "[gw compiled evidence " + packet["id"] + "]\n" + packet["text"]
    messages = out.get("input") if wire == "responses" else out.get("messages")
    if wire == "responses" and isinstance(messages, str):
        messages = [{"role": "user", "content": messages}]
    if not isinstance(messages, list):
        raise ValueError("Context injection requires a supported message list")
    if any(isinstance(m, dict) and m.get("role") == "user" and m.get("content") == block for m in messages):
        return out, False
    messages.append({"role": "user", "content": block})
    out["input" if wire == "responses" else "messages"] = messages
    return out, True


def supervisor_context(home, session, event, state, store):
    """Bound enrichment to the primary's existing input limit; never truncate task."""
    config = session["config"]
    c = config.get("context_compiler", DEFAULT_CONTEXT)
    if not c["enabled"] or not c["supervisor"]:
        return state, None
    remaining = config["decision"].get("max_state_chars", 16000) - len(canonical(state)) - 128
    if remaining < 512:
        raise ValueError("No room for required compiled decision context")
    packet = compile_context(home, event["project"], event["client"], task=session["task"],
                             query=(session["task"] + " " + event.get("tool", "") + " " + event.get("latest_user_excerpt", ""))[:4096],
                             session_id=session["id"], config=config, store=store, max_chars=remaining)
    return {**state, "compiled_evidence": packet["payload"]}, packet["id"]
