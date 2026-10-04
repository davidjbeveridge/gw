#!/usr/bin/env bash
# Pinned, user-local installation. No sudo, shell-profile edits, API keys or daemon.
set -euo pipefail
REF="${GW_REF:-v0.8.1}"
KNOWLEDGE=0
CONTEXT=0
PLUGINS=0
AGENT_TOOLS=0
ARGS=()
for arg in "$@"; do
  if [ "$arg" = "--context" ]; then CONTEXT=1; elif [ "$arg" = "--knowledge" ]; then KNOWLEDGE=1; CONTEXT=1; elif [ "$arg" = "--plugins" ]; then PLUGINS=1; elif [ "$arg" = "--agent-tools" ]; then AGENT_TOOLS=1; CONTEXT=1; ARGS+=("--agent-tools"); else ARGS+=("$arg"); fi
done
case "$REF" in *[!A-Za-z0-9._-]*) echo 'Invalid GW_REF' >&2; exit 1;; esac
ROOT="${GW_INSTALL_DIR:-${XDG_DATA_HOME:-$HOME/.local/share}/gw}"
BIN="${GW_BIN_DIR:-$HOME/.local/bin}"
PYTHON=""
for candidate in python3 python3.13 python3.12 python3.11 python3.10; do
  if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; assert sys.version_info >= (3,10)' >/dev/null 2>&1; then
    PYTHON="$(command -v "$candidate")"; break
  fi
done
if [ -z "$PYTHON" ]; then
  echo 'gw needs Python 3.10+. Install Python, then rerun this command.' >&2
  exit 1
fi
mkdir -p "$ROOT" "$BIN"
if [ -e "$BIN/gw" ] || [ -L "$BIN/gw" ]; then
  if [ "$(readlink "$BIN/gw" 2>/dev/null || true)" != "$ROOT/venv/bin/gw" ]; then
    echo "Refusing to overwrite an unrelated $BIN/gw. Set GW_BIN_DIR to another directory." >&2
    exit 1
  fi
fi
"$PYTHON" -m venv "$ROOT/venv"
"$ROOT/venv/bin/python" -m pip install --disable-pip-version-check --no-input --upgrade \
  "https://github.com/davidjbeveridge/gw/archive/${REF}.zip"
"$ROOT/venv/bin/python" -m pip install --disable-pip-version-check --no-input --upgrade \
  "https://github.com/davidjbeveridge/gw/archive/${REF}.zip#subdirectory=packages/gw-builtin"
if [ "$CONTEXT" = 1 ]; then
  "$ROOT/venv/bin/python" -m pip install --disable-pip-version-check --no-input --upgrade \
    "https://github.com/davidjbeveridge/gw/archive/${REF}.zip#subdirectory=packages/gw-context"
fi
if [ "$KNOWLEDGE" = 1 ]; then
  "$ROOT/venv/bin/python" -m pip install --disable-pip-version-check --no-input --upgrade \
    "https://github.com/davidjbeveridge/gw/archive/${REF}.zip#subdirectory=packages/gw-knowledge"
fi
if [ "$PLUGINS" = 1 ]; then
  for package in gw-observe gw-learning gw-sync; do
    "$ROOT/venv/bin/python" -m pip install --disable-pip-version-check --no-input --upgrade \
      "https://github.com/davidjbeveridge/gw/archive/${REF}.zip#subdirectory=packages/${package}"
  done
fi
if [ "$AGENT_TOOLS" = 1 ]; then
  "$ROOT/venv/bin/python" -m pip install --disable-pip-version-check --no-input --upgrade \
    "gw-supervisor[agent] @ https://github.com/davidjbeveridge/gw/archive/${REF}.zip"
fi
ln -sfn "$ROOT/venv/bin/gw" "$BIN/gw"
"$ROOT/venv/bin/gw" bootstrap "${ARGS[@]}"
printf '\nInstalled %s\n' "$BIN/gw"
case ":${PATH}:" in *":${BIN}:"*) ;; *) printf 'For the gw command in this shell: export PATH="%s:$PATH"\n' "$BIN";; esac
printf 'Next: gw doctor. Restart agents; in Codex, review /hooks.\n'
