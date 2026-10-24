User approval addendum: output/itemkit/pistol-trial/completed-weapons-user-approval-v1.json
SHA256: 28da1b6dbcde332078ec2468f5a292d2c89f13735c7a1a2ff7ef1b0d803d8e38
All three Cougar blades and the Colt L36 pistol are user-approved and finished. The SMG remains on hold. Package bytes and historical records are unchanged; no production deployment performed.

Authoritative completion: output/itemkit/pistol-trial/checkpoint-v31.json
SHA256: dc4334d5e87eda8b4313bb369a3327bcaebde7ec7855c380dd98f595fb688b80
User accepted the pistol after viewing the updated test module and called it finished. SMG remains on hold. No production deployment performed; individual client checklist items were not separately reported. Historical readiness records remain unchanged.

Authoritative completion: output/itemkit/pistol-trial/checkpoint-v30.json
SHA256: be266357a473b4dbec7be9c48e0274a052fe6dcb54c1203764f2ce5ccc1266a0
Pistol delivery-v2 is ready for user-controlled in-game testing: both finishes, all three completed Cougars and both Human bodies. Final qualification supersedes the delivery manifest pending-audit marker. Full regression was not repeated; targeted repairs passed. Client acceptance and production promotion remain pending. SMG remains on hold.

Latest user instruction: Do not run the full regression suite again. The single full run is now terminal; preserve its results and use only narrowly targeted tests for the known mock/catalog fixes. This supersedes earlier full-rerun suggestions.

Authoritative continuation: output/itemkit/pistol-trial/checkpoint-v29.json
SHA256: 5f602f3824dc99f4eca6ec302350f40b141ae7b23b6a080300b2156e706ac292
Real native package, combined fixture and ZIP/gallery built. Final sign-off pending full validation (live session 78397), test mock/catalog repairs and final audit. Read exact bindings. Earlier active-operation text is historical.

Authoritative continuation: output/itemkit/pistol-trial/checkpoint-v28.json
SHA256: 71ed8322d7ab65b875839c9de60a6e2a423b9fd91d6fdf5627e42b69c4c31b12
Shadow reviewed at 468 triangles. Final transfer has zero unresolved misses; base and alternate maps complete. Final matched renders/native array export active: session 46372. All previous operations terminal. Read exact checkpoint bindings; package is not yet ready.

Authoritative continuation: output/itemkit/pistol-trial/checkpoint-v27.json
SHA256: dc5ed47d3ce5b057cfd29acd83c62ce50e3eebada21145bfabcd4a5f1fc0fd35
Final atlas passes. Active sessions: final texture transfer 8182 and simple silhouette shadow 65890. All earlier experiments terminal; voxel proxy rejected visually.

Latest operation correction: session 14757 is terminal failed (proxy retained microscopic cavities). Shadow-surface v2 is now active; see pistol-shadow-surface-v2-config.json and its exact launcher receipt. Session 14757 must not be restarted. The v2 helper uses 0.003 native voxel pitch and retains the largest connected shadow surface; final silhouette/opening acceptance remains mandatory.

Authoritative continuation: output/itemkit/pistol-trial/checkpoint-v26.json
SHA256: 461cc518a223ebcc7d99a6426a64e8bd15df493a1093be74079775e3a2e0ad42
High-genus topology measured (414 handles). Shadow-only surface proxy active session 14757. All earlier runs terminal. No accepted final atlas or shadow.

Authoritative continuation: output/itemkit/pistol-trial/checkpoint-v25.json
SHA256: 7f8b8869504514d581e286deb4fc2654a3d1410b118fb61fb33a0012be3b61be
Active: atlas chart-quality session 94714 and shadow connectivity session 90455. All earlier runs terminal. Collect both exact results before new work.

Authoritative continuation: output/itemkit/pistol-trial/checkpoint-v24.json
SHA256: c42c0bdd395677df4d6e6d4014cca9998f8779ba34999e0bb3decb414eece339
Normalized UV packing active (73921). All shadow experiments terminal; no accepted shadow. Matched visible geometry reviewed with final shading still pending. Earlier active-operation text is historical.

Authoritative continuation: output/itemkit/pistol-trial/checkpoint-v23.json
SHA256: dc5347b6ce8b28a9d4270421f6d7b075d8f6ab36b73d7478ad3cecbf0680e761
Visible reduction passed at 9996 assembly triangles. Shadow opening failed. Matched geometry review active, session 12845. Earlier active operations are terminal.

