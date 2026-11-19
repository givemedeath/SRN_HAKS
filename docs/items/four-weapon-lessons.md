# Four-weapon workflow review — 2026-10-24

The Cougar Longblade, Knife, Longsword and Colt L36 are user-approved.
Their selected package bytes remain unchanged. The Ingram Smartgun X is on hold.
This review changes tooling for future runs, not historical receipts or approvals.

## What the four weapons taught us

| Weapon | Cost or error | Rule for the next item |
| --- | --- | --- |
| Longblade / short sword | Repeated in-game width/depth corrections; overall bounds were a poor sizing reference. Low-resolution exports obscured where defects began. | Fit to measured usable grip landmarks and transverse sections; compare raw, donor and reduced geometry with matched cameras before blaming generation. Preserve length explicitly when changing thickness. |
| Knife | Affine object decomposition lost shear; fragmented UVs and a few projection misses caused late failures. A requested total-length change was initially misunderstood. Runtime-created actors were missing. | Apply the same matrix directly to donor and target mesh data, inverse-transpose normals, preserve exact UVs. State the final whole-assembly length ratio. Place both Human actors directly in the entry area. Retain completed bake data for bounded recovery. |
| Longsword | Five attempts, overly destructive cleanup and lengthy repairs; larger input images did not establish better construction. Collinear part cuts generated invalid caps. | Use smooth clay/detail pairing. Inspect each generation before appearance. Preserve meaningful construction; seek a design decision on a small imperfection rather than erasing surrounding structure. Use the validated cap route and inspect cut boundaries before baking. |
| Colt L36 | A vertex-colour preview looked much worse than the saved appearance field. Melee grip length made the pistol oversized. Dense shell topology defeated repeated shadow decimation. Variant rendering repeated identical clay views. | Judge the per-pixel saved-field donor and actual runtime diffuse. Use the approved firearm grip standard. Triage shadow construction early and consider an independently built simple proxy. Render shared geometry once per finish batch. |

Sources: `cougar-workflow-audit.md`, the four authoritative item checkpoints,
`output/itemkit/cougar-fineblade-longsword/finishing-code-audit-v3.json`, and
`output/itemkit/colt-l36-pistol/finishing-optimization-audit-v2.json`.
Final approval is bound by
`output/itemkit/pistol-trial/completed-weapons-user-approval-v1.json`.

## Changes in this pass

1. **Bound dependency verification to a stage.** The runner now shares one
   `VerificationPass` among its execution-time dependency lookups. A fresh
   completion pass checks ancestors and reviews again after processing. Worker
   dispatch and completion checks remain independent. No persistent cache,
   timestamp trust, source-scope reduction or Comfy verifier change is involved.
2. **Do not scan source for every old failure.** Attempt history is read once per
   receipt and compared against one current source version per dispatch phase.
   Two failures on an unchanged CPU snapshot still stop retries. This does not
   alter the separate five-geometry-submission ledger or uncertainty rules.
3. **Reuse only identical geometry views.** The maintained `review.render_variants`
   callable and Blender worker `render-variants` action render the first finish
   normally, then copy its eight byte-verified clay frames for later finishes.
   Exact scene bytes, family and camera/light settings must agree. Lit/unlit views,
   icons and runtime mesh exports remain finish-specific. Geometry-changing
   variants require separate batches. Nothing is reused across separate runs.

The render batch accepts a normal worker configuration with `scene`, `family`,
`render` and a `textures` mapping from safe variant names to runtime textures.
Declare the scene and every texture in `inputs`, plus the consumed tooling, and
dispatch through the existing verified launcher. Set `stage` to `render-variants`.
Results are under `variants/<name>/result.json`, with a batch result above them.
Single-finish `render` and existing CLI defaults remain compatible.

## Next-item order

1. Bind a stable design identity and reserve the native resources. Confirm the
   effective contract with a small native fixture before expensive generation.
2. Review smooth clay and detailed colour images together: framing, alpha edges,
   tip/muzzle, structural members and intentional openings. Do not infer quality
   from source pixel dimensions alone. Keep the frozen sampler and five-attempt
   ledger; reconcile uncertain jobs before a retry.
3. Review geometry before saved-shape appearance. Then inspect the actual
   per-pixel original-frame donor bake; a vertex preview is not a texture gate.
