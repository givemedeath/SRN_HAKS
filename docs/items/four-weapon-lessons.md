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
