# Cougar workflow review and knife preparation

## Corrections

| Finding | Correction | Verification |
| --- | --- | --- |
| Diamond dependencies repeatedly validated the same ancestors and source version. | Operation-local receipt/result/hash caches; fresh passes at command boundaries. Dependency and review checks remain mandatory, with cycle and conflicting-pin rejection. | Diamond, stale code, rejected review, conflicting pin and changed-byte regressions. |
| Operations could freeze unrelated geometry, native archives or fixture HAKs. | Explicit stage input roles; defer native archive validation to consumers that need the contract. Unspecified legacy calls retain full validation. Fixture/comparison HAKs are scoped to fixture/client operations. | Missing unconsumed geometry is excluded while full validation rejects it; existing calibration/CPU scope tests. |
| Grip sizing was documented but not enforced. | Hash-bound `inputs.gripStandard` calibrates the measured transverse section, records five fitted sections and requires the approved usable length. The same final matrix applies to donor and working geometry. | Native grip calibration and exact preserved-axis tests. |
| Post-bake resizes depended on ignored trial scripts. | Maintained `resize-corners` command transforms authored native corners/normals and closed shadows, preserves UVs, checks unchanged axes, and writes a fresh lineage receipt. | Closed tetrahedron roundtrip, unchanged source, UV and length tests; overwrite rejection. |
| Intake, native packaging and fixtures assumed one shortsword identity. | Explicit intake ID/family, dagger profile/schema support, configurable resource identity and comparison HAK/blueprint support. Existing defaults remain compatible. | Dagger table contract, identity, budgets, texture/blueprint collision and legacy itemkit tests. |
| Dependency selection missed absolute imports through the repository's `tools` namespace. | Recognize exact repository-relative namespace module paths while preserving qualified-package checks. | New transitive-selection regression; full helper suite required after this shared helper correction. |

The existing conditional Comfy startup checks, runtime/source hashes, selected
checkpoint scopes, shared queue/submission lock, saved-shape binding, deadlines,
attempt counting and uncertain-job reconciliation are unchanged. No timestamp-only
cross-command hash cache was introduced. Archived receipts remain immutable.

## Measurements

`output/itemkit/cougar-fineblade-knife/verification-benchmark-v1/benchmark.json`
compares 32 references to one 4 MiB immutable input:

- Before: 32 hash calls, 134,217,728 bytes, 0.614683 seconds.
- After: one hash call, 4,194,304 bytes, 0.118947 seconds.

This is a bounded verification benchmark, not an end-to-end generation speed claim.
Future dispatch and completion still perform fresh checks. The focused validation
logs include `output/itemkit/knife-workflow-tests-v3.log` (124 tests passed) and
`knife-workflow-tests-v4.log` (70 focused itemkit tests after final scoping). Full helper
results and timings are retained separately in `output/itemkit/knife-full-helper-*`.

## Knife state

The supplied knife image is retained byte-for-byte, SHA-256
`3c697aa120b1d1deece42bf9d542f2c301e1099854ed463ca8739b1876a47ec3`.
Active preparation is `output/itemkit/cougar-fineblade-knife/calibration-v1.json`.
Image analysis selects background removal; foreground and camera calibration must
still be performed and visually reviewed before geometry submission.

Installed dagger donors and icons were extracted from a stock-only resource lookup
and measured locally. The verified contract is BaseItem 22, ItemClass `wswdg`,
ModelType 2. Appearance index 7 / colour 1 is collision-free in the declared private
stock + shipped Human + approved shortsword namespace. Knife texture and blueprint
names are distinct (`sr_cfk_07`, `sr_cfk`); the candidate HAK/module use
`srn_cfk_test` / `sr_cfk_test`. No gameplay table was edited.

The approved shortsword HAK and GLB were reverified unchanged. The existing trial
ledger is retained; no knife geometry attempt has been submitted. The knife retains
its two-attempt allowance. No client was launched or controlled.

