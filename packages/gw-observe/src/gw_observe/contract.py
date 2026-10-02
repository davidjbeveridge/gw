"""Versioned metadata-only observation contract; OTLP is the export standard.

No LLM calls. No implicit token estimates. Sources stay with their owners.
"""
from __future__ import annotations
import hashlib
import json
import math
import os
import pathlib
import re
import sqlite3
from typing import Protocol, runtime_checkable

PROTOCOL = 'gw.observation/1'
METRICS = ('input_tokens','output_tokens','cache_read_input_tokens','cache_write_input_tokens','reasoning_output_tokens','cost_usd')


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False)


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',', ':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()


def private_dir(path):
    p = pathlib.Path(path).expanduser().absolute()
    if p.is_symlink(): raise ValueError('State directory must not be a symlink')
    p.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name != 'nt': p.chmod(0o700)
    return p


def connect(path):
    p = pathlib.Path(path)
    if p.is_symlink(): raise ValueError('Database must not be a symlink')
    try:
        fd = os.open(p, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600); os.close(fd)
    except FileExistsError: pass
    if os.name != 'nt': p.chmod(0o600)
    db = sqlite3.connect(p, timeout=2, check_same_thread=False)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('PRAGMA busy_timeout=2000')
    return db


def text(value, field, limit=1024):
    if not isinstance(value,str) or not value or len(value)>limit or '\0' in value:
        raise ValueError('Invalid '+field)
    return value


def finite(value, field):
    if type(value) not in (int,float) or not math.isfinite(value) or value<0:
        raise ValueError('Invalid '+field)
    return value


def redact(value):
    """Best effort only; capture is opt-in and bounded even after redaction."""
    if isinstance(value,dict):
        return {k: '[REDACTED]' if re.search(r'(?i)(password|secret|token$|api.?key|authorization|cookie)',k) else redact(v) for k,v in value.items()}
    if isinstance(value,list): return [redact(v) for v in value]
    if isinstance(value,str):
        return re.sub(r'(?i)(?:Bearer\s+\S+|\b(?:sk|rk)-[\w-]{12,}|\bgh[pousr]_[\w]{15,}|(?:password|secret|api[_-]?key|token)\s*[=:]\s*[^\s,;]+)', '[REDACTED]',value)
    return value


def normalize_usage(raw, provider='generic'):
    """Input/output are totals; cache and reasoning are subsets, never additions.

    Anthropic reports uncached input separately, so its cache counts are added
    once to obtain the common input total. No tariff or plan pricing is guessed.
    """
    out = {}
    if not isinstance(raw,dict): return out
    def put(name,*keys):
        for key in keys:
            val=raw.get(key)
            if type(val) is int and val>=0: out[name]=val; return
    put('input_tokens','input_tokens','prompt_tokens')
    put('output_tokens','output_tokens','completion_tokens')
    put('cache_read_input_tokens','cache_read_input_tokens','cached_input_tokens')
    put('cache_write_input_tokens','cache_creation_input_tokens','cache_write_input_tokens')
    put('reasoning_output_tokens','reasoning_output_tokens','reasoning_tokens')
    for source,field in [('input_tokens_details','cache_read_input_tokens'),('prompt_tokens_details','cache_read_input_tokens'),('output_tokens_details','reasoning_output_tokens'),('completion_tokens_details','reasoning_output_tokens')]:
        d=raw.get(source,{})
        key='reasoning_tokens' if field.startswith('reasoning') else 'cached_tokens'
        if isinstance(d,dict) and type(d.get(key)) is int and d[key]>=0: out[field]=d[key]
    if provider=='anthropic' and 'input_tokens' in out:
        out['input_tokens']+=out.get('cache_read_input_tokens',0)+out.get('cache_write_input_tokens',0)
    for key in ('cost_usd',):
        if type(raw.get(key)) in (int,float) and math.isfinite(raw[key]) and raw[key]>=0:
            out[key]=raw[key]
    if out.get('reasoning_output_tokens',0)>out.get('output_tokens',float('inf')):
        out.pop('reasoning_output_tokens',None)
    if out.get('cache_read_input_tokens',0)>out.get('input_tokens',float('inf')):
        out.pop('cache_read_input_tokens',None)
    return out


def validate_observation(event):
    allowed={'protocol','id','run_id','session_id','parent_id','kind','start_ns','end_ns','attributes','source'}
    if not isinstance(event,dict) or set(event)-allowed: raise ValueError('Invalid observation fields')
    if event.get('protocol')!=PROTOCOL: raise ValueError('Unsupported observation protocol')
    for key in ('id','run_id','kind'): text(event.get(key),key)
    for key in ('session_id','parent_id'):
        if event.get(key) is not None:text(event[key],key)
    for key in ('start_ns','end_ns'):
        if type(event.get(key)) is not int or not 0<=event[key]<=2**63-1: raise ValueError('Invalid timestamp')
    if event['end_ns']<event['start_ns']: raise ValueError('Negative duration')
    if not isinstance(event.get('attributes',{}),dict) or not isinstance(event.get('source',{}),dict): raise ValueError('Expected objects')
    if len(canonical(event))>32768: raise ValueError('Observation exceeds metadata budget')
    return event


@runtime_checkable
class ObservationSink(Protocol):
    def record(self, observation: dict) -> bool: ...


@runtime_checkable
class TraceRepository(ObservationSink, Protocol):
    def bind_session(self, session_id: str, project: str, client: str, *, run_id: str | None=None, config: dict | None=None) -> str: ...
    def start(self, name: str, project: str, **metadata) -> dict: ...
    def finish(self, run_id: str, outcome: str, evidence=None) -> dict: ...
    def run(self, run_id: str) -> dict: ...
    def event(self, event_id: str, *, resolve_source: bool=True) -> dict: ...
    def compare(self, run_ids: list[str]) -> dict: ...
    def close(self) -> None: ...
    def runs(self, limit: int=100) -> list[dict]: ...
    def report(self, run_id: str) -> dict: ...
    def timeline(self, run_id: str, *, offset: int=0, limit: int=200) -> dict: ...


@runtime_checkable
class SourceReader(Protocol):
    def read(self, reference: dict) -> dict: ...
