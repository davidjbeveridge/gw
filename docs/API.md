# HTTP and Python API

[Handbook](README.md) · [Extension contracts](EXTENSIONS.md) · [CLI](CLI.md) · [Standalone knowledge contract](../packages/gw-knowledge/ADAPTERS.md)

This reference describes the current interfaces, not a future universal harness API. `gw serve` wraps the same synchronous engine used by native hooks. It does not execute tools or selected inference plans.

## Start and authenticate

```bash
gw serve --port 7777
```

The service binds `127.0.0.1` only. Its bearer token is `$GW_HOME/api-token`, default `~/.config/gw/api-token`. Use a real HTTP client; browser-Origin requests are rejected and no CORS access is provided. `GET /healthz` is the only unauthenticated route and reports service/version, not state.

For a local health check:

```bash
curl --fail --silent --show-error http://127.0.0.1:7777/healthz
```

Do not expose this development server publicly. Supplied client/session/project identities are host assertions, not enterprise workload identities. An authenticated local caller can select an existing project path. Strong multi-user access control belongs outside this development facade.

## Endpoints

| Method / path | Input | Result |
|---|---|---|
| GET `/healthz` | None | Minimal service/version |
| GET `/v1/status` | Bearer auth | Recorded session/candidate/usage summary |
| POST `/v1/events` | Normalized event | Supervisor verdict |
| POST `/v1/inference/select` | `{context, requirements}` | Verdict plus typed selection plan |
| POST `/v1/model/request` | `{context, payload, format}` | Verdict plus supported request transformations |
| POST `/v1/model/response` | `{context, payload}` | Audit verdict plus unchanged response object |
| POST `/v1/knowledge` | `{context, method, request}` | Optional knowledge facade; host assigns scope |

POST bodies must be `application/json`, include a valid Content-Length, and fit within 4,194,304 bytes. Transfer-Encoding is not supported. The server applies a socket timeout; it is not a streaming inference proxy. JSON must have no duplicate keys or non-finite values.

HTTP 200 means the evaluation completed—not that an action is allowed. Inspect `decision`. Authentication failures return 401; unknown paths 404; invalid body size 413; unsupported content type 415; handled invalid requests/policies 400; unexpected/internal failures 503. Error bodies suppress internal payload details. There is no automatic retry contract for failed calls.

## Normalized events

Every event needs `type`, `client`, `project`, and `session`. `project` must identify an existing directory. `id` is optional but should be supplied by integrations for reliable deduplication.

```json
{
  "type": "tool.before",
  "id": "tool-017",
  "client": "my-harness",
  "project": "/absolute/existing/project",
  "session": "workflow-001",
  "tool": "browser.submit",
  "input": {"form_id": "application"},
  "operation": "application.submit",
  "target": {"origin": "https://jobs.example.test"}
}
```

This is a template; replace the path with a real directory and the semantic fields with evidence supplied by your host. The generic API preserves additional JSON fields for rules and classification. It does not attest that the claimed origin or operation is true.

| Event type | Additional input | Role |
|---|---|---|
| `session.start` | Optional `task` string | Pin a task when no explicit/project task was already set |
| `tool.before` | Nonempty `tool`, object `input` | Evaluate before execution |
| `tool.after` | `tool`, object `input`, optional `output`, `success` boolean/null | Record outcome and evaluate returned data |
| `model.request` | Model/feature projection; `requirements` for registry selection | Evaluate inference; use the model-request endpoint for transformations |
| `model.response` | Model, optional normalized `usage`, status metadata | Record response observations |
| `inference.select` | `requirements` | Select a capability without executing it |

There is no `stop`, `compact`, `subagent.start`, or arbitrary lifecycle event accepted by this version. Native input names are translated by adapters before this engine sees them.

### Identity and idempotency

A session is keyed by client + canonical project + native session ID. An event result is keyed by that session + event ID + event type. Use the same ID for one tool's pre/post pair; use a new ID for another action attempt.

A duplicated event returns the first recorded result with `duplicate: true`. It is not reauthorized against later policy. Therefore **event IDs are delivery identities, not reusable permission tokens**. Do not reuse them for new work or altered payloads.

### Verdict shape

A typical result contains:

```json
{
  "version": 1,
  "decision": "allow",
  "reason": "No supervisor objection; native permissions still apply",
  "reasons": [],
  "advice": [],
  "labels": {},
  "session_id": "opaque-internal-session-id",
  "policy_hash": "opaque-policy-hash",
  "config_status": "global_only",
  "metrics": {"failures": 0, "successes": 0, "drift": 0, "observations": 0}
}
```

The IDs above are illustrative, not literal hash output. Conditional fields include `classifier_status`, `classifier_cached`, `classifier_error`, `recommended_tool`, `automation_candidate`, `model`, `inference`, `authority`, `would_decision`, and `duplicate`.

