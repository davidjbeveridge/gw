"""Runtime configuration: inheritance, locks and reviewed project snapshots.

Defaults and validation of domain fields are supplied by the selected plugins.
No provider, goal, proxy, knowledge, or harness implementation is imported here.
"""
from __future__ import annotations
import copy
import os
import pathlib
import secrets
from typing import Any
from .util import digest, read_json, write_json

EFFECTS = {"allow", "advise", "approve", "deny"}
EVENTS = {"session.start", "tool.before", "tool.after", "model.request", "model.response", "inference.select"}
CORE_DEFAULTS = {"version": 1, "mode": "enforce", "locked": [],
                 "runtime": {"profile": "standard", "enable": [], "disable": []}}


def defaults(manager=None):
    from .registry import current_manager
    manager = manager or current_manager()
    return merge(CORE_DEFAULTS, manager.defaults())


def __getattr__(name):
    if name == 'DEFAULTS':
        return defaults()
    if name == 'PROJECT_KEYS':
        return project_keys()
    raise AttributeError(name)


def project_keys():
    from .registry import current_manager
    return {'version', 'mode', 'clients', 'locked'} | {s.name.split('.')[0] for s in current_manager().sections.values() if s.project}


def check_project_fields(overlay):
    from .registry import current_manager
    for layer in [overlay, *overlay.get('clients', {}).values()]:
        for section in current_manager().sections.values():
            for field in section.host_only:
                if get_path(layer, section.name + '.' + field, _ABSENT) is not _ABSENT:
                    raise ValueError('Project cannot configure host-only field: ' + section.name + '.' + field)

_ABSENT = object()

def home_path(value: str | None = None) -> pathlib.Path:
    return pathlib.Path(value or os.environ.get("GW_HOME") or pathlib.Path.home() / ".config/gw").expanduser().resolve()


