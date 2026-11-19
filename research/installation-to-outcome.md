# Installing an agent harness does not measure its effect

David Beveridge. AI-assisted technical report, 19 November 2026.

A useful evaluation needs four separate records: what was installed, what actually
ran, what resources the models consumed, and whether the resulting work passed a
separate pre-existing acceptance check. gW's prior studies show why none can stand
in for the next. The evidence includes failed gates and missing captures. It does
not establish general savings or developer-productivity gains, and no independent
human adjudication is claimed.

## Installation and activation

In an isolated OpenCode 1.18.35 discovery check, the installed `gw.mjs` file was
ignored while identical bytes named `gw.js` were discovered. File installation
alone therefore cannot establish that a hook loaded. Discovery, hook binding and
an actual harmless pre-tool denial are separate checks. A successful denial on one
path does not establish coverage of every tool or host version. The retained
[host-behavior finding](https://github.com/davidjbeveridge/gw/blob/1aa0a149a0a785a3845d71f09d0ead92f4c552ab/docs/HARNESS_RESEARCH.md#what-remains-to-be-tested)
is discovery evidence, not proof of live enforcement.

Activation also differs by component. In the configured-repository cohort,
66 gW hook events were recorded but there were zero `gw_context_compile` calls;
semantic supervision was disabled. The treatment was not a test of fresh
classifier quality or routine context-tool uptake. The
[configured-work findings](https://github.com/davidjbeveridge/gw/blob/1aa0a149a0a785a3845d71f09d0ead92f4c552ab/docs/HARNESS_RESEARCH.md#configured-repository-work)
and [public cohort records](https://github.com/davidjbeveridge/gw/blob/f3041b552f9c0d086d860b28b39b63183bf35971/research/harness-performance/results.json)
retain these distinctions. The public export permits summary replay, not
inspection of every original hook or request.

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
of successful optimization. Failed attempts remain in resource totals. Two
selected tasks do not support a population estimate.

Separate source-answer cohorts reinforce that point. The first lexical comparison
accepted 7/24 baseline and 6/24 treatment, despite about 12% less treatment input.
A later calibration-repair cohort accepted 8/8 versus 5/8 and used 12.63% more
treatment tokens. Both failed their gates. The final frozen repair accepted 8/12
versus 10/12 with two treatment-only gains and no baseline-only loss. It met the
registered quality branch but failed the 15% token-saving branch: evaluation
tokens increased from 11,968 to 15,089, or 26.08%. These are distinct cohorts,
not pooled replications. A post-hoc identity-label sensitivity is separate from
the original grades. The repaired packet comparison does not isolate ranking,
chunking or budgeting as the cause. The retained
[source-answer findings](https://github.com/davidjbeveridge/gw/blob/1aa0a149a0a785a3845d71f09d0ead92f4c552ab/docs/HARNESS_RESEARCH.md#source-backed-answers)
include the failed comparisons and scoring limits.

## Intervention and completion

In historical small selected OpenCode task families, some approval-required
judgments prevented edits in an unattended harness. Four first blocked patches
passed the unchanged pre-existing acceptance check when applied offline; all
four original runs remain live failures. This distinguishes a useful candidate
patch from a workflow that delivers accepted work. It does not make every review
request a wrong classifier judgment. There was no staffed review queue. These
[historical intervention findings](https://github.com/davidjbeveridge/gw/blob/1aa0a149a0a785a3845d71f09d0ead92f4c552ab/docs/HARNESS_RESEARCH.md#why-semantic-gating-is-opt-in)
do not establish a production model ranking.

## A practical measurement record

Connect an installed version and configuration hash to observed hook events,
classifier requests or context delivery, complete worker and classifier usage,
and acceptance of the resulting artifact. Count wrong blocks, review requests,
unresolved alerts, retries and elapsed review time alongside failures and missing
outcomes. Keep hard deterministic authorization unchanged when testing advisory
semantics. Qualify a harmless path before a matched live cohort, and retain a
failed qualification instead of weakening its acceptance check.

The published [aggregate replay](https://github.com/davidjbeveridge/gw/blob/f3041b552f9c0d086d860b28b39b63183bf35971/research/harness-performance/summarize.py)
recomputes selected recorded cohort summaries without dispatching a model. It does
not regrade captures, execute native workers or reproduce classifier runs.
Installation tests establish installation behavior. A model label measures the
classifier's answer to a stated question. Accepted task artifacts measure delivered
work. The current evidence supports those distinctions and bounded engineering
recommendations; developer productivity and organizational returns remain unmeasured.
