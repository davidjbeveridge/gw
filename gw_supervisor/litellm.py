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
    return {"client": gw.get("client", "litellm"), "project": project, "session": session, "id": gw.get("request_id") or str(uuid.uuid4()), "requirements": gw.get("requirements", {}), "run_id":gw.get("run_id") or os.environ.get("GW_RUN_ID"), "parent_id":gw.get("parent_id")}


class GWCallback(CustomLogger):
    async def async_pre_call_hook(self, user_api_key_dict, cache, data: dict, call_type: str):
        formats = {"completion": "chat", "acompletion": "chat", "responses": "responses", "aresponses": "responses", "anthropic_messages": "anthropic", "image_generation": "image", "aimage_generation": "image", "embeddings": "embedding", "embedding": "embedding", "aembedding": "embedding", "speech": "speech", "aspeech": "speech", "audio_transcription": "transcription", "transcription": "transcription", "atranscription": "transcription", "rerank": "rerank", "arerank": "rerank", "video_generation": "video", "avideo_generation": "video"}
        wire = formats.get(call_type)
        if wire is None:
            # Do not pretend unrecognized gateway operations were supervised.
            raise ValueError("gw: unsupported LiteLLM call_type " + str(call_type))
        context = context_for(data)
        # Pass only provider request fields, not LiteLLM auth/cache/internal objects.
        fields = {"model", "messages", "input", "instructions", "system", "tools", "tool_choice", "stream", "max_tokens", "max_completion_tokens", "max_output_tokens", "temperature", "response_format", "reasoning", "thinking", "modalities", "text", "previous_response_id", "conversation", "prompt", "n", "size", "quality", "seconds", "duration", "voice", "speed", "dimensions", "encoding_format", "query", "documents", "top_n", "image_url", "image_config", "audio", "video_url"}
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
        context = {"client": gw["client"], "project": gw["project"], "session": gw["session"], "id": gw["request_id"],
                   "run_id":gw.get("run_id"),"parent_id":gw.get("parent_id"),
                   "usage_provider":"anthropic" if kwargs.get("custom_llm_provider",kwargs.get("litellm_params",{}).get("custom_llm_provider"))=="anthropic" else "generic"}
        if start_time is not None and hasattr(start_time,"timestamp"):context["started_ns"]=int(start_time.timestamp()*1e9)
        if end_time is not None and hasattr(end_time,"timestamp"):context["finished_ns"]=int(end_time.timestamp()*1e9)
        cost=kwargs.get("response_cost")
        if isinstance(cost,(int,float)):context["cost_usd"]=cost
        def run():
            with Supervisor() as supervisor:
                process_response(supervisor, context, response)
        await asyncio.to_thread(run)


    async def async_log_failure_event(self, kwargs, response_obj, start_time, end_time):
        metadata=kwargs.get("litellm_params",{}).get("metadata") or kwargs.get("metadata") or {}
        gw=metadata.get("gw") or {}
        if not gw.get("request_id"):return
        def record():
            import time
            from .plugins import publish_component
            from .util import digest
            with Supervisor() as supervisor:
                context={"client":gw["client"],"project":gw["project"],"session":gw["session"],"id":gw["request_id"],"run_id":gw.get("run_id")}
                session=supervisor.session_context({**context,"type":"model.response"})
                now=time.time_ns()
                publish_component(supervisor.home,session["config"],{**context,"session_id":session["id"]},"model.failure",
                    {"request_id":context["id"],"model":kwargs.get("model"),"status":"failed","cost":"unknown"},
                    start_ns=now,end_ns=now,event_id=digest(["model.failure",session["id"],context["id"]]))
        await asyncio.to_thread(record)


gw_callback = GWCallback()
