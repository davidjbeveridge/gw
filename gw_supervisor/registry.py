"""Explicit installed-plugin composition and per-runtime service lifecycle."""
from __future__ import annotations

import contextlib
import contextvars
import copy
import importlib.metadata
import re
from pathlib import Path
from .api import API_VERSION, Plugin, PluginError
from .util import digest, read_json

GROUP = 'gw_supervisor.plugins'
# A distribution preset is data, not a core dependency or implementation import.
STANDARD = ('gw.state', 'gw.policy', 'gw.inference', 'gw.governance', 'gw.context',
            'gw.knowledge', 'gw.observe', 'gw.learning', 'gw.sync', 'gw.harness',
            'gw.gateway', 'gw.agent')
CURRENT = contextvars.ContextVar('gw_plugin_manager', default=None)
NAME = re.compile(r'^[A-Za-z][A-Za-z0-9_.-]{0,127}$')


def selection(config):
    if not isinstance(config, dict) or set(config) - {'profile', 'enable', 'disable'}:
        raise PluginError('runtime accepts profile, enable and disable only')
    profile = config.get('profile', 'standard')
    if profile not in {'standard', 'minimal'}:
        raise PluginError('Unknown runtime profile')
    enable, disable = config.get('enable', []), config.get('disable', [])
    for entries in (enable, disable):
        if not isinstance(entries, list) or len(entries) > 64 or any(not isinstance(x, str) or not NAME.fullmatch(x) for x in entries):
            raise PluginError('Invalid runtime plugin IDs')
        if len(set(entries)) != len(entries):
            raise PluginError('Duplicate plugin IDs')
    if set(enable) & set(disable):
        raise PluginError('A plugin cannot be enabled and disabled together')
    return tuple(sorted(((set(STANDARD) if profile == 'standard' else set()) | set(enable)) - set(disable)))


def installed():
    result = {}
    for ep in importlib.metadata.entry_points(group=GROUP):
        result.setdefault(ep.name, []).append(ep)
    return result


