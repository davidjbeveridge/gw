---
name: gw-setup
description: Configure and verify gw's core supervisor decision model without changing worker authentication or exposing credentials.
---

# Configure the core decision backend

Use for TypeSafe/OpenRouter Jev, local Kev/Laya, an existing System One or JSON
chat proxy, or an evaluated custom/CUA classifier bridge.

1. Run `gw --version`, `gw setup --describe`, and `gw decision status` using the
   intended `--project`/`--client`. Do not confuse this with `gw models` worker
   selection. Read `docs/DECISION_SETUP.md` for the selected backend.
2. Establish the user's chosen model, host and protocol. Reuse supplied facts.
   Never infer System One support merely from an OpenAI-compatible base URL.
   Do not claim CUA-S1 nano/forms are general-purpose classifiers.
3. Ask the operator to provision a credential in an environment variable or
   existing private file OUTSIDE chat. Only accept its variable NAME or file
   path in setup arguments. Never inspect unrelated OAuth or password stores.
4. Use `gw setup --preset PRESET ... --dry-run`. Preserve worker registry,
   credentials, goals and existing client overrides; respect locked policy.
   Use `--client NAME` only for a requested client-specific override.
5. Explain the destination and that `--check` makes one synthetic, possibly
   billable request containing no project data. After consent to configure/test,
   run the same setup with `--check --yes`. Exit 2 means the check failed and
   config was not changed. Do not retry blindly, heal JSON or switch providers.
6. Run `gw decision check --client NAME --project PATH` from the same environment
   as the agent, if the setup check ran elsewhere. Start new agent sessions and
   run the README deny canary to verify actual hook loading. Report exactly
   which checks ran, not hypothetical live support or accuracy.

Local runtimes are installed and warmed separately, never implicitly. Do not
install GPU packages/download weights without authorization. Use a separate
uninstrumented decision endpoint to avoid the classifier recursively invoking
itself through gw's proxy callback. Keep ordinary inference supervised.

For unattended operation always use explicit flags, `--dry-run` or `--yes`.
`gw setup --describe` is the machine-readable interface. A successful smoke test
is not an evaluation of actual task alignment, governance or model quality.
