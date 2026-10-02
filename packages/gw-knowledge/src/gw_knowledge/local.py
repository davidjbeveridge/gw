"""Transactional SQLite/FTS5 reference provider. Sources are durable; indexes rebuild.

Only explicit UTF-8 text is ingested. This provider does not crawl URLs, scan
folders, execute documents, generate embeddings, or interpret saved facts as
permissions. The scope principal is supplied by a trusted host, not a model.
"""
from __future__ import annotations

import base64
import contextlib
import json
import os
import pathlib
import re
import sqlite3
import threading
import time
import uuid
from typing import Iterator
from .contract import (
    PROTOCOL, Scope, SearchRequest, ReadRequest, DocumentInput, Conflict,
    InvalidRequest, NotFound, Unsupported, canonical, digest, loads, text,
)

INDEX_VERSION = "fts5-unicode61-lines-1800/v1"
SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS generations (tenant TEXT, collection TEXT, generation INTEGER NOT NULL,
    PRIMARY KEY(tenant,collection));
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY, tenant TEXT NOT NULL, collection TEXT NOT NULL,
    document_id TEXT NOT NULL, owner TEXT NOT NULL, readers TEXT NOT NULL,
    revision TEXT NOT NULL, title TEXT NOT NULL, source TEXT NOT NULL,
    content TEXT NOT NULL, metadata TEXT NOT NULL, expires_at REAL, updated REAL NOT NULL,
    UNIQUE(tenant,collection,document_id));
