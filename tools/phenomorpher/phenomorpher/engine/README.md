# PhenoMorpher Engine

## Overview
Internal numerical backends and geometric algorithms for the PhenoMorpher toolkit. This component contains the core fitting, deformation, measurement, silhouette rasterization, animation library extraction/repointing, connector surface auditing, and stock armor retargeting routines. All public entry points are exposed through `phenomorpher.api` and the PhenoMorpher CLI; modules within this engine package are internal implementation details.

## Interface
### Fitting & Morphology
- `fit_anatomy_stage1_v15a.fit_stage1(meshes, frames, motion, reference, policy=None, preserve=False)`: Computes Stage 1 per-part uniform scale, rotation, and chain placement.
- `morph_anatomy_v15c.fit_stage2(stage1, reference, policy=None, preserve=False)`: Computes Stage 2 continuous morphology fitting over Stage 1 standing meshes.
- `morph_anatomy_v15c.geometry_hash(meshes)`: Computes deterministic SHA-256 hash of mesh positions and topology.
- `morph_preview_pose_v13.native_keys_hash(motion)`: Generates SHA-256 digest of source animation controller keys.
- `warp_segments_v12.warp_segments(...)`: Computes differential segment preview before contour fitting.
- `warp_torso_support_v12.warp_torso_support(...)`: Calculates chest/shoulder anchor support fields in source coordinates.

### Seam & Connector Auditing
- `check_connector_surfaces_v15.audit(source, candidate, source_frames, candidate_frames, ...)`: Evaluates source-owned seam surface coverage and penetration diagnostics.
- `check_connector_surfaces_v16.audit(source, candidate, source_frames, candidate_frames, ...)`: Additive v16 connector surface diagnostics (neck, penetration).
- `check_terminal_connectivity_v13.audit(source, fitted, source_frames, fitted_frames, ...)`: Calibrated seam diagnostics and point-triangle distance distributions.
- `check_terminal_connectivity_v13a.audit_minimum(source, candidate, source_frames, candidate_frames, ...)`: Exact terminal minimum segment-to-triangle clearance audits.

### Assembly & Silhouette Measurement
- `silhouette_model.assemble(rig_path, parts)`: Assembles static rigid mesh nodes from ASCII or native model files.
- `silhouette_model.rasterize(meshes, view, metres_per_pixel)`: Renders 2D binary projection masks from 3D triangle meshes.
- `silhouette_model.measure(meshes, joints)`: Calculates exact geometric dimensions from assembled part meshes.
- `silhouette_model.cross_section(meshes, z, axis)`: Computes planar polygon cross-sections at specified height coordinates.
- `measurement_workflow.run_measurement_workflow(...)`: End-to-end extraction of measurement masks and metadata sidecars.

### Scene I/O & Model Conversion
- `phenomorpher_scene_v15b.read_attributes(model_path)`: Reads node hierarchy, source attributes, and bind transforms from model files.
- `phenomorpher_scene_v15b.export_glb(meshes, frames, parents, output)`: Exports diagnostic neutral GLB scenes.
- `phenomorpher_scene_v15b.derived_normals(positions, faces)`: Derives display-only surface normals for neutral diagnostic scenes.
- `convert_model.convert_text(text, source_frames, target_frames, ...)`: Transforms ASCII model node hierarchies between donor and target frames.
- `clothing_core.convert(...)`: Transforms static modular clothing parts onto target body geometries.

### Animation Library & Runtime Release
- `anim_library.extract_stock(resman_cat, game_root, seeds, output)`: Extracts stock supermodel chains from game BIF data.
- `anim_library.inventory(root, manifest_path, stock_manifest)`: Inventories body animation clips, supermodel chains, and stock deltas.
- `anim_library.build(root, manifest_path, stock_manifest, fit, ...)`: Builds shared animation library ASCII and restore plans.
- `anim_library.restore(root, plan_path, compiled_path, output)`: Restores exact source controller and event bytes into compiled libraries.
- `anim_library.repoint(blob, parent)`: Repoints binary model supermodel field.
- `retarget_v2.retarget(...)`: Retargets carrier chains for Fit and Large body variants over stock base chains.
- `runtime_release.adopt(root, plan_path, output)`: Stages runtime-optimized body release files from verified libraries and roots.
- `runtime_rules.check(root, manifest, stock_manifest, max_texture)`: Validates Phase 9 runtime layout rules (stock termination, carrier uniqueness, texture limits).
- `texture_downsample.downsample(root, manifest_path, output, max_size)`: Downsamples palettes and normal maps by 2:1 area reduction.
- `stock_armor.extract(...)`, `stock_armor.fit_profiles(...)`, `stock_armor.convert(...)`, `stock_armor.publish(...)`, `stock_armor.verify_pack(...)`: Stock armor extraction, calibration, conversion, and packaging.
- `body_sweep.sweep(root, manifest_path, output, ...)`: Read-only check sweep over published bodies verifying geometry, measurements, and connectors.
- `target_contract.load(path, verify_inputs)` / `validate(data)`: Validates and loads hash-pinned phenotype target contracts.

## Invariants
- `[__init__.py]` **Internal Scope**: Engine modules are private implementation details; external callers must consume functionality via `phenomorpher.api` or CLI commands.
- `[fit_anatomy_stage1_v15a.py:fit_stage1]`, `[morph_anatomy_v15c.py:fit_stage2]` **Input Immutability**: Fitting functions never mutate input mesh or frame dictionaries in-place (explicit deep copies are made); Human Fit donor inputs (`human_male_fit`, `human_female_fit`) preserve identity without morph distortion.
- `[morph_preview_pose_v13.py:native_keys_hash]` **Motion Key Preservation**: Source animation keys must remain unchanged across morphing operations; verified by strict SHA-256 controller key hashing.
- `[check_connector_surfaces_v15.py]`, `[check_connector_surfaces_v16.py]` **Connector Taper Rule**: Connector surfaces must transition continuously without visible shelves, lip ledges, or cuff discontinuities; numerical clearance does not constitute anatomy approval.
- `[runtime_rules.py:check]` **Phase 9 Runtime Rules**: Carrier chains must terminate on stock supermodels, no private carriers are permitted in published contracts, and textures/palettes must not exceed 1024px.
- `[silhouette_model.py:assemble]` **Static Geometry Only**: Only static rigid meshes and hierarchies are supported; weighted or animated skin meshes are rejected explicitly.
- `[stock_armor.py]`, `[armory_rigid.py]` **Coordinate System**: All model calculations use NWN metric units (meters, +Z up, +Y front).

## Side Effects
- `[phenomorpher_scene_v15b.py:export_glb]` Writes binary `.glb` scene diagnostics to disk.
- `[anim_library.py:extract_stock]`, `[anim_library.py:build]`, `[anim_library.py:restore]` Writes extracted stock models, animation library text files, restore plans, and compiled model outputs to disk.
- `[runtime_release.py:adopt]` Stages files into destination runtime release directories.
- `[texture_downsample.py:downsample]` Reads and writes downsampled `.plt`, `.tga` textures and normal maps to disk.
- `[stock_armor.py:extract]`, `[stock_armor.py:convert]`, `[stock_armor.py:publish]` Extracts stock models, writes converted armor models, receipts, and published pack resources to disk.
- `[build_silhouette_comparison_sheet.py]` Generates comparison image sheets to disk.
- `[stock_armor.py:resman_extract]`, `[stock_armor.py:convert]`, `[anim_library.py:extract_stock]` Spawns external extractor tools (`resman_cat`), model decompilers, and NWNArmory binaries via subprocess.

## Verification
- Run: `pytest tools/phenomorpher`
