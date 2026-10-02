# gw-learning

Reviewable learning plugins and bounded, explicit research workers. Independent
MIT package, Python 3.10+, no runtime dependencies. Version 0.1.0. Worker protocol
`gw.learning/1`.

```bash
python -m pip install .
gw-learning init
gw-learning run --input evidence.json
gw-learning list
gw-learning show PROPOSAL_ID
```

`--directory PATH` precedes the command. Supply evidence metadata explicitly:

```json
{
  "repetitions": [{"action_hash":"example","tool":"Bash","successes":3,"reference":"source:action"}],
  "goal_patterns": [{"id":"task_alignment","interventions":3,"evidence":["source:event"]}]
}
```

Defaults create tool-plan and guidance proposals without inference. They do not
scan conversation files, fabricate unseen evidence, or install generated code.
`LearningPlugin` defines name/version plus `propose(context, settings)`. Installed
plugins use `gw.learning.plugins`; operator-installed plugin code is trusted code.
Proposal shape: key, kind (`tool_plan`, `guidance`, `research_job`), title, body,
evidence references and goal IDs. Inputs/proposals are bounded. Records reference
sources rather than duplicating complete conversations.

`init --config FILE` merges a configuration with defaults. Modes are off/propose/
auto; strategies thematic/expansion; lookback and proposal count are configurable.
Research is disabled until topics with explicit IDs and queries are configured.
A recurring topic does not imply consent to autonomously research it.

The optional executor is a literal argv list. It receives JSON on stdin and must
return JSON with a nonempty Markdown `report`, optional `sources` and `usage`.
`approve ID` then `execute ID` authorizes one claim. `mode:auto` can authorize the
configured executor's `allowed_kinds`; by default that list contains research_job
only. Adding guidance/tool_plan explicitly permits workers to expand those reports.
No worker is bundled that extracts subscription credentials or silently spends
model credits. Configure your own harness/API bridge.

Time/output limits and duplicate claims are enforced. Arbitrary worker API costs
and OS side effects require controls in that worker's execution environment; it
runs as the current user, not in a sandbox. Failed jobs are retained rather than
retried secretly. Changing configuration invalidates old execution approval.

`publish ID --destination DIRECTORY` writes a new immutable Markdown artifact,
recording its hash and path. It never installs or activates the artifact in a live
harness. `watch --interval 3600` is an explicit foreground recurring process, not
an automatically installed service. Research cadence is at least hourly.

The SQLite store owns proposal payloads, configuration snapshots, result reports
and transition journals. An optional observer callback receives compact lifecycle
metadata; observers do not own a second copy of each report and cannot authorize
mutations. Historical reports and generated recommendations remain evidence, not
policy or verified truth.

Copy this directory to another repository and build it unchanged. Run
`python -m unittest discover -s tests -v`. Tests use deterministic metadata and
local fixture workers, no paid inference. Full GW setup is documented at
https://github.com/davidjbeveridge/gw/blob/main/docs/LEARNING.md.
