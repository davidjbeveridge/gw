# Known-overhead regression check — October 4, 2026

Reference: GW v0.8.0, commit `4aa76c63c64eef1aa97a1927a4424670d000e994`.
Candidate: the cache/output/runtime fixes in this pull request, measured before the
package-version bump. Model calls: **zero**. No native agent completed a task.

## Measurements

Native measurements are actual CLI pre/post hook subprocess pairs around a fixed
Read proposal. Each arm has five warmups and thirty measured pairs; before/after
order is randomized within each block using seed 71411. Histories are seeded
untimed with 0 or 10,000 synthetic events. The tracing toggle is the only scenario
configuration difference. Both arms use the same Python executable, machine and
source fixtures. This is a shared Linux/Python 3.13 environment, not user hardware.
CPU scheduling noise is visible in the raw samples; do not generalize the absolute
latencies or high percentiles to other machines.

| Initial events | Tracing | Before median pair | After median pair |
|---:|---|---:|---:|
| 0 | Off | 280.99 ms | 250.70 ms |
| 0 | On | 308.38 ms | 263.58 ms |
| 10,000 | Off | 296.97 ms | 254.52 ms |
| 10,000 | On | 341.04 ms | 257.08 ms |

The separate reused-runtime measurements contain sixty measured events, after
five warmups, without an externally held plugin scope. At 10,000 events with
tracing, median API evaluation changed from 17.26 ms to 4.86 ms. That comparison
includes the new automatic composition reuse; it is not equivalent to the earlier
experiment that manually held a scope around the old runtime. Command hooks still
pay process-startup costs. No daemon or persistent cross-process cache was added.

The original 200-line context fixture retained its **11,322-character payload**.
The agent result changed from **25,108 to 12,888 characters**. The duplicate `text`
field is absent; source metadata remains. These are serialized character counts,
not provider token measurements. MCP transports may offer both structured and text
representations; the consuming harness determines model-visible framing.

The deterministic regression in `tests/test_efficiency_fixes.py` sends twenty
identical successful actions through the real supervisor. It now produces two
fixture-classifier invocations rather than forty, with 57 individual goal cache
hits across the remaining nineteen pre/post pairs. A fixture is not evidence of
model accuracy, cost, or real-workflow hit rates. The negative tests change failure
counts, task, scope, model/rubric identity and compiled evidence, and check fresh
authority decisions even when labels are cached.

## Reproduce

Build/install each source revision's core, reference bundle and optional libraries
into separate target directories with pip `--target`. Use a clean Python 3.10+
virtual environment for the subprocess executable; it must not have another GW
installation on its default import path. The replay selects the target with
`PYTHONPATH`, so the plugin entry-point metadata must accompany each target.

```bash
export GW_BENCH_PYTHON=/absolute/path/to/clean-venv/bin/python
export GW_BENCH_BEFORE_SITE=/absolute/path/to/before-site
export GW_BENCH_AFTER_SITE=/absolute/path/to/after-site
export GW_BENCH_OUT=/absolute/path/to/results
python benchmarks/overhead-20261004/replay.py
```

`runtime.json` preserves individual native and warm samples. `surface-before.json`
and `surface-after.json` preserve the serializer measurements. The replay creates
only temporary fixture projects/ledgers, runs sequentially, times out subprocesses,
and performs no model requests or repository resets. No live frontier comparison,
large-corpus knowledge test, cached approval reuse, or causal savings claim is
included in this check.
