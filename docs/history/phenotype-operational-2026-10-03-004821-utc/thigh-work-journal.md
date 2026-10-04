# Purpose-built Human male thigh continuation

Started 2026-10-02 in `D:\srwt\codex\f0b3\SRN_HAKS`. The user's latest “Do it” starts the recommended next part after the accepted pelvis: perfect one left muscular thigh, then mirror its geometry and independently fit and validate the right thigh. This is authorized continuation; the completed pelvis goal must not be recreated or paused.

## Protected baseline

- Torso: `output/phenotypes/purposebuilt-torso-pilot-v1/common-cap-atlas-v4-perimeter/common-atlas-local.glb`, SHA256 `3ae78d023ba522d94c44d9914bac0b36f35b640c42b9532015575e5572161a50`.
- Pelvis: `output/phenotypes/purposebuilt-pelvis-pilot-v1/selected-d-original-polished-material-v1/postfit-local.glb`, SHA256 `db0bdf16099068da3bb685bcb61ae93ebed115e6ddbae90990c0b55e59b8d98a`.
- Accepted pelvis native/package evidence: `docs/phenotype-pelvis-validation.md`; implementation `a212c24`, checkpoint `607ba72`.
- Actual stock Human male `pmh0_legl001`, `pmh0_legr001`, shins, attachment matrices and male animation chain remain the dimensional and motion references. Preserve stock Human height, rig, animations, neck/head and identity equipment scaling.

## Scope and order

Latest user correction: the accepted pelvis bottom may contribute to crouch-only weirdness, and the user can live with that limited defect. Preserve the pelvis for this task. Finish measured thigh attachment improvements and prioritize clean standing/walking/running joins; do not keep reducing thigh mass or reopening pelvis geometry to chase perfect crouch coverage. Record remaining crouch-only limitations honestly.

Measure stock hip/knee connections and ownership; create coherent isolated left-thigh front/left/back/right references; save normalized images, prompt and provenance beneath the user's original `D:\source\repos\SRN_HAKS\.tools\reference_images`; reconstruct through the running `SR_NWN_3d_pixal3d_multi_views` workflow, retaining immutable masters and job receipts.

Exhaust uniform scale, proper rotation and placement before measured local edits. Keep pelvis/underwear/groin on the pelvis and shin anatomy on the shin. Both thigh ends need shallow closed skin overlap. Review the donor with the accepted pelvis and stock shin through actual stock poses before mirroring.

Mirror mesh geometry only, preserving correct triangle winding, normals, tangent handedness and material sampling. Independently verify opposite stock attachments and motion. Never reflect root, skeleton or animation resources. Compile only the declared new thigh replacements; copy accepted torso/pelvis native resources unchanged. Package fresh isolated fixtures and finish actual client checks with unlocked camera controls, exact resource hashes, screenshots and logs.

## Current state

First generation is complete and collected: Comfy prompt `23bb7cf6-ee38-4544-a611-ea0169057fe4`, `output/phenotypes/purposebuilt-thigh-pilot-v1/comfy-v1`. Never resubmit this attempt. The raw, remeshed, shape and textured masters are preserved; textured SHA256 `1e20a6f4983b207bb3457f74fc4bf5646a231e9d428ee4e54e4fed00e2411d83`, generation receipt `18caf27507d694138999e44b17e5a8de5e0a24e2a8c4eb65a075382dba0d0e6b`. All four views share one isotropic normalization.

Selected sheet: `image-design-v1/source.png`, SHA256 `3e42ac74d593ed27110f95cf91070e7146d3eedbd69e2898395e2399850cb760`; exact prompt `image-design-v1/prompt.txt`. Normalized panels/provenance/source/prompt are copied to the user's `reference_images/normalized/purposebuilt-human-male-left-thigh-v1` folder. Comfy preparation SHA256 `23bd121636ddf7f43b7d95d1c63ff35908e7aa4564a34ba7cfe5abe95b785a8b`.

Measured actual left thigh length534.815mm, hip crown+71.769mm, knee end−463.046mm in thigh-local Z; maximum width206.652mm/depth205.737mm. Hip-to-knee pivot offset `[30.6218,−16.4711,−460.936]`mm; moving stock shin crown provides about44–60mm overlap across idle/crouch. `stock-connectors-v1/measurements.json` and ten stock-context guides retain exact ownership and pose evidence. Guide cages are dimensional references, not generated surface projection targets.

First fit: `left-thigh-firstfit-v1/placed-local.glb`, SHA256 `bab65114aeba3dc732bdcdd5fd61b6bec42da8df50b7e5bbf3b015de893df53b`; receipt `97c24de25a0df5ac7f06b1119c27ad131f444ce78a697401285f90426f3a69f6`. Uniform scale0.571983653, proper180°Z plus minimal6.9605° axial correction. No X/Y shrink, stretch or mesh deformation. Untouched source/idle/crouch/casting views are preserved.

**First fit is not accepted:** crouch rear/side reveals a broad proximal cap protruding through the pelvis. Height matches but section depth is up to49mm too broad. Small rigid pitches move the knee16–32mm and cannot change the broad cap shape. `firstfit-proximal-profile-v1` records this evidence; bounded proximal cap refinement is underway without changing the muscular shaft or accepted neighbours.