## External prerequisite

At the latest probe, port 8188 was owned by an unrelated Troll workflow started
through ordinary `main.py`. `/headkit/runtime-identity` returned HTTP 409 with
`verified: false`; the queue was idle. This is not a verified generation runtime.
The process was left untouched under the workspace's other-worktree rule. The user
explicitly selected waiting for that session to release the shared runtime.
Do not bypass the verifier or spend a geometry attempt until this is resolved.

## CPU donor and fitting corrections, 2026-10-23

The preceding intake/runtime status is historical. Current state is bound by
`cougar-fineblade-knife-checkpoint.md`; one knife geometry attempt is used and
GPU work/release are complete. The approved shortsword remains unchanged.

The 200K donor exposed two source-atlas issues: residual UV defects and excessive
padding at the 4K source resolution. The item-specific bounded repair now retains
failed candidates, preserves geometry and healthy UV domains, and tests measured
two-pixel 4K gutters. Starting padding at four pixels produced 52.02% useful coverage
with no missing charts. The successful source stage took 255.297 seconds, including
126.109 seconds for the atlas and 111.862 seconds for the bake. These are separate
stage measurements, not a controlled performance comparison with the failed runs.

Eight matched clay/lit/unlit source views passed for fitting and finishing. The
95.9% nearest-voxel fallback prompted a distance/axis audit: the original-frame
sample median is 0.001074 units and maximum 0.001976, consistent with the exported
UDF shell lying just outside the sparse 1536 appearance surface. Alternative axis
frames are much farther away. The source was not transformed during sampling.
Generated grip lettering still needs the authorized reference-based finishing.

The actual calibrated fit then failed its unchanged correspondence check. Assigning
a rotated, transversely calibrated affine map as a Blender object transform loses
its shear during decomposition. The maintained fitter now applies coordinates
directly to mesh data, transforms split normals analytically by inverse transpose,
preserves UVs exactly, and measures Blender's display-normal encoding separately.
The regression combines rotation and unequal transverse scales: maximum coordinate
error is 2.18e-8, maximum encoded normal-vector error 8.20e-5. All 79 affected itemkit
tests and the Blender affine/native-fit smoke pass on unchanged source. This fixes
correctness; no speedup is claimed. The failed real fit took 87.16 seconds and is
retained. Native/client acceptance is still pending.

The diagnostic render itself succeeded. Its orchestration script subsequently
refused to overwrite an older completion filename; the old file was preserved and
the new exact launch/render receipts were explicitly rebound in checkpoint v26.
CPU dispatch now uses fresh paths, pinned input records and captured launcher errors.

## Requested follow-up optimization pass

Reviewed the new item atlas, donor, fit, verification and dispatch paths. Fresh byte
checks and receipt/review gates remain intact; no timestamp cache was added.

- Replaced Python mesh-corner tuple lists with bulk Blender reads and eliminated
  duplicate correspondence passes already enforced by the affine helper. Reading
  598,128 donor corner normals measured 0.6142 seconds versus 0.02046 seconds, with
  exactly equal values. This is a read-phase benchmark, not a complete-fit speedup.
- Replaced repeated two-dimensional gutter windows and padded copies with separable
  NumPy operations using two result arrays and one scratch buffer. On identical
  retained ownership data tiled to 4K, the final comparison measured 4.8022 versus
  1.1403 seconds (4.21x), with identical radius-1/2/4 collision counts. Peak tracked
  temporary allocation fell from 487,070,741 to 251,660,716 bytes (48.3%). This is
  `item-optimization-benchmark-v3.json`; it does not measure host RSS or end-to-end
  generation. An earlier filtering-library experiment saved memory but was slower
  and was rejected; its evidence remains retained.
- Fixed final UV evidence accidentally recording the last native part's face group
  as the isolated repair faces. A regression exercises the saved proof and unchanged
  mesh data. Independent explicit-neighbourhood tests cover random labels, empty
  images, image boundaries and one-pixel dimensions.