4. Fit early to the correct grip authority: Cougar for melee, approved Colt for
   firearms. Measure each design, preserve its angles/proportions and review on
   both Human bodies. Do not copy historical source-scale multipliers.
5. Before a full transfer, inspect reduced-to-donor offsets, normals, cuts and
   runtime-resolution UV coverage. Check small charts and gutters at 1K, not just
   at 4K. Diagnose high-genus shells before repeatedly decimating shadow geometry.
   Simple proxies still need closed outward topology, opening probes and visual
   comparison; high silhouette overlap alone did not preserve the pistol guard.
6. Bake original-frame appearance to the donor at 4K, then transfer from the fitted
   textured donor to final UVs. Preserve EXR, owner/cap/miss masks and source scene
   before correction. Recover only failed pixels from a measured, reviewed donor
   policy. Never widen bounds or copy another item's exceptional face IDs merely
   to pass. The subsequent [early-check and recovery implementation](early-checks-and-recovery.md)
   provides maintained recovery preparation and per-part silhouette proxies;
   geometry-specific settings and visual review remain mandatory.
7. Derive 2K/1K/512 maps, review the actual 1K diffuse, and batch finishes that share
   geometry. Keep four CPU render threads. Compile each unique native resource
   once per qualification, then rebuild only the affected fixture/package.
8. Include all requested completed weapons and both Human actors in the fixture.
   Find comparison blueprints in their verified MOD resources when absent from
   HAKs. Verify exact payloads and preserve approved comparison HAK hashes.
9. Choose tests from changed code and dependencies. **For this optimization pass,
   the user explicitly prohibits another full regression run.** Run focused
   regressions, catalog equality and the synthetic render smoke only. Do not
   reinterpret a historical failing full run as a clean pass.

## Measurements and limits

- Earlier knife DAG benchmark: 32 reads of one 4 MiB file became one read;
  0.615 s became 0.119 s. This is not total generation time.
- Earlier loaded-code synthetic benchmark: 6.810 s became 2.702 s, with traced
  allocations falling from 5.33 MB to 1.79 MB. Broad runtime costs remain real;
  do not remove stale-callback or conditional-setting checks to hide them.
- Pistol shadow construction itself took 0.991 s after the correct approach was
  found; that excludes failed experiments, launch checks and review.
- Pistol retained-bake recovery took 52.827 s; final matched rendering took
  347.057 s. These are different phases, not before/after measurements.
- A two-finish firearm batch needs 40 view renders plus two icons rather than
  48 views plus two icons: **eight fewer render calls (16%)**. This is a work-count
  reduction, not a promised 16% end-to-end time saving.
- A retry-history test with twelve obsolete failed receipts now performs one
  source-version query in the dispatch phase rather than one for each failure
  plus the receipt. Completion checks remain fresh.

One-to-two-hour turnaround remains a target, not a demonstrated guarantee.
Record generation preparation, verification, queue time where available,
execution, collection and CPU finishing separately. Preserve unknown memory and
queue measurements as unknown. Do not confuse file bytes hashed with live RAM.

### Current turnaround requirement — 2026-11-02

The user requires **less than 120 minutes from Comfy startup through a finished,
body-fitted native weapon**. Include startup qualification, verification, waits,
retries, agent preparation/review and packaging in that clock. Reusing a running
service or measuring only inference does not demonstrate a cold-start result.
Use existing run timestamps and the authoritative item checkpoint; add no timing
framework or parallel tracking ledger.

Budget the normal path to 105 minutes, with at most ten minutes of bounded
recovery: target completion within 115 minutes, leaving five minutes of margin
under the user's two-hour ceiling.

| Work | Budget |
| --- | ---: |
| Startup and fresh runtime qualification | 10 min |
| Geometry, construction/opening review and working-mesh decision | 20 min |
| Saved-shape appearance and original-frame donor | 15 min |
| Both-body fit, reduction and final UVs | 20 min |
| 4K transfer, recovery and runtime maps | 20 min |
| Native export, actual runtime-texture views and private package | 20 min |

These are operating limits, not measured guarantees. New carrier implementation
is real development work; keep its cost visible instead of hiding it outside an
item's reported elapsed time. Reuse its qualified adapter on subsequent items.

