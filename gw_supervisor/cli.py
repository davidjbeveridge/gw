"""Generic command host. Feature commands are registered by selected plugins."""
from __future__ import annotations
import argparse
import json
import sys
from . import __version__
from .api import PluginError
from .config import home_path, initialize, project_root, resolve, trust_project, defaults
from .registry import installed, manager_for, discover
from .util import write_json


def output(value):
    print(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False))


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    prefix = argparse.ArgumentParser(add_help=False)
    prefix.add_argument('--home')
    prefix.add_argument('--version', action='store_true')
    prefix.add_argument('--transport-plugin', default='gw.harness')
    args, rest = prefix.parse_known_args(argv)
    if args.version:
        print(__version__); return
    home = home_path(args.home)
    scope_parser = argparse.ArgumentParser(add_help=False)
    scope_parser.add_argument('--client', default='generic')
    selected, _ = scope_parser.parse_known_args(rest)
    try:
        if rest and rest[0] == 'init' and '--profile' in rest:
            setup = argparse.ArgumentParser(prog='gw init')
            setup.add_argument('--profile', choices=['minimal', 'standard'], required=True)
            parsed = setup.parse_args(rest[1:])
            target = home / 'config.json'
            if target.exists(): raise ValueError('Configuration already exists')
            initialize(home)
            write_json(target, {'version': 1, 'runtime': {'profile': parsed.profile}})
            output({'created': str(target), 'profile': parsed.profile}); return
        if rest and rest[0] == 'hook':
            transport = discover([args.transport_plugin])
            try:
                if 'hook' not in transport.commands: raise PluginError('Selected transport has no hook codec')
                return transport.commands['hook'].run(['--home', str(home), *rest])
            finally:
                transport.close()
        if rest and rest[0] == 'plugins':
            available = {name: [{'distribution': ep.dist.name if ep.dist else None, 'version': ep.dist.version if ep.dist else None} for ep in eps] for name, eps in installed().items()}
            try:
                manager = manager_for(home, selected.client)
                active = manager.describe(); manager.close()
            except PluginError as exc:
                active = {'error': str(exc)}
            output({'installed': available, 'active': active}); return
        manager = manager_for(home, selected.client)
        try:
            with manager.activate():
                if not rest or rest[0] in {'-h', '--help'}:
                    print('usage: gw [--home PATH] COMMAND\n\nRuntime: config, init, trust, plugins, runtime\n')
                    for name, command in sorted(manager.commands.items()): print(name + (' — ' + command.summary if command.summary else ''))
                    return
                command = rest[0]
                if command == 'runtime':
                    if rest[1:] not in ([], ['inspect']): raise ValueError('Use gw runtime inspect')
                    output(manager.describe()); return
                if command in {'config', 'init', 'trust'}:
                    parser = argparse.ArgumentParser(prog='gw ' + command)
                    parser.add_argument('--project', default='.' if command != 'init' else None)
                    parser.add_argument('--client', default='generic')
                    parser.add_argument('--defaults', action='store_true')
                    parsed = parser.parse_args(rest[1:]); initialize(home)
                    if command == 'config':
                        if parsed.defaults: output(defaults())
                        else:
                            config, status = resolve(home, project_root(parsed.project), parsed.client)
                            output({'status': status, 'config': config})
                    elif command == 'trust':
                        result = trust_project(home, project_root(parsed.project))
                        output({'trusted_project': result['project'], 'source_hash': result['source_hash'], 'applies_to': 'new sessions'})
                    else:
                        target = project_root(parsed.project)/'.gw.json' if parsed.project else home/'config.json'
                        if target.exists(): raise ValueError('Configuration already exists')
                        write_json(target, {'version': 1}); output({'created': str(target)})
                    return
                if command not in manager.commands:
                    raise PluginError('No selected plugin provides command: ' + command)
                return manager.commands[command].run(['--home', str(home), *rest])
        finally:
            manager.close()
    except (ValueError, OSError, KeyError, TypeError, RuntimeError) as exc:
        print('gw: ' + str(exc), file=sys.stderr)
        raise SystemExit(1)


def parser():
    """Deprecated parser facade for the reference command bundle."""
    from importlib import import_module
    return import_module('gw_builtin.cli').parser()
