# Pre-inference dispatch amendment

The owner explicitly removed the 75,000 input-token ceiling before any inference.
The 64-request ceiling and US$0.50 incremental inference ceiling remain. All frozen
cases, gold labels, deterministic baseline and grading remain unchanged. The typed
Choice rubric and runner are frozen separately in dispatch-freeze.json before smoke.

Use POST /api/alpha/decisions with typesafe/jev-1.14, TypeSafe only, no fallback
and provider maximum rates US$0.042/M prompt, US$0/M completion and US$0/request.
Verify current metadata and sufficient account funds before smoke. Reserve US$0.015
for each inference request against the full advertised 262,144-input-token maximum
and zero output rate. Thirty-three calls reserve US$0.495, more than the published
worst-case US$0.363331584. Count all runner HTTP requests toward 64, including
metadata, smoke and failures. Input and output tokens are measured without an
input-token ceiling. No top-up, automatic retry or credential change is permitted.
Unknown outcomes retain the reservation and halt; an existing ledger prevents rerun.

First run one independent synthetic smoke. If its typed response, model/provider,
usage/cost and supporting label validate, continue once over the 32 frozen cases.
Do not tune the prompt from smoke. Send only synthetic task/action/failure data,
without gold labels or rationales. Classify all cases for diagnostic confusion;
compute H and A mappings afterward with the frozen reducer. These are policy
projections, not deployed interventions or delivered review requests. Classifier
operation remains advisory and deterministic authorization is unchanged.
