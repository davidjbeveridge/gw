# gw v0.1.0

Initial pre-release of the local-first configurable agent supervisor.

## Install

Python 3.10+ is required. macOS / Linux:

```bash
curl -fsSL https://raw.githubusercontent.com/davidjbeveridge/gw/v0.1.0/install.sh | bash -s -- --all
```

Windows PowerShell:

```powershell
& ([scriptblock]::Create((irm https://raw.githubusercontent.com/davidjbeveridge/gw/v0.1.0/install.ps1))) -All
```

Restart the agents after bootstrap. In Codex, explicitly review/trust hooks with `/hooks`. Existing agent authentication, models and subscription billing are left unchanged.

## Included

- Claude Code, Codex, Gemini CLI, Cursor, Copilot/VS Code Local, and OpenCode classic-v1 bootstrap.
- Dependency-free Python engine with deterministic rules and opt-in Jev or vendor-neutral HTTP classification.
- Client/project inheritance, immutable locks, reviewed project snapshots and pinned task/session policy.
- Cumulative drift, repeated-failure limits, installed-tool recommendations and research-first advice.
- SQLite action metadata, automation candidates after repeated success, usage accounting and idempotency.
- Optional LiteLLM callback, authenticated loopback API, JSON tool-output minification and pinned-task injection.
- Configurable model-alias selection with declared capability checks, and documented optional Caveman upstream setup.
- External-authority and credential-injection extension contracts for future integrations.

## Validation

The suite contains 78 tests: 73 dependency-free tests across Python 3.10/3.13 on Linux, macOS and Windows, plus five callback tests with the actual LiteLLM package in a separate CI job. Fresh installers and repeated bootstrap are exercised on all three operating systems. The OpenCode test includes a real Node-to-Python pre-tool denial.

These are not licensed-agent end-to-end tests, a live Jev accuracy benchmark, a Caveman savings benchmark or an enterprise security audit. The release job runs only after the test, installer and LiteLLM jobs pass.

## Deliberately not implemented

OpenCode v2 adapter, automatic generation/promotion of deterministic tools, a credential vault/browser-password executor, Warden-specific access enforcement and arbitrary rewriting of model responses. Repetition creates reviewable candidates, not self-installed code. Model/provider safety policies are not bypassed.

Jev is opt-in: set `TYPESAFE_API_KEY`, run `gw enable-jev`, and start a new agent session. LiteLLM/Caveman remain optional and separately configured. See README.md and SECURITY.md for setup, support boundaries and the runtime deny canary.
