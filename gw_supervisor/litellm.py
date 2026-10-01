"""Optional LiteLLM callback. Install gw into the same environment as LiteLLM.

Configuration: litellm_settings.callbacks: [gw_supervisor.litellm.gw_callback]
Uses the SAME local engine and SQLite store as native hooks; no daemon needed.
"""
from __future__ import annotations

import asyncio
import os
import uuid
try:
    from litellm.integrations.custom_logger import CustomLogger
except ImportError as exc:
    raise ImportError("Install the optional litellm[proxy] package to use this integration") from exc
from .engine import Supervisor
from .proxy import process_request, process_response


def context_for(data: dict) -> dict:
    metadata = data.get("metadata") or {}
    gw = metadata.get("gw") or {}
    project = gw.get("project") or os.environ.get("GW_PROJECT")
    session = gw.get("session") or os.environ.get("GW_SESSION")
    if not project or not session:
        raise ValueError("gw requires metadata.gw.project/session or GW_PROJECT/GW_SESSION; refusing unscoped proxy traffic")
    return {"client": gw.get("client", "litellm"), "project": project, "session": session, "id": gw.get("request_id") or str(uuid.uuid4())}


class GWCallback(CustomLogger):
    async def async_pre_call_hook(self, user_api_key_dict, cache, data: dict, call_type: str):
        if call_type not in {"completion", "acompletion", "responses", "aresponses", "anthropic_messages"}:
            return data
        context = context_for(data)
        wire = "responses" if "responses" in call_type else "anthropic" if call_type == "anthropic_messages" else "chat"
        # Pass only provider request fields, not LiteLLM auth/cache/internal objects.
        fields = {"model", "messages", "input", "instructions", "system", "tools", "tool_choice", "stream", "max_tokens", "max_completion_tokens", "max_output_tokens", "temperature", "response_format", "reasoning", "thinking"}
        payload = {k: v for k, v in data.items() if k in fields}
        def run():
            with Supervisor() as supervisor:
                return process_request(supervisor, context, payload, wire)
        result = await asyncio.to_thread(run)
        if result["decision"] in {"deny", "approve"}:
            raise PermissionError("gw: " + result["reason"])
        data.update(result["payload"])
        # Local callback correlation; LiteLLM metadata is not an instruction to the model.
        metadata = data.setdefault("metadata", {})
        metadata["gw"] = {**context, "request_id": context["id"]}
        return data

    async def async_post_call_success_hook(self, data, user_api_key_dict, response):
        # Observation lives in async_log_success_event so streaming and non-streaming
        # calls are accounted for once. Never mutate already-delivered SSE chunks.
        return response

    async def async_log_success_event(self, kwargs, response_obj, start_time, end_time):
        metadata = kwargs.get("litellm_params", {}).get("metadata") or kwargs.get("metadata") or {}
        gw = metadata.get("gw")
        if not gw or not gw.get("request_id"):
            return
        response = response_obj.model_dump(mode="json") if hasattr(response_obj, "model_dump") else response_obj
        if not isinstance(response, dict):
            return
        context = {"client": gw["client"], "project": gw["project"], "session": gw["session"], "id": gw["request_id"]}
        def run():
            with Supervisor() as supervisor:
                process_response(supervisor, context, response)
        await asyncio.to_thread(run)


gw_callback = GWCallback()
