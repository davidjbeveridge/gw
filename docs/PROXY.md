# Model-gateway integration

[Handbook](README.md) · [Model registry](MODELS.md) · [API](API.md) · [Troubleshooting](TROUBLESHOOTING.md)

The optional proxy integration adds gW decisions to requests handled by LiteLLM. It is separate from native action hooks. One observes inference; the other observes tools. Neither sees traffic that bypasses it.

## What the callback does

The [callback](../gw_supervisor/litellm.py) projects a bounded model-request event, invokes the same supervisor engine, applies supported request transformations, and passes the result back to LiteLLM. A denial or review requirement raises before that controlled inference call. Completed responses are observed through the success callback; streamed chunks are not rewritten.

This release has no generic response paraphraser, refusal remover, hidden retries, or semantic answer replay. A completion's status and usage can be recorded without interpreting all its text. The callback does not implement a universal refusal detector.

## Install into the same environment

For the standard Unix installation:

```bash
~/.local/share/gw/venv/bin/python -m pip install 'litellm[proxy]'
gw proxy-init --model 'openai/YOUR_MODEL_ID' --output gw-litellm.yaml
```

Replace `YOUR_MODEL_ID` with a supported model you have deliberately configured. For a checkout, use that environment's interpreter. The generated file references `gw_supervisor.litellm.gw_callback`; the gateway process must be able to import it.

Provision `GW_PROXY_KEY` and `GW_UPSTREAM_API_KEY` outside chat and source control. The former authenticates access to your local gateway; the latter authenticates the configured provider. They are different credentials. `--api-key-env NAME` changes the provider credential reference.

For a single, deliberately scoped workflow:

```bash
export GW_PROJECT="$PWD"
export GW_SESSION="my-workflow-001"
~/.local/share/gw/venv/bin/litellm --config gw-litellm.yaml --host 127.0.0.1 --port 4000
```

Point an API-capable client at `http://127.0.0.1:4000/v1`, model `gw-default`, using the local proxy key. `proxy-init` only writes a config; it does not start the service or redirect a client.

A native ChatGPT/Claude subscription setup is not automatically convertible into this API path. Bootstrap leaves it alone. Keep supported subscription execution in its authorized client; do not extract OAuth tokens to make an API example appear free.

## Correlate requests explicitly

For multiple workflows, prefer per-request metadata over fixed process environment:

```json
{
  "metadata": {
    "gw": {
      "project": "/absolute/existing/project",
      "client": "custom",
      "session": "workflow-001",
      "request_id": "inference-017",
      "requirements": {"capabilities": ["code"], "context_tokens": 12000}
    }
  }
}
```

This is a fragment of a LiteLLM request. `project` and `session` are required through metadata or the environment fallback. The default client is `litellm`. To share a native session's state deliberately, all three identity components must match. gW does not infer native session IDs from prompt text.

Use a stable request ID for delivery retries, but a new ID for a new inference attempt. Reusing one ID for different work reuses the first recorded event result. Context-token requirements are caller assertions; the callback does not tokenize every model's input itself.

The additional requirements may strengthen capabilities or context needs and exclude candidates. They cannot change the observed wire operation, modalities, or execution kind to admit an incompatible route.

## Supported contracts

| API `format` | Required operation | Default input → output |
|---|---|---|
| `chat` | `chat` | text → text |
| `responses` | `responses` | text → text |
| `anthropic` | `messages` | text → text |
| `image` | `image.generate` | text → image |
| `video` | `video.generate` | text → video |
| `speech` | `audio.speech` | text → audio |
| `transcription` | `audio.transcribe` | audio → text |
| `embedding` | `embedding` | text → embeddings |
| `rerank` | `rerank` | text → rerank |
| `decision` | `decision` | text → decisions |

These are the direct gW model-request API's formats. The LiteLLM callback has a narrower explicit call-type map; it does not currently map a System One decision call. Unknown LiteLLM call types fail instead of silently bypassing supervision. Provider/media support still depends on the gateway and the chosen endpoint. A named format is not a provider implementation.

