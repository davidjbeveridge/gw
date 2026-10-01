# gw development and setup

For configuring the core supervisor decision provider, follow
[skills/gw-setup/SKILL.md](skills/gw-setup/SKILL.md) and
[docs/DECISION_SETUP.md](docs/DECISION_SETUP.md). `gw setup --describe` provides a
machine-readable setup manifest without accessing model services.

Run `python -m unittest discover -s tests -v` before proposing changes. Core
runtime dependencies stay empty. Never use real provider keys in tests or logs.
Native harness tests are not licensed-agent end-to-end evidence. Do not weaken
policy, protocol checks or existing tests to make a new model appear supported.
