# What we learned about gW

[Project README](../README.md) · [Benchmark protocol](BENCHMARKS.md) ·
[Curated evidence and replay](https://github.com/davidjbeveridge/gw/tree/research/harness-performance/research/harness-performance)

David Beveridge initiated and directed this AI-assisted research. These studies
test different treatments and endpoints. Their samples should not be pooled.
This write-up reports engineering evidence, including failed gates and missing
outcomes; it is not an independently reviewed productivity study.

## Scope and continuity

A structured scope and handoff scaffold was compared with ordinary tools and
notes in 64 staged episodes: eight selected tasks in four Python repositories,
two worker models, and two fresh repeats per arm and model. Masked AI-rated
quality improved by **21.68 points** on a 100-point scale (task-bootstrap 95%
interval **15.08 to 28.52**). Nine scaffold episodes met the useful-progress
threshold versus zero baseline episodes. The scaffold retained 20 handoffs
versus none. Reported worker tokens were 642,666 versus 679,350, or 5.4% lower.

Only two of 192 milestones ended in native completion. Guards prevented new
inference at 28 of 64 middle milestones. The grader saw truncated action evidence
in every episode, and a persisted handoff made partial evidence easier to assess.
The result supports retaining bounded progress evidence across session changes;
it does not isolate better task execution from better visibility of that work.
There was no independent human adjudication.

## Configured repository work

Two real repository tasks, two fresh repeats per arm, and the same Sol worker in
OpenCode produced eight measured attempts. Baseline delivered **4/4** accepted
artifacts. Configured gW delivered **2/4**, with one known failure and one missing
capture; its acceptance fraction is bounded by **50–75%**. The engineering
criterion failed. The study recorded 66 gW hook events, but **zero**
`gw_context_compile` calls. Semantic supervision was disabled.

Cache-inclusive worker tokens fell from 270,841 to 254,627 (**−5.99%**).
Uncached input plus all output rose from 70,393 to 73,763 (**+4.79%**). These
are different measures and neither prices a subscription. Two selected tasks do
not support a population estimate. Keep installation, actual activation, model
consumption, and accepted work as separate checks.

## Source-backed answers

The original 24-pair lexical comparison accepted **7/24** baseline versus
**6/24** gW answers. gW used about 12% less input but failed its quality and
resource gate. A subsequent eight-pair calibration-repair cohort still favored
the baseline (**8/8** versus **5/8**, with **12.63% more** treatment tokens).
These are separate cohorts, retained as negative evidence.

The final context repair was frozen before a fresh evaluation: 12 questions
from four repository lineages, with three each on identity, callers, defaults,
and assertions. Separate calibration accepted 3/4. A conventional source selector
and the repaired pipeline had equivalent source access and owner facts, and a
3,000-character serialized packet ceiling. Actual packet sizes differed. Each
worker made one bounded answer call without tools.

Baseline accepted **8/12** and the repair accepted **10/12**. There were two
treatment-only gains, no baseline-only losses, and eight jointly accepted pairs.
The repair passed the registered quality branch (at least 10/12 accepted, no
baseline-only loss, at least two net gains); it failed the 15% token-saving branch.
Evaluation tokens increased from **11,968 to 15,089 (+26.08%)**. Tokens per
accepted answer increased **0.86%** including failed attempts. A separate post-hoc
correction for an ambiguous identity label gives 9/12 versus 11/12; it does not
replace the primary grades. One gain delivered missing source; the other occurred
where baseline already had supporting source and abstained. This comparison does
not isolate the effect of ranking, chunking, or budgeting.

An offline replay in a relocated export reproduced all 28 calibration and
evaluation verdicts and the full analysis. It ran 101 control tests and verified
144 frozen interactive files without model or network calls. That is reproduction
of the recorded result and setup, not a new model replication.

## Overhead and accounting

[PR #1](https://github.com/davidjbeveridge/gw/pull/1) merged decision dependency
caching, removal of duplicated context output, and runtime reuse. The
[overhead check](https://github.com/davidjbeveridge/gw/tree/f3041b552f9c0d086d860b28b39b63183bf35971/benchmarks/overhead-20261004) measures specific
subprocess and serializer fixtures. For example, a 200-line source payload was
unchanged while the serialized result fell from 25,108 to 12,888 characters.
Reuse classification only when its task, action, evidence, policy, and model
dependencies match; resolve current authority separately. A fixture hit rate is
not a real-workflow hit rate.

The historical accounting audit reconciled 152 captured comparative worker
attempts, 682 native usage records and 216 session IDs without evidence of
orchestration contamination in retained worker totals. Historical process and
provider provenance is incomplete. An earlier 443,118-token app-counter stop
occurred before experimental answers. The V4 context cohort used 30,552 measured
tokens including calibration; design, orchestration, and review are separate
research costs. They still consume resources.

## What to keep and what to remove first

1. **Keep a verified minimum.** Pin scope, use exact rules and retry limits for
   known problems, and record effects the host actually exposes. Check a harmless
   pre-tool denial on each adapter and path you rely on. Avoid duplicate adapters
   or native plus imported hooks for the same event.
2. **Add evidence when there is a source question.** Retain exact source spans,
   provenance, and access and revision checks. Reuse bounded handoffs across
   sessions. Avoid repeated context injection and full transcript carryover when
   a smaller artifact supplies the needed evidence.
3. **Treat extra judgment as opt-in.** Remove unused tools and model routes from
   the active setup. Consider dropping routine critic, reviewer, and classifier
   passes that have no named decision or demonstrated value. Keep checks that
   prove the task outcome and human approval where the action requires it.
   Keep learning, broad routing, compression, and shared knowledge experimental
   until a matched evaluation shows their benefit in that workflow.

## Why semantic gating is opt-in

In the early controlled OpenCode screening, each of the Jev supervision and
Jev-plus-context arms verified 4/6 attempts, versus 6/6 in control. The
separately frozen extension repeated those counts; the corresponding Clef arms
verified 6/6 but took longer than control. Some approval-required decisions
prevented edits in the unattended harness. The first blocked patches from
four failed extension runs passed the unchanged grader when applied offline.
Those runs remain live failures. These were small constructed task families
with no staffed review queue, not a production classifier ranking.

That evidence favors a deterministic default. Fresh bootstrap on `main`
keeps exact rules, task pinning, retry limits, and local records. It leaves the
bundled semantic goals inactive even when a backend is configured. Model
judgment, source delivery and operational add-ons remain available through
[explicit setup](GETTING_STARTED.md#add-only-the-optional-component-you-need).
The change preserves existing policy and human authorization.

## What remains to be tested

- **Host behavior.** An isolated check with OpenCode 1.18.35 found the installed
  `gw.mjs` ignored and identical `gw.js` bytes discovered. The
  [migration fix branch](https://github.com/davidjbeveridge/gw/tree/fix/opencode-plugin-discovery)
  preserves the source fix for review. This is discovery evidence, not a release
  or proof of live enforcement. Verify binding, actual context delivery, and a
  harmless denial before evaluating a worker.
- **Classifier accuracy.** The fresh 32-case Jev/Clef diagnostic was frozen but
  never dispatched. It contains 12 permissible, 12 conflicting, and eight
  uncertain cases. Report wrong denials, missed conflicts, abstentions, latency,
  and cost. Its three choices are a screening test, not the complete native
  five-choice alignment policy.
- **Live semantic integration.** Two tasks passed environment qualification.
  Two instrumented canaries and eight matched interactive slots were never run.
  The live cohort stopped before dispatch because credential access was
  unavailable. Compare identical prompts without requiring the treatment
  worker to call gW. Report uptake, accepted artifacts, scope violations,
  interventions, retries, elapsed time, and all worker and classifier tokens.
- **Incremental and organizational effects.** Test one feature at a time against
  a strong baseline, then test interactions where justified. Knowledge reuse
  needs source-change, revocation, and stale-cache checks. Shared learning and
  developer productivity need longitudinal or human outcome data; none of
  these short agent studies measures them.