Authoritative continuation: output/itemkit/pistol-trial/checkpoint-v22.json
SHA256: b1727dfea853cbde1d05d046619bfb41831cee7b99063a26b2d31d66f2389ff5
Real fit verified. Component-aware reduction active, session 79257. Collect exact receipts before further processing. Earlier active-operation descriptions are historical.

Authoritative continuation: output/itemkit/pistol-trial/checkpoint-v21.json
SHA256: 4517e1dac6e6b3d5dceb682cac0ecbaa77aa4411a38a04f2a2aabeda9386c699
Donor bake v3 completed successfully. Real pistol fitting/reduction is active, session 14065. Collect exact receipts before editing pinned sources. Earlier active-operation descriptions below are historical.

V3 progress: repair.json is retained (SHA256 3f15949d23b6ac31c428413b300ce4c3ac0b1b786665192c6818254fd276220c): all four UV audits and preserved-domain padding passed; 20 relocated faces cover 0.00701 percent of surface, geometry unchanged. Session 37716 is confirmed live and baking. Prepared next helper output/itemkit/pistol-trial/process-real-pistol-v1.py is not yet dispatched or qualified; inspect and bind real donor after successful collection. It uses the approved firearm standard, selected working mesh, and exact same donor/working transform.

Authoritative continuation: output/itemkit/pistol-trial/checkpoint-v20.json
SHA256: 53690cc1e0fe84d3a0c967b524dc8007249793caa9a0367d3e1c9ec13db29fd9
Approved firearm grip is now enforced; 39 affected tests passed. Donor UV repair/bake v3 is active in session 37716. Collect its exact receipt before source edits. Previous v19 active-operation instructions are historical.

## Latest scope instruction (2026-10-24)

Finish the Colt L36 pistol and its validated private test package, then stop.
Keep the Ingram Smartgun X on hold; do not resume its preparation or generation.
This changes the stopping boundary, not the pistol's validation requirements.

The final installable test bundle and accessible module inventory must include
all completed weapons: approved Cougar Fineblade Longblade (shortsword),
Cougar Fineblade Knife, Cougar Fineblade Longsword, and Colt L36 in both finishes.
Retain the three approved Cougar HAKs byte-for-byte, verify their bound hashes,
and validate every weapon's blueprint, module availability and resource resolution.
Merely copying comparison HAKs without making the items accessible is insufficient.
The existing comparison bindings are in
`output/itemkit/pistol-trial/package-adapter-inputs-v1/local.json`.

Authoritative continuation: output/itemkit/pistol-trial/checkpoint-v19.json
SHA256: 46139f2d8bb5868e9abe7232c979a07b1c85ae56e193af22c5ef09e922bba17c
User selected thickness-based fit uniformly enlarged 15 percent. Both native-hand
previews are retained. Original exact grip-length target is superseded for this trial.
Donor bake v1 failed its 1K UV audit after writing maps. Local UV repair/bake v2
is active (session 36843); collect its exact status and receipt before further work.
Do not edit pinned maintained source during the run. Afterwards qualify explicit
length-departure support before fitting. No client launch or production promotion.

Historical v18:

Authoritative continuation: output/itemkit/pistol-trial/checkpoint-v18.json
SHA256: f55fd52bf8f6673737e4cb8dc4bdecdfc5543a799108d0ed769905e226354146
Reviewed donor selection is closed and outward at 179892 triangles.
The existing CPU 4K donor bake is active (session 37215); collect its exact
status/launch receipt before any new bake. Final fitting, reduction, transfer,
finish variants and native private delivery remain pending. GPU already released.

Historical v17:

Authoritative continuation: output/itemkit/pistol-trial/checkpoint-v17.json
SHA256: 5ca10c41e0b5ce96628683591cb07e4f1c90c88277aabd2044adf5a87f354107
Candidate v5 is terminal: edge/fan defects repaired, but multiple outward components
require review before exterior selection. Read exact candidate and report bindings.
No repair process remains active. Final topology/visual acceptance is still pending.

Historical v16 observation (superseded):

Pistol CPU repair continuation: output/itemkit/pistol-trial/checkpoint-v16.json
SHA256: 98021c486e9fc496901ea6c1546f87e686e421067ce32cc0d832b55e1962ed53
Read this checkpoint and its v15 parent. Candidate v5 is active (session 16785);
reconcile its exact output/launch before further repair. Only an intermediate exists;
final topology, opening preservation and visual gates remain unproven.
GPU release and user-approved appearance remain as recorded below.

# Pistol trial: source appearance approved; GPU released

Authoritative checkpoint: output/itemkit/pistol-trial/checkpoint-v15.json
SHA256: e28fee2bcf89ba38f6f6298aff0a3a67653cb07cd10326cbc90648a76082300e
Read its exact bindings and previous-checkpoint chain before continuation.

