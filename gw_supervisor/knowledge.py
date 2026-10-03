"""Compatibility import; implementation belongs to the reference plugin bundle."""
import sys
from importlib import import_module
sys.modules[__name__] = import_module("gw_builtin.knowledge")
