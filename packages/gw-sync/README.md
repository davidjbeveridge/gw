# gw-sync

Content-addressed, reviewed harness bundles. Independent MIT package, Python 3.10+,
no runtime dependencies. Version 0.1.0. Portable protocol `gw.bundle/1`.

```bash
python -m pip install .
gw-sync --store ./repository push --root ./harness --include '*.md' --channel team
gw-sync --store ./repository plan team --destination /absolute/staging --output plan.json
# Review plan.json before applying.
gw-sync --store ./repository apply plan.json
```

Only explicit matching UTF-8 files are stored. Sources, manifests and channels are
separate: blobs are addressed by SHA-256; immutable manifests list paths, hashes,
sizes and executable flags; mutable channel updates use compare-and-swap. Reuse
the prior channel reference with `push --expected REFERENCE` when updating it.

A reviewed plan includes existing destination hashes. Changed plans, stale local
state, conflicts, symlinks, path traversal and tampered content are rejected.
Obsolete files are reported, not deleted. Cooperative application locks and atomic
per-file writes reduce accidental races; this is not a whole-filesystem transaction
or protection against a malicious same-user writer. Inspect crash-left locks.

Secrets, transcripts, databases, common credentials and generated dependencies
are excluded. Pattern checks are not complete DLP; review every selected file.
Applying a bundle never runs its code, changes native permissions, trusts a project,
or restarts an agent. Activation remains an explicit host/operator action.

`BundleProvider` has put_blob/get_blob/publish/resolve. `SyncWorkspace` keeps local
application/journal state independently of the provider. A remote implementation
needs no knowledge of local paths or SQLite. Native plugin factories use
`gw.sync.providers` and receive operator-controlled options.

`HttpBundleProvider` implements the same contract over authenticated HTTPS or
loopback HTTP, with bounded messages, hash validation and no redirects. Serve a
reference repository on local disk, not SQLite WAL on an arbitrary NFS share:

```bash
# Provision GW_SYNC_TOKEN outside chat/config beforehand.
gw-sync --store /absolute/repository serve --port 7791 --writable
```

Off-machine use needs a correctly configured TLS/authentication ingress. Omit
`--writable` for a read-only service. The reference token covers the repository;
enterprise RBAC, signatures, SSO, staged rollouts and a managed SLA are not bundled.
Content integrity hashes are not publisher authentication.

The HTTP envelope is protocol/method/request. Methods: put_blob(data: base64),
get_blob(hash), publish(manifest/channel/expected), resolve(reference). Replies
contain protocol/result. Clients verify blob and manifest hashes after receipt.
The service exposes no shell or arbitrary server-file read operation.

Copy the package directory elsewhere and build it unchanged. Run
`python -m unittest discover -s tests -v`; tests cover local and actual loopback
HTTP providers, CAS, reviewed application and conflict rejection. No cloud account
or live team credentials are needed. GW integration instructions:
https://github.com/davidjbeveridge/gw/blob/main/docs/SYNC.md.
