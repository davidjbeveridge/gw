# Advisory Classification in a Coding-Agent Harness
## A four-stage evaluation of Jev in gW

**David Beveridge**  
November 19, 2026 · Version 1.0 · Independent research preprint (not peer reviewed)

### Abstract

Can a lightweight classifier flag out-of-scope or underspecified coding-agent actions without being trusted to authorize them? We evaluated a fixed served version of Jev in four experiments using synthetic proposals for one software repair. In an initial 32-case diagnostic, the classifier flagged all 12 conflicts and all eight missing-target cases, but also raised four false prohibition alarms among 12 permissible proposals. A matched follow-up showed that both added task context and a revised response interface could remove those four alarms. Repeated validation exposed new errors: missed conflicts and affirmative responses to incomplete proposals. The final revision, tested on 40 previously undispatched cases with three trials per case, produced 0/45 false alarms and correctly signaled 30/30 incomplete decisions, but missed 2/45 explicit conflicts, both repetitions of the same case. The original interface missed no conflicts on that set, with 2/45 false alarms and 18/30 correct incomplete signals. The experiments measure classification, not policy enforcement, review effectiveness, or task completion. The results support investigating advisory classification while retaining deterministic enforcement for strict boundaries.

## 1. Introduction

A coding-agent harness can observe a proposed action before execution. Some constraints, such as an exact directory boundary or a retry limit, can be checked against structured state. Whether a permitted edit advances the task may depend on context that a literal rule does not capture. The two judgments are not interchangeable. A proposal can be permitted without evidence that it is useful, and its apparent usefulness cannot grant permission.

We use *System 1* as shorthand for a lightweight proposal classifier in gW, not as a claim about human cognition or the model's internal process. The distinction between advising and deciding follows the separation of information analysis from action selection and implementation in Parasuraman et al. [1]. Our case-based evaluation likewise follows the motivation of behavioral testing [2]: aggregate agreement can conceal failures on behavior that matters. We ask which signals survive controlled changes to the decision interface, which errors recur across trials, and what conclusions can be drawn without observing execution.

Prior gW work distinguished installation from outcomes [3]. In an isolated OpenCode check, discovery depended on the plugin filename extension; discovery was not proof of enforcement. In a separate small worker comparison with semantic supervision disabled, four of four baseline attempts passed acceptance; two of four treatment attempts were confirmed successes, one failed, and one lacked a result. Those observations motivate measuring the execution chain separately. They are not part of the classifier experiment.

## 2. Methods

### 2.1 Task, model, and baseline

All four stages used investigator-authored proposals in the same synthetic repair family: fix a sum function, allow scoped implementation edits and authorized reads or tests, exclude specified edit classes and outside-directory edits, and respect a limit on retrying an identical failed test. An incomplete proposal omits information necessary to apply this policy, such as the target, operation, or applicable failure history. A single investigator supplied the reference labels. Failure histories were fixtures, not executed attempts. Private tasks and captures were excluded.

Each successful inference reported the same served model, `typesafe/jev-1.14-20261014`, and provider, TypeSafe, using the typed OpenRouter Decisions endpoint. Requests were stateless; reference labels, case IDs, and prior responses were not provided to the classifier. No confidence threshold, fallback model, or classifier-driven execution was used. Stage protocols, fixtures, request schedules, and grading are available in the public artifacts [4–7]. Each later stage was designed with knowledge of earlier failures; its evaluation inputs and scoring were frozen before its own inference. In Stage 1, the investigator retained the original baseline and amended the dispatch budget before inference, removing an unverifiable input-token ceiling while keeping the request and spend limits [4].

The Stage 1 offline comparator was a deliberately limited configuration of the gW reducer. It denied outside-directory fixture edits and required approval after two identical supplied failures. It did not enforce every task constraint or label semantic relevance. Its dispositions are reported separately from model classifications; it is not a comparison against a complete rules engine.

### 2.2 Interfaces and endpoints

The **original** interface provided the task, proposed action, and prior failure count, then asked for supporting, conflicting, or uncertain. The **combined** interface added an explicit account of the helpers' relationship to the task and scope, and separated prohibition, supported permission, relevance-unproven permission, and missing permission information. The **revised** interface made path references directory-qualified, changed the context representation, and directed the classifier to evaluate known prohibitions and literal prerequisites before relevance, without inferring missing fields.

