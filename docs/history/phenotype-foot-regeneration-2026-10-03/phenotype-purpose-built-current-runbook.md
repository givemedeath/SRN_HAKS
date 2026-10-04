# Current purpose-built Human male workflow

Current later 2026-10-03 foot direction: regenerate tapered closed ankle
overlap and use directional reference lighting plus restrained crease/AO
shadowing for clearer texture detail. Active pilot `purposebuilt-foot-taper-v3`,
single submitted job `b40648ff-28d4-48e8-8dab-2f09016b1ee4`; inspect receipts
before retrying. The v2 pair is superseded diagnostic history. Preserve six
accepted geometry and combined-v2 materials; finish feet offline then stop.
No active goal. Earlier statements below are historical and will be archived.

**Current task (2026-10-03): fresh foot generation/fitting to remove the extra
toe, explicitly resumed by the user.** Use the foot checkpoint and fresh
`purposebuilt-foot-regeneration-v2` pilot. Review the untouched sole before
fitting; perfect one donor then mirror through stock attachment frames.
Preserve all accepted neighbours and combined-v2 runtime materials. Finish
feet then stop. The stopped-generation statements below are historical.

Updated 2026-10-03. Completed task: material repair on every latest custom Human
male part, including actual client validation explicitly authorized by the
user. Read [material validation](phenotype-body-texture-repair-validation.md),
[the recovery checkpoint](phenotype-body-texture-repair-checkpoint.md) and
[native material process](phenotype-body-material-process.md). The earlier
client hold is superseded for this work. Preserve selected geometry and rig.

Foot regeneration remains stopped. Its current +3 mm stock-local +Y pair has
an extra underside lobe and is diagnostic anatomy, even when material checks
pass. Rejected lobe-roll/excision trials are not selected. No new generation,
arm, head, Troll or other part work is authorized by this material repair.
The established default cadence still collects parts offline for bulk client
tests; this task is the user's explicit material-test exception.

## Preserved baseline

Current effective runtime materials: **combined-v2**,
`human-male-material-repair-v1/selected-runtime-v1/selection.json`.
The clean current-eight HAK is `human_male_current8_materials.hak`, SHA256
`7f9c834a5d1c8499bf5dc4ed586544ddf428e860dfd9bd821dadc12b8003905f`.
It includes diagnostically unfinished feet. The accepted-six subset HAK is
`human_male_accepted6_materials.hak`, SHA256
`4f84d29f94796f0476d45f9f4486193172472e45fba167ce94ded4890b68e1d1`.
Both live under `human-male-material-repair-v1/selected-runtime-v1` and contain
body resources only. Their material operation leaves all selected geometry
and normal maps unchanged. Preserve those effective materials separately from
the immutable older compile receipts. Do not bake the same AO twice.

All asset paths below are relative to `output/phenotypes` in this workspace.
Keep actual stock Human male height 1.9339157 m, attachment transforms,
supermodel and male controllers unchanged. Human equipment stays identity-scaled.
Stock neck/head and arms are context; heads are a separate future sprint.

| Part | Selected source | SHA256 |
| --- | --- | --- |
| Chest | `purposebuilt-torso-pilot-v1/common-cap-atlas-v4-perimeter/common-atlas-local.glb` | `3ae78d023ba522d94c44d9914bac0b36f35b640c42b9532015575e5572161a50` |
| Pelvis | `purposebuilt-pelvis-pilot-v1/selected-d-original-polished-material-v1/postfit-local.glb` | `db0bdf16099068da3bb685bcb61ae93ebed115e6ddbae90990c0b55e59b8d98a` |
| Left thigh | `purposebuilt-thigh-pilot-v1/left-thigh-proximal-cap-v2-proof/refined-local.glb` | `5420a77d5e9d51b7841f678d12710ce335bab16ed5ad417ae49b67f1e2950ab6` |
| Right thigh | `purposebuilt-thigh-pilot-v1/right-thigh-v2-mirror-v1/mirrored-local.glb` | `3c002789b74bfb5e94392d7c557e3105924e078f0133c47d496b1c123764b980` |
| Left shin | `purposebuilt-shin-pilot-v1/left-shin-connectors-v3-monotone/refined-local.glb` | `bde4b16194010cd42ad40d282512e1189c7c992a5ab6df06d0d24c27c5123ee7` |
| Right shin | `purposebuilt-shin-pilot-v1/right-shin-v3-mirror-v1/mirrored-local.glb` | `7efe4b5a9e85bacd1b8d23958c96fe4518e186363f5c6c8b91aed5b17b3f4e24` |

