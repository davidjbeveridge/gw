"""Explicit, read-only OpenRouter catalog discovery. Never reads subscription tokens.

Catalog presence is not account entitlement or endpoint compatibility. Imported
entries remain disabled and availability=unknown until the operator reviews them.
"""
from __future__ import annotations

import datetime as dt
import urllib.request
from .models import strings, validate_registry
from gw_supervisor.api import digest, strict_json

OPENROUTER_CATALOG = "https://openrouter.ai/api/v1/models?output_modalities=all"


def fetch_openrouter():
    # No auth needed for public catalog discovery; no arbitrary URLs or redirects.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None
    opener = urllib.request.build_opener(NoRedirect)
    request = urllib.request.Request(OPENROUTER_CATALOG, headers={"Accept": "application/json", "User-Agent": "gw-supervisor"})
    with opener.open(request, timeout=15) as response:
        raw = response.read(16_777_217)
    if len(raw) > 16_777_216:
        raise ValueError("OpenRouter catalog too large")
    return strict_json(raw.decode())


def import_openrouter(snapshot, ids):
    strings(ids, "model IDs", nonempty=True)
    rows = snapshot.get("data") if isinstance(snapshot, dict) else None
    if not isinstance(rows, list):
        raise ValueError("Expected an OpenRouter data array")
    indexed = {}
    for row in rows:
        if isinstance(row, dict) and isinstance(row.get("id"), str) and row["id"] in ids:
            if row["id"] in indexed:
                raise ValueError("Duplicate requested ID in catalog")
            indexed[row["id"]] = row
    missing = sorted(set(ids) - indexed.keys())
    if missing:
        raise ValueError("Models absent from this catalog: " + ", ".join(missing))
    models = {}
    for mid in dict.fromkeys(ids):
        row = indexed[mid]
        arch = row.get("architecture") or {}
        inputs, outputs = arch.get("input_modalities"), arch.get("output_modalities")
        strings(inputs, "catalog input_modalities", nonempty=True)
        strings(outputs, "catalog output_modalities", nonempty=True)
        params = row.get("supported_parameters") or []
        strings(params, "supported_parameters")
        capabilities = [v for p, v in (("tools", "tools"), ("response_format", "structured_output"), ("reasoning", "reasoning")) if p in params]
        # Only text chat and System One have an unambiguous conventional contract
        # here. Media modality alone does not identify its wire API or executor.
        if outputs == ["text"]:
            operation, execution = ["chat"], {"kind": "proxy", "target": "gw-or-" + digest(mid)[:12]}
        elif outputs == ["decisions"]:
            operation, execution = ["decision"], {"kind": "adapter", "target": "jev"}
        else:
            operation, execution = ["configure.operation"], {"kind": "adapter", "target": "configure-executor"}
        model = {"provider": "openrouter", "model": mid, "description": str(row.get("name", mid)), "enabled": False, "availability": "unknown", "operations": operation, "input_modalities": inputs, "output_modalities": outputs, "capabilities": capabilities, "execution": execution, "billing": {"kind": "metered"}, "metadata": {"catalog_url": OPENROUTER_CATALOG, "fetched_at": dt.datetime.now(dt.timezone.utc).isoformat(), "pricing_as_published": row.get("pricing"), "supported_parameters": params, "review_required": True}}
        context = row.get("context_length")
        if isinstance(context, int) and not isinstance(context, bool) and context > 0:
            model["context_window"] = context
        models["openrouter:" + mid] = model
    result = {"models": models, "policy": {}}
    validate_registry(result)
    return {"inference": result}
