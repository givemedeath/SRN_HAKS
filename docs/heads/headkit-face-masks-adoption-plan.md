# Adopt head texture steps 1-5 into headkit (plan)

Approved by the user 2026-10-30. Status: in progress.

**Naming change during implementation:** `features` is already the manifest's feature-inventory key, so the new stage is `masks` (manifest section `faceMasks`) and the modules are `face_masks.py`, `face_encode.py` and `quality.py`. The tone switch is `tone.faceTreatment`. Wherever the plan below says `features`, read `masks` / `faceMasks`.

## Context

Steps 1-5 of `docs/heads/head-texture-quality-plan.md` passed as prototypes in `S:/Scratch/claude-scratch/race-heads-v1/review-kit`, and the user asked to adopt them into headkit. Validation so far: three elf heads in the client, step 5 calibrated, hair-lock fix done.

The prototypes chain into the pipeline through `exec` and hand-picked attempt folders, so they can't produce receipted, reviewable heads. Adoption makes them headkit stages, opt-in per manifest, so they run inside the normal receipts, approvals and pins.

| Prototype | Purpose |
|---|---|
| `face_priority_proto.py` | Face charts at 3x density |
| `mask_project_proto.py` + `mask_feasibility.py` + `iris_refine.py` + `hairlock.py` | Masks from the head's own front render |
| `mask_plt_proto.py` | Channel moves, de-light, smoothing, darks, brow and iris treatment, ownership-consistent 1K blocks |
| `qa_check.py` + `qa_thresholds.json` | Automatic quality gate |

**Out of scope:**
- **Shipped heads:** no shipped head, ledger or published asset changes. Re-encoding shipped heads is a later, separate decision.
- **Other races:** encoding was validated only on elves; the parser worked on all six races in step 0. The feature stays opt-in, and a per-race client check comes before any race uses it.
- **Step 4** (eye UV chart) is not done.

## Pipeline shape

New stage order (`runner.py` `STAGES`):

`prepare, precluster, fit, repair, unwrap, bake, paint, features, ownership, tone, palette, quality, export, native, render`

