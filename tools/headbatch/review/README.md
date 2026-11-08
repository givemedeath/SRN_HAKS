# Headbatch Review Tools

## Overview
A comprehensive suite of read-only diagnostic tools, visual contact sheet renderers, and geometric verification utilities for evaluating head batch pipeline stages. These tools are invoked directly or via `run_headbatch.py review <tool> [args...]` to inspect neck cuts, jaw clearance, UV unwrapping, material baking, texture palettes, face landmarks, and mesh convergence without mutating pipeline state or granting implicit stage approvals.

## Interface
### Neck-Cut, Jaw & Shell Verification
- [`cutdry.py:dry_positions(neck, source, cut)`](./cutdry.py#L32-L46): Evaluates cut band positioning and physical vertex groupings before repair execution.
- [`cutdry.py:verified_cut_positions(head, attempt, source, cut)`](./cutdry.py#L49-L64): Replays neck-cut extraction against recorded repair inputs.
- [`cutreplay.py`](./cutreplay.py#L1-L27): CLI script replaying toolkit neck cuts with custom slope/reach overrides on uncut repair masters.
- [`cutshells.py:wrap(vertices, faces, alpha)`](./cutshells.py#L11-L22): Reproduces repair neck cutting and alpha wrapping.
- [`jaw.py`](./jaw.py#L1-L33): Dry-runs measured jaw line heights and cut bands.
- [`chinprofile.py`](./chinprofile.py#L1-L19): Generates front profile height band metrics for uncut repair masters.
- [`skirtzone.py`](./skirtzone.py#L1-L25): Generates review sheets for neck-cut skirt hair zones.
- [`slopescan.py`](./slopescan.py#L1-L23): Evaluates neck-cut boundary metrics across candidate slope angles.
- [`shells.py:capture(head, interior)`](./shells.py#L22-L78): Captures shell selection metrics and interior manifold geometry.
- [`boundary.py`](./boundary.py#L1-L24): Extracts and visualizes mesh boundary edge loops to detect holes.
- [`backcount.py`](./backcount.py#L1-L8): Reports per-height-band vertex density along the central X band to verify skull closure.

### Orthographic Views & Clay Renders
- [`_fit_views.py:compare(heads, views, resolution)`](./_fit_views.py#L131-L168): Renders multi-head matched orthographic clay views in NWN `head_g` frame.
- [`_frame.py:head_neck(head)`](./_frame.py#L13-L16): Resolves head manifest, fit-reviewed neck policy, and body neck reference geometry.
- [`_frame.py:band(local, cut, jaw, bv, bf)`](./_frame.py#L19-L31): Calculates cut plane height and identifies vertices drawn onto the body neck.
- [`_frame.py:report_uncut_jaw(head)`](./_frame.py#L39-L58): Inspects uncut jaw underside at neck centre against bound body neck rims.
- [`clay.py`](./clay.py#L1-L68): Renders multi-view orthographic clay contact sheets from GLB meshes.
- [`gpuclay.py:field_sheet(...)`](./gpuclay.py#L16-L45): Renders multi-view contact sheets for raw GPU geometry.
- [`repairclay.py:draw(head, attempt, output)`](./repairclay.py#L13-L52): Compares repair stage inputs, reductions, and neck cuts against final meshes and stored normals.

### Texture, Bake & Material Inspection
- [`bakelook.py:draw(head, attempt, output)`](./bakelook.py#L12-L47): Renders unlit base color views on UV meshes with full ray coverage.
- [`bakeviews.py`](./bakeviews.py#L1-L18): Compiles bake evidence sheets (texture, UV grid, fit matrix) for a bake attempt.
- [`grid.py`](./grid.py#L1-L44): Renders textured head views with bounding-box-relative ISO coordinate lines.
- [`materialchart.py:chart(head, attempt, output)`](./materialchart.py#L12-L46): Renders orthographic material charts in head-local coordinates.
- [`texturesheet.py:draw(head, stage, attempt, output)`](./texturesheet.py#L104-L137): Generates labeled atlas and mask contact sheets for tone and palette stages.
- [`uvfinal.py:probe(head, attempt)`](./uvfinal.py#L12-L66): Analyzes face-priority UV packing metrics on failed unwraps.

### Palette, Roles & Facial Features
- [`eyereference.py:propose(image_path)`](./eyereference.py#L10-L45): Derives eye bounding boxes and eyelid span proposals from source references.
- [`irisrows.py:run(head, attempt)`](./irisrows.py#L13-L44): Renders decoded iris crops alongside source appearance and alternative palette rows.
- [`rowramps.py`](./rowramps.py#L1-L18): Compiles color ramp evidence for mapped texture channels.
- [`gamesize.py:run(head, attempt)`](./gamesize.py#L10-L24): Builds compact palette verification sheets at game-native resolution.
- [`roles.py:measure(head, rules)`](./roles.py#L18-L62): Analyzes vertex group ownership role distributions without modifying head configuration.
- [`hairgaps.py:measure(head, attempt)`](./hairgaps.py#L14-L44): Evaluates scalp hair ownership boundaries against source geometry.
- [`own_draft.py`](./own_draft.py#L1-L38): Previews vertex assignment for draft ownership rules offline.
- [`ownsheet.py`](./ownsheet.py#L1-L53): Visualizes finished ownership atlas partitions on consumed UV meshes.

### Fit & Landmarks
- [`design_landmarks.py:detect(image, refine)`](./design_landmarks.py#L32-L78): Detects 2D/3D facial landmarks from source imagery for landmark-based fitting.
- [`fitcheck.py`](./fitcheck.py#L1-L38): Verifies nose-tip positioning and profile scaling in the fit matrix.
- [`exportfit.py:check(head, export_mdl)`](./exportfit.py#L10-L28): Validates native MDL export dimensions against reviewed fit matrices and Troll sizing policies.
- [`hot.py`](./hot.py#L1-L40): Evaluates bidirectional Hausdorff distance clusters between master and final meshes.

## Invariants
- All review tools are strictly read-only diagnostics; they never modify manifests, approve stages, or mutate candidate meshes.
- Texture and bake review tools (`bakelook.py`, `texturesheet.py`, `gamesize.py`) strictly bind to exact stage receipts and attempt numbers, failing if referenced receipts are absent or mismatched.
- Eye reference proposals (`eyereference.py`) reject occluded, closed, or reversed eyelid spans and never write modified reference records.
- Cut calculations (`_frame.py`, `cutdry.py`) ensure explicit height settings take precedence over detected jaw heights and exclude skirt hair from cut bands.

## Side Effects
- Writes rendered diagnostic images (`.png`), contact sheets, and summary JSON metrics to head review folders (e.g. `{head}/review-evidence/`) or designated command-line output paths.
- Reads head manifests, receipts, mesh GLBs, textures, and body neck reference geometry from the workspace.
- Outputs diagnostic measurements, warnings, and error summaries to stdout/stderr.

## Verification
- Run: `pytest tools/headbatch`