- Keep the high-detail UDF colour donor separate from the solid working mesh.
  The donor needs valid sampleable faces and the exact original coordinate frame,
  not native closure. Explicit `sampling-surface-v1` preserves positive-area
  microtriangles and only removes bounded exactly-zero-area faces. Working and
  shadow closure, openings, UV coverage and bake gates remain mandatory.
- Inspect raw construction once, then choose the working route immediately.
  Nearest-normal SDF needs consistent winding; its manifold option cannot fix
  inconsistent signs in fragmented generated meshes. Use the existing solid
  remesh for that case, with measured opening preservation. Keep the required
  768-resolution UDF export for the colour donor.
  Use `request --stage export --working-shell` for the separate solid engineering
  export. The default still exports the family's UDF colour donor; the working
  option neither changes that profile nor requires another asset manifest.
- Limit working repair to one bounded method and ten minutes of recovery per
  item. A failed construction gate triggers the next permitted geometry attempt
  or an explicit resumable failure; do not chain whole-mesh wrap/voxel experiments.
  Preserve the five-attempt ceiling and reconcile uncertain submissions first.
- During GPU execution prepare the next independent CPU operation. Reuse exact
  accepted source, fit, donor and carrier evidence with fresh byte checks. Run one
  complete stage review and only affected tests, then finish the item.

Observed partial-stage evidence: the corrected live verifier completed a loaded-
model neural gate in 140.816 seconds; Heavy Crossbow donor UVs plus its 4K bake took
204.851 seconds. Neither establishes a complete sub-two-hour weapon. That claim
requires a finished native candidate, both-body fit and the full elapsed clock.

Validation and exact changed-source bindings for this pass are retained under
`output/itemkit/four-weapon-optimization-v1/`. No accepted item was regenerated,
rebaked or repackaged, and no SMG work was resumed.

Final validation: 101 affected itemkit tests passed in 10.232 seconds; catalog
equality passed separately. The four-thread synthetic Blender smoke passed with
42 render calls versus 50 independent calls, with identical copied clay images
and distinct finish textures. It uses a 32-pixel test scene; its timing is not
a production rendering benchmark. Exact final source pins, logs and unchanged
accepted-package checks are bound by `output/itemkit/four-weapon-optimization-v1/result.json`.
The first smoke had a relative-output-path error; the second was stopped after
Blender ignored a test-only size override. Both remain retained. The corrected
smoke passed. No full helper regression was run.

Before the next item, freeze fresh source/runtime bindings for the updated tools.
Do not rewrite old source pins or accepted receipts to make historical runs current.


Measured continuation: Shield native delivery (2026-11-02)

The whole-item120minute target is not yet demonstrated. Reusable changes now
include the qualified single-model Shield adapter and exact constant-alpha
roundtrip, source-matched cap sampling, curved contact-cap classification and
a reserved unmapped material cell. Retain one original-frame4K bake; recovery
can use each touched triangle's own donor material and computes normals only
for sampled triangles. The real two-material smoke verifies distinct RGB,
linear colour and unchanged successful pixels. Shield recovered60147texels in
30.5seconds within the same3mm/facing policy, without rebaking.

CPU transfer steps now declare their actual source/data closure (16bake inputs,
19recovery inputs), rather than inheriting an unrelated full helper inventory.
Fresh dispatch/completion byte checks remain. The earlier UV step was already
scoped, so it provides no4500-to-small-count speedup claim. Actual1K32-view/icon
render took50.5seconds at4threads; offline Shield compilation and exact native/
UTI/HAK validation took13.437seconds. These are partial-stage timings, not a
claimed end-to-end result. The fixture completion reused already-built body
and weapon packs after a module-format correction; unchanged assets were not
rebuilt. Remaining generation operations retain their current source/runtime
gates. Do not start another verifier architecture or bookkeeping project.

Measured continuation: combined appearance and donor (2026-11-03)

For the qualified single-image route, use `request --stage appearance
--appearance-donor` after geometry approval. It retains the original raw mesh
and appearance field and adds the unchanged 200K/768 UDF donor recipe to that
same job. The existing exact saved-shape comparison and fresh dispatch/completion
gates still apply. Legacy requests remain unchanged. This replaces two GPU jobs
and six verified child launches with one job and three launches; it removes no
required verification boundary within the remaining job.