- The dense donor exposed Blender's display-normal quantization: 164 of 598,128
  corners exceeded the provisional .002 vector-error gate; maximum angular error
  was about .608 degrees. Fitting now retains exact analytic normals separately
  from their Blender encoding, records both errors, and bounds display error at
  one degree maximum / .05 degrees at the 99th percentile. Position and UV checks
  retain their original tolerances. This is an explicit measured display allowance,
  not permission to alter native corner attributes or source/runtime verification.

Source atlas chart/sampling checks and the shared stale-code verifier were reviewed
without additional changes. Their existing fresh-byte, conditional-setting,
callback, conflict and dependency coverage remains required. Final regression
results and the next real fit are bound by the authoritative checkpoint.

## Final transfer corrections

The first final transfer stopped on 537 texels across 13 knife faces, out of
6,301,178 mapped texels. Exhaustive donor queries isolated the failures to small
guard and pommel recesses with conflicting surface directions. The affected
triangles cover 0.2381% of the surface. Their nearest donor distance is at most
0.002923669 native units. Matched target/donor views are retained with the decision.
A knife-specific, exact-geometry-bound colour patch is qualified to 0.00293,
within the existing 0.003 global transfer bound and 0.0001 texture-fraction cap.
The legacy 0.0021 default remains unchanged. Other faces still require compatible
normals; no geometry, successful bake pixels or appearance-field coordinates change.
Final runtime texture approval remains a separate visual gate.

The final bake's Blender pixel read constructed a Python float tuple before
conversion. A bulk read produces bit-identical pixels and avoids that allocation.
On the real Blender 1K float-image API, tracked peak temporary allocation fell
from 150,995,080 to 16,777,672 bytes. The measurement is deliberately bounded to
the read phase; it does not establish 4K process RSS or end-to-end bake savings.
The 120 affected tests and real-image regression passed on unchanged source.

An early shadow preflight found that ordinary reduction partially obstructed the
knife's angled pommel bore. The maintained loop proxy now constructs in the
measured opening frame and returns to native coordinates. Native-X behavior is
preserved. Rotated/translated loop, winding, opening and zero-axis tests cover the
extension. Real preflight and subsequent production results are bound in the
checkpoint; a failed preflight is not native or client acceptance.


## Private delivery closure

The actual final transfer clears all visible misses. The qualified patch accounts
for exactly 537 texels; successful projection pixels remain unchanged apart from
recorded float-range normalization below 3.6e-7. The closed shadow assembly passes
at 488 triangles and preserves both measured bore rays. The final 1K views pass
for private testing, with reduced-shell/rim faceting retained for client assessment.

The first inventory previews were too dark and vertical. A separately pinned
CPU icon pass uses the actual 1K diffuse unlit, a shared diagonal camera and the
measured 32px native cells. It changes neither runtime geometry nor maps. The
explicit delivery route feeds those reviewed icons to maintained native.prepare
and native.compile_package. Original previews/receipts remain unchanged. Native
corner/shadow roundtrips, both distinct Cougar resource namespaces, the unchanged
shortsword and all 21 private module resources are verified. The fixture contains
both shipped Human bodies. The client has not been launched.

A final review found three separate parent-validation calls in the new delivery
helper. Version 2 shares one VerificationPass across those calls while retaining
fresh dispatch/completion checks. On the actual unchanged receipts it hashed
3,910 files / 1,860,286,728 bytes; the second and third lookups added zero hashes.
The equivalent independent scopes contain 11,316 file reads / 5,393,529,893 bytes.
The shared validation phase measured 35.281 seconds. The independent workload
is computed from exact receipt scopes, not a second timed benchmark. The complete
measurement script, including scope accounting and fresh checks, took 96.422
seconds. The selected private package was built with the retained v1 helper and
is unchanged by this separately versioned follow-up.