The clean bank is `purposebuilt-stock-inputs-v1`, inventory SHA256
`72b08b309f346d9603c085228ab33871920a55bb689a9bfb87a8d77ba53a8d49`.
Do not refit or regenerate completed neighbours from historical recipes.
Their completed evidence is in the [shin checkpoint](phenotype-shin-checkpoint.md),
[shin validation](phenotype-shin-validation.md), [thigh checkpoint](phenotype-thigh-checkpoint.md)
and [thigh validation](phenotype-thigh-validation.md).

Preserve the accepted [pelvis skin correction](phenotype-pelvis-skin-continuity.md)
as the material repair parent, not the final effective shade map:
`pmh0_pelvis001.plt` SHA256
`990aa66b5c642d6c45ab4f1c60ceffd732cd290b53207c9c5021698dc9181690`.
The exact accepted native donor is
`purposebuilt-shin-pilot-v1/client-pair-v3-pelvis-skin-minus54-front3-v1/human_male_fit/converted`.
Its original compiler union SHA256 is
`82410338755269f3cb6f583ccdcc837fd3366f04c3e8ad34b4ad8fff4220146f`;
its explicit runtime material patch SHA256 is
`31e97f500fed4f9ebb43a33dded612fb48fad52774c8ceba180045a23e346ae7`.
Original compile-time dependencies remain immutable. The corrected fixture
HAK SHA256 is `2ea5a2ffd5ee9b717e785b6aae08e88d39449395665ee18adb07c6513fcbb299`.
It contains 26 body resources and 42 comparator/test resources; copy its full
payload only as an explicitly isolated diagnostic fixture, never as production.

## Preserved diagnostic foot lineage

Pilot: `purposebuilt-foot-pilot-v1`. Read [foot fitting](purposebuilt-foot-fitting-pilot.md).
Use `stock-connectors-v2`, measured from actual `pmh0_footl001`/`lfoot_g` and
`pmh0_footr001`/`rfoot_g`. The earlier v1 spanning-shin bounds are historical.
Left foot medial is +X; source orientation requires anatomy review.

Source sheet `image-design-v1/source.png` and shared-scale `normalized-v1`
are preserved. Fifteen files are byte-exact in the user's original
`D:/source/repos/SRN_HAKS/.tools/reference_images/normalized/purposebuilt-human-male-left-foot-v1`,
bound by `reference-copy-audit-v1.json`.
Comfy job `9b103b49-458d-4a54-825a-130b18b07923` completed successfully in
`comfy-v1`. Do not resubmit. Its untouched textured master SHA256 is
`1757c79e20c7ee294082e33d4be980be7c260806a4cf32e7b6d7918d381a0323`.
Raw, remeshed and compact shape masters are retained.

`left-foot-firstfit-v1` uses proper Z180, uniform scale 0.3187211742 and an
explicit ankle-ring-to-stock-pivot inference. Preserve this fit. Source-to-fit
ordered attributes and six neighbours are independently verified. Idle ground
height differs from stock by 0.16 mm in the recorded pose. Offline pose previews
are evidence of sampled assembly only; they are not client screenshots.

The source has 17 nonmanifold contacts between toes. Root's foot-specific
repair separates measured vertex fans by at most 0.05 mm and replaces only
13 faces around one remaining contact with 5 boundary triangles. Repair v1
failed independent crossing and UV checks and remains rejected diagnostic
history. Corrected v2 changes only the three implicated fan directions, with
10-micrometre inward geometric offsets. Independent actual FLOAT32 all-face
crossing and vertex-link proof passes. `left-foot-contact-chart-v1`
maps only the five added faces into one small existing chart and derives their
tangents from actual UV differentials; all geometry, retained UV/T and maps stay
exact. Do not adopt a candidate until its independent review passes.

The current +3 mm pair and its exact hashes are in the [foot checkpoint](phenotype-foot-checkpoint.md).
`forward3mm-pair-offline-review-v1` owns the 32 current standing/kneeling
images. `paired-feet-forward3mm-offline-collection-v1/body-resource-manifest.json`
owns the earlier clean 34-resource offline assembly and then-deferred commands. The separate
76-resource HAK includes comparator/test payloads and is diagnostic only.
Both preserve all accepted body bytes and explicit pelvis runtime correction.
Five main toes plus an extra toe-shaped plantar-lateral lobe are confirmed in
the original and shifted source. Local correction attempts were rejected;
regeneration remains stopped. Current
package proof does not resolve this visible anatomical defect. Established
tools/process are committed in `b9fa9df` before that new refinement.

