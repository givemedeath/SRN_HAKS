# Generation verification performance

The October 22 correction optimizes verification without reusing acceptance across
operations. Historical generation receipts, the two-attempt knife ledger and the
accepted shortsword remain unchanged. No Comfy service was started or modified.

## Corrections

| Cost | Correction | Preserved checks |
| --- | --- | --- |
| The same bytes were hashed by separate helpers during a single preparation or dispatch validation. | Explicit, bounded verification passes share actual hashes. The server shares source reads between membership, startup proof and live-code checks. | New passes at preparation, preflight, locked dispatch, collection inspection and final completion. Separate launcher/process boundaries remain independent. Conflicting pins still fail. |
| One module was parsed several times, and each retained instance re-walked the full file for its constructor. | One AST per freshly verified content hash/path/compiler setting; one constructor index per source. Conditional analysis copies only changed statement nodes. | Conditional branches still resolve against each actual instance; unknown conditions and ambiguous declarations fail closed. Shared ASTs remain unchanged. |
| Foreign instance/function/frame snapshots and a persistent raw-source LRU inflated retained state. | Keep only state that contributes to verified source settings, while continuing to traverse foreign holders. Remove the persistent raw-source cache; bound the shared byte cache to 32 MiB total and 1 MiB per file. | Foreign callbacks, closures, iterators, native containers, descriptors and execution frames remain traversed. Only exact builtin leaves/containers use fast paths; subclasses keep full inspection. Live code is freshly fingerprinted. |
| Runtime/model verification could overlap. | Server verification entry points share a process-local gate. Existing shared submission/release locking remains. | Queue ownership, uncertainty reconciliation, deadlines and before-load checkpoint checks are unchanged. |
| Timing conflated verification, waiting and model execution. | Per-phase elapsed time, files/bytes hashed, cache hits, objects visited, parsed files, retained state counts and sampled process RSS. | Measurements are metadata, outside runtime identity fingerprints and all acceptance decisions. Unavailable RSS is null. |

Measurements are retained beside prepared requests as `*.verification.json`, at
submission in `submission-verification.json`, and in collection receipts under
`verification`. The server also logs phase reports and returns them in the
`X-Headkit-Verification` response header, which the client retains at submission.
RSS is sampled every 50 ms and at phase boundaries: it includes any resident
models and is not an exact allocator peak. File hashing remains streamed; four
runtime readers each use a 1 MiB buffer. Reading a large checkpoint does not put
the whole checkpoint into the verification cache.
The byte-cache cap is not a total process-memory limit: the current loaded-code
pass also owns source-analysis records, syntax trees and live-object traversal
state. These remain temporary and are discarded after the pass.

## Measured CPU comparison

Retained matched results are `output/verification-optimization/before-final.json`
and `after-final.json`. The synthetic fixture contains 150 helper functions, 100
conditional model instances and 1,000 foreign callback holders. Three passes per
variant use allocation tracing in both variants; the verified source/code
identities agree exactly.

| Median / count | Before | After |
| --- | ---: | ---: |
| Elapsed time | 6.810 s | 2.702 s |
| Peak traced Python allocations | 5,330,443 bytes | 1,785,538 bytes |
| AST parses per source/pass | 6 | 1 |

The separate synthetic startup-proven branch comparison
(`startup-proof-benchmark-v1.json`) also preserves the exact identities: median
4.548 s to 2.026 s and 2,303,539 to 1,149,315 traced peak bytes. That comparison
simulates proof acquisition; real import-time proof and stale cached-bytecode
behavior are covered by subprocess regression tests.

This is about 60% less elapsed time and 66% lower traced peak allocation in this
fixture. It is not a measured end-to-end Comfy speedup, a GPU benchmark, or an
attribution of the earlier host RAM spike. The full runtime file census remains
required. No timestamp-only cache or trust shared between client and server was
introduced.

The retained knife geometry request has 1,337 distinct client input pins, including
1,221 source files and three selected models. Counting the old and new client
submission call paths gives 6,345 versus 2,674 file hash operations (preflight plus
fresh locked dispatch). This is a derived work count, not a measured complete job:
it excludes the launcher's additional dependency pins, server verification and
collection. The one-read-per-pass regression exercises the underlying guarantee.

`phase-telemetry-v2.json` additionally exercises the actual reporting API on a
bounded CPU fixture. Source reading hashes one 6,410-byte file; loaded-code analysis
then hashes no additional file bytes, parses one AST and visits 47,213 objects.
That analysis phase sampled 34,848,768 bytes peak process RSS and ended at
32,985,088 bytes. The report confirms pass storage was released. This fixture
is separate from the matched benchmark; its RSS includes interpreter residency.

## Validation and deployment

The added regressions assert work counts rather than fragile timing thresholds:
one hash per distinct file/pass, fresh bytes with restored timestamps, conflicting
pins, nested pass isolation, exception cleanup, bounded binary/source retention,
parallel same-file requests, serialization of heavy passes, unchanged ASTs and
stale code after an earlier successful verification. Existing conditional-state,
stale callback, namespace, source inventory, startup-proof, queue and release
regressions remain in the required full suite.

