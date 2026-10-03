# Add a review gate without editing GW

This installable fixture demonstrates a complete runtime extension using only
`gw_supervisor.api`. It contributes a setting, an evaluator, and an agent tool.
It performs no model, network, or shell calls.

From the repository root, with the standard reference bundle installed:

```bash
python -m pip install ./examples/runtime-plugin
```

Ask the agent to prepare a global configuration plan enabling the installed plugin
`gw.example.review`. The configuration fragment is:

```json
{"runtime":{"enable":["gw.example.review"]}}
```

Apply only after reviewing the plan. Start a new native session and restart the
GW MCP interface. Package installation alone does not activate this extension.
`gw_runtime_inspect` should list it, and `gw_review_demo_status` should report its
project-scoped settings.

The exact proposed shell command `echo GW_EXTENSION_REVIEW` requests human review.
Other spellings do not match. The evaluator does not run that command and does not
overrule any other denial. Hosts without a native approval mechanism still deny
rather than converting review into permission.

Its `review_demo.enabled` setting is project-configurable and explicitly available
to the managed agent configuration tools. Try a reviewed plan setting it false;
the status tool and new sessions should reflect the change without a core edit.

The descriptor is in `src/gw_example_plugin/__init__.py`. The entry point is in
`pyproject.toml`. The integration tests install this as a separate distribution,
exercise the review verdict, configure the new section through agent tools, and
check client/project isolation and stale-tool rejection.

This is a teaching fixture, not shell-command containment, a production security
policy, or a separately published PyPI product.
