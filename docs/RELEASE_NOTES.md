# gw v0.3.0 — guided decision-backend setup

Configure the supervisor's own decision model independently of worker models.

- `gw setup`: interactive guide; noninteractive presets, dry-run, backup and apply.
- TypeSafe and OpenRouter System One endpoints; keyless/authenticated local Kev
  and Laya; arbitrary compatible System One or JSON chat proxies; custom HTTP
  and explicit CUA bridge configuration.
- `gw setup --describe`: JSON manifest; an agent setup skill and detailed guide.
- `gw decision status/check`: no-network inspection or one synthetic test call.
  Failed checked setup leaves existing config unchanged. The smoke is not an
  accuracy evaluation.
- Environment/private-file credential references; no raw keys stored in config.
- Reject invalid/incomplete/refused decisions and reported context truncation.
- Preserve worker login/billing, policies, registry and old session snapshots.

## Install or update

Python 3.10+, macOS/Linux:

```bash
curl -fsSL https://raw.githubusercontent.com/davidjbeveridge/gw/v0.3.0/install.sh | bash -s -- --all
gw setup
```

Restart agents and start new sessions. For OpenRouter, provision
OPENROUTER_API_KEY outside chat, then run
`gw setup --preset openrouter --check --yes`.

## Validation and limits

152 tests: 144 core tests across the six OS/Python combinations, plus eight
actual-LiteLLM callback tests separately. Installer checks run on all three OSes;
publication is gated on those jobs. No live provider keys or model weights were
used. Local model servers must be installed/warmed separately. CUA nano/forms
are NOT claimed as general-purpose drop-in supervisors; a task-appropriate,
evaluated bridge is required. Arbitrary proxy compatibility requires the chosen
wire contract. See docs/DECISION_SETUP.md and docs/VALIDATION.md.