The first Katana combined job completed GPU processing in37.67seconds and passed
the raw saved-shape comparison plus runtime/model completion checks. Its child
request/submit/collect timings were33.469/137.141/167.891seconds. The separate
Katana engineering export had taken10.954/184/107.188seconds in those children
(313.202seconds from submission through collection). That is evidence for an
approximately five-minute avoided export cycle, not a matched end-to-end speedup
benchmark or proof of the120minute target. Its subsequent source UVs and4K donor
bake took155.015seconds. Both-body fit preparation ran during GPU work. The
optional branch is isolated from raw outputs by the installed remesher's copied
mesh result; exact raw equality also passed in the real collection.

The affected graph/request, itemkit and Greatsword checks are the validation
scope. Do not run unrelated headkit classes or the full helper suite for this
change. Continue from the completed stage and rebuild only changed descendants.


Katana continuation: avoid repeated repair and late appearance discovery (2026-11-03)

Protect mating-rim incident faces during selected-face reduction, then check the
closed assembly, exact rims and budgets before the final appearance transfer.
For the small native-coordinate meshes, optional `coordinate_scale=1000` changes
only temporary xatlas charting positions. It fixed collapsed charts while keeping
all physical positions and UV coverage/gutter limits unchanged; legacy scale1
remains the default. Eleven affected atlas/contour/shadow checks passed.

A failed transfer retains its actual pixels, masks and scene. Diagnose all failed
faces together, add only measured source-matched auxiliary sampling patches, and
resume that bake. Katana recovery corrected84880texels in69.547seconds without
changing successful pixels. Its200K original donor and native9988/308 budgets
were not enlarged; six auxiliary triangles belong only to the sampling copy.
Seventeen focused donor/patch checks passed; no full suite was run.

Inspect actual donor materials immediately after the original-frame4K bake and
before final reduction/transfer. The Katana donor itself lacked the reference's
wrap detail; transfer was faithful. Its existing reference-grip finishing method
restored that appearance in110.813seconds with zero unresolved misses and exact
unchanged geometry/UV/normal/shadow arrays. Re-render only changed appearance and
icons, reuse unchanged geometry/shadow views with fresh checks, and compile the
native package once. These measured stage savings do not establish the full
cold-start-to-both-body-fitted120minute target; measure that on a completed item.


Staff continuation: avoid repeating a failed construction pattern (2026-11-03)

Two seeds from the same side view produced a large false sheet behind the shaft.
Both were rejected before appearance or baking. A matched oblique color/clay
pair exposing the round end face removed that construction failure on attempt3.
The same stable model and all three attempts remain counted. For this repeated
construction failure, change the revealing input view rather than spending more
seeds or broad manual repair on the same defect. This is a measured result for
Staff, not a guarantee for every thin object.

Keep the owned GPU queue and independent CPU finishing overlapped: the stock Bow
draw/hand preview completed in22.922seconds during Staff collection, and Staff
hand-fit preparation ran during Bow calibration. Use existing job tokens for
collection and stop the sequential chain on failure. Do not resubmit a job to
recover a collection-command error. A full strict working-mesh audit still gates
appearance; preserve a reduced candidate and its diagnostic before a failing
assertion so recovery does not repeat an otherwise valid reduction.


Verified operational pass (2026-11-03)

Use a single checked preparation/submission/collection sequence for the next
known GPU stage. The local Wave2 run recipe completed the actual Bow geometry
job; it binds its own script, stops on failure and collects the prepared token.
Reuse the already retained portable grip reference instead of reconstructing
paths to the same document. No new queue, ledger or runtime verifier was added.

Share CPU helper/library hashes only inside the initial validation pass, then
start a fresh completion pass over the full actual closure. Staff's selected
working run checked3621distinct files per boundary and reused1410initial checks;
20.156seconds includes its numerical shell finishing. The earlier omitted
library completion closure was corrected before selection; no historical
receipt or approved asset was rewritten. This is a work-count observation,
not a matched end-to-end speedup claim.

