"""Host adapters for context evidence. Knowledge is one optional input.

No knowledge import occurs on the project-only or installed-source path. Provider
selection is global configuration, not an instruction in a retrieved document.
"""
from __future__ import annotations

import contextlib
import time

from .ports import publish_component
from gw_supervisor.api import digest, redact, service


def gather_sources(home, root, client, config, task, query, *, session_id=None, max_chars):
    from gw_context import ContextItem, ContextRequest, collect, open_source

    settings = config["context_compiler"]
    scope = digest({"project": str(root), "client": client,
                    "sources": settings.get("sources", {}), "knowledge": config.get("knowledge", {})})
    items, unavailable, results = [], [], []
    retrieval = None
    identity = {"project": str(root), "client": client, "session": "context", "session_id": session_id}
    for name, spec in sorted(settings.get("sources", {}).items()):
        if not spec.get("enabled", True):
            results.append({"name": name, "status": "disabled"})
            continue
        started = time.time_ns()
        info = {"name": name, "provider": spec["provider"], "scope": scope}
        try:
            request = ContextRequest(task=task, scope=scope, query=query, limit=spec.get("limit", 16))
            with contextlib.ExitStack() as stack:
                source = open_source(spec["provider"], spec.get("options", {}))
                if callable(getattr(source, "close", None)):
                    stack.callback(source.close)
                result = collect(source, request, namespace=name)
            accepted = []
            for item in result.items:
                if redact(item.content) != item.content:
                    unavailable.append({"source": item.source, "reason": "potential_secret"})
                else:
                    accepted.append(item)
            items.extend(accepted)
            info.update(status="collected", revision=result.revision, items=len(accepted))
        except Exception as exc:
            info.update(status="unavailable", error=type(exc).__name__)
            if spec.get("on_error", "error") != "omit":
                raise ValueError("Context source unavailable: " + name + " (" + type(exc).__name__ + ")") from None
            unavailable.append({"source": name, "reason": "unavailable", "error": type(exc).__name__})
        finally:
            results.append(info)
            publish_component(home, config, identity, "context.source", info,
                              start_ns=started, end_ns=time.time_ns())

    if settings["knowledge"] and config.get("knowledge", {}).get("enabled", False):
        # This is the only path that loads the optional knowledge implementation.
        # It can itself use a local, remote HTTP, or third-party KnowledgeProvider.
        packet = service('knowledge').evidence(home, root, client, query=(query or task),
            mode=settings['knowledge_mode'], limit=settings['knowledge_limit'], max_chars=max_chars)
        retrieval = {"revision": packet["revision"], "cache": packet["cache"]}
        for n, passage in enumerate(packet['evidence']):
            if redact(passage['text']) != passage['text']:
                unavailable.append({'source': 'knowledge:' + passage['document_id'], 'reason': 'potential_secret'})
                continue
            items.append(ContextItem('knowledge:' + passage['document_id'] + ':' + str(n), 'knowledge', passage['text'],
                'knowledge:' + packet['provider_id'] + ':' + passage['document_id'],
                passage['revision'], False, 75, passage['start_char']))
        results.append({"name": "gw-knowledge", "status": "collected", "revision": packet["revision"],
                        "items": len(packet["evidence"]), "scope": scope})
    return items, unavailable, retrieval, results, scope
