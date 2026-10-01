"""Protocol-aware request transforms; no rewriting tool calls or provider refusals."""
from __future__ import annotations

import copy
import json
import uuid
from .util import canonical, redact, strict_json

MARKER = "[gw pinned task] "


def compact_json(text: str) -> str:
    """Remove JSON whitespace OUTSIDE strings without reserializing numbers.

    Invalid/duplicate-key JSON is left alone. No logs/code/prose is truncated.
    """
    if not isinstance(text, str) or not text.lstrip().startswith(("{", "[")):
        return text
    try:
        strict_json(text)
    except (ValueError, RecursionError):
        return text
    out, quoted, escaped = [], False, False
    for char in text:
        if quoted:
            out.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
            out.append(char)
        elif char not in " \r\n\t":
            out.append(char)
    return "".join(out)


def compact_tools(payload: dict) -> dict:
    out = copy.deepcopy(payload)
    for message in out.get("messages", []):
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        if message.get("role") == "tool" and isinstance(content, str):
            message["content"] = compact_json(content)
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_result" and isinstance(block.get("content"), str):
                    block["content"] = compact_json(block["content"])
    if isinstance(out.get("input"), list):
        for item in out["input"]:
            if isinstance(item, dict) and item.get("type") == "function_call_output" and isinstance(item.get("output"), str):
                item["output"] = compact_json(item["output"])
    return out


def inject_task(payload: dict, task: str, wire: str) -> dict:
    if not task:
        return payload
    out = copy.deepcopy(payload)
    text = MARKER + canonical(redact(task))
    if wire == "anthropic":
        system = out.get("system", [])
        if isinstance(system, str):
            system = [{"type": "text", "text": system}] if system else []
        if not isinstance(system, list):
            raise ValueError("Unexpected Anthropic system value")
        if not any(isinstance(x, dict) and str(x.get("text", "")).startswith(MARKER) for x in system):
            out["system"] = [*system, {"type": "text", "text": text}]
    elif wire == "responses":
        existing = out.get("instructions", "") or ""
        if MARKER not in existing:
            out["instructions"] = existing + ("\n" if existing else "") + text
    else:
        messages = out.setdefault("messages", [])
        if not any(m.get("role") in {"system", "developer"} and isinstance(m.get("content"), str) and m["content"].startswith(MARKER) for m in messages):
            # Stable for the session; do not insert changing health metrics into cache prefixes.
            index = 0
            while index < len(messages) and messages[index].get("role") in {"system", "developer"}:
                index += 1
            messages.insert(index, {"role": "system", "content": text})
    return out


def model_summary(payload: dict) -> dict:
    """Bounded feature projection, not a second copy of the entire transcript."""
    messages = payload.get("messages", payload.get("input", []))
    user = ""
    if isinstance(messages, str):
        user = messages
    elif isinstance(messages, list):
        for m in reversed(messages):
            if isinstance(m, dict) and m.get("role") == "user":
                user = canonical(redact(m.get("content", "")))
                break
    raw = canonical(payload)
    capabilities = ["text"]
    if payload.get("tools"):
        capabilities.append("tools")
    if any(k in raw for k in ('"image_url"', '"input_image"', '"type":"image"')):
        capabilities.append("images")
    return {"model": payload.get("model", ""), "latest_user_excerpt": user[:6000], "excerpt_truncated": len(user) > 6000, "request_chars": len(raw), "capabilities": capabilities}


def process_request(supervisor, context: dict, payload: dict, wire: str = "chat") -> dict:
    if wire not in {"chat", "anthropic", "responses"} or not isinstance(payload, dict):
        raise ValueError("Unsupported model request format")
    event = {**context, "type": "model.request", "id": context.get("id", str(uuid.uuid4())), **model_summary(payload)}
    session = supervisor.session_context(event)
    config = session["config"]["proxy"]
    if config.get("block_detected_secrets", False) and canonical(redact(payload)) != canonical(payload):
        # Heuristic detection only; this is neither complete DLP nor a secret broker.
        return {"decision": "deny", "reason": "Potential secret detected in model input", "payload": payload}
    result = supervisor.evaluate(event)
    out = copy.deepcopy(payload)
    before = len(canonical(out).encode())
    if result["decision"] not in {"deny", "approve"}:
        if config.get("compact_tool_json"):
            out = compact_tools(out)
        compacted = len(canonical(out).encode())
        if config.get("inject_task"):
            out = inject_task(out, session["task"], wire)
        if result.get("model"):
            out["model"] = result["model"]
        cap = config.get("max_output_tokens", 0)
        if cap:
            default_key = {"chat": "max_tokens", "anthropic": "max_tokens", "responses": "max_output_tokens"}[wire]
            key = next((k for k in ("max_completion_tokens", "max_output_tokens", "max_tokens") if k in out), default_key)
            current = out.get(key)
            if current is not None and (isinstance(current, bool) or not isinstance(current, int) or current <= 0):
                raise ValueError("Invalid output token limit")
            out[key] = min(cap, current) if current is not None else cap
    else:
        compacted = before
    return {**result, "payload": out, "request_id": event["id"], "transform": {"input_bytes": before, "compacted_bytes": compacted, "output_bytes": len(canonical(out).encode()), "measurement": "bytes, not token savings"}}


def extract_usage(response: dict) -> dict:
    usage = response.get("usage") or {}
    return {"input_tokens": usage.get("input_tokens", usage.get("prompt_tokens")), "output_tokens": usage.get("output_tokens", usage.get("completion_tokens"))}


def process_response(supervisor, context: dict, response: dict) -> dict:
    # Responses are audited, not paraphrased. Preserve tool-call IDs, arguments,
    # signatures, refusals, structured output and streaming ordering byte-for-byte.
    event = {**context, "type": "model.response", "id": context.get("id", str(uuid.uuid4())), "model": response.get("model", ""), "usage": extract_usage(response), "response_chars": len(canonical(response)), "status": response.get("status"), "finish_reasons": [x.get("finish_reason") for x in response.get("choices", []) if isinstance(x, dict)]}
    result = supervisor.evaluate(event)
    return {**result, "payload": response}