Prepare the working target independently of the future textured donor: Staff
fit/part extraction8.171s, constrained reduction9.344s, exact Blender installation
1.422s, early UV/shadow/source-distance checks15.187s. All passed before appearance.
Retain the exact recorded transform and later apply it once to the textured
original-frame donor. Native triangles9988/216, strict UV/gutter/source gates
unchanged. Small internal part-cut offsets can avoid source-vertex coincidences;
Staff required85/109micron shifts, preserving the entire external shape.
Do not regenerate geometry or repeat completed target work for these cut errors.

Melee wave 1: long weapons bow and twist (2026-11-10)

Five designs, flat side-on single-view references. Only the short knife came out
usable on attempt 1. The Sword's guard became a deep slab, the Claymore's blade
twisted, the Club bowed and the Spear's head bent about 90 degrees into depth.
A second seed fixed only the Claymore. This repeats the 2026-11-03 Staff lesson
above, which was not read before the second seed was spent.

An oblique matched pair fixed invented part depth (Sword guard and hilt on
attempt 3) but not the bow along the length: the blade still curved in depth
like a sabre. The bow is a habit of the model with long thin objects, not a
reference fault, so a further seed or view does not remove it.

Guards now in the toolkit:

| Mistake | Guard |
| --- | --- |
| Geometry attempt spent on a long weapon from a flat side view | `request --stage geometry` refuses a `shortsword`, `longsword`, `greatsword` or `staff` manifest without `approval.referenceView` (`view: oblique`, or `view: side` with `sideViewWaiver: true` and review notes). |
| Bent or twisted clay reaches review unnoticed | `python -m tools.itemkit.straightness check MESH.glb --family F` reports centreline bend, blade twist and guard skew against advisory limits (1.5% of length, 12 degrees, 6 degrees). Run it on every collected clay; a flag goes to the reviewer with the views. |
| Seeds spent on a bow that seeds do not fix | `python -m tools.itemkit.straightness straighten MESH.glb OUT_DIR` unbends about the smoothed centreline. Cross-sections move and turn rigidly; triangles, UVs and textures are carried exactly. |
| A hafted head stays cocked after straightening (wave-4 Mace: haft straight to 1.5 mm, head 2 degrees off, bend 1.8%) | The default skips wide sections so a cross-guard does not steer the centreline, which leaves a wide head where it is. `straighten ... --whole` follows the head too (Mace bend 2.4% to 0.75%). Use it for maces and other hafted heads, not for guarded blades. |
| Straightened clay and its colour drift apart | Appearance and the source bake stay in the generated frame. Re-apply the saved map (`--map OUT_DIR/straighten-map.npz`) unchanged to the textured donor and the working shell, then bind those in a fresh fitting manifest. |

Calibration on the ten wave-1 clays: every bowed mesh measured 2.3% to 18.6%
bend, the twisted Claymore 31.9 degrees of twist, and the two acceptable
results (Claymore attempt 2, straightened Sword) passed. The check does not
detect an invented thick part such as the slab guard; end-on views still need a
close look. Its midline assumes a roughly symmetric section, so an asymmetric
knife reads as bent and the limits are advisory outside the long families.

Straightening is a geometry change after generation. It needs the same user
clay review as a generated attempt, on the straightened views, and the review
record names the generated source, the map hash and the straightened mesh hash.

Melee wave 1 follow-up: thickness, size and fitting (2026-11-10)

| Mistake | Guard |
| --- | --- |
| Invented slab or plate guard passes the straightness check | `check` reports `guardSectionRatio`; above 2.5 is flagged (wave-1 slabs 3.1 and 3.6, bar guards 1.1 to 1.3). |
| Blade far too thick for its width | `check` reports `bladeDepthToWidth`; above 0.5 is flagged. The Sword at 0.40 was accepted, the Claymore at 0.65 was called too thick. |
| Thick blade sent back for a new seed | `python -m tools.itemkit.straightness thin MESH.glb OUT_DIR [--factor F \| --ratio R]` scales only the blade's depth about its mid-plane; guard, grip, pommel, width and length are untouched. The default halves the blade: on the Claymore the user rejected a 0.22 target as too thin and chose half. Thin after straightening, review the thinned views, and re-apply the saved map (`--map`) to the textured donor and working shell. |
| Weapon overscaled by a strict pommel-to-guard hand span | `autofit.grip_start_for_length` extends the hand span into the pommel so the weapon matches the stock carrier's length. The Sword came out 1.26 m, was sent back, and was accepted at 1.10 m. |
| Part cut lands on mesh vertices and the part fails its closed-solid check | `autofit.clear_cut` moves each cut up to 0.3 mm to the plane farthest from any vertex. |
| Cut rims of a 200K shell exceed the per-part triangle budgets | `autofit.thin_shell` collapses the closed working shell to 40,000 triangles (same genus, within 0.25% of the length) before fitting. |
| Hand-picked grip endpoints, joins and probes per design | `autofit.landmarks` finds pommel, grip, guard and blade from a straight shell, by cross-guard or, for a knife, by the thin blade run. |