The user approved the direct saved-field grip appearance. Pixel-sampled donor
views restore detail lost in the earlier vertex-color preview and closely match
the direct saved-field projections. Preserve this appearance through the 4K bake.
Small lettering and final runtime texture review remain finishing items.

All planned GPU stages are retained and terminal. Guarded release verified the
ledger, unloaded models and stopped both exact owned processes. Port 8188 was
closed. The user has been notified; do not send a duplicate release notification.
One of five geometry attempts used. No new generation is planned.

CPU shell repair, grip fitting, 4K donor bake/transfer, two finishes and the
validated native private package remain incomplete. Preserve the original donor;
its topology has not passed the closed-shell gate. No client launch or production
promotion. Qualified source and 150-test evidence remain bound through v14.

## Historical checkpoint v14
# Pistol trial: appearance and donor export chain active

Authoritative checkpoint: `output/itemkit/pistol-trial/checkpoint-v14.json`
(SHA256 `8e7cac0c3a08dad23db94611773d8bca3a21aa634d0610b80ce039eeca999d21`). Read its exact bindings first.
The existing appearance operation and the existing `gpu-tail-v1` operation are
both active. Inspect their explicit status/session bindings; **do not dispatch a
second appearance or export**. The tail retains appearance, prepares and runs
one 768 UDF 200K donor export, then stops for donor review and guarded GPU release.
It has no automatic retry and does not consume another geometry attempt.

Geometry review and the 150-test source freeze from v13 remain current. Source,
runtime, ledger, finalized Cougars and client restrictions remain unchanged.
GPU release has not occurred. The real pistol package is not ready yet.

## Historical checkpoint v13

# Pistol trial: geometry reviewed; saved-shape appearance active

Authoritative checkpoint: `output/itemkit/pistol-trial/checkpoint-v13.json`
(SHA256 `2607cc60acea75b038a9525e0f8488f9c0be779d6128e5dab35fc27110814c03`). Read its exact bindings, the live shared
ledger and `output/itemkit/colt-l36-pistol/pistol-appearance-v1-status.json`
before dispatch. Resume the existing operation; never duplicate an uncertain job.

One of five geometry attempts has completed and passed the construction review.
Raw geometry (16,925,474 triangles), exact saved shape and two sets of eight
four-thread inspection views are retained. Tiny raw surface pits/faceting and
minor rail-edge roughness remain explicit donor/working-shell review items.
The approved manifest is `appearance-v1.json`; this is no native/client approval.

Current source `6b9b2c36e86475a7e338bcbc9b11962a860c05d4bb2a98da6731017be6a00126` passes 150 affected tests.
The inspection optimization reads eight bounding corners instead of full mesh
vertices/faces when transforms are applied; real raw bounds and synthetic affine
cases match exactly. Optional fill lighting enables underside/grip review.
The raw bounds call measured 0.21 ms. New/old render timings differ in lighting and
framing, so they do not establish a controlled total speedup or RAM reduction.

The owned Comfy service is still needed for appearance and donor export. Do not
announce GPU release yet. Retain all outputs, finish required GPU stages, then
use the guarded release procedure and notify once. Preserve accepted Cougars,
five-attempt ledger history, client-control restrictions and the full pistol goal.
Neverblender 4.5.1 codec qualification remains separate from full Blender 5.2
scene qualification; the current CPU run still uses its verified Blender 4 binding.

## Historical checkpoint v12

# Pistol trial: paired inputs approved; first geometry operation active

## Current execution checkpoint

Authoritative evidence: `output/itemkit/pistol-trial/checkpoint-v12.json`
(SHA256 `d3933061155ebe57af719121c8c84555b83d09663fd6470327e1c2bc670e5582`). Read the active geometry status and shared ledger
before any dispatch; do not duplicate a submitted or uncertain job.
The owned `runtime-pistol-v1` service remains active. Both calibrations are retained.
The calibrated images have matching 1024-square framing; seven inspected paired
landmarks meet the 2% gate. The original detailed camera estimate (31.64124 degrees)
is selected for both stages; the clay estimate (27.32702) is retained as evidence.
A bounded correction cleared exactly 45 faint detail pixels outside the reviewed
foreground footprint (maximum value 10/255); foreground RGB and mask stayed exact.
No actual pistol geometry, appearance, grip or client approval is implied.

The first geometry operation uses `geometry-v1.json` and `pistol_stage_v3.py`.
Its status is `output/itemkit/colt-l36-pistol/pistol-geometry-v1-status.json`.
Keep five geometry attempts maximum and inspect/reconcile the live shared ledger.
Use the current generation-only binding and qualified source from this checkpoint.

