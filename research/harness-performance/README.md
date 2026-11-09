# Harness performance evidence

[Findings, recommendations, and study bounds](../../docs/HARNESS_RESEARCH.md) ·
[Benchmark protocol](../../docs/BENCHMARKS.md)

This branch consolidates the public evidence from David Beveridge's AI-assisted
gW research. It is separate from the runtime build and releases.

[Results](results.json) contains only the fields needed to inspect the three
headline comparisons:

| Cohort | Evidence included | What can be checked here |
|---|---|---|
| Scope and continuity | 64 masked AI ratings grouped by task, worker, arm, and repeat; arm resource totals | Equal-task mean score difference and aggregate worker-token comparison |
| Configured repository work | Eight attempt summaries with capture status, accepted artifact, time, and tokens | Counts, missing-outcome bounds, and cache-inclusive totals |
| Final context repair | Twelve paired verdicts and worker resource totals, separate calibration and gate record | Pair wins and losses, token difference, and the registered quality and token-saving branches |

Run `python3 research/harness-performance/summarize.py` from the repository
root to recompute those summaries. The stored uncertainty interval,
cache-excluded totals, and audit counts come from the original analyses.
This replay does not regrade answers, re-execute workers, or reproduce results
from raw captures. The private research archive retains the original protocols,
run evidence, failed cohorts, and reproducibility records.

The arms are cohort-specific. In particular, the continuity scaffold is not the
configured gW package, and the repaired context pipeline is not proof of model
uptake in a normal installation. The fresh classifier and semantic interactive
cohorts were prepared but not executed.
