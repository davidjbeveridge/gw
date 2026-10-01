# Validation

The offline suite exercises configuration precedence/locks, project trust snapshots, session pinning, deterministic decisions, classifier abstention and malformed output, cumulative drift, retry/repetition tracking, duplicate event IDs, project isolation, credential-pattern redaction, protocol-aware JSON compression, response preservation, usage accounting, native hook codecs, non-destructive/idempotent bootstrap, a real Node-to-Python OpenCode bridge, CLI subprocesses and authenticated HTTP requests.

CI is configured for Python 3.10/3.13 on Ubuntu, macOS and Windows. Node 22 checks the generated OpenCode module and runs a pre-tool denial through the Python adapter. Providers are mocked; the HTTP integration tests use a real loopback server with temporary state.

Not established by these tests:

- Real licensed-agent sessions in every Claude/Codex/Gemini/Cursor/Copilot release.
- Jev accuracy or latency on the user's workload, or live provider credentials.
- Caveman token savings, recovery fidelity or live provider compatibility.
- Enterprise tamper resistance or existing Warden compatibility.
- Equivalent task quality after routing to a cheaper model.

The install smoke test should use an isolated HOME, verify the installed `gw --version`, bootstrap all adapters twice and confirm unchanged settings on the second pass. Run a real deny canary inside each agent after installation or vendor updates. Fixtures validate our protocol handling; they do not prove runtime hook delivery.

Reference contracts consulted for this release (2026-10-01):

- Claude: https://code.claude.com/docs/en/hooks
- Codex: https://developers.openai.com/codex/hooks
- Gemini: https://geminicli.com/docs/hooks/reference/
- Cursor: https://cursor.com/docs/hooks
- Copilot: https://docs.github.com/en/copilot/reference/hooks-reference
- VS Code: https://code.visualstudio.com/docs/agent-customization/hooks
- OpenCode classic: https://opencode.ai/docs/plugins/
- LiteLLM: https://docs.litellm.ai/docs/proxy/call_hooks
- Caveman: https://docs.caveman.so/docs/proxy/litellm

These URLs are references, not pinned runtime version guarantees. In particular, native approval support, tool coverage, context delivery and timeout behavior vary. A future conformance runner should launch installed runtimes with harmless fixtures and publish a tested-version matrix.