Neverblender candidate codec comparison v2 found exact native positions, normals,
UVs and triangle winding for three binary fixtures, with closed outward shadows.
Diffuse names stayed exact; the placeholder spelling changed from `NULL` to `null`.
No external compiler was used. This is **codec-only** qualification, not Blender
5.2 scene import/export qualification or production adoption. Preserve both the
initial strict comparison and the follow-up interpretation. Defer changing the
shared tool lock/Blender bindings until GPU jobs finish and release is evidenced.

## Historical execution checkpoint (v11)

Authoritative evidence: `output/itemkit/pistol-trial/checkpoint-v11.json`
(SHA256 `50795e59e93b5fde5d16512b17a648677b8cdea3a4521f770b1cf3d528f1de6e`). Follow its active-operation pointer before dispatch.
Clay calibration completed and is retained locally; normalized clay and its mask
have been inspected, with paired detail framing and approval still pending.
No pistol geometry attempt has been submitted. The owned Comfy service remains active.

The user requested an audit of 6,904 cached verification lookups. Evidence in
`scope-correction-v1.json` identifies 4,048 redundant pin reconstructions and unused
Blender, client and UV-tool checks. The new verified-pin interface and separate
generation binding reduce cache hits to 2,847 and remove about 178 MiB per scope
pass. Measured scope time was 22.16s before and 20.89s after; this is a modest local
saving, not an end-to-end generation benchmark. Whole package/runtime membership
and toolkit source identities remain intentionally conservative. All 150 itemkit
and affected headkit background tests passed on the new exact source. Shared
headkit generation/runtime code is unchanged. Historical receipts remain immutable.

The user reported Neverblender installed in Blender 5.2. Its installed version is
4.5.1 and contains the cleanmodels v4.10.0 Python binary reader/compiler. A separate
54-file candidate snapshot and codec smoke have been prepared; inspect their
results before any adoption. Full Blender scene import/export qualification remains
separate. Do not alter the existing shared addon or production Blender bindings.

## Historical execution checkpoint (v10)

Authoritative evidence: `output/itemkit/pistol-trial/checkpoint-v10.json`
(SHA256 `8539a3d2e8291e0850ef71704437a3d04f6e3f52cdeba7ccc5db9daf9d99d3ba`). This supersedes the historical Troll wait below.
The user reported the GPU available. Fresh checks found the prior process gone
and port 8188 unowned. Our isolated `runtime-pistol-v1` service started with its
own inputs, outputs, user directory and temporary directory. Installed sources
match our prior verified runtime exactly; no reinstall or other worktree change.
The checkpoint and retained 147-test inputs were freshly verified unchanged.

Follow the checkpoint's active-operation pointer before any dispatch. The first
calibration preparation reached the service before readiness and failed before
creating a request or ledger job. The next operation includes a bounded readiness
check and uses one verification pass for dependency gathering. No geometry
attempt has been used. Client controls remain with the user.

## Historical input revision (v9)

Authoritative evidence: `output/itemkit/pistol-trial/checkpoint-v9.json`
(SHA256 `5b87fed8266f363fc1fea73ee22a06f09eb6c127533d04fd791f9099301639f3`).
The user requested smoother pistol clay and explicitly requested a retry after
the image service rejected the first edit. The RPG-context retry succeeded.
Both the rejected request and successful prompt/output are retained in
`output/itemkit/colt-l36-pistol/reference-v1/`.

Selected clay is `clay-smoothed-v3.png`
(SHA256 `26e99d4589201eabf43bd9445275d8b4f59d3bea9eb7c82465b10a4bd60bad1a`).
It removes slide serrations, the grip panel and fine control marks while preserving
the main shape, trigger, guard, sights and rear loop. Pale fringe still needs
conditioning review. The detailed original and all earlier clay remain unchanged.
New `asset-native-v2.json`, `calibrate-clay-v2.json`, `calibrate-detail-v2.json` and
`calibration-preparation-v2.json` bind this selection. Use these v2 manifests on
resume; old calibration manifests remain historical and must not be dispatched
for the new selection. No normalized pair or generation review is approved yet.

The maintained source and its 147-test qualification are unchanged. Fresh manifest,
background-route and premature-submission checks passed. Accepted Cougar packages
remain byte-identical. No Comfy submission, GPU claim or client launch occurred.
The goal still waits for genuine shared runtime release as described below.

The user also authorized preparation of Ingram Smartgun X; its independent state
is in `docs/items/ingram-smartgun-x-checkpoint.md`. That later instruction permits
SMG preparation and supersedes the original pistol objective's no-SMG restriction
for this additional preparation task. It does not replace the full Colt objective.

