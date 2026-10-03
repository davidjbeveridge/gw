"""Small peer-call facades; no import of a peer's implementation."""
from gw_supervisor.api import service, runtime


def Store(home):
    return service('state').open(home)


Supervisor = runtime


def publish_component(*args, **kwargs):
    from gw_supervisor.api import optional_service
    observer = optional_service('observation')
    if observer is not None:
        return observer.publish_component(*args, **kwargs)


def enabled(config):
    from gw_supervisor.api import optional_service
    observer = optional_service('observation')
    return observer is not None and observer.enabled(config)


def trace_repository(*args, **kwargs):
    return service('observation').repository(*args, **kwargs)


def open_service(*args, **kwargs):
    return service('knowledge').open(*args, **kwargs)


def compile_context(*args, **kwargs):
    return service('context').compile(*args, **kwargs)


def inject_context(*args, **kwargs):
    return service('context').inject(*args, **kwargs)


def requirements(value):
    return service('inference').normalize_requirements(value)
