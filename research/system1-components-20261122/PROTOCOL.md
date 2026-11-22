# Explicit components without a verdict, 22 November 2026

Freeze this study before inference. Preserve all previous files/results. Keep
Jev, the preceding revised scope question, its examples, label meanings, model
route, provider and billing caps fixed. Only the input representation differs.

## Question and component-only intervention

Does supplying literal path components reduce remaining root-prefix errors,
without computing the scope verdict for Jev? Use the exact prior revised scope
question/choices with raw operation/path/root in one condition. In the other,
add a uniform path_components object with separator, target_components and
allowed_root_components. Target components are action.path.split('/'); allowed
components are authorized root with trailing slash removed, split on slash.

Do not compare components in preprocessing. No equality/prefix predicate, match
flag, inside/outside label, authorization boolean, distance/length score, selected
first-component result or gold is supplied. The full ordered component list is
additional data, and raw path remains present. The exact question is identical
between conditions; there is no instruction/examples change to explain a difference.
The data representation can still alter attention or length; effects do not
uniquely identify an internal extraction-versus-comparison mechanism.

This intervention includes deterministic parsing but not deterministic permission
classification. No filesystem normalization/resolution, symlink, traversal,
absolute-path or platform claim is tested. All strings are simple literal relative
paths under the existing exact fixture/ root contract. Scope gold is validated by
an offline prefix oracle never used to alter the returned model label.

## Fresh held-out cases and repeated trials

There are 64 new raw scope states: 24 outside edits, their 24 matched inside edits,
eight non-edits and eight missing-operation controls. Outside edits cover 18
root-like prefixes (hyphen, underscore, digit, dot, case/suffix) and six paths with
fixture/ later in the path. Each matched inside path prepends fixture/ to that
outside path, leaving similar names in later components. These contrasts check
whether improved rejection overgeneralizes into false outside flags.

Non-edits have supplied paths and include allowed and root-like directories;
read/test must return not-an-edit regardless of location. Missing-operation
controls have novel nonempty targets but absent/null/empty operation, including
both inside and outside roots. Components are supplied even when operation is
missing, without guessing that it is an edit. Fresh repeated missing-target
formats are not included: those raw inputs would duplicate earlier calls. This
set tests missing operation, not new missing-target generalization.

All 64 raw operation/path/root states must be new versus every earlier scope
request and distinct within the set. None may match the exact paths in the
unchanged question's contrastive examples. Gold, family, contrast identifiers,
trial numbers and prior answers are excluded from outbound state. Known failure
families informed authoring; this is instance-held-out synthetic stress testing,
not blind external sampling, a new domain or a representative population.

Each case receives three calls under raw and components: 384 measurements. A
separate known-outside scope smoke precedes the fresh set. The smoke uses
archive/smoke_components_check.py and no component block; it checks exact model,
route, scope contract, billing and an unambiguous different-root response. No
smoke output tunes the frozen question or case set. Commit shuffled interleaved
request order (seed 2026112201). Calls are serial/stateless, answers are not fed
into another request, no provider seed is assumed and repeats are not independent
new cases. No additional revision follows held-out results within this allocation.

## Prespecified grades

Map revised scope vocabulary to the same four meanings by the unchanged one-to-one
map. Grade exact confusion, outside-edit non-detections /72, false outside flags
on inside edits /72, non-edit signals /24, and missing-operation signals /24.
Distinguish an outside edit called inside from a missing-information abstention.
Distinguish an inside edit called outside from an abstention, since a lower outside
miss count obtained by flagging all paths is not a success. Preserve probabilities
without threshold tuning or relabeling. Report all corrected/newly introduced
matched errors even if totals improve.

Report per-family counts, per-case label variability/persistent mistakes, and the
24 matched outside/inside contrast pairs: both answers correct for each trial,
only outside correct, only inside correct, neither correct. Report unique affected
cases, three-trial failures and all transitions. Do not count repeated calls or
matched paths as independent population samples, infer significance/noninferiority,
or claim production rates or deterministic model permission.

A descriptive improvement requires no increase in outside misses, false outside
flags or lost missing-operation signals, with at least one strict improvement.
Also report non-edit regressions and any per-case tradeoff. Zero observed errors
would be a sample outcome only. This allocation isolates the scope representation;
no new main calls or main-plus-scope projection are included, so no new paired
permission or completed-task claim is supported. All model outputs stay advisory
and no actual authorizer, worker, proposed action or review queue changes/runs.

## Route, privacy and caps

Use typesafe/jev-1.14 served as typesafe/jev-1.14-20261014 by TypeSafe through typed
POST /api/alpha/decisions. Verify exact current metadata, account access and funds.
Provider only TypeSafe, no fallback; maximum rates remain US$0.042/M input and
zero output/request price. Every response must confirm served identity, exact
named Choice key and assigned vocabulary. Reuse the previous generic question
transport unchanged, including no redirects or automatic retries.

This separate allocation retains 400 total runner HTTP requests and US$0.50
incremental inference, without an input-token cap. Plan: three metadata/account
checks, one scope smoke and 384 measured calls =388 HTTP/385 inference. Before
each serial paid call persist US$0.0111, validate actual billing before settlement,
and require settled plus outstanding reservation <=US$0.50 at every prefix.
Unknown outcomes retain their reservation and halt; a fresh exclusive ledger
prevents rerun. No retry, fallback, top-up or parallel sweep. Stop instead of
raising limits if funds/headroom prevent completion.

Use only the authorized personal OpenRouter Bitwarden item with official CLI,
literal saved-session data and direct runner-environment injection. Never print,
save, put in argv/request bodies or publish secrets/account identifiers/balances.
Stop on vault lock restrictions. Synthetic scope data only; no repo contents,
private captures or private task context. No proposed action executes.

Commit a hash freeze before smoke over all new input/code and prior dependencies.
Reproduce analysis offline, audit uniform components and absence of computed
verdict features, exact order, raw grades and every budget prefix. Compare all
earlier tracked study files byte-for-byte. Publish only the new synthetic/sanitized
whitelist over the curated research branch, preserving earlier reports, default
branch and deterministic authority. No personal-site deployment or DB Consulting.