## Historical stop: shared runtime owned by Troll

The goal is **blocked**, not complete. The same external blocker was confirmed
over three consecutive goal turns; the intervening CPU preparation is now done.
`output/itemkit/pistol-trial/blocked-audit-v1.json`
(SHA256 `b0bfe3ff631626737a54ac41a446d29e4d25dd9b6c85c1f94f6e7c71bbd80131`)
records the requirement audit and exact live ownership observations v4/v5/v6.
The latest check confirms PID 2788 still owns port 8188 with Troll's configuration.
No release was established. Do not stop, reconfigure or use that service.

Checkpoint v8 below was the binding at the blocked audit; v9 above supersedes its
input selection while preserving the qualified implementation.
Its source, all 147-test evidence, calibration manifests, approved packages and
five-attempt ledger were reverified. Zero pistol jobs exist. Remaining work needs
the owned runtime and actual generated mesh; no further independent preparation
was identified. Resume after genuine runtime release by establishing fresh owned
startup/bindings and running the two prepared calibration manifests. No client
launch, production promotion or GPU submission occurred.

## Prepared implementation checkpoint

Current evidence: `output/itemkit/pistol-trial/checkpoint-v8.json`
(SHA256 `93a792bade02f8b4ea941bfc28f78f8326f678771c01ac74b83ad1d7871faa74`).
Read its exact bindings first. Current maintained source is
`0d9cd623c5998a30a1bd742c5adeed3dec3ce11cd94260e0e0351c7c91165770`.
The previous goal turn made progress on the static native contract. This turn
made progress on a real preparation defect and its regression coverage; the
full goal remains active and incomplete.

The paired-image review previously checked both source background routes against
the detailed original. This rejected the correct preserve-alpha review for a
separate transparent clay source. Geometry now binds `inputs.clayReference` when
present; detail keeps `inputs.reference`. Without a separate clay source, legacy
behavior remains unchanged. Geometry and appearance consumed-input sets include
the clay source. Changed source bytes, mismatched review hashes and wrong routes
are rejected. No shared headkit/runtime verifier was changed or weakened.

All 147 full itemkit plus affected headkit background tests passed on this source.
Execution took 22.69 seconds; including fresh dispatch/completion verification,
35.65 seconds. The audit is `paired-background-audit-v1.json`. The correction adds
only source selection and dependency membership, with no new runtime scans or
source parsing. No measured throughput improvement is claimed. A byte-bound AST
comparison confirms all other contract functions unchanged. Historical native and
processing smoke remains earlier-source evidence, not a current-source end-to-end
delivery claim; actual delivery will be built and verified on the frozen new source.

Ready calibration-only manifests are
`output/itemkit/colt-l36-pistol/calibrate-clay-v1.json` and
`output/itemkit/colt-l36-pistol/calibrate-detail-v1.json`, bound by
`calibration-preparation-v1.json`. Both retain the stable Colt model identity and
original detailed-reference hash. Clay uses existing alpha; detail requires
foreground removal. Both reject premature geometry submission because normalized
background/pair/camera reviews are absent. No calibration has been submitted yet.

`runtime-ownership-v5.json` confirms the live Troll process and listener still own
Comfy. Preserve that service and its configuration. After genuine release,
establish fresh owned startup/source bindings before calibration. The accepted
Cougar packages remain unchanged; no pistol geometry attempt or GPU claim occurred.
Metadata-only scorecard accounting remains unavailable (URLError).

Next: run the two prepared calibration manifests after release, inspect edge
contamination and normalized common framing/masks, then complete actual pistol
generation, saved-shape appearance, fitting/donor transfer, both Color finishes,
native private fixture and installable bundle. No client launch or promotion.

---

## Previous static native contract checkpoint

Current evidence: `output/itemkit/pistol-trial/checkpoint-v7.json`
(SHA256 `e690200a8cd6e2121f2f06555f0a234e0d1821cc3b34010001a3f9fed52b5bf6`).
Read its exact bindings first. The maintained source remains
`64479a1a5810a7f6e6ce63323171bb085a68f6adee0e3a3cd0bd55ea5c9bb7a3`,
matching the retained 136 tests and native/processing qualifications. No maintained
helper changed during this static contract pass. The full pistol goal is active
and incomplete. The preceding display-only turn made no new goal progress; this
turn completed the installed native contract and its visual frame evidence.

