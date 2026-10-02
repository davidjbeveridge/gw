# Security model

## Intended boundary

This release supervises cooperative, user-controlled agent workflows. It is not an OS sandbox, an enterprise identity product, or tamper-resistant agent containment.

Native hooks constrain only the operations and lifecycle events their host exposes. Agents or users may disable hooks, invoke unobserved tools, or edit files with the same OS identity. User-owned configuration outside a repository reduces accidental edits; it does not stop another process running as that user. Some native runtimes fail open on hook timeouts or unsupported output fields. Verify coverage with a real deny canary after agent upgrades.

## Permissions

A clean gw verdict never auto-approves a native tool permission. Local deny wins over external allow. Native review is used only where the adapter supports it; otherwise review is denied. No approval is inferred from an action's eventual success. No saved blanket approvals, automatic legal assent, hidden password typing, provider-policy bypass or model-refusal rewriting are implemented.

The external authority interface is opt-in. Unsupported constraints and unavailable authorities fail closed. This does not enforce third-party receipts unless a real executor integration validates them.

## Data

Raw model requests/responses and raw tool payloads are not stored in the event log. Pinned task text and complete resolved configuration are stored locally. Typed classifier input is redacted with best-effort patterns before network transmission. This is not complete PII/secret detection. Secrets can be unrecognizable to regexes, encoded, or embedded in code. Prefer opaque references resolved only inside a credential executor; do not place secrets in task descriptions or configuration.

`GW_HOME` is created with user-only permissions on POSIX. The SQLite database and API token use mode 0600. Windows ACL enforcement needs an administrator deployment policy; POSIX mode bits alone are not an ACL guarantee. Existing parent directory permissions are not rewritten.

The optional server binds to IPv4 loopback, requires a local bearer token except for minimal health status, rejects browser Origin headers, and caps request size. HTTPS is required for non-loopback external services. Redirects are refused so authorization headers are not forwarded elsewhere. Do not expose this development server publicly or treat caller-supplied client/session fields as verified identities.

## Classifiers and compression

A classifier is probabilistic, not injection-proof simply because its output is typed. Classifier errors are explicit; each goal chooses advise/approve/deny on error. The default provider is off. Operator `mode=observe` is an explicit non-enforcement mode for local policy; external authority denials still apply.

JSON minification removes only whitespace outside strings, without reserializing numbers or altering function-call arguments. No tool results are silently truncated, no generated answers are served from a semantic cache, and no reasoning signatures are modified. Caveman is an independently installed optional component with its own security/recovery model.

## Reporting

Open an issue without credentials, private tasks, or raw production traces. For a potentially exploitable disclosure, contact the repository owner privately through an appropriate existing channel before posting technical details publicly. Do not submit live secrets as a reproduction.

## Knowledge extension

Knowledge ingestion is explicit. Source/cache text remains untrusted data, not
authorization or high-trust instructions. The standalone reference HTTP/MCP
servers bind scope outside model arguments; SDK scope remains a trusted-host
assertion. Local storage is not encrypted or tamper-proof against same-user code.
Context-cache reuse depends on truthful corpus/index/ACL revision tokens. Unknown
revision caching is off by default; provider outages never serve stale packets.
Logical deletion is not secure disk/WAL/backup erasure. See the standalone
package security limitations before applying enterprise retention requirements.
