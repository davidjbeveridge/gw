# Reviewed harness sync

[Handbook](README.md) · [Plugins](PLUGINS.md) · [Learning](LEARNING.md)

`gw-sync` distributes explicit, versioned sets of harness assets. It is not a
live settings mirroring daemon. The initial free implementation supports a local
bundle repository and an HTTP adapter/reference service; remote storage can be
replaced behind the same `BundleProvider` contract.

## Publish a bundle

```bash
gw sync init
gw sync push --root /path/to/portable-harness --include 'skills/**/*.md' \
  --include 'tools/*.py' --include 'policy.json' --channel team
```

Only matching explicitly named UTF-8 files participate. The command returns a
content-addressed manifest reference. A file's bytes are stored once by SHA-256;
unchanged assets are reused by later manifests. Channel updates require the old
reference through `--expected OLD_REFERENCE`; a concurrent update cannot silently
replace another publisher's channel.

Repository paths, credentials, transcripts, model weights, local databases,
generated dependencies and private keys are not a portable harness. The packer
excludes common sensitive files and detects some literal secrets, but this is
best-effort screening, not DLP. Review the selected files before publication.
Environment-variable and credential references can be portable; actual credentials
must be provisioned separately on each machine.

## Inspect, plan, then apply

```bash
gw sync show team
gw sync plan team --destination /absolute/staging/harness --output sync-plan.json
# Inspect files, revisions and conflicts in sync-plan.json.
gw sync apply sync-plan.json
gw sync history
```

The plan records destination contents and its own hash. Changing the plan or the
destination invalidates it. Unmodified previously applied files can update;
conflicting local edits require reconciliation. Removed manifest files are listed
but **not automatically deleted**. Symlinks, path traversal, case-colliding files,
tampered blobs and incompatible descriptors are rejected.

A cooperative destination lock excludes simultaneous applications from this tool.
A crash can leave a lock file; inspect the process and destination before manually
removing it. Writes are atomic per file, with best-effort rollback that avoids
clobbering a later external edit. This is not an atomic filesystem transaction or
protection against a malicious same-user process.

Application never runs the bundled code, imports project trust, restarts an agent,
or changes native permissions. Review the result, then perform the harness's
normal installation and GW trust steps. This separation is especially important
for automatically generated learning artifacts.

## Team/server use without shared SQLite WAL

Do not place a live SQLite repository database directly on arbitrary NFS or a
file-sync service. Run a repository service on its own local disk instead:

```bash
# Provision GW_SYNC_TOKEN outside chat and source control first.
gw-sync --store /absolute/bundle-repository serve --port 7791 --writable
```

It binds loopback and requires the private bearer token. Off-machine deployment
needs an operator-managed TLS ingress and appropriate authentication/network
policy. This reference service has one shared repository token, not enterprise
SSO, per-team RBAC, or a managed cloud SLA. Omit `--writable` for read-only serving.

On a client, create an options file:

```json
{"endpoint":"https://bundles.example/v1/bundles","key_env":"GW_SYNC_TOKEN"}
```

Then:

```bash
gw sync init --provider http --options bundle-provider.json
gw sync plan team --destination /absolute/staging/harness --output sync-plan.json
```

Client application history remains local; bulk content and channels live at the
chosen provider. Blob/manifest hashes are checked again by the client. The HTTP
adapter refuses redirects and non-HTTPS endpoints except loopback. There is no
arbitrary remote file-path or shell-execution operation.

## Interface and observability

`BundleProvider` implements `put_blob(bytes)`, `get_blob(hash)`,
`publish(manifest, channel, expected)`, and `resolve(reference)`. The portable wire
version is `gw.bundle/1`. An installed `gw.sync.providers` entry point supplies
another implementation. `SyncWorkspace` owns local application state, so a remote
provider does not need SQLite or knowledge of a user's destination paths.

Published/planned/applied/failed operations are journaled. With GW tracing enabled,
the trace stores compact operation data and journal references. It does not copy
the synchronized files into the observability store.

This synchronizes a selected portable harness, not every account or piece of
machine state. Cloud adapters, cryptographic signatures, managed rollout policies,
secret provisioning and cross-platform execution testing remain separate concerns.
Content hashes provide integrity, not publisher identity or trust in executable
content. HTTPS/token configuration and human review remain important.