CREATE TABLE IF NOT EXISTS chunks (
    id INTEGER PRIMARY KEY, document INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    ordinal INTEGER NOT NULL, title TEXT NOT NULL, content TEXT NOT NULL,
    start_char INTEGER NOT NULL, end_char INTEGER NOT NULL,
    start_line INTEGER NOT NULL, end_line INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS documents_scope ON documents(tenant,collection);
CREATE INDEX IF NOT EXISTS chunks_document ON chunks(document,ordinal);
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(title,content,
    content='chunks', content_rowid='id', tokenize='unicode61');
CREATE TRIGGER IF NOT EXISTS chunks_insert AFTER INSERT ON chunks BEGIN
    INSERT INTO chunks_fts(rowid,title,content) VALUES(new.id,new.title,new.content);
END;
CREATE TRIGGER IF NOT EXISTS chunks_delete AFTER DELETE ON chunks BEGIN
    INSERT INTO chunks_fts(chunks_fts,rowid,title,content) VALUES('delete',old.id,old.title,old.content);
END;
"""


def private_directory(path: str | pathlib.Path) -> pathlib.Path:
    path = pathlib.Path(path).expanduser().absolute()
    if path.is_symlink():
        raise InvalidRequest("Knowledge directory cannot be a symlink")
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name != "nt":
        path.chmod(0o700)
    return path


def connect(path: pathlib.Path) -> sqlite3.Connection:
    if path.is_symlink():
        raise InvalidRequest("Knowledge database cannot be a symlink")
    # Create privately before SQLite opens it (including on umask 022 systems).
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        pass
    else:
        os.close(fd)
    if os.name != "nt":
        path.chmod(0o600)
    db = sqlite3.connect(path, timeout=10, isolation_level=None, check_same_thread=False)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA busy_timeout=10000")
    db.execute("PRAGMA journal_mode=WAL")
    return db


def chunks(content: str, width: int = 1800):
    """Exact Unicode character ranges, biased toward newline boundaries."""
    start, line, ordinal = 0, 1, 0
    while start < len(content):
        end = min(len(content), start + width)
        if end < len(content):
            boundary = content.rfind("\n", start + width // 2, end)
            if boundary >= 0:
                end = boundary + 1
        piece = content[start:end]
        end_line = line + (piece[:-1] if piece.endswith("\n") else piece).count("\n")
        yield ordinal, piece, start, end, line, end_line
        line += piece.count("\n")
        start, ordinal = end, ordinal + 1
    if not content:
        yield 0, "", 0, 0, 1, 1


class LocalKnowledgeProvider:
    def __init__(self, directory: str | pathlib.Path):
        self.directory = private_directory(directory)
        self._lock = threading.RLock()
        self.db = connect(self.directory / "knowledge.sqlite3")
        try:
            self.db.executescript(SCHEMA)
            with self._transaction(write=True):
                self.db.execute("INSERT OR IGNORE INTO settings VALUES ('store_id',?)", (str(uuid.uuid4()),))
                self.db.execute("INSERT OR IGNORE INTO settings VALUES ('index_generation','0')")
                self.db.execute("INSERT OR IGNORE INTO settings VALUES ('schema','1')")
                self.db.execute("INSERT OR IGNORE INTO settings VALUES ('index_version',?)", (INDEX_VERSION,))
                if self.db.execute("SELECT value FROM settings WHERE key='schema'").fetchone()[0] != "1":
                    raise Unsupported("Unsupported knowledge database version")
                if self.db.execute("SELECT value FROM settings WHERE key='index_version'").fetchone()[0] != INDEX_VERSION:
                    raise Unsupported("Index version changed; explicit migration is required")
            self.provider_id = "sqlite:" + self.db.execute("SELECT value FROM settings WHERE key='store_id'").fetchone()[0]
        except Exception:
            self.db.close()
            raise

    @contextlib.contextmanager
    def _transaction(self, write=False):
        with self._lock:
            self.db.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            try:
                yield
                self.db.execute("COMMIT")
            except BaseException:
                self.db.execute("ROLLBACK")
                raise

    def close(self):
        with self._lock:
            self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def capabilities(self) -> dict:
        return {"protocol": PROTOCOL, "provider_id": self.provider_id,
                "search_modes": ["keyword", "structured"], "revision_tracking": True,
                "writes": True, "index_version": INDEX_VERSION,
                "optional_operations": ["put", "delete", "export", "reindex"]}

    def _revision(self, scope: Scope, now: float) -> str:
        gen = self.db.execute("SELECT generation FROM generations WHERE tenant=? AND collection=?",
                              (scope.tenant, scope.collection)).fetchone()
        expired = self.db.execute("SELECT MAX(expires_at) FROM documents WHERE tenant=? AND collection=? AND expires_at<=?",
                                  (scope.tenant, scope.collection, now)).fetchone()[0]
        index = self.db.execute("SELECT value FROM settings WHERE key='index_generation'").fetchone()[0]
        # Opaque token. New documents, access changes, deletes, expiration and
        # explicit reindexing invalidate retrieval, including previous empty hits.
        return digest([self.provider_id, scope.to_dict(), gen[0] if gen else 0, expired, INDEX_VERSION, index])

    def revision(self, scope: Scope) -> str:
        if not isinstance(scope, Scope):
            raise InvalidRequest("Scope required")
        with self._transaction():
            return self._revision(scope, time.time())

    def _bump(self, scope: Scope):
        self.db.execute("INSERT INTO generations VALUES (?,?,1) ON CONFLICT(tenant,collection) DO UPDATE SET generation=generation+1",
                        (scope.tenant, scope.collection))

    @staticmethod
    def _visible(row, scope, now):
        return (row["expires_at"] is None or row["expires_at"] > now) and (
            row["owner"] == scope.principal or scope.principal in json.loads(row["readers"]) or "*" in json.loads(row["readers"]))

    def _row(self, scope, document_id):
        return self.db.execute("SELECT * FROM documents WHERE tenant=? AND collection=? AND document_id=?",
                               (scope.tenant, scope.collection, document_id)).fetchone()

    def _passage(self, row, scope, start, end):
        content = row["content"]
        return {"scope": scope.to_dict(), "document_id": row["document_id"], "revision": row["revision"],
                "title": row["title"], "source": row["source"], "metadata": json.loads(row["metadata"]),
                "text": content[start:end], "start_char": start, "end_char": end,
                "start_line": content.count("\n", 0, start) + 1,
                "end_line": content.count("\n", 0, max(start, end - (1 if content[start:end].endswith("\n") else 0))) + 1,
                "expires_at": row["expires_at"]}

    def read(self, request: ReadRequest) -> dict:
        if not isinstance(request, ReadRequest):
            raise InvalidRequest("ReadRequest required")
        with self._transaction():
            row = self._row(request.scope, request.document_id)
            if row is None or not self._visible(row, request.scope, time.time()):
                raise NotFound("Document not found")
            if request.revision is not None and row["revision"] != request.revision:
                raise Conflict("Document revision changed")
            end = len(row["content"]) if request.end_char is None else request.end_char
            if end > len(row["content"]) or request.start_char > end:
                raise InvalidRequest("Requested range is outside the document")
            return self._passage(row, request.scope, request.start_char, end)

    def search(self, request: SearchRequest) -> dict:
        if not isinstance(request, SearchRequest):
            raise InvalidRequest("SearchRequest required")
        if request.mode not in self.capabilities()["search_modes"]:
            raise Unsupported("Local provider supports keyword and structured search; use a semantic-capable adapter")
        with self._transaction():
            now = time.time()
            revision = self._revision(request.scope, now)
            offset = 0
            key = digest({**request.to_dict(), "cursor": None})
            if request.cursor:
                try:
                    cursor = loads(base64.urlsafe_b64decode(request.cursor.encode()).decode())
                    if set(cursor) != {"revision", "key", "offset"} or cursor["key"] != key or cursor["revision"] != revision:
                        raise Conflict("Search cursor expired or belongs to another query/scope")
                    offset = cursor["offset"]
                    if type(offset) is not int or not 0 <= offset <= 1_000_000:
                        raise InvalidRequest("Invalid cursor offset")
                except Conflict:
                    raise
                except Exception as exc:
                    raise InvalidRequest("Invalid search cursor") from exc
            params = [request.scope.tenant, request.scope.collection]
            base = " FROM chunks c JOIN documents d ON d.id=c.document "
            where = " WHERE d.tenant=? AND d.collection=? "
            if request.mode == "keyword":
                terms = re.findall(r"\w+", request.query, flags=re.UNICODE)
                if not terms:
                    return {"scope": request.scope.to_dict(), "revision": revision, "hits": [], "next_cursor": None}
                if len(terms) > 64:
                    raise InvalidRequest("Keyword query has more than 64 terms")
                # Treat user text literally, not as an executable FTS expression.
                match = " OR ".join('"' + t.replace('"', '""') + '"' for t in dict.fromkeys(terms))
                base += " JOIN chunks_fts ON chunks_fts.rowid=c.id "
                where += " AND chunks_fts MATCH ? "
                params.append(match)
                score, order = "bm25(chunks_fts)", "rank ASC,d.document_id ASC,c.ordinal ASC"
            else:
                where += " AND c.ordinal=0 "
                score, order = "0", "d.document_id ASC,c.ordinal ASC"
            # Only return authorized, nonexpired rows. Filtering in this trusted
            # provider occurs before constructing hits/cursors or exposing scores.
            rows = self.db.execute("SELECT d.*,c.start_char,c.end_char," + score + " AS rank" + base + where + " ORDER BY " + order, params)
            hits, skipped = [], 0
            for row in rows:
                if not self._visible(row, request.scope, now):
                    continue
                meta = json.loads(row["metadata"])
                if any(k not in meta or canonical(meta[k]) != canonical(v) for k, v in request.filters.items()):
                    continue
                if skipped < offset:
                    skipped += 1
                    continue
                hit = self._passage(row, request.scope, row["start_char"], row["end_char"])
                hit.update(score=row["rank"], score_kind="sqlite_bm25_lower_is_better" if request.mode == "keyword" else "unranked")
                hits.append(hit)
                if len(hits) > request.limit:
                    break
            next_cursor = None
            if len(hits) > request.limit:
                next_cursor = base64.urlsafe_b64encode(canonical({"revision": revision, "key": key, "offset": offset + request.limit}).encode()).decode()
            return {"scope": request.scope.to_dict(), "revision": revision, "hits": hits[:request.limit], "next_cursor": next_cursor}

    def _index(self, doc_id, title, content):
        self.db.executemany("INSERT INTO chunks(document,ordinal,title,content,start_char,end_char,start_line,end_line) VALUES (?,?,?,?,?,?,?,?)",
                            ((doc_id, n, title, piece, a, b, la, lb) for n, piece, a, b, la, lb in chunks(content)))

    def put(self, scope: Scope, document: DocumentInput, *, expected_revision: str | None = None) -> dict:
        if not isinstance(scope, Scope) or not isinstance(document, DocumentInput):
            raise InvalidRequest("Scope and DocumentInput required")
        if expected_revision is not None:
            text(expected_revision, "expected_revision", 256)
        revision = digest(document.to_dict())
        with self._transaction(write=True):
            old = self._row(scope, document.document_id)
            if old and old["owner"] != scope.principal:
                raise NotFound("Document not found")
            if old and expected_revision is None:
                # Exact idempotent re-ingestion is safe; differing updates need CAS.
                if old["revision"] == revision:
                    return {"document_id": document.document_id, "revision": revision, "changed": False}
                raise Conflict("Updating a document requires its expected revision")
            if expected_revision is not None and (old is None or old["revision"] != expected_revision):
                raise Conflict("Document revision changed")
            if old and old["revision"] == revision:
                return {"document_id": document.document_id, "revision": revision, "changed": False}
            if old:
                self.db.execute("DELETE FROM documents WHERE id=?", (old["id"],))
            cur = self.db.execute("INSERT INTO documents(tenant,collection,document_id,owner,readers,revision,title,source,content,metadata,expires_at,updated) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (scope.tenant, scope.collection, document.document_id, scope.principal, canonical(document.readers), revision,
                 document.title, document.source, document.text, canonical(document.metadata), document.expires_at, time.time()))
            self._index(cur.lastrowid, document.title, document.text)
            self._bump(scope)
        return {"document_id": document.document_id, "revision": revision, "changed": True}

    def delete(self, scope: Scope, document_id: str, *, expected_revision: str) -> dict:
        text(document_id, "document_id", 256)
        text(expected_revision, "expected_revision", 256)
        with self._transaction(write=True):
            row = self._row(scope, document_id)
            if row is None or row["owner"] != scope.principal:
                raise NotFound("Document not found")
            if row["revision"] != expected_revision:
                raise Conflict("Document revision changed")
            self.db.execute("DELETE FROM documents WHERE id=?", (row["id"],))
            self._bump(scope)
        return {"document_id": document_id, "deleted": True}

    def export(self, scope: Scope) -> Iterator[dict]:
        # Owner-only portable sources (not retrieved snippets, permissions of
        # other users, provider IDs, or cached/model-generated answers).
        with self._transaction():
            rows = self.db.execute("SELECT * FROM documents WHERE tenant=? AND collection=? AND owner=? ORDER BY document_id", (scope.tenant, scope.collection, scope.principal))
            for row in rows:
                yield DocumentInput(row["document_id"], row["title"], row["content"], row["source"], json.loads(row["metadata"]), json.loads(row["readers"]), row["expires_at"]).to_dict()

    def rebuild_index(self) -> dict:
        """Rebuild from durable originals; invalidates retrieval, not document IDs."""
        with self._transaction(write=True):
            self.db.execute("DELETE FROM chunks")
            for row in self.db.execute("SELECT id,title,content FROM documents"):
                self._index(row["id"], row["title"], row["content"])
            self.db.execute("INSERT INTO chunks_fts(chunks_fts) VALUES ('integrity-check')")
            self.db.execute("UPDATE settings SET value=CAST(value AS INTEGER)+1 WHERE key='index_generation'")
        return {"rebuilt": True, "index_version": INDEX_VERSION}


def from_options(options: dict) -> LocalKnowledgeProvider:
    if set(options) != {"directory"}:
        raise InvalidRequest("Local provider requires only directory")
    return LocalKnowledgeProvider(options["directory"])
