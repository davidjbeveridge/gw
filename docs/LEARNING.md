# Learning plugins: evidence, proposals, review, and execution

[Handbook](README.md) · [Interfaces](PLUGINS.md) · [Observability](OBSERVABILITY.md) · [Sync](SYNC.md)

Learning is a separate optional package, not an extra agent hidden in every hook.
Default analysis is deterministic and produces proposals. It does not install a
generated tool, rewrite policy, or infer a research goal from a repeated topic.

## Start with proposals

```bash
gw learn init
gw learn run
gw learn list
gw learn show PROPOSAL_ID
```

GW reads bounded metadata from its existing ledger for the configured project and
lookback period. Tool optimization finds repeated successful action fingerprints.
Skill expansion groups repeated goal interventions into guidance-review proposals.
Neither implies that the old agent or the old supervisor was correct. The input
coverage and source references are part of the record; whole transcripts are not
copied into the learning store.

Defaults are `mode: propose`, 14-day lookback, thematic analysis, at most 20
proposals per pass, and research disabled. Configure through a JSON file or the
small CLI options:

```bash
gw learn init --mode propose --lookback-days 30 --strategies thematic
```

Default proposals deliberately ask for evidence review instead of pretending
that three matching commands constitute a reusable deterministic workflow. Exact
fingerprints are not semantic clustering. Richer analysis belongs in an explicit
worker or installed plugin, not unmetered inference in the observer.

## Review and publish

```bash
gw learn approve PROPOSAL_ID
gw learn publish PROPOSAL_ID --destination /absolute/staging/guidance
```

`reject` records rejection. `publish` creates a new immutable Markdown artifact
and records its hash/path; it refuses overwrites. The artifact can later be
reviewed as a skill, guidance, research report, or tool plan. **It is not installed
into a running harness.** Use the sync/review/native-trust workflow deliberately.
Live activation remains review-only in this release even when research execution
is autonomous. An operator can inspect historical proposal payload, configuration,
evidence references, status transitions, result, and published artifact.

## Add explicitly authorized research

Save a configuration file such as:

```json
{
  "mode": "propose",
  "strategies": ["thematic", "expansion"],
  "lookback_days": 14,
  "plugins": {
    "research": {
      "enabled": true,
      "interval_seconds": 86400,
      "topics": [{"id": "local-form-automation", "query": "Research more reliable local form automation; cite sources and propose tests.", "goal_ids": ["tool_efficiency"]}]
    }
  },
  "executor": {
    "argv": ["/absolute/python", "/absolute/research-worker.py"],
    "allowed_kinds": ["research_job"],
    "timeout_seconds": 120,
    "max_output_bytes": 262144
  }
}
```

These paths are templates. `gw learn init --config FILE` merges the document with
defaults. `gw learn tick` creates due proposals without running an unapproved job.
After approval, `gw learn execute ID` runs the configured worker once. `mode: auto`
permits execution of explicitly enabled worker kinds without a separate approval;
research topics still must be configured. A repeated conversation topic does not
implicitly authorize research, spending, account access, or a new goal.

`allowed_kinds` can explicitly include `guidance` or `tool_plan` to let a worker
expand those proposals into a report after approval (or under explicit auto mode).
It does not execute the generated report or turn it into trusted policy.

## Worker contract

The worker is a literal executable/argv list, launched without a shell from a
temporary working directory. It receives one JSON request on stdin:

```json
{
  "protocol": "gw.learning/1",
  "job_id": "opaque-id",
  "kind": "research_job",
  "topic": "The explicitly configured query",
  "proposal": {"body": "The query", "evidence": []},
  "goal_ids": ["tool_efficiency"],
  "limits": {"timeout_seconds": 120, "max_output_bytes": 262144},
  "instructions": "Return JSON with a report; do not change harness policy."
}
```

Return JSON with a nonempty Markdown `report`, optionally `sources` and reported
`usage`. The actual runtime request contains the complete configured executor
limits; fields shown above explain the contract rather than a literal captured job.

```json
{"report":"# Findings\n\nThe available evidence suggests ...","sources":["https://example.test/source"],"usage":{"input_tokens":1200,"output_tokens":300}}
```

Reports and source claims are worker output, not independently verified facts.
Usage is worker-reported and is not invented when absent. The worker can wrap your
preferred native harness or API model, but the library does not extract subscription
credentials or assume an arbitrary CLI accepts this input format. Supply a bridge
that explicitly implements the contract.

Hard limits cover process duration, captured output size, and duplicate job
claims. They **do not enforce an API dollar budget inside arbitrary worker code**.
The worker runs with the launching user's OS rights and environment, not a sandbox.
Constrain its model/network/tool budgets in that execution layer. Configuration
changes invalidate previous job approval; hidden retries are not performed.

## Recurrence and state

```bash
gw learn watch --interval 3600
```

This foreground local process checks due work until stopped. It does not install
an OS service or create a cloud schedule. Research cadence is at least hourly;
polling can be more frequent but never means duplicate execution of the same
cadence slot. Configure research before running it unattended. Thematic lookback
is refreshed on each GW watch pass. Standalone callers supply their own input.

Proposal identities include plugin version, pattern/topic slot, the full learning configuration,
and body. Existing proposals do not run twice merely because the pass repeats.
The same unresolved pattern can remain a single proposal. Changes to the relevant
plugin, evidence interpretation or cadence slot can produce a new one.

State is `proposed → approved/rejected → running → succeeded/failed → published`
where applicable. Tool/guidance plans can be published after review without worker
execution. A failed job stays failed; retry is an explicit new reviewed proposal.
Observer errors never authorize or abort the learning operation.

## Extension point

An installed entry point in `gw.learning.plugins` returns a plugin with `name`,
`version`, and `propose(context, settings)`. It emits bounded proposals containing
key, kind, title, body, evidence references, and goal IDs. Plugin code is trusted
operator-installed code. No project configuration can dynamically import arbitrary
worktree Python.

The core retains its existing repetition counters as evidence. The learning
package owns analysis passes, configuration snapshots, proposals, execution, and
publication history. GW observability stores references to those records, not a
second copy of every research report. See the independent package and tests for
contract examples.
