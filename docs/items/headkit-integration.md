# Headkit/itemkit integration, 2026-10-24

PR #56 integrates main through `2fe9741ad18c5a17648cc9d84999924f590bce74`
(headkit PRs #54 and #55). The imported tree shared the frozen
`e607a617c273828a37d8fc56dd43d7d8a0070844` baseline. Conflicts were reconciled
against that baseline, rather than choosing an entire side. The original source
lock and historical asset receipts remain unchanged.

## Combined behavior

- Preserve headkit's chart-once UV packing, paint/rule stages, neck shaping,
  scoped receipts, chain command and multiview geometry/detail roles.
- Retain itemkit's shared request preparation, bounded export settings,
  background decisions, geometry seeds, server-owned model verification and
  fresh dispatch/completion checks.
- Require the controlled runtime session (schema 3) and pin its startup
  configuration in every new request. Retain live loaded-code checks, including
  conditional settings and stale callbacks, in addition to deployment checks.
  Managed startup enters the import-time verifier before Comfy's main script.
  Direct bootstrap uses an empty bytecode-cache directory and does not import
  the GPU adapter entry point.
- Keep verification locking, per-pass hash reuse and phase measurements. Runtime
  session identity remains distinct from the temporary verification-pass object.
  There is no cache across dispatch, execution, completion or separate requests.
- Preserve the bounded legacy atlas helpers used by item donor/target unwraps;
  head unwraps use the newer chart-once algorithm. Explicit legacy group limits
  remain validated and enforced when supplied.

The headkit validation entry describing removal of live-object inspection records
its original revision. This integration retains that verifier alongside controlled
startup to preserve the item trial's stale-code guarantees. No performance gain
is claimed for the combined live verification path without a live measurement.

## Deployment and validation boundaries

Existing installed adapters and local runtime bindings are not changed by this
merge. A future generation run needs a freshly installed, byte-bound adapter,
controlled-startup configuration and request for its own released runtime.
Older schema-2 requests cannot be dispatched through the new runtime contract;
their receipts and generation-attempt history remain historical evidence.
Do not restart or reconfigure another session's service.

Validation is limited to affected headkit, itemkit and test-selection modules,
including both startup test families and the item atlas/recovery tests. The user
explicitly prohibited rerunning the full helper suite. CPU fixtures test the
composed startup, session changes, stale callbacks, source changes and UV
compatibility; they do not qualify a live GPU deployment. Exact source pins,
test results and unchanged accepted-package hashes are retained under
`output/itemkit/pr-conflict-resolution-v1/`.

No generated asset, production pack or client fixture is rebuilt. The four
accepted weapons remain unchanged and the Ingram Smartgun X remains on hold.

Final frozen-source validation: 608 tests across 28 affected modules passed.
All 119 frozen source pins and the six accepted package/fixture hashes were
rechecked unchanged. The separate 40-test startup integration check also passed.