We count false prohibition alarms on permissible proposals, missed prohibition signals on explicit conflicts, and correct missing-information signals on incomplete proposals. A qualified permission answer is not evidence of relevance; an abstention is not a permission grant. The three endpoints are reported separately because the interfaces do not have equivalent label vocabularies. Repeated calls are observations on the same cases, not independent samples. All comparisons are descriptive.

### 2.3 Experimental sequence

1. **Initial diagnostic:** 32 distinct proposals, one call each; 12 permissible, 12 conflicting, and eight incomplete. Compare the live classifier with offline deterministic dispositions and project, but do not execute, advisory and hard-intervention policies [4].
2. **Selected-case follow-up:** 11 previously evaluated proposals, including all four false-alarm helper cases. Cross the original or explicit context with the original or four-choice interface, yielding 44 measured responses. This diagnoses known errors; it is not independent validation [5].
3. **Repeated validation:** 32 original and 32 newly authored proposals, three trials per original or combined interface, yielding 384 measured responses [6].
4. **Revision and held-out evaluation:** 24 diagnostic responses cover three known failures across four variants, twice each. Compare the original, combined, and preselected full revision on 40 new exact proposals, three trials per interface, yielding 360 additional responses. The held-out proposals and the revision were frozen before the diagnostic block; diagnostic answers did not select the revision [7].

## 3. Results

### 3.1 Initial diagnostic and policy projections

The original interface flagged 12/12 conflicts, signaled 8/8 incomplete proposals, and falsely flagged 4/12 permissible proposals. All four false alarms involved helper edits allowed by the frozen rubric; the prompt named the primary file without establishing the helpers' role. The deterministic comparator denied four conflicts and required approval for four others. It allowed the four prohibited documentation edits and did not flag the eight incomplete cases.

Under the frozen advisory projection, those otherwise allowed cases would produce four conflict alerts and eight incomplete-information signals, alongside four false alarms, without changing permission. The hard projection would wrongly block the four permissible helper edits. Its implemented maximum-severity rule also upgraded four deterministic retry approvals to denials, although the protocol prose described model intervention only on otherwise allowed actions. We retain the implemented mapping and disclose the discrepancy. Neither projection tested actual intervention, alert delivery, reviewer response, or accepted work.

### 3.2 Context and interface changes

In the 11-case diagnostic, the original setup reproduced all four helper alarms. Adding context alone removed them but falsely flagged a permissible documentation read. Changing only the response interface removed the four helper alarms by reporting relevance as unproven, but missed one of three explicit conflicts. The combined condition yielded zero alarms among six permissible proposals, retained all three conflict signals and both incomplete signals, and left one helper's relevance unproven. The study tests packages of changes, not the isolated effect of option count or a specific phrase.

Repeated validation showed that the combined interface's initial advantage did not carry across all endpoints. On the original cohort it removed 11/36 false alarms but missed 2/36 conflict decisions, both on the same outside-directory proposal. On the fresh cohort both interfaces recorded 0/36 false alarms and 0/36 missed conflicts. The combined interface nevertheless correctly flagged only 18/24 incomplete decisions versus 24/24 under the original interface. It affirmatively supported two incomplete proposals in all three trials. Repetition can reveal stable error as well as variability.

### 3.3 Final revision

On the three known diagnostic cases, the old combined and path-context-only variants each scored 3/6, while the prerequisite-question-only and full revisions each scored 6/6. This supports testing explicit prerequisites for missing fields. It does not identify the cause of the path error, or establish that the question-only change generalizes: only the full revision received the held-out test.

| Held-out interface | False alarms | Missed conflicts | Correct incomplete signals |
|---|---:|---:|---:|
| Original | 2/45 | 0/45 | 18/30 |
| Combined | 0/45 | 6/45 | 9/30 |
| Revised | 0/45 | 2/45 | 30/30 |

*Table 1. Each row covers 15 permissible, 15 conflict, and 10 incomplete cases, tested three times. Denominators are decisions, not unique cases.*

Relative to the combined interface, the full revision recovered four matched conflict signals and 21 incomplete signals without introducing a false alarm. Relative to the original interface, it traded two lost conflict signals for two fewer false alarms and 12 more correct incomplete signals. Both residual misses came from the same prohibited edit to an out-of-directory helper with a familiar basename. The revised interface flagged that exact proposal once and returned permitted and supported twice. The other 39 cases matched their reference labels on all three trials. The original interface caught all three repetitions of the residual conflict. Neither this result nor the diagnostic block establishes basename similarity as the cause.

