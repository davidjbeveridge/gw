# Recipes and counterexamples

[Handbook](README.md) · [Runnable examples](../examples/README.md) · [Configuration](CONFIGURATION.md)

These are small policies you can inspect. JSON blocks are fragments to merge, not replacements for your global file. Review project changes with `gw trust`; begin a new session after changing the task or policy.

## Keep a coding change bounded

Pin a task that includes the expected deliverable and the important exclusion:

```bash
gw task 'Fix the date parser regression, add tests, and leave unrelated APIs unchanged. Do not deploy.' --project .
```

Make uncertain backend failures require review:

```json
{
  "goals": {
    "task_alignment": {"on_error": "approve"},
    "retry_limit": {"threshold": 2}
  }
}
```

This still requires an enabled, functioning classifier for semantic alignment. It does not turn off-task detection into an exact static rule. Test the chosen backend with representative supporting work as well as obvious drift; setup, reading documentation, and running tests can legitimately serve the task.

**Counterexample:** a scope saying only “edit parser.py” can make a necessary fixture change appear unrelated. A root task should describe the job, not merely the first guessed file.

## Stop exact retries before another speculative attempt

```json
{
  "goals": {
    "retry_limit": {
      "threshold": 2,
      "effect": "approve",
      "message": "This action failed twice. Inspect the error or choose a different approach before retrying."
    }
  }
}
```

The next matching pre-tool event after two recorded failures requires review. Counts are per exact redacted action fingerprint and session; they are not a generalized “same bad idea” detector. Supply honest failure outcomes. A changed command can start another fingerprint, and an unknown outcome breaks the streak.

**Counterexample:** limiting retries by changing the model's prompt alone provides no external count. Conversely, gW's exact count does not prove that a differently worded command is a new approach.

## Recommend a known CLI for a browser-shaped task

```json
{
  "registry": {
    "github_pull_request": {
      "kind": "cli",
      "executable": "gh",
      "when": {"tool": "*browser*", "text": "*github.com*"},
      "description": "Inspect a pull request using the authenticated GitHub CLI",
      "example": "gh pr view NUMBER --json title,body,statusCheckRollup"
    }
  }
}
```

This recommendation is eligible when the event matches and `gh` is on the supervisor process's PATH. It does not prove `gh` is authenticated. It does not force a tool switch; native pre-tool advice is not delivered by every adapter. Match the actual tool names in your harness rather than assuming all browser tools contain the same word.

**Counterexample:** always preferring CLI over browser is not evidence that the CLI can perform the specific operation. If the assignment is to test the UI itself, using an API would avoid the thing being tested.

## Enforce a semantic action boundary in a custom host

A custom executor can provide a precise action instead of an opaque mouse click:

```json
{
  "type": "tool.before",
  "client": "forms-worker",
  "project": "/absolute/existing/project",
  "session": "application-001",
  "id": "submit-001",
  "tool": "application.submit",
  "input": {"application_id": "local-fixture"},
  "operation": "application.submit",
  "target": {"origin": "https://jobs.example.test"}
}
```

A matching rule can require review:

```json
{
  "rules": {
    "review_final_submission": {
      "when": {"operation": "application.submit"},
      "effect": "approve",
      "reason": "Review final fields before external submission"
    }
  }
}
```

The executor must pause and implement the actual approval path. In a noninteractive workflow, review does not become allow. The model should not be able to falsely label its action as read-only; the executor supplies and checks the semantic fields.

**Counterexample:** `click(812,443)` does not tell the supervisor what will be clicked. A password or legal-assent executor is not created by adding an operation name. Those integrations remain outside the current implementation.

## Add a custom judgment without code

```json
{
  "goals": {
    "evidence_before_change": {
      "on": ["tool.before"],
      "evaluator": "choice",
      "question": "Does this proposed integration change rely on an API or configuration option that the supplied evidence does not establish? Choose uncertain when you cannot tell.",
      "choices": {
        "grounded": "Routine or supported by the available evidence",
        "research_needed": "Consult the official contract before implementing this mechanism",
        "uncertain": "Insufficient evidence to decide"
      },
      "effects": {"research_needed": "advise", "uncertain": "advise"},
      "on_error": "advise"
    }
  }
}
```

This uses the existing choice primitive. It does not add a browsing tool or cause research automatically. If the host cannot provide enough evidence for this question, the uncertainty outcome is the correct result. Narrow questions are preferable to asking a small classifier to review the entire architecture from one tool call.

## Keep local policy in observation mode

```json
{"mode": "observe"}
```

Observation mode records what a local rule would have denied or sent for review, but returns advice instead. It is useful while examining false positives. It is not a blanket safety-off switch: unavailable or denying external authority remains blocking, and malformed hook/configuration paths can still fail conservatively.

Use new sessions when changing modes. Do not verify the deny canary in observation mode and conclude the adapter is broken because the tool ran.

## Select a configured capability, not a marketing tier

```bash
gw models select --operation image.generate --input text --output image --execution proxy,adapter
```

The registry must contain an enabled, declared-available compatible entry. The result is an execution plan. A classifier may be used for selection if configured; the selected image generator itself is not invoked by this command.

For a subscription preference, use `billing_preference` and a suitable harness entry in [the model registry](MODELS.md). Do not use an API alias to pretend a native subscription can pay an unrelated provider.

**Counterexample:** an image input capability says nothing about image output. A video model cannot answer a Chat Completions request merely because its registry priority is better.

## Reuse verified project knowledge

Install with `--knowledge`, then use an existing local source file:

```bash
gw knowledge init
gw knowledge ingest README.md --id project-readme
gw knowledge context 'decision provider'
gw knowledge context 'decision provider'
```

The second context lookup can reuse a valid packet. It still checks the provider's revision. A new source can invalidate the search even when the old matched document has not changed. The [knowledge demo](../examples/knowledge_demo.py) exercises this behavior with temporary data.

**Counterexample:** modifying README.md on disk does not automatically update an ingested snapshot. Re-ingest explicitly with the expected current document revision. A cache cannot fix missing synchronization in the source ingestion path.

## Separate project rules from backend credentials

Use project config to adjust goals and registry preferences. Use global/global-client config to choose the decision or knowledge endpoint and credential reference. A reviewed project should not be able to redirect classification context to an arbitrary service.

**Counterexample:** committing a `decision.endpoint` in `.gw.json` to make setup convenient is not supported. Provide an operator-controlled setup command or guide instead. Never include a literal key in a copied configuration example.

## Turn repetition into a reviewable experiment

Keep the default three-success threshold or change `repeat_work.threshold`. Inspect `gw status` for proposed candidates. Decide whether the pattern warrants a deterministic wrapper, a skill, or no automation at all.

The current record identifies repeated actions, not a complete replayable workflow. A future implementation needs explicit fixtures, tests, promotion, and rollback. Three successes are a reason to investigate—not a reason to install generated code automatically.