The callback inspects a whitelist of model-request fields. It does not inspect every gateway-internal object or uploaded binary. Do not treat its projection or heuristic secret screen as exhaustive inspection of all traffic, especially multipart requests.

## Transformations

All transformations below are opt-in and configured under `proxy`.

**JSON tool-result minification:** remove whitespace outside strings in valid object/array JSON. Invalid or duplicate-key JSON is left alone. Numeric spelling and strings are preserved. Eligible locations include chat tool messages, string-valued Anthropic tool results, and Responses function-call outputs. It does not compact tool schemas or function-call arguments.

**Pinned-task injection:** add the session task in an appropriate instruction location once. The task is stable for that session. This is not retrieval from the knowledge store, dynamic skill loading, or a continually changing progress summary.

**Output cap:** cap the appropriate output-limit field for text-generation formats. A cap can interrupt useful reasoning or code generation. Zero means disabled; it is not a budget of zero tokens.

**Secret-pattern screen:** optionally reject a request when the best-effort redactor detects a matching value. False negatives and false positives are possible. Secrets should stay outside model traffic rather than relying on this screen. Raw response text is not comprehensively scanned by this callback.

**Model alias routing:** apply only a selected compatible proxy target. Opaque provider state, such as signed reasoning and continuation identifiers, remains bound to its current route. A model name cannot turn chat into a video-generation request or launch a native agent.

Text transformations and output caps are not applied to nontext wire formats. [Implementation](../gw_supervisor/proxy.py).

## Responses and streaming

The success logger receives a completed response when LiteLLM supplies one and stores input/output usage fields. It avoids double accounting by request ID. Reasoning, cache-hit, cache-write, image, and dollar metrics are not normalized separately in the current GW store.

The post-success hook returns the response object unchanged. This is an object-preservation guarantee at our integration point, not a claim that JSON or HTTP bytes are never serialized elsewhere in the stack. A post-stream audit cannot block content already delivered.

Request-transform reports measure UTF-8 bytes before/after supported transformations. They do not estimate tokens or imply a percentage cost reduction. [Benchmark plan](BENCHMARKS.md).

## Caveman

[Caveman](https://docs.caveman.so/docs/proxy/litellm) is a separate compressor and recovery system. Start it using its own documentation, inspect its security/data-retention behavior, and obtain the provider-specific base URL:

```bash
caveman snippets litellm --app gw
```

Using the documented OpenAI mount as an example:

```bash
gw proxy-init --model 'openai/YOUR_MODEL_ID' \
  --api-base http://127.0.0.1:8787/w/gw/openai/v1 \
  --output gw-litellm-caveman.yaml
```

The intended sequence is client → LiteLLM with gW callback → separately running Caveman → provider. Use the route printed by your Caveman version. gW does not ship a Caveman SDK or enable lossy compression by default. Start with one transformation layer and measure recovery/quality before stacking compressors.

## Avoid recursive decision calls

The supervisor's classifier must not travel through a gateway callback that asks the same classifier to supervise that call. Use a distinct decision endpoint/deployment without the recursive callback, or an operator-controlled internal routing arrangement. Do not add a caller-controlled “skip governance” header as a shortcut.

Keep ordinary worker inference instrumented. The separate decision path is an internal dependency, not a general-purpose exemption for arbitrary client traffic.

## Common counterexamples

“Set the OpenAI base URL on every agent” is not universal setup. Native subscription authentication, protocol variants, cloud execution, and provider-managed state differ.

“Rewrite a refusal into a tool call” is neither implemented nor a durable execution design. Use explicit authorized executors for known workflows, not hidden response surgery.

“Fewer request bytes means lower cost” ignores tokenization, provider caching, added classifier calls, and changes in task success. Measure completed work, not one transformed payload.
