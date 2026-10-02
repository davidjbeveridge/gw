"""Native hook codecs and non-destructive, idempotent bootstrap.

An internal 'allow' means no supervisor objection, not permission escalation.
Native timeouts, disabled hooks and same-user tampering remain harness/OS limits.
"""
from __future__ import annotations

import copy
import json
import os
import pathlib
import shlex
import shutil
import subprocess
import sys
import time
import uuid
from .util import atomic_write, canonical, digest, read_json, strict_json, write_json

PROFILES = {
    "claude": {"path": ".claude/settings.json", "project_path": ".claude/settings.local.json", "grouped": True, "events": {"UserPromptSubmit": "start", "PreToolUse": "pre", "PostToolUse": "post", "PostToolUseFailure": "error"}, "approval": True, "command": "claude"},
    "codex": {"path": ".codex/hooks.json", "grouped": True, "events": {"UserPromptSubmit": "start", "PreToolUse": "pre", "PostToolUse": "post"}, "approval": False, "command": "codex"},
    "gemini": {"path": ".gemini/settings.json", "grouped": True, "events": {"BeforeAgent": "start", "BeforeTool": "pre", "AfterTool": "post"}, "approval": False, "command": "gemini"},
    "cursor": {"path": ".cursor/hooks.json", "grouped": False, "events": {"beforeSubmitPrompt": "start", "preToolUse": "pre", "postToolUse": "post", "postToolUseFailure": "error"}, "approval": False, "command": "cursor-agent"},
    "copilot": {"path": ".copilot/hooks/gw.json", "project_path": ".github/hooks/gw.json", "grouped": False, "events": {"UserPromptSubmit": "start", "PreToolUse": "pre", "PostToolUse": "post", "PostToolUseFailure": "error"}, "approval": True, "command": "copilot"},
    "opencode": {"path": ".config/opencode/plugins/gw.mjs", "project_path": ".opencode/plugins/gw.mjs", "events": {}, "approval": False, "command": "opencode"}
}
ALIASES = {"claude-code": "claude", "gemini-cli": "gemini", "vscode": "copilot", "github-copilot": "copilot"}


def parse_object(value):
    if isinstance(value, str):
        try:
            return strict_json(value)
        except ValueError:
            return value
    return value


def normalize(agent: str, phase: str, raw: dict, cwd: str | None = None) -> dict:
    if not isinstance(raw, dict):
        raise ValueError("Hook input must be an object")
    if agent == "generic":
        return raw
    inp = parse_object(raw.get("tool_input", raw.get("toolArgs", {})))
    project = raw.get("cwd") or (raw.get("workspace_roots") or [None])[0] or cwd or os.getcwd()
    session = raw.get("session_id") or raw.get("sessionId") or raw.get("conversation_id")
    if not session:
        raise ValueError("Hook omitted session identity; refusing to mix unrelated sessions")
    event = {"client": agent, "session": session, "project": project, "type": {"start": "session.start", "pre": "tool.before", "post": "tool.after", "error": "tool.after"}[phase]}
    native_id = raw.get("tool_use_id") or raw.get("toolUseId")
    event["id"] = str(native_id or (digest([session, raw.get("timestamp"), phase, raw.get("tool_name", raw.get("toolName")), inp]) if raw.get("timestamp") else uuid.uuid4()))
    if isinstance(raw.get("transcript_path"),str):
        event["native_trace_hint"]={"path":raw["transcript_path"],"status":"unregistered_reference"}
    if isinstance(raw.get("parent_tool_use_id"),str):event["parent_id"]=raw["parent_tool_use_id"]
    if isinstance(raw.get("agent_id"),str):event["agent_id"]=raw["agent_id"]
    if phase == "start":
        task = raw.get("prompt", raw.get("user_prompt", ""))
        event["task"] = task if isinstance(task, str) else ""
        return event
    event["tool"] = raw.get("tool_name") or raw.get("toolName") or ""
    if not isinstance(inp, dict):
        raise ValueError("Unrecognized tool arguments: expected an object or JSON object string")
    event["input"] = inp
    if phase in {"post", "error"}:
        output = parse_object(raw.get("tool_response", raw.get("tool_output", raw.get("toolResult", raw.get("tool_result", "")))))
        event["output"] = output
        if phase == "error" or raw.get("error") or raw.get("error_message"):
            event["success"] = False
        elif isinstance(output, dict):
            error = output.get("error") or output.get("isError") or output.get("is_error")
            code = output.get("exit_code", output.get("exitCode", output.get("returncode")))
            kind = output.get("resultType", output.get("result_type"))
            event["success"] = not bool(error or (code is not None and code != 0) or kind in {"failure", "error"})
        else:
            # Native PostToolUse hooks normally fire only on success. Generic API
            # callers should send success=null when execution outcome is unknown.
            event["success"] = True
    return event


