"""Standalone CLI. No GW, LLM credentials, or model calls required."""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import pathlib
import sys
from . import __version__
from .cache import ContextCache
from .contract import (
    Scope, DocumentInput, KnowledgeError, InvalidRequest, Unsupported,
    MAX_DOCUMENT_CHARS, canonical, loads,
)
from .registry import open_provider
from .service import KnowledgeService


def emit_json(value):
    """ASCII JSON preserves Unicode through parsing on legacy console encodings."""
    print(json.dumps(value, ensure_ascii=True, allow_nan=False, separators=(",", ":")))


def add_operations(sub):
    add = sub.add_parser("ingest", help="Explicitly ingest one UTF-8 text file")
    add.add_argument("file")
    add.add_argument("--id", required=True)
    add.add_argument("--title")
    add.add_argument("--source")
    add.add_argument("--metadata", default="{}", help="JSON object of structured metadata")
    add.add_argument("--expected-revision")
    for name in ("search", "context"):
        command = sub.add_parser(name)
        command.add_argument("query", nargs="?", default="")
        command.add_argument("--mode", choices=["keyword", "structured", "semantic", "hybrid"], default="keyword")
        command.add_argument("--filters", default="{}", help="Exact-match metadata JSON")
        command.add_argument("--limit", type=int, default=8)
        if name == "context":
            command.add_argument("--max-chars", type=int, default=12000)
        else:
            command.add_argument("--cursor")
    read = sub.add_parser("read")
    read.add_argument("document_id")
    read.add_argument("--revision")
    read.add_argument("--start-char", type=int, default=0)
    read.add_argument("--end-char", type=int)
    delete = sub.add_parser("delete")
    delete.add_argument("document_id")
    delete.add_argument("--revision", required=True)
    sub.add_parser("capabilities")
    sub.add_parser("revision")
    sub.add_parser("cache-status")
    sub.add_parser("cache-clear")
    sub.add_parser("export", help="Write owner-visible durable sources as JSONL to stdout")
    restore = sub.add_parser("restore", help="Import an exported JSONL file; differing documents are not overwritten")
    restore.add_argument("file")
    sub.add_parser("reindex", help="Local reference provider only; rebuild derived indexes")
    conform = sub.add_parser("check", help="Read-only adapter contract smoke, not a quality audit")
    conform.add_argument("--query", default="conformance")
    mcp = sub.add_parser("mcp", help="Optional read-only MCP stdio server")
    mcp.add_argument("--writable", action="store_true", help="Explicitly expose knowledge_store")
    serve = sub.add_parser("serve", help="Authenticated loopback HTTP service, bound to this scope")
    serve.add_argument("--port", type=int, default=7788)
    serve.add_argument("--token-env", default="GW_KNOWLEDGE_SERVER_TOKEN")
    serve.add_argument("--token-file", default="")
    serve.add_argument("--writable", action="store_true")


def run_operation(args, service, output):
    scope = service.scope.to_dict()
    op = args.operation
    if op == "ingest":
        path = pathlib.Path(args.file).expanduser().resolve()
        if path.stat().st_size > MAX_DOCUMENT_CHARS * 4:
            raise InvalidRequest("Document file too large")
        with path.open(encoding="utf-8", newline="") as source:
            content = source.read(MAX_DOCUMENT_CHARS + 1)
        doc = DocumentInput(args.id, args.title or path.name, content, args.source or path.as_uri(), loads(args.metadata))
        output(service.dispatch("put", {"scope": scope, "document": doc.to_dict(), "expected_revision": args.expected_revision}))
    elif op in {"search", "context"}:
        request = {"scope": scope, "query": args.query, "mode": args.mode, "filters": loads(args.filters), "limit": args.limit}
        if op == "context":
            request["max_chars"] = args.max_chars
        else:
            request["cursor"] = args.cursor
        output(service.dispatch(op, request))
    elif op == "read":
        output(service.dispatch("read", {"scope": scope, "document_id": args.document_id, "revision": args.revision,
                                         "start_char": args.start_char, "end_char": args.end_char}))
    elif op == "delete":
        output(service.dispatch("delete", {"scope": scope, "document_id": args.document_id, "expected_revision": args.revision}))
    elif op in {"capabilities", "revision"}:
        output(service.dispatch(op, {} if op == "capabilities" else {"scope": scope}))
    elif op == "cache-status":
        output(service.cache.stats())
    elif op == "cache-clear":
        output(service.cache.clear(service.scope))
    elif op == "export":
        if not hasattr(service.provider, "export"):
            raise Unsupported("This provider does not support source export")
        for document in service.provider.export(service.scope):
            output(document)
    elif op == "restore":
        path = pathlib.Path(args.file)
        count = 0
        # Bounded streaming, no whole-corpus RAM requirement. Idempotent entries
        # can be retried; a later conflict does not roll back earlier imports.
        with path.open(encoding="utf-8") as stream:
            while line := stream.readline(MAX_DOCUMENT_CHARS * 6 + 64000):
                if not line.endswith("\n") and len(line) >= MAX_DOCUMENT_CHARS * 6 + 64000:
                    raise InvalidRequest("Export row exceeds size limit")
                if line.strip():
                    doc = DocumentInput.from_dict(loads(line))
                    service.dispatch("put", {"scope": scope, "document": doc.to_dict()})
                    count += 1
        output({"imported": count, "atomic_batch": False})
    elif op == "reindex":
        if not service.writable or not hasattr(service.provider, "rebuild_index"):
            raise Unsupported("Reindex requires the writable local provider")
        output(service.provider.rebuild_index())
        service.cache.clear()
    elif op == "check":
        from .conformance import check_provider
        output(check_provider(service.provider, service.scope, args.query))
    elif op == "mcp":
        from .mcp import build_server
        build_server(service).run(transport="stdio")
    elif op == "serve":
        from .http import credential, make_server
        server = make_server(service, credential(args.token_env, args.token_file), args.port)
        print(f"Knowledge server on 127.0.0.1:{server.server_port}, fixed scope, writable={service.writable}", file=sys.stderr)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()


def main(argv=None):
    parser = argparse.ArgumentParser(prog="gw-knowledge")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--store", default=str(pathlib.Path.home() / ".local/share/gw-knowledge"))
    parser.add_argument("--provider", default="local", help="local, http, or explicitly installed entry-point name")
    parser.add_argument("--options", help="JSON file of provider options, credential references only")
    parser.add_argument("--tenant", default="local")
    parser.add_argument("--collection", default="default")
    parser.add_argument("--principal", default="owner")
    operations = parser.add_subparsers(dest="operation", required=True)
    add_operations(operations)
    args = parser.parse_args(argv)
    try:
        options = loads(pathlib.Path(args.options).read_text(encoding="utf-8")) if args.options else {"directory": args.store}
        provider = open_provider(args.provider, options)
        with contextlib.ExitStack() as stack:
            if hasattr(provider, "close"):
                stack.callback(provider.close)
            cache = stack.enter_context(ContextCache(pathlib.Path(args.store) / "cache"))
            writable = args.operation not in {"serve", "mcp"} or args.writable
            service = KnowledgeService(provider, cache, scope=Scope(args.tenant, args.collection, args.principal), writable=writable)
            run_operation(args, service, emit_json)
    except (KnowledgeError, OSError, UnicodeError, RuntimeError) as exc:
        # Don't echo external errors, tokens, source content or request bodies.
        code = exc.code if isinstance(exc, KnowledgeError) else type(exc).__name__
        print(canonical({"error": code}), file=sys.stderr)
        raise SystemExit(2)


if __name__ == "__main__":
    main()
