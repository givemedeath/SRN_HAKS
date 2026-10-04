# Purpose-built Human male feet: current process

This record owns the offline foot method. The newer material task explicitly
released client access and completed material-specific native/TBN/client checks;
see [material validation](phenotype-body-texture-repair-validation.md). Foot
regeneration remains stopped and anatomy is unfinished. Its checkpoint owns
those boundaries; earlier client-hold descriptions below are historical.
Follow [native material preservation](phenotype-body-material-process.md) before
adopting a new foot: carry selected neighbour materials forward and retain AO,
roughness, palette and fabric behavior through explicit runtime descendants.
The user prefers bulk client validation after offline collection of the
phenotype's parts. Complete each part's offline proof and retain native/palette,
motion, equipment and performance cases for that assembled phase.

## Stock measurement, images and reconstruction

Measure actual `pmh0_footl001` at `lfoot_g`, accepted shin coverage, ankle pivot,
heel/toe and sole. Stock left medial is +X. The closed crown is hidden overlap;
do not generate a shin shaft or ankle cuff. The low-poly wedge is a dimensional
and attachment reference, not a target for projecting an anatomical exterior.

`stock-connectors-v2` clips distal shin triangles before posing. The initial
v1 whole-spanning-face bounds were too broad and remain historical. Preserve
face IDs and exact controller matrices alongside rendered guides.

Generate one isolated left foot and four coherent views. Shared isotropic
normalization preserves anatomical proportions, but generated views can still
differ: this sheet's medial/lateral length discrepancy was 6.42%, with an
18-pixel normalized sole-height difference. Treat prompt alignment as intent,
measure actual images and inspect the reconstruction before retrying. Do not
stretch the views to hide those discrepancies.

One Comfy job, `9b103b49-458d-4a54-825a-130b18b07923`, completed successfully
with retained raw, remeshed, shape and textured masters. The selected untouched
textured source is SHA256
`1757c79e20c7ee294082e33d4be980be7c260806a4cf32e7b6d7918d381a0323`.
Source orientation was opposite the nominal renderer's front filename:
actual toes pointed -Y and the big toe -X. Proper Z180 fixes both for the
left foot; no reflection or rig change is involved.

## Similarity fitting and local contact repair

The first fit keeps one uniform scale 0.3187211742 and proper Z180, with an
explicit source-ring-to-stock-pivot ankle inference. It produces length 293.983,
width 115.736 and height 163.261 mm. Idle minimum world height is within 0.16 mm
of stock. Do not shift the foot solely to match a wedge's silhouette extremes.
Six accepted neighbouring GLBs and corrected pelvis runtime PLT stay exact.

The source was closed but had 17 valence-4 toe contacts. Closed edges, positive
volume and one component were insufficient adoption gates. Independent fan
continuation identified 23 split vertices; micro-separation of 89 corners resolved
16 contacts. A bounded remaining one-ring replaced 13 faces with 5 unchanged-rim
triangles. No whole-foot remeshing or surface fitting occurred.

The first repair passed manifold/vertex-link checks but introduced 14 genuine
crossings. Their measured ownership implicated just three fan offsets. The
corrected trial changes those to 10-micrometre inward geometric fan offsets;
the other 50-micrometre separations remain unchanged. Full actual FLOAT32 tests
now find zero positive crossing pairs, boundary/nonmanifold/winding/degenerate
defects or bad vertex links. Preserve the failed parent as rejected diagnostics.

The clean exterior remains genus 4 because the generated toe gaps have handles.
It also retains a tiny source-authored negative-normal corner set. These are
recorded anatomical/shading limits, not a claim of a perfect simple solid or
native visual acceptance. Later correctly exposed sole inspection found an
extra toe-shaped lobe hidden behind the little toe. This remains an open
anatomical defect even though geometric proofs pass; client review is pending.

## New-face materials and mirroring

Copying UVs from geometric boundary corners is insufficient when a boundary
crosses atlas seams. Four first-repair triangles spanned 0.48–0.83 UV and had
poor authored-T/UV alignment. The explicit mapping descendant projects only
the 5 new faces into one existing local skin chart, original source face 45842.
Its UV span is 0.003447 by 0.004425, projection displacement at most 0.633 mm.
It derives new tangent directions and signs from serialized UV differentials,
orthogonalized against unchanged authored normals. Retained UV/T, all P/N,
embedded maps, materials and original BIN remain unchanged.

Independent new-tangent/UV agreement exceeds 0.9999999998. Nine same-position
boundary samples differ at most 5.4/255 in a base-color channel; that is a finite
sampling result, not proof of an invisible seam under every shader. The clean
donor before the final placement correction is `left-foot-contact-chart-v1/mapped-local.glb`, SHA256
`c36c5f999b38a0c8767b7c6761b53856638c6b7273fdfc71c8cda8aa46ac9d21`.
Root selected it offline after close front/rear/medial inspection. Mirror only
the selected placement descendant through actual stock foot frames, reverse winding
and T handedness, preserve UV/map sampling and independently verify the right side.

