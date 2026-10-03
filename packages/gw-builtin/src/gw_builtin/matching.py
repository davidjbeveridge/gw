"""Configured goals and deterministic policy; no runtime permission ownership."""
from __future__ import annotations
import copy
import fnmatch
import shutil
import time
from types import SimpleNamespace
from gw_supervisor.api import (Assessment, Advice, canonical, digest, finite, redact, service)
from .host import get_path

def matches(event: dict, conditions: dict) -> bool:
    """Conjunctive, literal/glob matching; never eval arbitrary policy code."""
    for path, pattern in conditions.items():
        value = canonical(redact(event)) if path == "text" else get_path(event, path)
        if isinstance(pattern, list):
            if value not in pattern:
                return False
        elif isinstance(pattern, str):
            if not isinstance(value, str) or not fnmatch.fnmatchcase(value, pattern):
                return False
        elif value != pattern:
            return False
    return True