Possible classifier states include `disabled`, `no_pinned_task`, `scored`, and `unavailable`. Absence of `labels` is not a safe semantic verdict. `metrics` is the state seen before this event's update.

Your executor must stop on deny, suspend on approve, and still perform its native checks on allow/advice. Post-action blocking is converted to advice because the action already happened.

## Python engine

```python
from pathlib import Path
from gw_supervisor.engine import Supervisor

project = Path.cwd().resolve()
with Supervisor() as supervisor:
    result = supervisor.evaluate({
        "type": "tool.before",
        "id": "example-action-1",
        "client": "custom",
        "project": str(project),
        "session": "example-session-1",
        "tool": "Read",
        "input": {"file_path": "README.md"},
    })
    if result["decision"] in {"deny", "approve"}:
        raise PermissionError(result["reason"])
    # Continue through the host's normal authorization and execution path.
```

This uses your normal state and can call an enabled classifier. For a no-network, temporary-state demonstration, run [supervision_demo.py](../examples/supervision_demo.py). Do not execute a command simply because the JSON was parsed successfully.

`Supervisor(home=...)` selects another state directory. Injectable `classifier` and `authority` objects support tests and integrations. Their shape follows [providers.py](../gw_supervisor/providers.py). Always close the supervisor; the context manager does that for you.

## Model selection

POST `/v1/inference/select` with:

```json
{
  "context": {
    "client": "custom",
    "project": "/absolute/existing/project",
    "session": "workflow-001",
    "id": "selection-001"
  },
  "requirements": {
    "operation": "image.generate",
    "input_modalities": ["text"],
    "output_modalities": ["image"],
    "capabilities": [],
    "execution_kinds": ["proxy", "adapter"]
  }
}
```

A selected `inference.plan` contains `model_id`, `provider`, `model`, `operation`, `execution: {kind, target}`, and billing metadata. The top-level verdict still applies. `selection_only: true` is intentional: this route returns a plan.

Other selection states include unavailable, abstained, classifier_unavailable, and blocked_by_policy. `eligible`, `rejected`, and the optional classifier shortlist make the decision inspectable. [Model reference](MODELS.md) defines policy and all requirement fields.

## Model request/response interception

The request endpoint accepts a complete supported model payload, a context with identity, and a `format`:

```json
{
  "context": {
    "client": "custom",
    "project": "/absolute/existing/project",
    "session": "workflow-001",
    "id": "model-017"
  },
  "format": "chat",
  "payload": {
    "model": "configured-proxy-alias",
    "messages": [{"role": "user", "content": "Explain the change."}]
  }
}
```

On allow/advice, forward the returned `payload` through your authorized provider client. On deny/approve, do not send it. The output also includes a request ID and byte-count transformation report. `format` defaults to `chat`; accepted formats and operation mappings are in [Proxy integration](PROXY.md#supported-contracts).

Send the completed response to `/v1/model/response` with the **same context ID** and its payload. The response is returned unchanged as an object while metadata/usage is recorded. The endpoint does not stream or undo delivered content. A failed provider call does not become a successful usage record merely by sending an empty response.

Calling `/v1/events` directly with `model.request` evaluates an event projection; it does not run the transformation pipeline. Use the dedicated endpoint or `gw_supervisor.proxy.process_request` when you need that behavior.

## Knowledge facade

With the optional package installed and configured:

```json
{
  "context": {"project": "/absolute/existing/project", "client": "codex"},
  "method": "context",
  "request": {"query": "decision provider failures", "max_chars": 8000}
}
```

The GW facade assigns tenant/collection/principal from trusted configuration. A `scope` inside `request` is rejected. It wraps the result with `protocol: gw.knowledge/1` but is **not** the same request envelope as the standalone HTTP service.

The standalone service accepts `{protocol, method, request}`, including its host-bound scope. Its schema, capabilities, errors, and optional write behavior are defined in the [knowledge adapter guide](../packages/gw-knowledge/ADAPTERS.md). Its loopback server uses a separate token and route. Do not swap the two endpoints while preserving the wrong envelope.

A context result contains source passages and provenance, not a generated answer. A cache hit revalidates according to provider capabilities. Nothing in that result authorizes a tool action.

## External authority

At supported pre-action boundaries, the optional authority receives a redacted event, pinned task, policy hash, session, and proposed inference plan when present. A valid reply contains allow/deny/approve, a reason, and optionally a receipt. Unsupported obligations or constraints are denied by the built-in adapter.

The current HTTP implementation is an integration seam, not a signed-capability verifier. Your actual executor must enforce any external access system's identity, scope, expiry, and receipt semantics. [Authority contract](EXTENSIONS.md#authorityprovider--future-warden-adapter).

## Counterexamples to avoid

Do not regard HTTP 200, exit 0, or `selection_only` as permission to execute. Do not reuse event IDs as cache keys for new actions. Do not expose the local API as a multi-tenant service without identity binding. Do not send tool output as a trusted task or policy update. Do not treat a knowledge receipt as a standing approval.