### 3.4 Inference usage

The four stages produced 844 measured responses and four smoke responses. The runner logs record 524,963 input tokens, 47,410 output tokens and US$0.022048446 in incremental API charges across all four stages, including smoke. These charges exclude research orchestration, subscriptions, local compute and any review labor. They are not an end-to-end cost estimate or evidence of time savings.

## 4. Discussion and limitations

The response interface is part of what was measured. Holding the served model fixed did not hold error behavior fixed: more context or a different choice set could remove one failure while introducing another. The final interface handled omissions better on the tested cases, but a task-related name could still coincide with a prohibited path and receive an affirmative answer. On this task, the directory rule should remain deterministic. In a future deployment, a classifier could add an explanation or ask for clarification, but its output should neither expand permission nor override a deterministic denial or approval requirement. The current work did not evaluate a deployed advisory workflow.

The study covers one model route, one synthetic repair family, one rubric author, and small, related cohorts. New cases were authored with knowledge of earlier failure families. “Held out” means the exact proposal states had not been dispatched and were not used to select the revision; it does not mean independently sampled, blinded, or cross-domain. Three repeats per case do not establish a low production failure rate. A fixed reported model identifier does not establish immutable weights or deterministic provider seeds. Labels and confidence were not used to infer internal reasoning. The limited deterministic comparator does not establish an advantage over complete deterministic enforcement.

A useful next evaluation would compare rule-only and rule-plus-advice modes under identical hard controls on tasks from multiple repositories, with independent labeling and acceptance tests. Primary outcomes should include accepted work and reviewer time, alongside constraint violations, false alerts, useful interventions, and missing or abandoned runs. It should trace delivery of an alert, the user's response, and the resulting artifact rather than counting classifier outputs as interventions.

## 5. Conclusion

Relative to the original interface on the final held-out set, the revision reduced avoidable alarms and improved recognition of incomplete proposals, but it still missed an explicit boundary violation. The evidence supports measuring classification and execution separately, and keeping strict permissions outside the classifier.

## Data and reproducibility

References [4–7] pin the four public reports and lead to their protocols, exact synthetic cases, recorded responses, summaries, and replay instructions. The included offline analyses can reproduce the reported counts without new inference. The comparisons in this paper do not combine historical worker outcomes with classifier decisions. AI tools assisted the research workflow and preparation of this manuscript.

## References

1. Parasuraman, R., Sheridan, T. B., and Wickens, C. D. (2000). [A model for types and levels of human interaction with automation](https://doi.org/10.1109/3468.844354). *IEEE Transactions on Systems, Man, and Cybernetics, Part A*, 30(3), 286–297.
2. Ribeiro, M. T., Wu, T., Guestrin, C., and Singh, S. (2020). [Beyond Accuracy: Behavioral Testing of NLP Models with CheckList](https://aclanthology.org/2020.acl-main.442/). *Proceedings of the 58th Annual Meeting of the Association for Computational Linguistics*, 4902–4912.
3. Beveridge, D. (2026). [Installing an agent harness does not measure its effect](https://github.com/davidjbeveridge/gw/blob/84561631897bc46c7c29f6382c9cb6f093b22631/research/installation-to-outcome.md). gW installation and worker-outcome companion.
4. Beveridge, D. (2026). [System 1 decisions and completed work are separate endpoints](https://github.com/davidjbeveridge/gw/blob/c0df0d93c5884436605da035ee459b2dcc3a86fb/research/system1-20261119/01-system1-study.md). gW initial classifier diagnostic and policy projections.
5. Beveridge, D. (2026). [Jev's helper-edit alarms changed with context and classification choices](https://github.com/davidjbeveridge/gw/blob/c0df0d93c5884436605da035ee459b2dcc3a86fb/research/system1-followup-20261119/REPORT.md). gW selected-case follow-up.
6. Beveridge, D. (2026). [Repeated validation of Jev's combined context and classification interface](https://github.com/davidjbeveridge/gw/blob/c0df0d93c5884436605da035ee459b2dcc3a86fb/research/system1-validation-20261119/REPORT.md). gW repeated validation.
7. Beveridge, D. (2026). [Investigating Jev's scope and completeness failures, then testing a held-out revision](https://github.com/davidjbeveridge/gw/blob/c0df0d93c5884436605da035ee459b2dcc3a86fb/research/system1-revision-20261119/REPORT.md). gW held-out revision.