The user requested a tiny forward shift after reviewing the pair. Apply an
explicit +3 mm in stock foot-local +Y to the clean left donor, then mirror that
descendant. Preserve source shape, uniform scale, local height and orientation;
do not move the rig pivot to compensate. Measure the actual serialized positions
against this translation, bind a fresh placement receipt, and refresh ankle
coverage, previews and stage/material associations. Keep the pre-shift pair as
history, never as a competing active selection.

## Skin and package provenance

Measure area-weighted UV-used ankle regions against the accepted shin rather
than whole-atlas means. Two offline diagnostics measured the foot roughly
6.5–8.4 skin shade indices brighter. A separately bound -8 trial has been
verified offline; do not use the pelvis's -54 as a default. Preserve original maps and
base ASCII audit while identifying the corrected PLT as an explicit descendant.
Do not confuse source color exactness with native palette continuity.

Foot stages preserve `chest,pelvis,legl,legr,shinl,shinr`. Maintain accepted
pelvis runtime skin bytes while original compiler dependency records stay exact.
The full accepted 68-resource fixture includes 42 comparator/test payloads;
an offline mixed HAK can copy these byte-exact only with explicit diagnostic
labeling. Keep the clean 34-resource body collection (26 accepted resources
plus 8 declared foot resources) separate from the 76-resource diagnostic fixture.
Neither establishes native-foot acceptance before the queued engine checks.

## Reusable execution sequence

Before final donor adoption, review correctly exposed sole and oblique underside
images as well as top/front profiles. The current source has five distal toe
tips plus an extra plantar-lateral lobe; the defect predates repair, translation
and mirroring. `toe-anatomy-review-v2/finding.json`, SHA256
`bf6a448d90260dce9d46ab1a011ed11d1bf5e4868b85f02cdeaf7b2e2b1f2870`,
and `underside-anatomy-independent-v2/lobe-ownership.json` record its measured
ownership. The 599-face localization is evidence, not an automatic delete mask.
Preserve all five actual tips and record a bounded correction with new proof
before finalizing the feet. Overlit images can hide anatomy and cannot close this gate.

Use the bundled workspace Python and fresh output directories for every stage.
Completed directories are immutable evidence; commands below illustrate a new
stage, not instructions to rerun the completed Comfy job. The exact executed
11 staging/material/package commands and outputs are preserved in
`output/phenotypes/purposebuilt-foot-pilot-v1/forward3mm-offline-execution-v1/commands.json`.
The [generation procedure](phenotype-purpose-built-part-generation.md) and
[fitting record](purposebuilt-foot-fitting-pilot.md) own preceding image,
measurement, similarity, bounded repair and mirror commands.

```powershell
$partPython = 'C:/Users/benco/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
$selectedReceipt = 'path/to/verified-selected-fit-or-mirror.json'
$newPlan = 'path/to/fresh-foot-plan'
$newStage = 'path/to/fresh-foot-stage'
$newAudit = 'path/to/fresh-foot-audit'
& $partPython tools/phenotypes/prepare_stock_limb_stage_config.py --receipt $selectedReceipt --part footl --stock-bank output/phenotypes/purposebuilt-stock-inputs-v1 --output $newPlan
& $partPython tools/phenotypes/stage_stock_part.py --config "$newPlan/stage-config.json" --output $newStage
& $partPython tools/phenotypes/audit_limb_ascii_material.py --converted "$newStage/human_male_fit/converted" --config "$newPlan/stage-config.json" --output $newAudit
```

Change the declared side to `footr` only with its actual verified mirror receipt.
Read actual ASCII against GLB/map bytes; a successful export is not the audit.
The calibrated operation uses `adjust_foot_skin_plt.py --config <explicit-config>
--output <fresh-child>`. Bind the current stage, actual ASCII/palette hashes and
new calibration receipt; never reuse an old stage pin after moving geometry.

The foot calibration samples four barycentric points per triangle with area/4
weights in declared ankle bands, using the actual stock shin-to-foot frame.
It excludes near-horizontal caps/sole via a geometric side-normal mask. These
are finite UV-used samples, not engine-visible pixels; neighbour occlusion,
lighting and palette appearance remain unmeasured. Executed `measure.py`
snapshots and input hashes are retained in the left/right forward3mm ankle-shade
directories; their exact frame/band settings are evidence, not hidden defaults
for the next part or race.

For offline composition, use both final shade-stage roots and explicit material
receipt SHA256 pins. Also pass the exact accepted native donor receipt, runtime
pelvis material patch, accepted HAK and selected six-neighbour geometry manifest
with their pins. The last command in the execution record lists every required
flag. `compose_stock_limb_offline.py` preserves prior native bytes and records
unexecuted native commands; it cannot produce a native-foot assertion. Keep its
clean body manifest as the selected assembly index and its full diagnostic HAK
as a fixture only. Actual native compilation follows the future client release.

No offline stage/HAK establishes native tangents, actual palette rendering,
animation transitions, boots/armor fallback or gameplay performance. Queue
those checks for the user's client release. The latest direction is to stop
after feet and await instructions; earlier upper-arm continuation is superseded.
Archive diagnostic iterations without carrying their
old settings or candidates into the selected lineage.