The authoritative processing profile is
`output/itemkit/colt-l36-pistol/contract-v1/family-reviewed-v1.json`; the new asset
manifest is `output/itemkit/colt-l36-pistol/asset-native-v1.json`. Fresh verified
stock extraction binds Sling BaseItem 61 / WBwSl / effective ModelType 0 and its
32x64 icon. The profile declares the private multipart ModelType 2 separately.
Both shipped Human right-hand hooks match their stock relative transforms exactly.
Six CPU renders of the approved Cougar grip in these hands were inspected. This
approves the static frame and reference placement only: the actual pistol's grip
angle, barrel direction and trigger clearance still require generated geometry.
Bright diagnostic lighting limits fine shading assessment; it does not obscure
the grasp placement. No client checks were performed.

The content-stack allocation plan selects pistol bottom index 5, Colors 1 and 2,
with hidden top/middle placeholders. Its private override changes ModelType 0 to
2 and MaxRange 50 to 52; unrelated bytes and fields remain unchanged. Packaging
must re-resolve against the complete fixture HAK namespace before final reservation.
Profile qualification took 18.47 seconds; the six-view native hand review launch
took 55.28 seconds at four CPU threads. These are separate from generation costs.

Raw background analysis is retained under `reference-v1/background-analysis-v1.json`.
Both source images are 1448x1086. Preserve existing clay alpha; independently remove
the detailed original's opaque background and cast shadow. Inspect pale clay edge
remnants near the slide and trigger opening during calibration. Do not copy the
clay mask blindly onto the detailed image. Common normalized framing, paired
landmarks, masks and camera approval remain pending.

`runtime-ownership-v4.json` freshly confirms Troll PID 2788 still owns port 8188
with its own configuration. No GPU work, runtime changes or pistol submission
occurred. All five pistol geometry attempts remain available. The shared ledger
observation, source qualifications and accepted Cougar packages were rechecked;
the accepted packages remain byte-identical. Metadata-only scorecard calls were
unavailable (URLError); no local inference was used.

Next: after genuine runtime release, establish this workflow's verified startup,
calibrate and review the clay/detail pair, then generate the actual Colt and
complete both finishes, saved-shape appearance, 200K UDF donor, 4K transfer, 1K
runtime maps, native private fixture, review gallery and installable test bundle.
Queue idle alone is not release. Do not launch the client or promote production.

---

## Previous whole-firearm processing checkpoint

Current evidence: `output/itemkit/pistol-trial/checkpoint-v6.json`
(SHA256 `68fd3033a58546984885843ff9770bcea1330f3cd68058003d8c29e91737c40c`).
Read its exact bindings first. Source version
`64479a1a5810a7f6e6ce63323171bb085a68f6adee0e3a3cd0bd55ea5c9bb7a3`
passes all 136 itemkit tests, fresh synthetic native compilation/fixture checks,
and whole-firearm fitting, atlas, 4K transfer, 1K rendering and corner export.
This turn made concrete progress; the goal remains active and incomplete.

The maintained path now processes the complete pistol in bottom, counts inactive
placeholders in assembly budgets, measures five grip sections along the pistol's
own axis, preserves its uniform fit, and requires an exact review for a width/depth
departure. It exports a single Color's bound arrays/texture/icon for the separate
firearm package commands. A real profile still needs reviewed Sling whole-model
and icon donors, native frame and hand placement. Generic melee packaging remains
unavailable for firearm variants. Exact MOD extraction/hash comparison now belongs
to the maintained fixture builder. Grip measurement no longer imports a duplicate
dense source solely for measurement; the synthetic test verifies one source import.

`processing-complete-v1` retains the successful fit/atlas and initial failed bake.
That bake found 22 visible edge samples out of 8,491,482 mapped texels; it was not
accepted or overwritten. `processing-checker-v1` binds an explicit diagnostic
checker donor and a bounded nearest-finished-donor correction. All 22 corrected
samples lie within 3.73e-9 native units, with normal alignment above 0.9999999.
Zero unresolved visible misses, no hidden caps and no unrelated texture-patch
face IDs. The 4K transfer took 71.70 s; 24 matched geometry/lit/unlit views plus icon
took 109.73 s at four CPU threads. Both lit oblique and unlit side views were
visually inspected and shown at the user's request. The synthetic consists of
two boxes and a ring; it is not generated Colt geometry or appearance.

Native/fixture smoke took 68.75 s; no interactive client was launched. The full
optimization audit is `processing-optimization-audit-v2.json`. Blender reported
1676.54 MiB peak during baking; this is not a process RSS measurement or a Comfy
verification measurement. No controlled end-to-end speedup is claimed.