class PluginManager:
    """Validate one composition before instantiating any service.

    A selected service has exactly one owner. Replacement is disable-old plus
    enable-new; dependency errors and incompatible versions are not ignored.
    """
    def __init__(self, plugins, *, origins=None):
        self.plugins = {}
        for p in plugins:
            if not isinstance(p, Plugin) or p.api_version != API_VERSION:
                raise PluginError('Incompatible plugin API')
            if not NAME.fullmatch(p.id) or not isinstance(p.version, str) or not p.version:
                raise PluginError('Invalid plugin identity/version')
            if p.id in self.plugins:
                raise PluginError('Duplicate plugin: ' + p.id)
            self.plugins[p.id] = p
        self.origins = origins or {}
        self.owners, self.sections, self.commands, self.tools = {}, {}, {}, {}
        for p in self.plugins.values():
            for name, factory in p.services.items():
                if not NAME.fullmatch(name) or name in self.owners or not callable(factory):
                    raise PluginError('Duplicate or invalid service: ' + name)
                self.owners[name] = p.id
            for spec in p.config:
                if not isinstance(spec.name, str) or not NAME.fullmatch(spec.name) or any(not part for part in spec.name.split('.')) or spec.name.split('.')[0] in {'version', 'mode', 'locked', 'clients', 'runtime', '_runtime_manifest'} or not callable(spec.validate) or any(spec.name == n or spec.name.startswith(n + '.') or n.startswith(spec.name + '.') for n in self.sections):
                    raise PluginError('Duplicate or reserved config section: ' + spec.name)
                self.sections[spec.name] = spec
            for command in p.commands:
                if not NAME.fullmatch(command.name) or command.name in {'plugins', 'runtime', 'config', 'init', 'trust'} or command.name in self.commands:
                    raise PluginError('Duplicate or reserved command: ' + command.name)
                self.commands[command.name] = command
            for tool in p.tools:
                if not NAME.fullmatch(tool.name) or tool.name in self.tools:
                    raise PluginError('Duplicate or invalid tool: ' + tool.name)
                self.tools[tool.name] = tool
        for p in self.plugins.values():
            for dependency in p.requires:
                if dependency not in self.owners:
                    raise PluginError(p.id + ' requires service ' + dependency)
        self.order = self._order()
        self.evaluators = self._evaluators()
        self.instances, self.constructing, self.closed = {}, set(), False

    def _order(self):
        dependencies = {p.id: {self.owners[s] for s in p.requires} - {p.id} for p in self.plugins.values()}
        return self._topological(dependencies)

    @staticmethod
    def _topological(dependencies):
        pending = {k: set(v) for k, v in dependencies.items()}; result = []
        while pending:
            ready = sorted(k for k, v in pending.items() if not v)
            if not ready:
                raise PluginError('Plugin dependency/order cycle: ' + ', '.join(sorted(pending)))
            for key in ready:
                result.append(key); pending.pop(key)
            for v in pending.values():
                v.difference_update(ready)
        return result

    def _evaluators(self):
        values, owners = {}, {}
        for p in self.plugins.values():
            for e in p.evaluators:
                if e.phase not in {'local', 'plan', 'authority'} or e.name in values or not callable(e.evaluate):
                    raise PluginError('Duplicate or invalid evaluator: ' + e.name)
                values[e.name], owners[e.name] = e, p.id
        ranks = {'local': 0, 'plan': 1, 'authority': 2}
        dependencies = {}
        for key, e in values.items():
            if any(x not in values for x in e.after):
                raise PluginError('Unknown evaluator dependency: ' + key)
            if any(ranks[values[x].phase] > ranks[e.phase] for x in e.after):
                raise PluginError('Evaluator cannot run after a later phase')
            dependencies[key] = set(e.after) | {k for k, v in values.items() if ranks[v.phase] < ranks[e.phase]}
        return [(owners[k], values[k]) for k in self._topological(dependencies)]

    def defaults(self):
        result = {}
        for name, section in self.sections.items():
            target = result
            parts = name.split('.')
            for part in parts[:-1]:
                target = target.setdefault(part, {})
            target[parts[-1]] = copy.deepcopy(section.default)
        return result

    def validate(self, config):
        containers = {}
        for name in self.sections:
            parts = name.split('.')
            for i in range(1, len(parts)):
                containers.setdefault('.'.join(parts[:i]), set()).add(parts[i])
        for path, allowed in containers.items():
            value = config
            for part in path.split('.'):
                value = value[part]
            if not isinstance(value, dict) or set(value) - allowed:
                raise PluginError('Unowned plugin configuration under ' + path)
        with self.activate():
            for name, section in self.sections.items():
                value = config
                for part in name.split('.'):
                    value = value[part]
                section.validate(value)
            for key in self.order:
                validator = self.plugins[key].validate
                if validator:
                    validator(copy.deepcopy(config))

    def require(self, name):
        if self.closed:
            raise PluginError('Plugin runtime is closed')
        if name not in self.owners:
            raise PluginError('No configured provider for ' + name)
        if name in self.constructing:
            raise PluginError('Service construction cycle: ' + name)
        if name not in self.instances:
            self.constructing.add(name)
            try:
                with self.activate():
                    self.instances[name] = self.plugins[self.owners[name]].services[name](self)
            finally:
                self.constructing.remove(name)
        return self.instances[name]

    def optional(self, name):
        return self.require(name) if name in self.owners else None

    def manifest(self):
        return [{'id': key, 'version': self.plugins[key].version, 'api': self.plugins[key].api_version,
                 'origin': self.origins.get(key, 'injected'), 'services': sorted(self.plugins[key].services)} for key in self.order]

    def describe(self):
        return {'api_version': API_VERSION, 'plugins': self.manifest(), 'commands': sorted(self.commands),
                'tools': sorted(self.tools), 'configuration': [{'name': k, 'project': v.project, 'agent_writable': v.agent_writable, 'host_only': list(v.host_only)} for k, v in sorted(self.sections.items())], 'evaluators': [{'plugin': p, 'name': e.name, 'phase': e.phase} for p, e in self.evaluators]}

    @contextlib.contextmanager
    def activate(self):
        token = CURRENT.set(self)
        try:
            yield self
        finally:
            CURRENT.reset(token)

    def close(self):
        if self.closed:
            return
        self.closed = True
        errors = []
        for instance in reversed(list(self.instances.values())):
            close = getattr(instance, 'close', None)
            if callable(close):
                try: close()
                except Exception as exc: errors.append(type(exc).__name__)
        self.instances.clear()
        if errors:
            raise PluginError('Plugin cleanup failed: ' + ', '.join(errors))


def discover(ids):
    available = installed(); plugins = []; origins = {}; distributions = {}
    for key in ids:
        found = available.get(key, [])
        if len(found) != 1:
            raise PluginError('Expected one installed plugin ' + key + '; install the reference bundle or correct runtime selection')
        ep = found[0]
        value = ep.load()()
        if not isinstance(value, Plugin) or value.id != key:
            raise PluginError('Entry point identity does not match plugin: ' + key)
        plugins.append(value)
        # Several domain entry points usually share one distribution. Parse its
        # METADATA once per discovery, not twice for every plugin.
        dist = ep.dist
        if dist is not None and id(dist) not in distributions:
            meta = dist.metadata
            distributions[id(dist)] = (meta.get('Name'), meta.get('Version'))
        name, version = distributions.get(id(dist), (None, None))
        origins[key] = {'distribution': name, 'version': version, 'entry_point': ep.value}
    return PluginManager(plugins, origins=origins)


def manager_from_document(config, client='generic'):
    from .config import CORE_DEFAULTS, merge
    if not isinstance(config, dict) or not isinstance(config.get('clients', {}), dict):
        raise PluginError('Invalid global/client configuration')
    base = merge(CORE_DEFAULTS, {k: v for k, v in config.items() if k != 'clients'})
    effective = merge(base, config.get('clients', {}).get(client, {}))
    ids = selection(effective.get('runtime', {}))
    active = CURRENT.get()
    if active is not None and tuple(sorted(active.plugins)) == ids and not active.closed:
        return active
    return discover(ids)


def manager_for(home=None, client='generic'):
    from .config import home_path
    root = home_path(str(home) if home is not None else None)
    return manager_from_document(read_json(root / 'config.json', {}), client)


def current_manager():
    return CURRENT.get() or manager_for()