| Stage | Change | Manifest switch |
|---|---|---|
| unwrap | Face charts scaled to `faceDensity` x the rest, then repacked with the existing pack options. Bake then runs on the new layout from the field (better than the prototype's 3D remap of the old bake). | `mesh.uv.faceDensity` (default 1 = today) |
| features (new) | Front orthographic render of uv mesh + 4K colour (`rays.EmbreeScene`), MediaPipe landmarks, BiSeNet parse, iris refine, brow colour grow, hair locks, lip-line/socket darks. Soft masks are projected to 4K by depth match, filled from 3D neighbours and padded into gutters. Writes masks, front render, labels, landmarks and QA sheets; `visualReviewRequired`. | `features` section present |
| ownership | After the base labels (rules/atlas/project), apply the channel moves (step 2 rules plus RUNBOOK 129 and 133) and re-pad gutters. | `ownership.featureChannels: true` |
| tone | After adjust/tone match, apply step 3: de-light, smooth, lip line, socket, iris rim, lid line, brow luma, highlight cap and fringe refill. The 1K/2K maps use ownership-consistent blocks (RUNBOOK 125). | `tone.features: {...}` with the step 3 values as defaults |
| palette | Unchanged. It consumes the treated 1K colour and the majority-vote 1K ownership. | — |
| quality (new) | `qa_check` metrics against code-pinned thresholds. Fail → stage fails; export depends on a passing quality receipt when `features` is configured. | `quality` section present (required with `features`) |

**Channel moves (ownership stage):**
- iris → tattoo1;
- eye, lips and nose → skin;
- brows → hair;
- lash lines and old iris rings → skin;
- hair locks → hair.

Each stage keeps the runner's contract: stage-scoped manifest hash, code pins, `library()` byte-bound imports and dependency results.

## Files

New modules under `tools/headkit/`:

| Module | Source | Contents |
|---|---|---|
| `features.py` | `mask_project_proto.py` + `mask_feasibility.py` + `iris_refine.py` | Render, landmarks, parse, iris, brows, `hair_locks`, projection, QA overlays. Reuses `rays.EmbreeScene`, `textures.surface/pad`, `gltf.mesh`. |
| `feature_encode.py` | `mask_plt_proto.py` hook | `apply_channels(labels, masks, ...)` and `treat(colour, labels, masks, uv mesh, settings)`, plus `majority_1k(labels4k)` and `block_downsample(colour4k, labels4k)` |
| `quality.py` | `qa_check.py` | Metrics: featureFocus, blotch, specks, design specks, hair locks, roles, shade span. Thresholds in `quality-thresholds.json` (calibration provenance inside). |

Changes to existing files:

| File | Change |
|---|---|
| `uv.py` | `face_region` in the glTF frame (front +z, up +y; the prototype's export-matrix version translated) and the weighted chart scale + bisected repack from `face_priority_proto.repack`. Reuse `chart_ids` and `_pack_options`. |
| `runner.py` | Stages, dependencies (`features` ← unwrap + colour stages; ownership ← features when `featureChannels`; quality ← palette + features; export ← quality when configured), `stage_roles`, `stage_libraries` (features: `mediapipe`, `onnxruntime`), execution branches. |
| `common.py` | Manifest validation for the new sections; code pins for the new modules and the thresholds file. |
| `__main__.py` | Stage names in CLI choices, if listed there. |

**Libraries.** A new shared-tools folder `.tools/headkit-facemasks-v1/`, copied from the already-downloaded `review-kit/vendor/py` and `vendor/models`:

- **Contents:** mediapipe 1.1.0, onnxruntime 1.30.0 and their dependencies (absl, flatbuffers, google/protobuf, cv2, matplotlib, sounddevice and the rest).
- **Excluded:** numpy and PIL, which come from the headkit packages binding (itemkit-python-v1: numpy 2.3.5, Pillow 12.3.0; numpy is the same version mediapipe was tested with).
- **Models:** `face_landmarker.task` and `resnet18.onnx`, inside the same folder so the file inventory pins them.
- **Bindings:** two library bindings (`mediapipe`, `onnxruntime`) point to that folder.
- **Embree:** the features stage needs Embree 4.4.0 (`trellis-embreex-python-libs-v1/embreex.libs/embree4.dll`). The race-heads bindings currently point at pymeshlab's 4.3.3, so validation copies get bindings with 4.4.0. No version-gate relaxation.

**Docs:**
- `docs/heads/head-generation-toolkit.md`: a new "Face features (optional)" section covering manifest keys, the review points (features QA sheet, quality report), and that the quality gate must pass before a client check.
- `docs/heads/head-texture-quality-plan.md`: adoption status.
- `docs/heads/race-heads-v1-runbook.md`: rows for the guards that moved into headkit.
- Example manifest under `tools/headkit/examples/`.

## Order of work (commit at each checkpoint)

1. **Library folder and bindings.** Copy the vendor set into `.tools/headkit-facemasks-v1`, generate the file pins, and confirm `library(bindings,'mediapipe')` and `'onnxruntime'` import under the itemkit packages.
2. **features stage + `features.py`.** Port the prototype as is, with parameters as named constants and no behaviour change. Unit tests run on synthetic inputs:
   - hair-lock rule;
   - brow grow connectivity;
   - mask projection fill;
   - iris refine guards.
3. **ownership `featureChannels` + `feature_encode.apply_channels`, majority 1K.** Tests: channel-move table, gutter re-pad, ownership-consistent blocks.
4. **tone `features` treatment + block downsample.** Tests: darken-only de-light never brightens; smoothing leaves feature texels; brow luma lands at the hair median.
5. **unwrap `faceDensity`.** Tests: the face charts' texel-density ratio is within 10% of the target, no overlaps, and the 4K audit passes. A density of 1 is byte-identical to today.
6. **quality stage + thresholds.** Tests: each check trips on a synthetic failure, and calibration values from the plan pass and fail as recorded.
7. **Runner wiring, manifest validation, docs, example manifest.** The existing `test_headkit.py` suite must stay green.

## Verification

**Unit tests:**
- `python -m pytest tools/headkit/test_headkit.py` plus the new focused test files, using the itemkit packages and the new library bindings.
- The full helper suite, because `common.py` and `runner.py` are shared helpers (AGENTS.md).

**Parity runs:**
- **Setup:** validation copies of elf-male-a, -c and -d in `S:/Scratch/claude-scratch/race-heads-v1/trials/headkit-features-v1/<head>`, with the manifest plus `features`, `featureChannels`, `tone.features`, `quality` and `faceDensity: 3`, and their own bindings. Run through `launch_shared_tool.py` with declared inputs.
- **Pass:** every head passes the quality stage. Its metrics are within tolerance of the prototype's `9-hairlock` results:

  | Metric | Tolerance |
  |---|---|
  | featureFocus | ±15% |
  | Blotch and hair-lock pixels | ≤ limits |
  | Roles | ±0.03 |

  Any difference from the bake-on-new-layout change is explained.
- **Client check:** trial `stockcmp-v12`, checked at 0.9 m and 2.5 m (hair 117/17/5, tattoo1 26/153) next to the prototypes on slots 193-195.

**Not run:** no HAK rebuild, since no pack inputs change, and no shipped heads change.
