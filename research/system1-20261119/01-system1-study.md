# System 1 decisions and completed work are separate endpoints

David Beveridge. AI-assisted technical report, 19 November 2026.

## Finding

In a frozen 32-proposal synthetic diagnostic, Jev identified all 12 benign task-scope
conflicts and returned uncertain for all eight missing-target proposals. It also
flagged four of 12 investigator-labeled permissible actions as conflicting. The
limited deterministic baseline missed four conflicts and left eight uncertain
proposals unalerted, while blocking none of the permissible proposals.

Advisory semantics would add useful signals in this cohort, with four false alarms.
Hard intervention would wrongly block those same four permissible proposals.
Neither policy was deployed: the live experiment classified proposal data only.
No worker, proposed action, review queue or accepted task artifact was exercised.
These observations do not establish improved task completion or productivity.

## Frozen methods and amendment

The [protocol](PROTOCOL.md), [cases](cases.json), [configuration](config.json) and
[original freeze](freeze.json) define 12 permissible proposals, 12 benign scope
conflicts and eight missing-target proposals about an independently authored
synthetic sum-helper repair. Four conflicts concern documentation edits, four
concern edits under `other/`, and four concern an identical test after two supplied
failures. The failure histories are fixtures, not executed test runs. No private
captures, repository source, credentials or original private task context were
sent. All 32 private V4 cases remain excluded; [intake metadata](evidence/private-intake.json)
documents that boundary. The public cohort is a convenience sample with one
investigator-authored rubric, no independent annotation and little within-category
variation. It was designed after historical failure analysis.

Arm D uses the actual gW reducer with isolated temporary state and explicit
reference plugins at source commit `1aa0a149a0a785a3845d71f09d0ead92f4c552ab`.
A literal rule denies fixture edits under `other/`; an exact-action retry rule
requires approval after two supplied failures. Semantic goals are disabled.
These checks deliberately omit other task constraints. The retained baseline
and its original runner were unchanged. Its initial runner-commit deviation is
preserved in [the checkpoint record](evidence/premeasurement-checkpoint.json).

The first resumed preflight stopped before smoke because a billed-input bound
could not be verified; [the failed gate](evidence/resume-gates.json) is retained.
Before any inference, the owner removed the 75,000-input-token ceiling. The
[amendment](AMENDMENT.md) and [dispatch freeze](dispatch-freeze.json) retain the
64-request and US$0.50 incremental inference ceilings. No cases, labels or grading
were changed. The typed Choice question, criteria and runner were committed before
measurement. Input contains task, action and prior-failure count, without gold
labels, case identifiers or rationales. One independent synthetic smoke had to
pass before proceeding once over the 32 frozen cases. There was no prompt tuning,
retry, top-up, fallback model or proposed action execution.

## Typed route, budget and observed identity

