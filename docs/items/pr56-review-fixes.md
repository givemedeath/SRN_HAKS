# PR #56 verification and CI corrections

The review of `2b926221` identified two gaps: server-owned runtime files were
verified at dispatch but not at collection completion, and import-time execution
proof exempted retained literal settings from live verification. The CI packs
jobs also exposed repository namespace imports missing from their test child
processes and a Windows runtime test patch targeting a stale package alias.

Collection now calls the owning server's runtime verifier exactly once at the
fresh completion boundary, before it publishes a successful receipt. The client
does not consume the server's runtime file inventory. Reopening a pinned terminal
receipt remains read-only and does not poll the server. A changed dependency
produces an immutable failed-validation receipt.

Import-time proof continues to qualify dynamic initializers without replaying
them. Known literal defaults, keyword defaults, closures, module/class settings
and instance fields are checked during the existing graph traversal. Opaque
factory results and ordinary mutable runtime caches are not fingerprinted as
settings. Mutable closures explicitly named as settings/configuration still
check their declared literal values. Existing non-proven source checks retain
their strict behavior.

Each proven source file has one analysis plan per pass. It shares the freshly
hashed source, AST, callable declarations and constructor index. Function and
instance checks stream through the traversal; they do not accumulate a retained
object list. Compiled code objects are not cached across files or passes.
The work-count regression uses 50 instances: one source hash, one AST parse,
one constructor index, one callable analysis, zero retained instances/functions,
and no fingerprinting of an opaque factory result. A subsequent mutation must
still fail. Hash reuse remains limited to one verification pass.

Test children retain their own import root first and add the repository root for
`tools.*` namespace imports, independently of an inherited `PYTHONPATH`. Runtime
link tests patch the module defining the called function instead of resolving a
possibly stale parent-package alias. No production runtime traversal is changed
for that test correction.

Focused validation covers both review reproductions, stale-code and conditional
settings regressions, work counts, collection/reconciliation, the affected item
modules and test selection. The full local regression suite is excluded by user
instruction. Exact source pins, test logs and CI references are retained under
`output/itemkit/pr56-review-fixes-v1/`. No GPU, client or SMG work is involved.

Validation: 312 focused tests passed, followed by 72 final boundary tests and
35 CI-planning/result tests. Source hashes were rechecked unchanged after the
final refinement. The authoritative local summary is
`output/itemkit/pr56-review-fixes-v1/result-v2.json`.
