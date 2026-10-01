# Extension contracts

## Generic tool event

Send JSON on stdin to `gw hook generic pre`, or authenticated `POST /v1/events`:

```json
{
  "type": "tool.before",
  "id": "call-17",
  "client": "my-harness",
  "session": "workflow-123",
  "project": "/absolute/project/path",
  "tool": "browser.fill_secret",
  "input": {"credential_ref": "credential://vault/account"},
  "operation": "credential.inject",
  "target": {"origin": "https://trusted.example", "field": "password"}
}
```

Result includes `decision`, `reason`, `advice`, `labels`, `policy_hash`, `session_id` and metrics. Honor deny before executing. Suspend for approve; do not translate it to allow in a noninteractive host. Send `tool.after` with the same ID, input, output and explicit `success: true|false|null` after execution. Unknown success is not evidence for determinization.

The API is a local development contract, not an enterprise identity attestation. A caller can assert its own session/project. External integration must bind identity, device, workload and capabilities at a trustworthy executor before using it as an access control system.

## Model interception

`POST /v1/model/request` accepts:

```json
{
  "context": {"client":"custom", "session":"workflow-123", "project":"/absolute/project/path", "id":"request-7"},
  "format": "chat",
  "payload": {"model":"configured-alias", "messages":[{"role":"user", "content":"Do the work"}]}
}
```

Supported formats: `chat`, `anthropic`, `responses`, `image`, `video`, `speech`, `transcription`, `embedding`, `rerank`, `decision`. Nontext formats are not subjected to text-only transforms. See [Models](MODELS.md) for endpoint compatibility and typed selection plans. On allow/advice, the caller may send the returned payload upstream. On deny/approve, stop before inference. The complementary response endpoint accepts the same context and a complete response payload. v0.1 returns it unchanged and records provider-reported usage. Never treat a post-stream audit as pre-delivery enforcement.

## DecisionProvider

Python protocol is in `gw_supervisor.providers`. Built-ins:

- `systemone` (legacy `jev` alias): TypeSafe-compatible typed choice endpoint, including OpenRouter, Kev and Laya.
- `openai`: a Chat Completions endpoint using explicit JSON-schema/JSON mode and exact local label validation.
- `http`: vendor-neutral `POST {version:1,model,state,goals}` → `{decisions:{goal_id:choice_key}}`.
- `off`: no semantic classification; deterministic policy remains available.

Remote responses must include valid configured choices for every question. A malformed/oversized/failed result is an abstention/error, never an implicit semantic allow. There are bounded timeouts and no recursive frontier-model rescue loop. Global config chooses the endpoint, key environment variable and model; projects cannot redirect these.

## AuthorityProvider / future Warden adapter

Configure globally:

```json
{"authority":{"endpoint":"https://authority.example/authorize", "key_env":"GW_AUTHORITY_TOKEN", "timeout_seconds":2}}
```

Request: `{version:1,session,task,policy_hash,event,inference_plan}`. The event is redacted. Response:

```json
{"decision":"approve", "reason":"Approval required for this resource", "receipt":{"reference":"opaque-receipt-id"}}
```

Allowed decisions: allow, deny, approve. The engine applies the most restrictive local/external result. Network or validation failure denies. Unsupported nonempty `constraints`/`obligations` deny, rather than falsely claiming enforcement.

A Warden-specific adapter would translate this contract into Warden's real identity, policy, capability, receipt and executor interfaces. No Warden source/API schema was consumed for this implementation and no existing Warden compatibility is asserted. This is an intentionally narrow extension seam, not an access platform.

## CredentialInjector

A Python protocol only. The executor receives an opaque credential reference, origin/field binding, session/task and authorization evidence. It resolves/injects the secret locally and returns a receipt without the secret. Possible future implementations: password-manager integration, native browser credential broker, enterprise vault.

Not implemented: clipboard storage, vault reads, browser password injection, legal-terms acceptance. Clipboard paste is not intrinsically secret-safe; other local processes, history and synchronization can expose it. Do not hide actions or rewrite provider refusals. Authorized deterministic workflows should live in explicit executors, with independent permissions and auditable outcomes.

## InferenceExecutor

`POST /v1/inference/select` and `gw models select` return an operation-specific
plan for any configured proxy/harness/adapter. `InferenceExecutor.execute(plan,
request)` is the Python extension contract for non-proxy hosts. No executor is
automatically launched. Native authentication, response/artifact types, media job
polling, cancellation, idempotency and authorization remain the executor's job.
The selection result is not a capability token or authorization to execute tools.

See [Decision setup](DECISION_SETUP.md) for endpoint/credential onboarding and protocol limits.