The [official Decisions API](https://openrouter.ai/docs/api/api-reference/alphadecisions/submit-a-decisions-request)
accepts typed Choice questions at `POST /api/alpha/decisions`. The
[endpoint listing](https://openrouter.ai/api/v1/models/typesafe/jev-1.14/endpoints)
advertised TypeSafe, `typesafe/jev-1.14-20261014`, US$0.042 per million input tokens
and zero output price. The runner verified current metadata and authenticated
funds, then pinned the TypeSafe provider with fallback disabled and maximum input,
output and request rates. Each successful response confirmed the advertised served
model and provider and returned a typed answer and usage. The owner's personal
credential was injected directly into the runner environment; it is not in the
public evidence. Account identifiers and balances are also omitted.

The runner reserved US$0.015 per inference request, covering the published full
262,144-token prompt maximum at that price and zero output rate. All 33 calls
reserved US$0.495. A persisted ledger reserves before dispatch, counts all runner
HTTP requests toward 64, halts on errors or unknown outcomes, and refuses rerun
when its ledger already exists. No input-token cap was enforced after the owner's
amendment. The unchanged original protocol remains available to expose this change.

## Classifier results

The [live ledger](evidence/live-results.json), [per-case grades and summary](evidence/live-summary.json)
and [offline analysis script](scripts/analyze_live.py) retain the complete comparison.
The smoke is excluded from the following 32-case results and included in all usage.

| Gold label | n | Supporting prediction | Conflicting prediction | Uncertain prediction |
|---|---:|---:|---:|---:|
| Supporting | 12 | 8 | 4 | 0 |
| Conflicting | 12 | 0 | 12 | 0 |
| Uncertain | 8 | 0 | 0 | 8 |

Exact label agreement was 28/32. There were zero conflict-as-supporting misses,
four false conflict alarms and eight uncertain predictions. All uncertain
predictions matched the missing-target gold cases. No response was malformed,
absent or an API error. Confidence was recorded but never used as a threshold.

All four false alarms were implementation edits to `fixture/helper0.py` through
`fixture/helper3.py`. The task names `fixture/math.py`; the investigator's gold
rubric permits supporting helper edits under `fixture/`. The model disagreed with
that rubric. This ambiguity and the repeated case structure limit interpretation:
these are four scored false alarms under the frozen labels, not four independent
real-world demonstrations of bad judgment. No post-hoc relabeling was performed.

## Deterministic baseline and policy projections

[The frozen offline baseline](evidence/offline-results.json) allowed all 12
permissible proposals, denied four outside-directory edits, required approval for
four exhausted retries, allowed four prohibited documentation edits, and allowed
eight missing-target proposals without an alert. It has no semantic label, so it
is compared by disposition rather than fabricated classifier accuracy.

| Measure | D baseline | H hard projection | A advisory projection |
|---|---:|---:|---:|
| Wrong blocks on 12 supporting proposals | 0 | 4 | 0 |
| Conflicts allowed without a semantic alert | 4 | 0 | 0 |
| Conflicts allowed with an alert | 0 | 0 | 4 |
| Missing-target cases without an alert/review signal | 8 | 0 | 0 |
| Supporting proposals with false conflict alerts | 0 | 4 denials | 4 alerts |

The advisory projection contains 16 semantic alerts on otherwise allowed proposals:
four real scope conflicts, four false alarms and eight uncertainty/review signals.
It retains the baseline's four denials and four approval requirements. Alerts do
not imply correction; the four documentation conflicts remain permitted with advice.
No actual review queue delivery or human response was measured.

For H, the frozen max-severity reducer projects 16 denials, eight approvals and
eight allows. A protocol/implementation discrepancy is explicit: its reducer can
upgrade a deterministic retry approval to denial, while the prose describes adding
semantics only to otherwise allowed proposals. Four retry cases are affected.
We preserve and report the actual frozen mapping rather than silently changing it.
Both mappings leave deterministic restrictions intact; neither was installed as
live authorization. The 18 artificial-label controls validate that authority mapping
only, not classifier quality, native hooks or review delivery.

## Requests, tokens, cost and latency

There were **33 inference requests**: one smoke and 32 measured cases, with zero
retries. The runner made **36 HTTP requests** including three metadata/account
checks. Total usage was **16,689 input tokens, 1,518 output tokens and
US$0.000700938 actual reported incremental inference cost**. Evaluation alone used
16,225 input tokens, 1,472 output tokens and US$0.000681450; the remainder is smoke.
Reported costs sum exactly to the ledger total and match the listed input rate.
No credits were added. API-reported inference charges exclude subscription,
research orchestration, local compute and credit-purchase fees.

Measured serial request elapsed time had median 263.90 ms and range
211.09–1,070.57 ms across the 32 cases. These client timings include transport and
JSON processing; they are not a controlled service-latency benchmark. Original
local reducer timings are instrumentation only. No worker completion, accepted
artifact or productivity outcome was measured.

## Historical interpretation and limits

The [historical summaries](evidence/historical-screenings.json) distinguish the
24-attempt screening from the 36-attempt extension. Each Jev arm verified 4/6 in
each cohort; controls verified 6/6. In that historical notation A is baseline,
B adds context, C adds supervision, and D adds supervision plus context. Extension
Clef arms verified 6/6 and took longer than control. Four first blocked patches
passed the unchanged grader offline. They add zero live successes: offline patch
application removes the intervention and execution bottleneck being studied.
These are selected prior aggregate records, not new capture regrades.

The new result supports testing semantic alerts separately from authorization.
Its small, repetitive, synthetic cohort cannot rank production models, establish
representative error rates, prove delivered reviews, or show that alerts improve
completed work. The original private diagnostic and interactive slots remain unrun.
The [reproduction instructions](REPRODUCE.md) distinguish live labels, deterministic
replay, historical aggregates and policy projections. No site deployment or default
branch change is part of this evidence publication.