`source-full-audit-v1/audit.json` finds no genuine crossings in the generated source. The two microscopic rear contacts are repaired in `left-thigh-topology-repair-v1`, SHA256 `11b1d36c98d57b02d478d74ea16d89c4eab3f58a1a094a5cf0ff2daea4c7896c`;8corners moved20µm, all normals/tangents/UV/maps retained exactly. `repaired-full-audit-v1` confirms closed manifold with no genuine crossings across the full quantized mesh. Do not globally recompute normals: outward agreement median0.99924, only23 negative corners near the original pinch.

**Newest user selection:** “Hip crown taper” looks best in crouch. This label belongs to `left-thigh-proximal-cap-v1`, byte-identical geometry SHA256 `5420a77d5e9d51b7841f678d12710ce335bab16ed5ad417ae49b67f1e2950ab6` in the stronger `left-thigh-proximal-cap-v2-proof` receipt/archive. Use v2-proof for selected inputs: v1 had stale copied repair-delta archive metadata. Full geometry/attribute/Jacobian audits pass and the shaft below−10mm is exact. Earlier rejection of its residual crouch exposure is superseded by the user's preference and permission to retain minor crouch-only pelvis weirdness. Native ordinary-motion review remains required before final acceptance.

`left-thigh-proximal-cap-v3-centres` is an **unselected diagnostic**, SHA256 `0d834b5b7bc525a20e57fafff8116142f9c46aa3fdd1599331ea7b4185870850`. Its full actual-quantized topology/intersection audit passes, but 32 tiny tip faces (0.01634% of surface) have discrete normal disagreement despite correct differential transport. Native diagnostic `client-left-cap-v3` was compiled/built but never launched. Do not silently substitute it for the user-selected hip crown taper.

First native diagnostic `client-left-firstfit-v1` compiles only `pmh0_legl001` and copies all accepted torso/pelvis resources exactly. HAK `3eec3bd8f8e4bbf42c734f19d0478ce91449405cf752b422a9bb1828cb836c2d`, module `dd728e93ce43295d215a3a5142ba6e707579a8137e28744328d62f26cb33a9d0`. Actual package audit passes in `client-left-firstfit-package-audit-v2`; v1 failed because of a helper variable collision and remains diagnostic history. Native front appearance, skin3 and unlocked wheel control were observed and saved in `client-left-firstfit-v1/client-evidence`. This is material/initial-fit evidence, not pelvis-cap acceptance. The client is currently using this diagnostic; reobserve actual PID/argv/window before control.

Selected mirrored right: `right-thigh-v2-mirror-v1/mirrored-local.glb`, SHA256 `3c002789b74bfb5e94392d7c557e3105924e078f0133c47d496b1c123764b980`. `final-v2-independent-validation-v1/validation.json` certifies both actual FLOAT3249,992-face meshes closed/manifold/outward, zero global crossings and exact stock-frame reflection/winding/P/N/T/UV/maps. The20 inherited negative shading corners on16 microscopic source faces are not new cap/mirror defects. Fifteen paired actual-stock pose images are under `paired-thigh-v2-review-v1`; fixed accepted neighbours, nativeScale1. Small distal flesh visibility in kneel is being checked against the actual client/stock shin before completion.

Both selected thighs are independently compiled: `left-thigh-native-stage-selected-v2-left-v1` (legl binary `e82617d80230c5ac3496093de84bb01ceefdb16f2c25c4b96450cd995333126c`) and `right-thigh-native-stage-selected-v2-right-v1` (legr binary `cfd6d71f11594756fbb54a8710f3dc687f556c63bb69dde3a5998f7abef6f033`). `selected-v2-native-fixture-batch-v1/batch.json` records nine fresh built/audited pair fixtures with common60-resource HAK `050b010187d4f2188bfd19056043426bd3e3dbff71f83531dc0df80a111af866`; actual client gates are still pending. All cameras are unlocked. Focused lower-camera fixtures are being added so thighs/knees are visible above chat.

The owned running client at this checkpoint is `client-left-cap-v2`, PID47004 launched2026-10-02T20:39:22−04:00. HAK `25abdf27a49ef4c51835486f42306a83f35d3c6b5ab24360e8ccf8d040eb083b`, module `99d94fb6cf6ea7c01701a16cec784aa3b260dbb59d52e20ca867f52d87ed70f6`. Saved front idle, rear crouch and rear CONJURE1 observations confirm material/upper join behaviour; knees were cropped by chat in the latter views, so these are not full leg validation. Reobserve exact PID/argv/window before replacing it.

Mirror helper8 focused tests, composition helper6 focused tests, stage adapter5 focused tests, cap field6 focused tests and package audit23 negative guards pass. Native tangent/client validation remains required. Pilot outputs belong under `output/phenotypes/purposebuilt-thigh-pilot-v1`. Existing unrelated dirty files and historical custom limbs are excluded.

Original kit README now has a minimal guidance banner to `docs/image-to-parts-kit-current-workflow.md` in the active worktree; all original body bytes/scripts/models preserved. `kit-guidance-update.json` records before/after hashes. It prevents the old Meshy whole-body/stretching recipe from being mistaken for the current local Comfy purpose-built stock-rig process.

Update this checkpoint with selected inputs and completed receipts before compaction. Do not rerun successful generation or overwrite accepted assets merely because context was compacted.