Recorded delivery stages: export 72.156 seconds, native compile/audit 23.641,
fixture 18.156. The delivery child took 222.079 seconds; its launcher subprocess
and completion checks took 247.594 seconds. Launcher preparation is outside that
last timer. These are retained operation timings, not a claimed total production
time or controlled before/after end-to-end comparison.

## Knife length revision after client viewing

The user requested a 10% reduction in every knife part's length. Maintained
`resize.transform_part` applies the same positive affine map to all native
corners and shadows around the fixed grip centre. The retained dense donor
receives that map too. Each part measures [1, 0.9, 1] in native X/Y/Z; width,
depth and UVs remain exact. Normals use the analytic inverse transpose, while
Blender display encoding is separately measured (maximum 0.7491 degrees;
99th percentile below 0.00485). Both pommel bore probes still pass in visible
and shadow meshes. The three focused grip regressions pass. The first sandbox
test invocation encountered a temporary-directory permission error; the same
unchanged tests passed using the task's writable temporary directory.

The new code reuses maintained resize/render/native helpers, scopes inputs to
CPU operations, renders once at four threads, and compiles each part once.
It performs no Comfy inspection, generation, appearance sampling or rebake.
The validated comparison module is copied unchanged. Recorded child timings:
geometry 5.812 seconds, matched rendering 163.813, geometry/render/icon stage
198.062 total; native delivery 49.609 seconds. Launcher verification is additional.

A final metadata audit caught a shallow-copy omission: the fixture's singular
`hak` pointer still named the parent although `fixtureHaks` correctly named the
new package. The selected `private-fixture-v2.json` and `delivery-v2.json` correct
this redundant pointer; original receipts and package bytes remain immutable.
Independent checks confirm fresh native roundtrips, seven exact HAK resources,
unchanged diffuse bytes, the unchanged comparison module and approved shortsword.
The checkpoint is v35. Current usable grip length is 0.16487262 native units;
the global grip standard remains unchanged. Client review is pending.

## Corrected total length and missing private-fixture actors

The user clarified the target as 30% shorter overall. The length70 variant is
derived from original v34 corners, not compounded from length90. All three parts
and their combined bounds measure [1, 0.7, 1] in native X/Y/Z. Exact width/depth,
UVs and runtime diffuse bytes are preserved. Native normals use inverse transpose;
the retained donor receives the same transform. Eight geometry/lit/unlit views,
icons, blade thickness and pommel bore were reviewed. Counts remain 4,852/488.

The old client log contained blank NPC tags and no actor-ready events, consistent
with failed entry-time creation. The maintained fixture builder now places the
two pinned Human UTC bodies directly in the entry GIT, ahead of the player.
It rejects collisions and out-of-area placement, then verifies an exact GFF
roundtrip. The entry script waits for valid area/actors with a bounded retry,
reports equipped resrefs, and does not attach the player's camera. The inherited
motion heartbeat now uses the current item identity rather than the shortsword.
The rebuilt module was launched at the user's request; retained startup logs
confirm both actors spawned and both actors plus the player equipped the knife.
The user then said "looks good". V38 records that appearance/length approval
separately from full client validation and production promotion.

All 84 affected itemkit tests passed on unchanged source. The initial discovery
command lacked the package root and failed relative imports; the corrected
invocation passed in 18.588 seconds. Fresh native corner/normal/UV/shadow
roundtrips, seven HAK payloads and 21 module resources pass. The accepted
shortsword and shipped Human HAKs remain byte-identical.

Optimization review: the new placement work is linear in two actors and uses no
live polling. Only the affected knife and module are rebuilt. Existing maps and
maintained resize/render/export helpers are reused; there is no Comfy scan,
generation, appearance-field sampling or GPU work. Geometry took 3.078 seconds,
four-thread matched rendering 115.391, and the geometry/render/icon child 135.688
total. Native delivery took 56.813 seconds, including the rebuilt fixture.
These are retained child timings, not controlled performance comparisons;
launcher verification is additional. The prior 90% version remains immutable.
