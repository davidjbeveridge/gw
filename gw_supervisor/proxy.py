"""Protocol-aware request transforms; no rewriting tool calls or provider refusals."""
from __future__ import annotations

import copy
import json
import uuid
import time
from .util import canonical, redact, strict_json, digest
from .models import requirements

MARKER = "[gw pinned task] "
# These describe wire contracts, not interchangeable models or pricing tiers.
WIRES = {
    "chat": ("chat", ["text"], ["text"]),
    "responses": ("responses", ["text"], ["text"]),
    "anthropic": ("messages", ["text"], ["text"]),
    "image": ("image.generate", ["text"], ["image"]),
    "video": ("video.generate", ["text"], ["video"]),
    "speech": ("audio.speech", ["text"], ["audio"]),
    "transcription": ("audio.transcribe", ["audio"], ["text"]),
    "embedding": ("embedding", ["text"], ["embeddings"]),
    "rerank": ("rerank", ["text"], ["rerank"]),
    "decision": ("decision", ["text"], ["decisions"]),
}
TEXT_WIRES = {"chat", "responses", "anthropic"}


def request_requirements(payload, wire, extra=None):
    operation, inputs, outputs = WIRES[wire]
    inputs, outputs, caps = set(inputs), set(outputs), set()
    if payload.get("tools"):
        caps.add("tools")
        for tool in payload["tools"]:
            if isinstance(tool, dict) and tool.get("type", "function") not in {"function", "custom"}:
                caps.add("tool:" + str(tool["type"]))
    if payload.get("stream"):
        caps.add("streaming")
    if wire in TEXT_WIRES and payload.get("response_format"):
        caps.add("structured_output")
    for field in ("reasoning", "thinking", "previous_response_id", "conversation"):
        if payload.get(field):
            caps.add(field)
    if isinstance(payload.get("text"), dict) and payload["text"].get("format"):
        caps.add("structured_output")
    def visit(value):
        if isinstance(value, list):
            for item in value:
                visit(item)
        elif isinstance(value, dict):
            kind = value.get("type")
            if kind in {"image", "image_url", "input_image"}:
                inputs.add("image")
            elif kind in {"input_audio", "audio", "audio_url"}:
                inputs.add("audio")
            elif kind in {"video", "video_url", "input_video"}:
                inputs.add("video")
            elif kind in {"file", "input_file", "document"}:
                inputs.add("file")
            if kind in {"thinking", "redacted_thinking", "reasoning"}:
                caps.add("signed_reasoning")
            for item in value.values():
                if isinstance(item, (dict, list)):
                    visit(item)
    visit(payload.get("messages", payload.get("input", [])))
    if wire in {"image", "video"} and any(payload.get(k) for k in ("image", "image_url", "input_reference")):
        inputs.add("image")
    if payload.get("modalities"):
        if not isinstance(payload["modalities"], list) or not all(isinstance(x, str) for x in payload["modalities"]):
            raise ValueError("Invalid output modalities")
        outputs = set(payload["modalities"])
    req = {"operation": operation, "input_modalities": sorted(inputs), "output_modalities": sorted(outputs), "capabilities": sorted(caps), "execution_kinds": ["proxy"]}
    if caps & {"signed_reasoning", "previous_response_id", "conversation"} and payload.get("model"):
        req["execution_target"] = payload["model"]
    # Callers may strengthen requirements; never override the observed operation,
    # modalities or transport to make an incompatible model look admissible.
    if extra:
        if not isinstance(extra, dict) or set(extra) - {"capabilities", "context_tokens", "exclude"}:
            raise ValueError("Only additional capabilities, context_tokens and exclude may be supplied")
        for field in ("capabilities", "exclude"):
            if field in extra:
                values = extra[field]
                if not isinstance(values, list) or not all(isinstance(x, str) for x in values):
                    raise ValueError("Invalid additional inference requirement")
                req[field] = sorted(set(req.get(field, [])) | set(values))
        if "context_tokens" in extra:
            req["context_tokens"] = extra["context_tokens"]
    return requirements(req)


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


def model_summary(payload: dict, wire: str = "chat") -> dict:
    """Bounded feature projection, not a second copy of the entire transcript."""
    messages = payload.get("messages", payload.get("input", []))
    user = str(payload.get("prompt", ""))
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