`splitBladeSlices` only catches gross delamination: the Claymore's hairline edge split near the tip scored 1 and was
not flagged, so end-on views still decide. Halving the blade also closed that split visually.

Two-hand sizing departure (2026-11-10): sized by the approved midpoint depth, the wave-1 Claymore's round, thick
grip made it 0.98 m, shorter than the 1.10 m one-handed Sword. The user chose about 1.45 m instead. The two-hand
fit still refuses any depth departure by default; it now accepts one only when `fit.gripDeparture` carries
`depthDepartureApproved: true` and the digest of that exact measurement, taken from the fit worker's own retained
`grip-measurement.json` (an offline measurement differs in float rounding and will not match). The both-body visual
hand-fit review is unchanged and still required.

### Club continuation — 2026-11-11

The wave-1 Club (a round club on the longsword carrier) reached an approved in-game result at 0.76 m on geometry
attempt 3 of 5, from an oblique reference pair. It exposed four gaps, each now closed in the tools:

| What went wrong | Guard now in place |
| --- | --- |
| Straightening a bent thick shaft hooked and sheared its end caps: slices near the ends cut the caps obliquely, so the measured centreline curled | `straightness._midline` ignores the last section depth at each end and continues the adjacent interior line (a synthetic bent club went from 2.1% residual bend and 17% section error to 0.16%). |
| The generated pommel cap was flat but tilted 23 degrees (head cap 8); a 0.6%-of-length slab fit read it as 3.5 | The straightening map now carries `ends`: flat caps tilted 0.5 to 30 degrees are sheared square over one section size. Flatness is a plane fit to the cap's outward envelope within 2% of the section size, so blade points and rounded butts are left alone. Older maps without `ends` still load. |
| The one-hand transverse grip correction scales depth and width separately; it turned the round club into a 4 x 6.5 cm oval and amplified the cap tilt | `fit.sizingAuthority: usable-length-round` (`grip.one_hand_round`) applies one transverse scale so the midpoint diameter equals the approved face width. It refuses a section that is not round within 10% and always requires a `fit.gripDeparture` bound to the worker's measurement digest. |
| A strictly uniform fit (no transverse scale) left a 7.3 cm handle on a 0.76 m club | Not offered as a route. Check the fitted section in `grip-measurement.json`, not the pre-correction `sourceSection`, before quoting a handle size. |

The Club's grip is 4.9 cm round: face width on standard, depth +65%. The Human male hand closes around it in game.
The Human female was seen only mid-swing, so the both-body hand-fit review for this departure is half done.

Fit-driver notes for designs without a blade or cross-guard: `auto_fit.py` cannot find landmarks on a round club.
Name the striking end and all four landmarks by measurement (`bladeAtLowEnd`, `pommelEnd`, `gripStart`, `gripEnd`,
`bladeStart`), read from the width profile along the straightened shell. The thickness probes fall back to the
nearest far-side vertex when a sparse thick shaft has none straight above. The round route needs two fit passes, like
the two-hand departure: the first stops at the departure gate and retains the measurement, the second binds its digest.

Other points from this run:

- A fit manifest must carry `approval.texturedDonor` and `approval.workingMesh` for its exact inputs before the fit
  stage; a failed first attempt leaves its run folder unusable, so correct the manifest under a new suffix.
- A fixture manifest is a new manifest, so the whole CPU pipeline reruns under it (about 30 minutes for one weapon).
- The appearance job left a pale squiggle on the grip texture. It is not noticeable at game distance and is unfixed.
