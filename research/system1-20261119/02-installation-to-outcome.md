# Installing an agent harness does not measure its effect

David Beveridge. AI-assisted practical technical report, 19 November 2026.

A useful evaluation needs four separate records: what was installed, what actually
ran, what resources the models consumed, and whether the resulting work passed
an independent acceptance check. gW's prior studies show why none can stand in
for the next. The evidence includes failed gates and missing captures, not a
claim of general savings.

## Installation and activation

In an isolated OpenCode 1.18.35 discovery check, the installed `gw.mjs` file was
ignored while identical bytes named `gw.js` were discovered. A fix branch and later
managed-profile repair preserve that finding. File installation alone therefore
cannot establish that a hook loaded. Discovery, hook binding and an actual harmless
pre-tool denial are separate checks. A successful denial on one path does not
establish coverage of every tool or host version.

Activation also differs by component. In the configured-repository cohort,
66 gW hook events were recorded but there were zero `gw_context_compile` calls;
semantic supervision was disabled. The treatment was not a test of fresh
classifier quality or routine context-tool uptake. These observations come from
[the retained research findings](../../docs/HARNESS_RESEARCH.md), with selected
[public cohort records](evidence/public-cohorts.json). That public export permits
summary replay, not inspection of every original hook or request.

## Model consumption and accepted artifacts

The configured-repository comparison used two tasks, two fresh repeats per arm
and the same Sol worker in OpenCode. Baseline accepted 4/4 artifacts. Configured
gW accepted 2/4, with one known failure and one missing capture. Treatment acceptance
is bounded by 50% to 75%; the engineering criterion failed. A missing capture is
neither an accepted artifact nor evidence that no work occurred.

Cache-inclusive worker tokens were 270,841 baseline versus 254,627 treatment,
5.99% lower. Uncached input plus all output was 70,393 versus 73,763, 4.79% higher.
These measures answer different questions. Neither establishes a subscription's
monetary cost. A lower total coupled with fewer accepted artifacts is not evidence
of successful optimization. Failed attempts remain in resource totals.

Separate source-answer cohorts reinforce that point. The first lexical comparison
accepted 7/24 baseline and 6/24 treatment, despite about 12% less treatment input.
A later calibration-repair cohort accepted 8/8 versus 5/8 and used 12.63% more
treatment tokens. Both failed their gates. The final frozen repair accepted 8/12
versus 10/12 with two treatment-only gains and no baseline-only loss. It met the
registered quality branch but failed the 15% token-saving branch: evaluation
tokens increased from 11,968 to 15,089, or 26.08%. These are distinct cohorts,
not pooled replications. A post-hoc identity-label sensitivity is separate from
the original grades. The repaired packet comparison does not isolate ranking,
chunking or budgeting as the cause.

## Intervention and completion

Early live OpenCode screening verified 4/6 in each Jev arm and 6/6 in control.
A separately frozen extension repeated those counts. Some approval-required
judgments prevented edits in the unattended harness. Four blocked patches passed
the original grader when applied offline; all four original runs remain live
failures. This supports a distinction between a useful candidate patch and a
workflow that actually delivers accepted work. It does not make every review
request a wrong classifier judgment. There was no staffed review queue.

The extension's Clef arms verified 6/6 and took longer than control. The small
constructed task families, differing interventions and historical provider versions
cannot establish a production model ranking. [Aggregate replay](scripts/summarize.py)
recomputes the recorded arm counts without dispatching a model. It does not
regrade captures or reproduce native execution.

## What this checkpoint adds

The [new System 1 report](01-system1-study.md) evaluates 32 synthetic proposals.
The actual deterministic rules missed four documentation scope conflicts and left
eight missing targets unalerted. A subsequent typed Decisions evaluation caught
all 12 conflicts and returned uncertain for all eight missing-target cases, but
falsely flagged four of 12 permissible proposals. Advisory projections preserve
the deterministic restrictions and add four false alarms; hard projections would
wrongly block those four proposals. No worker, proposed action or review queue ran.
The smoke plus evaluation consumed 33 inference calls, 16,689 input tokens,
1,518 output tokens and US$0.000700938 in reported inference charges. The owner
removed the input-token ceiling before inference; request and spend caps remained.
The protocol/implementation discrepancy in the hard-policy projection is retained
and explained in that report. This result measures typed labels and policy
projections, not completed work or productivity. The private diagnostic and
interactive environments remain unrun.

A practical record should connect an installed version and configuration hash to
observed hook events, classifier requests or context delivery, complete worker and
classifier usage, and independent artifact acceptance. Count wrong blocks,
review requests, unresolved alerts, retries and elapsed review time alongside
failures and missing outcomes. Keep hard deterministic authorization unchanged
when testing advisory semantics. Qualify a harmless path before a matched live
cohort, and retain a failed qualification instead of weakening its grader.

Replay from cached outputs proves reproducibility of recorded calculations.
Installation tests prove installation behavior. A model label measures the
classifier's answer to a stated question. Accepted task artifacts measure delivered
work. Our current evidence supports those distinctions and bounded engineering
recommendations; developer productivity and organizational returns remain unmeasured.