def _process_request(supervisor, context: dict, payload: dict, wire: str = "chat") -> dict:
    if wire not in WIRES or not isinstance(payload, dict):
        raise ValueError("Unsupported model request format")
    event = {**context, "type": "model.request", "id": context.get("id", str(uuid.uuid4())), **model_summary(payload, wire), "requirements": request_requirements(payload, wire, context.get("requirements"))}
    session = supervisor.session_context(event)
    config = session["config"]["proxy"]
    if session["config"]["mode"] == "baseline":
        result = supervisor.evaluate(event)
        return {**result,"payload":payload,"request_id":event["id"],"transform":{"baseline":True,"input_bytes":len(canonical(payload).encode()),"output_bytes":len(canonical(payload).encode())}}
    if config.get("block_detected_secrets", False) and canonical(redact(payload)) != canonical(payload):
        # Heuristic detection only; this is neither complete DLP nor a secret broker.
        event["preflight_denial"] = "Potential secret detected in model input"
    result = supervisor.evaluate(event)
    out = copy.deepcopy(payload)
    if event["requirements"].get("execution_target") and result.get("model", payload.get("model")) != payload.get("model"):
        result.update(decision="deny", reason="Opaque provider state is bound to the current model route; refusing cross-model rewrite")
    before = len(canonical(out).encode())
    if result["decision"] not in {"deny", "approve"}:
        if wire in TEXT_WIRES and config.get("compact_tool_json"):
            out = compact_tools(out)
        compacted = len(canonical(out).encode())
        if wire in TEXT_WIRES and config.get("inject_task"):
            out = inject_task(out, session["task"], wire)
        if result.get("model"):
            out["model"] = result["model"]
        cap = config.get("max_output_tokens", 0)
        if cap and wire in TEXT_WIRES:
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
    event = {**{k: v for k, v in context.items() if k != "requirements"}, "type": "model.response", "id": context.get("id", str(uuid.uuid4())), "model": response.get("model", ""), "usage": extract_usage(response), "response_chars": len(canonical(response)), "status": response.get("status"), "finish_reasons": [x.get("finish_reason") for x in response.get("choices", []) if isinstance(x, dict)]}
    result = supervisor.evaluate(event)
    session=supervisor.session_context(event)
    from .plugins import enabled,publish_component
    if enabled(session["config"]):
        try:
            from gw_observe.contract import normalize_usage
            usage=normalize_usage(response.get("usage",{}),context.get("usage_provider","generic"))
            if isinstance(context.get("cost_usd"),(int,float)):
                usage.update(normalize_usage({"cost_usd":context["cost_usd"]}))
            now=time.time_ns()
            publish_component(supervisor.home,session["config"],{**context,"session_id":session["id"]},"model.usage",
                {"request_id":event["id"],"model":event["model"],"usage":usage,"usage_source":"proxy",
                 "billing_kind":context.get("billing_kind","unknown"),"cost_basis":"provider_reported" if "cost_usd" in usage else "unknown"},
                start_ns=context.get("started_ns",now),end_ns=context.get("finished_ns",now),
                event_id=digest(["model.usage",session["id"],event["id"]]))
        except Exception as exc:
            result["observability_error"]=type(exc).__name__
    return {**result, "payload": response}


def process_request(supervisor, context: dict, payload: dict, wire: str = "chat") -> dict:
    """Measure applied transformations separately from the supervisor's verdict."""
    started=time.time_ns()
    # Stable ID across evaluation, transformations, response and native references.
    context={**context,"id":context.get("id") or str(uuid.uuid4())}
    result=_process_request(supervisor,context,payload,wire)
    from .plugins import enabled,publish_component
    session=supervisor.session_context({**{k:v for k,v in context.items() if k != "requirements"},"type":"model.request"})
    if enabled(session["config"]):
        roles={}
        messages=payload.get("messages",payload.get("input",[]))
        if isinstance(messages,list):
            for m in messages:
                if isinstance(m,dict):
                    role=m.get("role",m.get("type","unknown"))
                    roles[role]=roles.get(role,0)+len(canonical(m))
        attrs={"request_id":context["id"],"wire":wire,"decision":result["decision"],
               "original_model":payload.get("model"),"effective_model":result["payload"].get("model"),
               "transform":result.get("transform",{}),"context_chars_by_role":roles,
               "tool_schema_chars":len(canonical(payload.get("tools",[]))),
               "measurement":"serialized characters/bytes, not model tokens"}
        publish_component(supervisor.home,session["config"],{**context,"session_id":session["id"]},
            "proxy.request",attrs,start_ns=started,end_ns=time.time_ns(),event_id=digest(["proxy.request",session["id"],context["id"]]))
    return result