## Current tools and proof boundaries

- `prepare_foot_connector_guides.py` measures actual ankle/sole/heel/toe
  geometry, clipped distal-shin context and stock poses without editing assets.
- `normalize_part_turnaround.py --layout-components` keeps complete four views
  at one isotropic scale. It preserves generated view disparities; it cannot
  establish exact orthographic coherence. Review the reconstructed anatomy.
- `generate_purpose_built_part.py` requires an explicit part configuration and
  freezes the live `SR_NWN_3d_pixal3d_multi_views` graph. Submit once with its
  frozen helper, then inspect receipts/history before retries.
- `place_purposebuilt_foot.py` binds successful generation, measured anchors and
  accepted neighbours. It permits only proper rotation, one positive uniform
  scale and placement. Source bounds are not an authored ankle skeleton.
- `repair_foot_contact_topology.py` applies bounded, measured contact repairs;
  `map_foot_contact_patch.py` gives new faces a coherent chart and derived T.
  Their old diagnostic outputs remain immutable; no old pelvis defaults apply.
- `translate_stock_foot.py` applies only a hash-bound bounded anterior shift; actual
  rendered X/Z, authored N/T/UV and maps stay exact. Its focused tests reject
  other axes, negative/oversized shifts and unbound parents.
- `mirror_stock_limb_part.py` reflects detached geometry through measured
  frames, reverses winding/tangent handedness and preserves map sampling.
  Independently validate the right foot; never reflect the rig/controllers.
- `prepare_stock_limb_stage_config.py` binds receipt ancestry and extracts exact
  embedded 2K PNG bytes. `stage_stock_part.py` exports only the declared foot.
- `audit_limb_ascii_material.py` proves source-to-ASCII P/N/UV and unchanged
  intended maps, with finite UV differential diagnostics. It does not read
  actual new native tangents or prove client shading/performance.
- `stock_limb_contract.py` requires feet to preserve `chest,pelvis,legl,legr,shinl,shinr`.
  `compose_stock_limb_native.py` keeps native compiler unions and runtime
  palette descendants separate. The material task completed actual foot
  compilation/TBN inspection in `human-male-material-repair-v1`; this does not
  close the anatomical gate.
- `compose_stock_limb_offline.py` can pack declared ASCII feet with byte-exact
  accepted native/test payloads. It records blocked native commands, creates
  no fake native receipt/module and labels the HAK native/client-pending.

`offline-tooling-proof-v3` contains 52 focused test passes and exact command
arguments. Use new output directories rather than rewriting proof parents.
Ankle UV-used shade diagnostics show the generated foot roughly 8 palette
levels brighter than the accepted shin. A separately bound -8 skin0 material
trial is verified offline; the pelvis's -54 correction is never a foot default.
The material repair uses that -8 parent and records actual palette, selected
motion, lighting and full-stock-armor checks separately. Comprehensive future
anatomy/boots/phenotype acceptance remains outside the material task.

## Execution and continuation

Use bundled Python:
`C:/Users/benco/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`.
Use Blender `E:/Program Files/Blender Foundation/Blender 4.0/blender.exe`
with `-b --python-exit-code 1`. Never use the Windows Store shim.
Frozen receipts and executed command arrays in each pilot own reproduction.
For current material checks use the guarded material-fixture launcher and
current receipts, not old PIDs/commands. Preserve logs, settings and exact
package hashes. The previously prepared left upper-arm stock measurement receipt is
`purposebuilt-upperarm-pilot-v1/stock-connectors-v1/measurements.json`, SHA256
`24dfd4d1efef3d5311e18e8130358aedbef12353a7fcfe45bc52654b438f574d`.
The moving bicep owns the deltoid, not the preserved torso. These measurements
are future context, not authorization to start arm work. Heads, Troll and other
races/armor profiles also remain later phases. The [generation procedure](phenotype-purpose-built-part-generation.md)
and [kit guidance](image-to-parts-kit-current-workflow.md) own reusable lessons.

The preceding runbook is [archived byte-exact](history/phenotype-foot-start-2026-10-03/phenotype-purpose-built-current-runbook.md)
with its [hash manifest](history/phenotype-foot-start-2026-10-03/manifest.json).
Its old client recipes and dated statuses are historical context.
