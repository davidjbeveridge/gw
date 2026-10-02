"""Non-destructive MCP registration plus a discoverable GW operations skill.

These registrations expose tools; they do not approve calls or change native
permissions. Managed writes remain deliberate agent actions under user direction.
"""
from __future__ import annotations

import copy
import importlib.resources
import json
import os
import pathlib
import sys
import uuid
from .adapters import ALIASES
from .util import atomic_write, strict_json

BEGIN = '# BEGIN gw-agent managed registration\n'
END = '# END gw-agent managed registration\n'
MARKER = 'gw_supervisor'


def _toml(content):
    try:
        import tomllib
    except ImportError:
        try:
            import tomli as tomllib
        except ImportError as exc:
            raise RuntimeError('Install gw-supervisor[agent] for TOML support on Python 3.10') from exc
    return tomllib.loads(content)


def _owned(entry):
    if not isinstance(entry, dict):
        return False
    argv = [entry.get('command', ''), *entry.get('args', [])]
    if isinstance(entry.get('command'), list):
        argv = entry['command']
    return MARKER in argv and 'agent' in argv and 'serve' in argv


def _codex(content, argv, install):
    parsed = _toml(content)
    old = parsed.get('mcp_servers', {}).get('gw')
    if old is not None and BEGIN not in content:
        raise ValueError('Refusing to overwrite an unrelated Codex MCP server named gw')
    if BEGIN in content:
        if content.count(BEGIN) != 1 or content.count(END) != 1:
            raise ValueError('Malformed GW TOML registration markers')
        a, b = content.index(BEGIN), content.index(END) + len(END)
        if b <= a:
            raise ValueError('Malformed GW TOML registration range')
        if old is not None and not _owned(old):
            raise ValueError('Managed block no longer contains a GW server')
        content = content[:a] + content[b:]
    if install:
        body = '[mcp_servers.gw]\ncommand = ' + json.dumps(argv[0]) + '\nargs = ' + json.dumps(argv[1:]) + '\n'
        content = content.rstrip('\n') + '\n\n' + BEGIN + body + END
    _toml(content)
    return content


def bootstrap_agent_tools(home, agents, project=None, *, user_home=None, install=True, dry_run=False, manage=True):
    home = pathlib.Path(home).resolve()
    user_home = pathlib.Path(user_home or pathlib.Path.home()).resolve()
    project = pathlib.Path(project).resolve() if project else None
    changes, pending = [], []
    for raw_agent in dict.fromkeys(agents):
        agent = ALIASES.get(raw_agent, raw_agent)
        if agent not in {'claude', 'codex', 'gemini', 'cursor', 'copilot', 'opencode'}:
            raise ValueError('Unknown agent for MCP bootstrap')
        argv = [sys.executable, '-m', 'gw_supervisor', '--home', str(home), 'agent', 'serve', '--client', agent]
        if project:
            argv += ['--project', str(project)]
        if manage:
            argv += ['--manage']
        settings = {
            'claude': (user_home / '.claude.json', project / '.mcp.json' if project else None),
            'codex': (user_home / '.codex/config.toml', project / '.codex/config.toml' if project else None),
            'gemini': (user_home / '.gemini/settings.json', project / '.gemini/settings.json' if project else None),
            'cursor': (user_home / '.cursor/mcp.json', project / '.cursor/mcp.json' if project else None),
            'copilot': (pathlib.Path(os.environ.get('COPILOT_HOME', user_home / '.copilot')) / 'mcp-config.json', project / '.github/mcp.json' if project else None),
            'opencode': (pathlib.Path(os.environ.get('XDG_CONFIG_HOME', user_home / '.config')) / 'opencode/opencode.json', project / 'opencode.json' if project else None),
        }
        path = settings[agent][1 if project else 0]
        if path.is_symlink():
            raise ValueError('Refusing a symlinked MCP configuration')
        if agent == 'opencode' and path.with_suffix('.jsonc').exists():
            raise ValueError('OpenCode JSONC config exists; use the printed server definition instead of shadowing it')
        before = path.read_text(encoding='utf-8') if path.exists() else None
        if agent == 'codex':
            after = _codex(before or '', argv, install)
        else:
            parsed = strict_json(before) if before else {}
            if not isinstance(parsed, dict):
                raise ValueError('Existing MCP config must be an object')
            key = 'mcp' if agent == 'opencode' else 'mcpServers'
            config = copy.deepcopy(parsed)
            servers = config.setdefault(key, {})
            if not isinstance(servers, dict):
                raise ValueError('Existing MCP registry is not an object')
            if 'gw' in servers and not _owned(servers['gw']):
                raise ValueError('Refusing to replace an unrelated MCP server named gw')
            if install:
                if agent == 'opencode':
                    entry = {'type': 'local', 'command': argv, 'enabled': True}
                else:
                    entry = {'command': argv[0], 'args': argv[1:]}
                    if agent in {'claude', 'cursor'}:
                        entry['type'] = 'stdio'
                    if agent == 'copilot':
                        entry.update(type='local', tools=['*'])
                servers['gw'] = entry
            else:
                servers.pop('gw', None)
                if not servers and key not in parsed:
                    config.pop(key, None)
            after = json.dumps(config, ensure_ascii=True, indent=2) + '\n'
        if before is None and not install:
            after = None
        pending.append((path, before, after))
        changes.append({'agent': agent, 'path': str(path), 'changed': before != after, 'installed': install,
                        'management_tools': manage, 'native_approval': 'unchanged', 'dry_run': dry_run})
        # Skills have verified discovery locations in these two clients. Other
        # MCP clients use the shared GW prompt and the tool descriptions.
        if agent in {'claude', 'codex'}:
            skill_root = '.claude/skills' if agent == 'claude' else '.agents/skills'
            skill_path = (project or user_home) / skill_root / 'gw/SKILL.md'
            old = skill_path.read_text(encoding='utf-8') if skill_path.exists() else None
            if skill_path.is_symlink() or (old is not None and '<!-- gw-agent operations skill -->' not in old):
                raise ValueError('Refusing to overwrite an unrelated GW skill')
            new = importlib.resources.files('gw_supervisor').joinpath('templates/agent-skill.md').read_text(encoding='utf-8') if install else None
            pending.append((skill_path, old, new))
            changes.append({'agent': agent, 'path': str(skill_path), 'changed': old != new, 'installed': install, 'dry_run': dry_run})
    # Validate all selected registrations first; then atomic per-file writes.
    if not dry_run:
        for path, before, after in pending:
            if before == after:
                continue
            if before is not None:
                atomic_write(home / 'backups' / ('agent-' + uuid.uuid4().hex + '-' + path.name), before)
            if after is None:
                if path.exists():
                    path.unlink()
            else:
                atomic_write(path, after)
    return changes