Fresh `runtime-ownership-v3.json` still identifies Troll PID 2788 on port 8188,
with its own startup/configuration. Do not use, stop or reconfigure it; queue idle
does not establish release. No pistol generation attempt or GPU claim has occurred.
Five attempts remain. The clay and detailed originals, shared history and all
three accepted Cougar HAKs remain unchanged. Metadata-only offload accounting
was attempted and unavailable (URLError); no local model inference was used.

Next: bind and inspect installed Sling donors/frame for the real processing
profile. After genuine shared runtime release, establish owned verified startup,
calibrate/review paired clay/detail foregrounds, generate and review the actual
Colt, reuse its saved shape for appearance, and finish both real variants through
donor transfer, native private packaging and an installable test bundle. Existing
synthetic successes do not grant actual asset, client or production approval.

---

## Previous native-adapter checkpoint

Current evidence: `output/itemkit/pistol-trial/checkpoint-v5.json`
(SHA256 `5b9d60be8fba2ebb67490f7e2cc567d0176feb82eedd00ad7a6bec8821ae2fef`).
Read its exact bindings first. Source version
`a5a947e4db7f2f0312ceff35ecd01afddb84a4a28e144ed8fe45e082d095ae94`
passes all 126 itemkit tests and the fresh maintained-adapter native smoke.
The prior turn made concrete progress; the goal is still active, not complete.

Maintained pistol intake now avoids melee materials and assigns the complete
10K/500 assembly budget correctly. `firearm-inputs`, `firearm-prepare`,
`firearm-native` and `firearm-fixture` expose explicit package stages. Stock KEY
namespaces now include UTI collisions. Packaging supports separate Color geometry,
tiny hidden zero-shadow placeholders, private Sling table overrides, exact native
corners, root/field blueprint audits and exact HAK payloads. The fixture consumes
the packaged UTIs, gives access to both variants, and places both Human actors.

Authoritative validation is `package-adapter-smoke-v4/smoke.json`, bound in v5.
Its geometry is explicitly synthetic. No real pistol, final finish or game-ready
pistol bundle exists yet. The first adapter smoke exposed a JSON-writer omission
of the UTI root struct ID; the corrected audit checks the binary sentinel and
every typed field. All failed/earlier test and smoke receipts remain retained.

Measured input enumeration took 8.47 s wall time (8.31 s verification), hashed
3,022 distinct files / 926,452,411 bytes, and reused 3,229 checks within one pass.
Sampled peak process RSS was 51,740,672 bytes. This is CPU input enumeration,
not Comfy verification or generation, and no comparable before-time was measured.
Final synthetic helper took 64.42 s; verified launcher execution took 76.06 s.
See `adapter-optimization-audit-v1.json` for phase timings, scope and limitations.

The stable pistol intake and reference review are in
`output/itemkit/colt-l36-pistol/intake-v1/`; clay and detailed originals remain
unchanged. Calibration and paired masks/landmarks are pending. At 21:14 UTC the
live 8188 process remained Troll PID 2788 with its own configuration. The shared
trial ledger contains zero pistol jobs, no outstanding jobs and a five-attempt
limit. Ledger idle does not release the Troll service. Do not alter or use it.

Next independent CPU work: integrate single-active-part fitting/UV/bake/render/
export and the measured angled pistol grip/frame; promote the smoke's exact
module-payload extraction audit into the maintained final fixture path. Then
qualify changed source before generation. After genuine runtime release, establish
owned verified startup, calibrate/review clay and detail, and complete generation,
saved-shape appearance, donor transfer, two real finishes and final delivery.
No client was launched; no production promotion occurred. All three accepted
Cougar HAKs remain byte-identical. Do not mark the goal blocked merely because
GPU work waits while useful CPU integration remains.

---

## Previous clay-retention checkpoint

Current evidence: `output/itemkit/pistol-trial/checkpoint-v4.json`
(SHA256 `a09c5aa2c546602c7d6515175605e3795bd4a7bdbb36dc6e9c8453680f055804`).
Read its exact bindings before continuing. The user-authorized retry succeeded:
`output/itemkit/colt-l36-pistol/reference-v1/clay-generated-v2.png` is retained
locally and in durable ignored storage. It is 1448x1086 RGBA, matching the original
canvas, with one connected opaque foreground and no edge clipping. It removes
logos, wear and grip stippling while retaining the main external construction.

The user subsequently allowed smoother clay surface detail, relying on the
original detailed image for appearance. The additional smoothing edit was
rejected by the image service before returning an image; both that failure and
the successful clay are retained. Do not treat the earlier missing-clay blocker
below as current. The successful clay is a candidate, not a completed calibration:
detailed foreground isolation, normalized paired landmarks and masks still need
review before mesh generation. No 3D attempt has been used.

