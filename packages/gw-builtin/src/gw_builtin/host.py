"""Reference plugins use only the public runtime configuration facade."""
from gw_supervisor.api import configuration

def __getattr__(name):
    if name.startswith('_'):
        raise AttributeError(name)
    return getattr(configuration(), name)