The complete helper suite ran 2,068 tests, with two skipped, in 1,503.979 seconds
on unchanged frozen source. Its only failure was an ambiguous dependency literal
in the startup test fixture: the new `verification.py` filename also exists in
itemkit. The fixture now uses three qualified paths that copy the same files.
The regenerated catalog has no unresolved edges. All 45 affected startup,
catalog and test-scope tests then passed in 97.434 seconds, again with unchanged
inputs. No runtime implementation changed between these validations.

Authoritative combined evidence is
`output/verification-optimization/validation-v2.json`, with final source bindings
in `freeze-v2.json`, codeVersion
`af8dd5a47cfaf59f7b0a498f77bbc4b24934256ea4d45193b74a7a7b644ac109`.
The initial `full-suite-result-v1.json` retains its nonzero status; it has not been
rewritten as a successful run. The correction receipt verifies that the only
changed pins were the test fixture and generated dependency catalog. Earlier
exploratory tests are not acceptance evidence; edits during those runs correctly
triggered stale-source failures.

Fresh synthetic native validation also passed on this final freeze:
`output/verification-optimization/native-smoke-v3-launch/launch.json` records
exit 0, unchanged consumed inputs and 52.047 seconds. It compiled and sanitized
the dagger parts, verified native roundtrips and built the separate combined
fixture. Its geometry is deliberately synthetic; it is not the generated knife
delivery, and neither the game client nor GPU was launched.

The installed adapter is intentionally untouched. A future GPU run must install
these frozen adapter sources in this workflow's owned runtime, establish a new
verified startup and fresh runtime/source bindings, then prepare a new request.
Do not make old runtime bindings pass by editing their hashes or receipts. The
knife's already-retained generation outputs can continue through separately
bound CPU stages; no new geometry submission is required by this correction.
# Preparation through collection: model ownership correction

New itemkit requests use `modelVerification: server-owned-v1`. Their checkpoint
dependencies remain explicit in `modelInputs`, the byte-bound local bindings and
hash-keyed graph loaders. Comfy resolves and freshly hashes those exact models at
preparation, under the dispatch lock, immediately before loading, and at completion.
The client and shared launcher no longer consume or repeatedly hash model weights.
Legacy headkit requests retain their previous client and server checks.

Completion now records model verification evidence; a mismatch becomes a terminal
failed-validation receipt. Re-reading an immutable terminal receipt does not need
the server. Source/runtime identity checks, conditional-setting and stale-callback
checks, saved-shape equality, queue locking, deadlines and reconciliation remain.
No timestamp cache or trust across validation boundaries was introduced.

Input enumeration and CLI startup share reads only within their lexical validation
pass. Measure client bytes, server bytes, elapsed time and sampled RSS separately;
do not interpret bytes hashed as resident memory. The third longsword baseline was
882.031 seconds preparation through collection versus 96.99 seconds reported by
Comfy; these overlapping intervals must not be subtracted as exact overhead.

The user-selected clay fallback is explicit `conditioning: clay-detail-v1`, with
separate reviewed foreground masks, exact image hashes and at least four paired
normalized landmarks within 2% of the frame. Detailed-only remains the default.
Both conditioning images must share the canvas and pass the existing foreground
checks; saved-shape appearance continues to use the detailed image.

Matched model verification on the actual owned service (including legacy
within-pass deduplication) measured **50.009 s before / 23.760 s after**. Client
bytes fell from **8,102,770,705 to 207,156,681**; the server still freshly hashed
all **7,895,614,024 model bytes** in each variant. This is a 52.5% reduction for
the measured boundary and 97.4% less client byte reading, not an end-to-end claim.
The full helper suite ran concurrently, so elapsed times are observational.
The fresh runtime identity checks and launcher/startup are outside this benchmark.

All **206 helper modules / 2,104 test executions passed** in 924.344 seconds with
unchanged source, version
`7a8d377460d48aad16ba12d319d44f0a423541dfbe2f994bbd06f085e778ef1d`.
Evidence: `output/itemkit/cougar-fineblade-longsword/retry-optimization-audit-v2.json`,
`model-ownership-benchmark-v2/result.json` and
`isolated-full-helper-optimization-v1/result.json` in the same asset directory.
Do not infer a verifier RAM reduction from these timings: sampled RSS includes
model residency, and the existing loaded-code traversal is unchanged by this pass.

The first real optimized run then completed preparation through collection in
**411.859 seconds (6m 52s)**, versus **882.031 seconds (14m 42s)** for attempt three.
Preparation was 184.281 versus 315.156 seconds; acknowledged submission was reached
at 342.687 versus 677.734 seconds. Comfy reported 50.25 versus 96.99 seconds of
execution. These intervals overlap. The new run used clay input and already-loaded
models, so the observed 53.3% total reduction is not a controlled attribution of
every saved second to this code change. All fresh checks passed, including the
new server model check at completion. Exact bindings and caveats are retained in
`output/itemkit/cougar-fineblade-longsword/optimization-end-to-end-v1.json`.

---