A fresh host process inspection found port 8188 owned by Troll batch PID 2788,
started at 2026-10-23 16:01:09 -04:00 with its own model/input/output configuration.
No request was submitted and no service was changed. Wait for genuine release,
then establish this workflow's verified startup; do not use Troll's service or
configuration. Queue idle alone is insufficient. All 18 distinct prior checkpoint
bindings were checked and all three protected Cougar HAKs remain unchanged.

Maintain clay mesh conditioning plus detailed saved-shape appearance. Five
geometry attempts remain. Native integration and final delivery are still
incomplete; the synthetic smoke is not the real pistol. No client was launched.

---

## Previous clay-service rejection checkpoint

Current evidence: `output/itemkit/pistol-trial/checkpoint-v3.json`.
The user supplied the Colt L36 pistol image and explicitly required clay mesh
conditioning with detailed-image appearance. Stable model ID: `colt-l36-pistol`.
Original 1448x1086 PNG is retained byte-for-byte locally and in durable ignored
storage. The original has an opaque background and cast shadow; foreground
calibration and paired landmark review are still required.

The built-in image service rejected the clay conversion before returning an
image (`moderation_blocked`, request ID retained in the bound failure receipt).
No bypass, alternate generator or retry was attempted. A matching supplied clay
image is needed to continue this conditioning route. No 3D generation attempt
was used and no GPU was claimed. The earlier missing-original-reference blocker
is resolved. Do not substitute detailed-image geometry for the latest instruction.

Historical foundation below remains unchanged.

---

## Previous missing-reference checkpoint

Previous evidence: `output/itemkit/pistol-trial/checkpoint-v2.json`. Read its exact
bindings before continuing. The user confirmed longsword `delivery-v1` as the
final baseline. All three accepted Cougar HAKs remain byte-identical.

The required image remains absent after three consecutive goal turns. The
foundation below is retained and unchanged; it does not complete the requested
pistol. Resume the full scope when the user supplies the design reference.

The task attachment contains text only. A pistol reference has been requested;
do not invent a design or stable model ID. No pistol generation has occurred.
Five geometry submissions remain permitted under the existing shared ledger.

## Completed foundation

- Retained all 114 original tooling files in the ignored finalized source
  snapshot before additive firearm code. Its isolated source-version check
  reproduces the finalized Cougar version. Historical receipts are unchanged.
- Added separate firearm allocation, private table override, placeholders and
  blueprint adapters without changing the legacy melee or shared verifiers.
- Resolved installed Sling BaseItem 61, ItemClass WBwSl, ModelType 0. The private
  synthetic override changes ModelType to 2 and MaxRange from 50 to 52 only.
  Existing orphan bottom icons reserve shapes 1–4, so shape 5 is the first free
  bottom shape. Colors 1/2 use 051/052; unused slots use 011/012 placeholders.
- Freshly compiled six valid four-triangle placeholders and two synthetic
  geometry variants. Native flags prove placeholders are neither rendered nor
  shadowed. Position, normal, UV and closed shadow checks pass.
- Separate private synthetic HAK/module contains both variants, both shipped
  Human actors and unchanged Cougar packages. Exact native payload checks pass.
  The initial smoke failed its final module audit because it called a HAK-only
  reader. A separate verified recovery extracted the retained module correctly;
  no recompilation or rewritten historical receipt was needed.
- All 114 itemkit tests pass on unchanged source. No shared helper or item-import
  dependency changed, so this addition did not require those broader suites.
- The occupied-slot benchmark visits 73,286 names once rather than four times:
  median 11.75 ms versus 52.62 ms. This isolates allocation work and makes no
  generation or end-to-end speed claim. See the bound audit for actual timings.

## Remaining work

Reference intake, actual pistol grip/frame measurements, maintained CLI/profile
integration, generation and visual gates, appearance, donor transfer, real finish
variants, final renders and installable delivery are incomplete. The existing
firearm profile still blocks general native packaging until integration qualifies.
The synthetic fixture is a contract test, not the requested pistol delivery.

Preserve the existing ledger, dispatch/completion byte checks, runtime/loaded-code
identity, saved-shape checks and uncertain-job reconciliation. New generation
requires its own fresh verified runtime ownership and bindings. No GPU was
claimed for this foundation. Do not launch/control the client automatically.
Inherited Sling animations, ammunition, projectile placement and actual Human
hand fit remain explicit user-controlled client checks.

Binary flag layout reference used for the native smoke:
[NwnMdlNodes.h](https://raw.githubusercontent.com/niv/nwn-tools/master/_NwnLib/NwnMdlNodes.h).