def native_response(agent: str, phase: str, result: dict) -> dict:
    if agent == "generic":
        return result
    decision = result["decision"]
    message = "gw: " + result.get("reason", "Supervisor decision")
    advice = "\n".join(dict.fromkeys(result.get("advice", [])))[:6000]
    if phase == "start":
        return {}
    if phase in {"post", "error"}:
        if not advice:
            return {}
        if agent == "cursor":
            return {"additional_context": advice}
        if agent == "copilot":
            return {"additionalContext": advice, "hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": advice}}
        if agent == "gemini":
            return {"hookSpecificOutput": {"hookEventName": "AfterTool", "additionalContext": advice}}
        return {"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": advice}}
    if decision in {"allow", "advise"}:
        if not advice:
            return {}
        if agent in {"claude", "codex"}:
            return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": advice}}
        # These pre-tool protocols don't guarantee a non-blocking model-visible
        # advisory field. Persist it in the trace rather than pretend it enforced.
        return {}
    permission = "ask" if decision == "approve" and PROFILES.get(agent, {}).get("approval") else "deny"
    if decision == "approve" and permission == "deny":
        message += " (This adapter cannot request approval; review and perform the action yourself.)"
    if agent == "cursor":
        return {"permission": "deny", "user_message": message, "agent_message": message}
    if agent == "gemini":
        return {"decision": "deny", "reason": message}
    specific = {"hookEventName": "PreToolUse", "permissionDecision": permission, "permissionDecisionReason": message}
    if agent == "copilot":
        # The same hook file is discoverable by CLI and VS Code Local. Emit
        # identical decisions in each documented envelope, never opposing ones.
        return {"permissionDecision": permission, "permissionDecisionReason": message, "hookSpecificOutput": specific}
    return {"hookSpecificOutput": specific}


def _ours(handler: dict) -> bool:
    return any("gw_supervisor" in str(handler.get(k, "")) and " hook " in str(handler.get(k, "")) for k in ("command", "bash", "powershell", "commandWindows"))


def command_for(home: pathlib.Path, agent: str, phase: str) -> str:
    argv = [sys.executable, "-m", "gw_supervisor", "--home", str(home), "hook", agent, phase]
    return subprocess.list2cmdline(argv) if os.name == "nt" else shlex.join(argv)


def settings_for(existing: dict, agent: str, home: pathlib.Path, install: bool = True) -> dict:
    if not isinstance(existing, dict):
        raise ValueError("Existing agent settings must be a JSON object")
    result = copy.deepcopy(existing)
    profile = PROFILES[agent]
    hooks = result.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise ValueError("Existing hooks must be an object")
    if agent in {"cursor", "copilot"} and result.get("version", 1) != 1:
        raise ValueError("Unsupported hook configuration version")
    if agent in {"cursor", "copilot"}:
        result.setdefault("version", 1)
    for event, phase in profile["events"].items():
        entries = hooks.setdefault(event, [])
        if not isinstance(entries, list):
            raise ValueError(f"Existing {event} hooks must be a list")
        kept = []
        for entry in entries:
            if not isinstance(entry, dict):
                raise ValueError("Malformed existing hook entry")
            if isinstance(entry.get("hooks"), list):
                entry["hooks"] = [h for h in entry["hooks"] if not _ours(h)]
                if entry["hooks"]:
                    kept.append(entry)
            elif not _ours(entry):
                kept.append(entry)
        if install:
            handler = {"type": "command", "command": command_for(home, agent, phase)}
            if agent in {"claude", "codex"}:
                handler["timeout"] = 20
            elif agent == "gemini":
                handler["timeout"] = 20000
            elif agent == "copilot":
                handler["timeoutSec"] = 20
                if os.name == "nt":
                    argv = [sys.executable, "-m", "gw_supervisor", "--home", str(home), "hook", agent, phase]
                    handler["powershell"] = "& " + " ".join("'" + x.replace("'", "''") + "'" for x in argv)
            if profile.get("grouped"):
                kept.append({"matcher": ".*" if agent == "gemini" else "*", "hooks": [handler]})
            else:
                # Cursor has command entries, not Claude matcher groups.
                if agent == "cursor":
                    handler.pop("type", None)
                kept.append(handler)
        if kept:
            hooks[event] = kept
        else:
            hooks.pop(event, None)
    return result


