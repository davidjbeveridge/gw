# Benchmarks: what would count as evidence?

[Handbook](README.md) · [Executed validation](VALIDATION.md) · [References](REFERENCES.md)

**No gW efficacy, cost-saving, or task-quality benchmark has been published.** The test suite checks implementation behavior. It is not a performance study. This document specifies how we intend to evaluate the design without turning someone else's result into our headline.

## Start with a falsifiable claim

“gW improves agents” is too broad. Useful claims are narrower: an exact retry rule prevents redundant attempts without lowering completion rate; a classifier detects specified kinds of drift at an acceptable intervention rate; a context cache avoids repeat retrieval while rejecting stale sources; a routing policy reduces total cost on a stated workload without an unacceptable quality loss.

Each claim needs an independent success criterion, a baseline, and a budget. If a cheaper run fails the task, it is not a successful optimization. If a reviewer had to rescue it, that intervention belongs in the record.

## Compare the same work

Use paired tasks from a versioned, redistributable fixture set. Keep agent version, worker model, provider, system/project instructions, tool availability, repository state, and network fixtures constant unless one of them is the variable under test.

Record the gW commit, configuration hash, classifier endpoint/model identifier, optional package versions, OS/runtime, hardware where local inference matters, and timestamps. Pin model versions when providers allow it; document moving aliases when they do not. Never call a vendor model update an experimental treatment accidentally.

A useful initial comparison is baseline agent versus baseline plus one feature. Add combinations only after the individual feature is understood. Otherwise a good result cannot tell us which component helped.

## Workloads

| Workload | Independent outcome | Important failure cases |
|---|---|---|
| Bounded code repair | Held-out regression tests and allowed-scope diff review | Missing setup, unrelated refactors, tests that only verify the proposed fix |
| Repeated tool failure | Whether a validated recovery completes the task | Equivalent failures with changed command spelling, false success reporting |
| Browser form fixture | Correct fixture fields and intended stop/submit state | Wrong origin, stale page state, unauthorized external effects |
| Capability routing | Correct operation/result contract and task quality | Chat routed to media, unsupported features, implicit paid fallback |
| Knowledge reuse | Exact evidence/source validity and retrieval work avoided | New relevant documents, edited/deleted sources, revoked readers, expiry |
| Hook enforcement | Attempted controlled action denied before execution | No tool attempt, missing hook, host timeout/fail-open, subagent omissions |

Use local or authorized test environments. No live credentials, production deployments, purchases, or consequential submissions are necessary to evaluate these mechanics.

## Measure quality and overhead together

Report completion rate, quality criteria, interventions, and errors alongside cost and latency. Include unsuccessful runs in the workload totals. A “cost per success” number that omits failed attempts rewards systems that fail cheaply.

Account for worker inference, supervisor classification, retrieval, model-loading/warm-up where applicable, tool calls, and any extra rerouting or repair. Separate input, output, reasoning, provider cache hits/writes, and non-token billing units when the provider exposes them. Do not infer unavailable fields or double-count reasoning already included in output totals.

The current GW store records basic provider-reported input/output totals; it does not collect this complete benchmark breakdown. A benchmark harness must obtain and retain the missing usage evidence independently.

Measure wall-clock task latency and per-decision latency. Distinguish warm local-model performance from first load. Report distributions, not only a best run. Human review has both count and elapsed-time implications; disclose how it was handled.

## Cache experiments need invalidation tests

A warm repeated-query test demonstrates a possible hit, not trustworthy reuse. At minimum, repeat after editing a matched source, adding a new relevant source, deleting a source, revoking access, changing filters, expiring content, changing the index/embedding version, and changing the principal.

Test empty-query-result caching too. An old empty answer must not hide newly ingested knowledge. For an unversioned backend, state the TTL and its limits explicitly. During a provider outage, the current cache must not return stale evidence.

Count avoided search/read operations and assembly latency. A cached packet subsequently inserted into a prompt still consumes context. Do not convert logical byte savings into token savings without the actual model tokenizer or provider usage.

## Classifier experiments need difficult negatives

Include legitimate supporting work, not only obvious bad actions. Installing a required test dependency, reading documentation, or touching an adjacent fixture can be on task even when the root request names a different file.

Separate wrong blocks from requests for review. “Stopped” can conflate a denial with a human escalation; both may prevent execution but have different operating costs. Publish the label definitions, annotator procedure, disagreements, false positives, false negatives, and abstentions.

Evaluate narrow specialist models only on the questions they support. A successful form-action scorer is not evidence of general model-routing or governance capability. Keep calibration claims separate from label accuracy.

## Ablations

Useful comparisons include deterministic rules only; classifier goals added; priority routing versus classifier routing; cold versus warm context cache; request minification alone; and the same stack with a separately configured compressor. Avoid changing every layer at once.

For each experiment, state the counterfactual: what work would the baseline have performed, and which component actually removed it? A reduction caused by dropping relevant context is not equivalent to a reduction from avoiding duplicate extraction.

## Publication requirements

Publish a clear task set, exact configuration, versions, procedure, raw or appropriately sanitized per-run records, aggregation code, inclusion/exclusion rules, and failure examples. Give sample size and uncertainty appropriate to the experiment. Keep a held-out set for policy/model selection; do not tune on the evaluation cases and then present them as independent.

Record external provider outages and hardware differences without silently deleting inconvenient runs. Use reproducible plots/tables derived from committed data. Sensitive tasks need a consented, redacted release process rather than an assertion that anonymization happened.

The README should link to an actual result directory and describe the tested population and setup. Until then, it should say that no benchmark exists. That is the present state.

## What already counts as useful evidence

The [validation record](VALIDATION.md) documents cross-platform, installer, protocol, storage, and MCP checks. The [offline examples](../examples/README.md) demonstrate inspectable behavior. Neither is presented as model quality or measured savings. Contributions can begin with a reproducible failed workflow; a credible result does not require a flattering result.

## Measured overhead corrections

The [October 4 regression check](../benchmarks/overhead-20261004/README.md) records
the cache/output/startup corrections, raw runtime samples, and a bounded replay.
It is a synthetic implementation diagnostic, not a live-agent productivity or
model-token benchmark.
