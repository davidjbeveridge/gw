# v0.2 validation

The suite now contains **121 tests**: 113 dependency-free tests and eight optional
LiteLLM callback tests. The added tests cover arbitrary model families, modality
and operation separation, subscription/proxy boundaries, declarative billing and
availability, allowlists, classifier abstention, project inheritance, media
payload preservation, CLI selection and explicit-list catalog import. The
release workflow runs the same six OS/Python combinations and three installer
jobs, plus a separate actual-LiteLLM job, before publishing.

No paid inference or native subscription executor was used. Selection plans and
callback routing are tested separately from provider execution. The following
section preserves the v0.1 baseline evidence.

# Validation

## Executed checks

Build `00d8daf995ee7988000576097cee4d902e1a1f33` passed all 11 jobs in [the validation run](https://github.com/davidjbeveridge/gw/actions/runs/36925260629): six OS/Python combinations, three fresh-installer tests, the LiteLLM callback suite, and source packaging. The subsequent release commit changes release automation/documentation only and reruns the same gates before creating a tag.

The suite contains 78 tests: 73 core/adapter/API tests and five optional LiteLLM tests. Core CI skips the optional five; the dedicated LiteLLM job installs the real package and runs those five. There were no skipped core or Node bridge tests in the successful CI matrix.

The first cross-platform run caught a canonical project-path bug affecting pinned task lookup on macOS/Windows. It was fixed at the storage API boundary, not hidden by weakening the tests, and a regression test was added.

The offline suite exercises configuration precedence/locks, project trust snapshots, session pinning, deterministic decisions, classifier abstention and malformed output, cumulative drift, retry/repetition tracking, duplicate event IDs, project isolation, credential-pattern redaction, protocol-aware JSON compression, response preservation, usage accounting, native hook codecs, non-destructive/idempotent bootstrap, a real Node-to-Python OpenCode bridge, CLI subprocesses and authenticated HTTP requests.

CI runs Python 3.10/3.13 on Ubuntu, macOS and Windows. Node 22 checks the generated OpenCode module and runs a pre-tool denial through the Python adapter. Providers are mocked; the HTTP integration tests use a real loopback server with temporary state. The LiteLLM job uses the actual SDK callback base class but makes no paid inference calls.

## Not established

- Real licensed-agent sessions in every Claude/Codex/Gemini/Cursor/Copilot release.
- Jev accuracy or latency on the user's workload, or live provider credentials.
- Caveman token savings, recovery fidelity or live provider compatibility.
- Enterprise tamper resistance or existing Warden compatibility.
- Equivalent task quality after routing to a cheaper model.

The installer tests use isolated state, download the package by the tested commit SHA, verify the installed command, bootstrap all adapters twice and confirm unchanged settings on the second pass. Run a real deny canary inside each agent after installation or vendor updates. Fixtures validate our protocol handling; they do not prove runtime hook delivery.

## Reference contracts consulted (2026-10-01)

- Claude: https://code.claude.com/docs/en/hooks
- Codex: https://developers.openai.com/codex/hooks
- Gemini: https://geminicli.com/docs/hooks/reference/
- Cursor: https://cursor.com/docs/hooks
- Copilot: https://docs.github.com/en/copilot/reference/hooks-reference
- VS Code: https://code.visualstudio.com/docs/agent-customization/hooks
- OpenCode classic: https://opencode.ai/docs/plugins/
- LiteLLM: https://docs.litellm.ai/docs/proxy/call_hooks
- Caveman: https://docs.caveman.so/docs/proxy/litellm

These URLs are references, not pinned runtime version guarantees. Native approval support, tool coverage, context delivery and timeout behavior vary. A future conformance runner should launch installed runtimes with harmless fixtures and publish a tested-version matrix.