def initialize(home: pathlib.Path) -> None:
    home.mkdir(parents=True, exist_ok=True)
    os.chmod(home, 0o700)
    token = home / "api-token"
    # Exclusive creation avoids racing concurrent hook processes.
    try:
        fd = os.open(token, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        pass
    else:
        with os.fdopen(fd, "w") as out:
            out.write(secrets.token_urlsafe(32))
    if not (home / "config.json").exists():
        # Defaults are built in; an empty global file is not needed for hooks.
        return


def project_root(cwd: str | pathlib.Path) -> pathlib.Path:
    p = pathlib.Path(cwd).expanduser().resolve()
    if not p.is_dir():
        raise ValueError("Project directory does not exist")
    for parent in (p, *p.parents):
        if (parent / ".gw.json").exists() or (parent / ".git").exists():
            return parent
    return p


def get_path(obj: Any, path: str, default: Any = None) -> Any:
    for part in path.split("."):
        if not isinstance(obj, dict) or part not in obj:
            return default
        obj = obj[part]
    return obj


def merge(base: dict, overlay: dict) -> dict:
    out = copy.deepcopy(base)
    for key, value in overlay.items():
        if key == "locked":
            out[key] = list(dict.fromkeys([*out.get(key, []), *value]))
        elif isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    for path in base.get("locked", []):
        if get_path(base, path) != get_path(out, path):
            raise ValueError(f"Cannot override locked configuration: {path}")
    return out


def validate(config: dict) -> None:
    from .registry import current_manager, selection
    if config.get('version') != 1 or config.get('mode') not in {'observe', 'enforce', 'baseline'}:
        raise ValueError('Expected version=1 and mode=observe|enforce|baseline')
    if not isinstance(config.get('locked'), list) or any(not isinstance(x, str) for x in config['locked']):
        raise ValueError('locked must contain dotted paths')
    selection(config.get('runtime', {}))
    manager = current_manager()
    allowed = set(CORE_DEFAULTS) | {name.split('.')[0] for name in manager.sections} | {'clients', '_runtime_manifest'}
    if set(config) - allowed:
        raise ValueError('Configuration belongs to an unselected plugin: ' + ', '.join(sorted(set(config)-allowed)))
    manager.validate(config)


def _resolve(home: pathlib.Path, project: pathlib.Path, client: str) -> tuple[dict, str]:
    global_config = read_json(home / "config.json", {})
    if not isinstance(global_config, dict):
        raise ValueError("Global config must be an object")
    base_defaults = defaults()
    unknown = set(global_config) - set(base_defaults) - {"clients"}
    if unknown:
        raise ValueError(f"Unknown global configuration keys: {sorted(unknown)}")
    config = merge(base_defaults, {k: v for k, v in global_config.items() if k != "clients"})
    config = merge(config, global_config.get("clients", {}).get(client, {}))
    snapshot = read_json(home / "projects" / (digest(str(project)) + ".json"), {})
    status = "global_only"
    if snapshot:
        overlay = snapshot["config"]
        check_project_fields(overlay)
        config = merge(config, {k: v for k, v in overlay.items() if k != "clients"})
        config = merge(config, overlay.get("clients", {}).get(client, {}))
        status = "trusted_snapshot"
        source = project / ".gw.json"
        if source.exists() and digest(read_json(source)) != snapshot["source_hash"]:
            status = "project_changed_review_required"
    elif (project / ".gw.json").exists():
        status = "project_untrusted_global_only"
    validate(config)
    return config, status


def _trust_project(home: pathlib.Path, project: pathlib.Path) -> dict:
    source = project / ".gw.json"
    overlay = read_json(source, {})
    if not isinstance(overlay, dict) or set(overlay) - project_keys():
        raise ValueError("Project config contains unsupported keys; provider/authority endpoints are global-only")
    for client_overlay in overlay.get("clients", {}).values():
        if set(client_overlay) - project_keys():
            raise ValueError("Client project override contains global-only keys")
    check_project_fields(overlay)
    # Each client can select a different provider composition. Validate the
    # project against every configured composition, not just the generic one.
    from .registry import manager_for, CURRENT
    global_config = read_json(home / 'config.json', {})
    clients = {'generic', *global_config.get('clients', {}), *overlay.get('clients', {})}
    for client in clients:
        previous = CURRENT.get()
        manager = manager_for(home, client)
        try:
            with manager.activate():
                if set(overlay) - project_keys() or any(set(x) - project_keys() for x in overlay.get('clients', {}).values()):
                    raise ValueError('Project field is not supported by the client composition')
                check_project_fields(overlay)
                base = merge(defaults(), {k: v for k, v in global_config.items() if k != 'clients'})
                candidate = merge(base, global_config.get('clients', {}).get(client, {}))
                candidate = merge(candidate, {k: v for k, v in overlay.items() if k != 'clients'})
                candidate = merge(candidate, overlay.get('clients', {}).get(client, {}))
                validate(candidate)
        finally:
            if manager is not previous: manager.close()
    snapshot = {"project": str(project), "source_hash": digest(overlay), "config": overlay}
    write_json(home / "projects" / (digest(str(project)) + ".json"), snapshot)
    return snapshot


def resolve(home, project, client, *, manager=None):
    # Public callers can supply path aliases; snapshot identity must match the
    # canonical project used by native hooks and the agent interface.
    home, project = home_path(str(home)), project_root(project)
    from .registry import manager_for
    manager = manager or manager_for(home, client)
    with manager.activate():
        return _resolve(home, project, client)


def trust_project(home, project):
    home, project = home_path(str(home)), project_root(project)
    from .registry import manager_for
    manager = manager_for(home)
    with manager.activate():
        return _trust_project(home, project)


def validate_document(document, client='generic'):
    """Resolve and validate proposed operator configuration without writing it."""
    from .registry import manager_from_document, CURRENT
    previous = CURRENT.get()
    manager = manager_from_document(document, client)
    try:
        with manager.activate():
            base = merge(defaults(manager), {k: v for k, v in document.items() if k != 'clients'})
            config = merge(base, document.get('clients', {}).get(client, {}))
            validate(config)
            return config
    finally:
        if manager is not previous:
            manager.close()


def validate_agent_patch(patch, document, client='generic'):
    """Validate host-approved edit capabilities declared by selected plugins.

    This is schema/capability validation, not evidence of human consent. The
    managed agent transport is responsible for its native approval workflow.
    """
    from .registry import manager_from_document, CURRENT
    previous = CURRENT.get()
    manager = manager_from_document(document, client)
    try:
        with manager.activate():
            effective = validate_document(document, client)
            def visit(value, path=''):
                if path in {'mode', 'runtime'}:
                    return
                section = manager.sections.get(path)
                if section:
                    if not section.agent_writable:
                        raise ValueError('Agent cannot administer section: ' + path)
                    if section.agent_validate: section.agent_validate(value, effective)
                    return
                if not isinstance(value, dict) or not value:
                    raise ValueError('Unknown administrative section: ' + path)
                for key, item in value.items():
                    visit(item, path + '.' + key if path else key)
            visit(patch)
    finally:
        if manager is not previous: manager.close()
