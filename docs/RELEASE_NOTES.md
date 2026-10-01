# gw v0.2.0 — capability-first model selection

The supervisor no longer assumes a cheap/medium/frontier model hierarchy.

## Added

- A configurable model registry separating model identity, operation, input/output modalities, capability tags, execution backend, billing and declared availability.
- Deterministic preference selection or a Jev/HTTP selector over compatible candidates, with explicit abstention and no implicit paid fallback.
- Typed plans for proxy aliases, subscription-backed native harnesses, and custom adapters. Arbitrary model/provider/capability names are supported.
- `gw models list`, `gw models select`, and authenticated `POST /v1/inference/select`.
- Explicit-list OpenRouter catalog import, including nontext modalities; imports stay disabled until reviewed.
- Protocol-aware media/audio/embedding/rerank/decision request routing. No text-only transforms on media payloads.
- `decision.model_ref` for the supervisor's own named classifier; external authority receives the proposed inference plan.
- Opaque provider state remains bound to its current model route.

## Install or update

Python 3.10+, macOS/Linux:

```bash
curl -fsSL https://raw.githubusercontent.com/davidjbeveridge/gw/v0.2.0/install.sh | bash -s -- --all
```

Restart agents after updating. Existing authentication and subscription billing remain unchanged. Start new sessions to use updated configuration. The v0.1 legacy alias router remains available when the new registry is empty.

## Scope and validation

121 tests: 113 dependency-free tests plus eight optional real-LiteLLM callback tests. CI exercises Python 3.10/3.13 on Linux/macOS/Windows, fresh installers on all three systems, and the actual LiteLLM package separately. Release publication is gated on those jobs.

Selection is implemented; arbitrary native subscription/custom executor launching is not. Subscription quota is not converted into API credit. Availability/remaining quota are operator declarations, not live account monitoring or atomic budget enforcement. No live model keys, media generation, subscription sessions or provider quality/savings benchmarks were used for this release.

See docs/MODELS.md for configuration and precise support boundaries.
