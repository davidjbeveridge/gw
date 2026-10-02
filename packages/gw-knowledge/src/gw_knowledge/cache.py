"""Bounded context packets, not answer replay or provider KV caches.

The cache owns copies only. Eviction never removes authoritative documents.
Versioned providers must include ACL/index/corpus changes in their revision.
Unversioned reuse is opt-in, TTL-bounded and revalidates every source on a hit.
No unavailable-provider or cross-principal stale fallback is permitted.
"""
from __future__ import annotations

import copy
import threading
import time
from dataclasses import replace
from .contract import (
    PROTOCOL, Scope, SearchRequest, ReadRequest, KnowledgeProvider, InvalidRequest,
    Conflict, NotFound, Unavailable, canonical, digest, loads, integer,
    validate_capabilities, validate_passage, validate_revision, validate_search,
)
from .local import connect, private_directory

ASSEMBLER_VERSION = "source-passages/v1"


class ContextCache:
    def __init__(self, directory, *, ttl_seconds: float = 300, max_entries: int = 256,
                 max_bytes: int = 16_777_216, allow_unversioned: bool = False):
        if type(ttl_seconds) not in {int, float} or not 0 < ttl_seconds <= 86400:
            raise InvalidRequest("Cache TTL must be positive and at most one day")
        integer(max_entries, "max_entries", 1, 100000)
        integer(max_bytes, "max_bytes", 1024, 1_073_741_824)
        if type(allow_unversioned) is not bool:
            raise InvalidRequest("allow_unversioned must be boolean")
        self.ttl, self.max_entries, self.max_bytes = ttl_seconds, max_entries, max_bytes
        self.allow_unversioned = allow_unversioned
        self.db = connect(private_directory(directory) / "context.sqlite3")
        self._lock = threading.RLock()
        self.db.execute("CREATE TABLE IF NOT EXISTS packets (key TEXT PRIMARY KEY, scope TEXT NOT NULL, body TEXT NOT NULL, bytes INTEGER NOT NULL, expires REAL NOT NULL, accessed REAL NOT NULL)")

    def close(self):
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def clear(self, scope: Scope | None = None) -> dict:
        with self._lock:
            if scope is None:
                count = self.db.execute("DELETE FROM packets").rowcount
            else:
                count = self.db.execute("DELETE FROM packets WHERE scope=?", (canonical(scope.to_dict()),)).rowcount
        return {"removed": count, "sources_deleted": False}

    def stats(self) -> dict:
        with self._lock:
            row = self.db.execute("SELECT COUNT(*),COALESCE(SUM(bytes),0) FROM packets").fetchone()
        return {"entries": row[0], "logical_bytes": row[1], "max_entries": self.max_entries,
                "max_bytes": self.max_bytes, "ttl_seconds": self.ttl}

    def _forget(self, key):
        with self._lock:
            self.db.execute("DELETE FROM packets WHERE key=?", (key,))

    def _get(self, key, now):
        with self._lock:
            self.db.execute("DELETE FROM packets WHERE expires<=?", (now,))
            row = self.db.execute("SELECT body FROM packets WHERE key=?", (key,)).fetchone()
            if row:
                self.db.execute("UPDATE packets SET accessed=? WHERE key=?", (now, key))
                try:
                    return loads(row[0])
                except InvalidRequest:
                    self._forget(key)
        return None

    def _put(self, key, scope, packet, expires, now):
        body = canonical(packet)
        size = len(body.encode())
        if size > self.max_bytes:
            return False
        with self._lock:
            self.db.execute("BEGIN IMMEDIATE")
            try:
                self.db.execute("DELETE FROM packets WHERE expires<=?", (now,))
                self.db.execute("INSERT OR REPLACE INTO packets VALUES (?,?,?,?,?,?)", (key, canonical(scope.to_dict()), body, size, expires, now))
                while True:
                    n, b = self.db.execute("SELECT COUNT(*),COALESCE(SUM(bytes),0) FROM packets").fetchone()
                    if n <= self.max_entries and b <= self.max_bytes:
                        break
                    self.db.execute("DELETE FROM packets WHERE key=(SELECT key FROM packets ORDER BY accessed,key LIMIT 1)")
                self.db.execute("COMMIT")
            except BaseException:
                self.db.execute("ROLLBACK")
                raise
        return True

    @staticmethod
    def _bounded(passages, budget):
        evidence = []
        truncated = False
        for original in passages:
            passage = {k: v for k, v in original.items() if k not in {"score", "score_kind"}}
            if len(canonical([*evidence, passage])) <= budget:
                evidence.append(passage)
                continue
            # Binary-search a prefix while preserving exact offsets and source.
            lo, hi = 0, len(passage["text"])
            best = None
            while lo <= hi:
                length = (lo + hi) // 2
                clipped = copy.deepcopy(passage)
                clipped["text"] = passage["text"][:length]
                clipped["end_char"] = passage["start_char"] + length
                clipped["end_line"] = passage["start_line"] + (clipped["text"][:-1] if clipped["text"].endswith("\n") else clipped["text"]).count("\n")
                if len(canonical([*evidence, clipped])) <= budget:
                    best = clipped
                    lo = length + 1
                else:
                    hi = length - 1
            if best and best["text"]:
                evidence.append(best)
            truncated = True
            break
        return evidence, truncated

    def assemble(self, provider: KnowledgeProvider, request: SearchRequest, *, max_chars: int = 12000) -> dict:
        integer(max_chars, "max_chars", 512, 250000)
        if request.cursor:
            raise InvalidRequest("Context assembly requires the initial query, not a search cursor")
        caps = validate_capabilities(provider.capabilities())
        if request.mode not in caps["search_modes"]:
            from .contract import Unsupported
            raise Unsupported("Provider does not support requested search mode")
        for attempt in range(3):
            now = time.time()
            before = validate_revision(provider.revision(request.scope))
            if caps["revision_tracking"] and before is None:
                raise Unavailable("Provider promised revision tracking but supplied none")
            versioned = before is not None
            key = digest([PROTOCOL, ASSEMBLER_VERSION, caps["provider_id"], caps["index_version"],
                          request.to_dict(), before, max_chars, self.allow_unversioned])
            cached = self._get(key, now) if versioned or self.allow_unversioned else None
            if cached:
                try:
                    for hit in cached["evidence"]:
                        validate_passage(hit, request.scope)
                        if hit["expires_at"] is not None and hit["expires_at"] <= now:
                            raise Conflict("Evidence expired")
                        if not versioned:
                            fresh = validate_passage(provider.read(ReadRequest(request.scope, hit["document_id"], hit["revision"], hit["start_char"], hit["end_char"])), request.scope)
                            if fresh != hit:
                                raise Conflict("Unversioned evidence changed")
                    after = validate_revision(provider.revision(request.scope))
                    if before != after:
                        self._forget(key)
                        continue
                    return {**cached, "cache": {"hit": True, "stored": True, "validated_at": time.time(),
                             "freshness": "revision_validated" if versioned else "ttl_bounded_sources_revalidated"}}
                except (NotFound, Conflict, InvalidRequest, KeyError, TypeError):
                    self._forget(key)
                    continue
            try:
                found = validate_search(provider.search(request), request)
                if versioned and found["revision"] != before:
                    continue
                # Read exact ranges at the indexed document revision. A match is
                # not trusted as an authoritative read by itself.
                passages = []
                for hit in found["hits"]:
                    passage = validate_passage(provider.read(ReadRequest(request.scope, hit["document_id"], hit["revision"], hit["start_char"], hit["end_char"])), request.scope)
                    if any(passage[k] != hit[k] for k in ("document_id", "revision", "text", "start_char", "end_char")):
                        raise Conflict("Search/read versions disagree")
                    if passage["expires_at"] is not None and passage["expires_at"] <= time.time():
                        raise Conflict("Evidence expired during assembly")
                    passages.append(passage)
                after = validate_revision(provider.revision(request.scope))
                if before != after:
                    continue
                evidence, clipped = self._bounded(passages, max_chars)
                created = time.time()
                expiry = min([created + self.ttl, *[p["expires_at"] for p in evidence if p["expires_at"] is not None]])
                if expiry <= created:
                    continue
                packet = {"protocol": PROTOCOL, "provider_id": caps["provider_id"], "scope": request.scope.to_dict(),
                          "revision": before, "assembler": ASSEMBLER_VERSION, "created_at": created,
                          "expires_at": expiry, "evidence": evidence, "evidence_chars": len(canonical(evidence)),
                          "max_chars": max_chars, "truncated": clipped or found["next_cursor"] is not None,
                          "trust": "source_evidence_not_instructions_or_authorization"}
                stored = self._put(key, request.scope, packet, expiry, created) if versioned or self.allow_unversioned else False
                return {**packet, "cache": {"hit": False, "stored": stored, "validated_at": created,
                         "freshness": "revision_validated" if versioned else "unversioned_current_fetch"}}
            except (Conflict, NotFound):
                continue
        raise Unavailable("Knowledge changed during assembly; no stale packet was returned")