def plugin_source(home: pathlib.Path) -> str:
    argv = [sys.executable, "-m", "gw_supervisor", "--home", str(home), "hook", "generic"]
    return """// Generated by gw-supervisor. OpenCode classic plugin API (v1).
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
const run = promisify(execFile);
const argv = __ARGV__;
export const GWPlugin = async ({ directory }) => {
  const send = async (phase, event) => {
    const child = execFile(argv[0], [...argv.slice(1), phase], { timeout: 15000, maxBuffer: 4194304 });
    const answer = new Promise((resolve, reject) => {
      let stdout = '', stderr = '';
      child.stdout.on('data', b => { stdout += b; });
      child.stderr.on('data', b => { stderr += b; });
      child.on('error', reject);
      child.on('close', code => {
        if (code !== 0) return reject(new Error('gw hook failed; refusing action'));
        try { resolve(JSON.parse(stdout)); } catch { reject(new Error('Invalid gw result')); }
      });
    });
    child.stdin.on('error', () => {});
    child.stdin.end(JSON.stringify(event));
    return answer;
  };
  return {
    'chat.message': async (input, output) => {
      const task = (output.parts || []).filter(p => p.type === 'text').map(p => p.text).join('\\n');
      await send('start', { type: 'session.start', client: 'opencode', session: input.sessionID,
        project: directory, task });
    },
    'tool.execute.before': async (input, output) => {
      const result = await send('pre', { type: 'tool.before', client: 'opencode', session: input.sessionID,
        project: directory, id: input.callID, tool: input.tool, input: output.args });
      if (['deny', 'approve'].includes(result.decision)) throw new Error(result.reason);
    },
    'tool.execute.after': async (input, output) => {
      const result = await send('post', { type: 'tool.after', client: 'opencode', session: input.sessionID,
        project: directory, id: input.callID, tool: input.tool, input: input.args || {},
        output: output.output, success: output.metadata?.error ? false : true });
      if (result.advice?.length) output.output += '\\n\\n[gw] ' + result.advice.join('\\n');
    }
  };
};
""".replace("__ARGV__", json.dumps(argv))


def profile_path(agent: str, user_home: pathlib.Path, project: pathlib.Path | None) -> pathlib.Path:
    profile = PROFILES[agent]
    if project:
        return project / profile.get("project_path", profile["path"])
    if agent == "opencode" and os.environ.get("XDG_CONFIG_HOME"):
        return pathlib.Path(os.environ["XDG_CONFIG_HOME"]) / "opencode/plugins/gw.mjs"
    if agent == "copilot" and os.environ.get("COPILOT_HOME"):
        return pathlib.Path(os.environ["COPILOT_HOME"]) / "hooks/gw.json"
    return user_home / profile["path"]


def bootstrap(home: pathlib.Path, agents: list[str], project: pathlib.Path | None = None, user_home: pathlib.Path | None = None, install: bool = True, dry_run: bool = False) -> list[dict]:
    user_home = user_home or pathlib.Path.home()
    outputs = []
    for agent in dict.fromkeys(ALIASES.get(a, a) for a in agents):
        if agent not in PROFILES:
            raise ValueError(f"Unknown agent {agent}; choose {', '.join(PROFILES)}")
        path = profile_path(agent, user_home, project)
        old = path.read_text(encoding="utf-8") if path.exists() else None
        if agent == "opencode":
            if old and not old.startswith("// Generated by gw-supervisor."):
                raise ValueError(f"Refusing to replace an unrelated plugin: {path}")
            new = plugin_source(home) if install else None
        else:
            existing = strict_json(old) if old else {}
            new = json.dumps(settings_for(existing, agent, home, install), indent=2) + "\n"
            if not install and old is None:
                new = None
        changed = old != new
        if changed and not dry_run:
            if old is not None:
                backup = home / "backups" / (time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8] + "-" + path.name)
                atomic_write(backup, old)
            if new is None:
                if path.exists():
                    path.unlink()
            else:
                atomic_write(path, new)
        outputs.append({"agent": agent, "path": str(path), "changed": changed, "dry_run": dry_run, "installed": install, "native_approval": PROFILES[agent]["approval"]})
    return outputs


def detected_agents(user_home: pathlib.Path | None = None) -> list[str]:
    user_home = user_home or pathlib.Path.home()
    return [agent for agent, profile in PROFILES.items() if shutil.which(profile["command"]) or profile_path(agent, user_home, None).parent.exists() or (agent == "copilot" and shutil.which("code"))]
