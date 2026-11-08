# PhenoMorpher Engine

## Overview
`phenomorpher.engine` provides internal numerical backends and algorithms for anatomy deformation, silhouette and cross-sectional measurement, connector continuity and penetration audits, animation library extraction and restoration, Neverblender MDL compilation and decompilation, runtime rule validation, and stock armor conversion. These internal modules underpin the stable entry points exposed by `phenomorpher.api` and `phenomorpher.cli`.

## Interface
- **Anatomy & Morphology**:
  - `[fit_anatomy_stage1_v15a.py:fit_stage1]`: Solves Stage 1 similarity scaling, axial chain placement, and bilateral positioning across body part meshes.
  - `[morph_anatomy_v15c.py:fit_stage2]`: Computes Stage 2 non-rigid broad morphology deformation pass while preserving frozen Stage 1 geometry.
  - `[morph_anatomy_v15c.py:geometry_hash]`: Computes deterministic SHA-256 hash of vertex positions across mesh structures.
  - `[morph_preview_pose_v13.py:native_keys_hash]`: Computes deterministic hash of native animation keyframe data.
  - `[anatomy_policy_v15.py:measurement_policy]`: Defines tolerance envelopes and policy constraints for target morphology fitting.
  - `[fit_scale_position_v13a.py:fit_stage1]`: Solves per-segment rigid transforms and joint contact constraints.
  - `[morph_coupled_v12d.py:fit_stage2]`: Solves coupled morphology deformations and reconciles joint seam transitions.
  - `[warp_segments_v12.py:warp_segments]`: Applies segment-specific geometric warping transformations.
  - `[warp_torso_support_v12.py:warp_torso_support]`: Smoothstep kernel torso transition deformation solver.
- **Connectors & Surface Audits**:
  - `[check_connector_surfaces_v15.py:audit]`: Quadrature-based connector surface evaluation for slope continuity, penetration, and shelf detection.
  - `[check_connector_surfaces_v16.py:audit]`: Validates connector seam point continuity, directional coverage, and overlap gates across body segments.
  - `[check_terminal_connectivity_v13c.py:audit_minimum]`: Measures minimum distance distributions between terminal part boundaries.
  - `[runtime_rules.py:check]`: Audits release contracts against runtime rules (unkeyed roots at origin, stock-terminated chains, texture caps).
- **Measurement & Silhouette**:
  - `[silhouette_model.py:assemble]`: Assembles individual part meshes into a unified static bind-pose character model.
  - `[silhouette_model.py:rasterize]`: Renders 2 mm/px orthographic silhouette binary masks (front, back, left, right).
  - `[silhouette_model.py:measure]`: Extracts exact geometric measurements, segment lengths, and bounding extents.
  - `[silhouette_model.py:cross_section]`: Computes planar polygon cross-sections and contour perimeters.
  - `[nwn_part_measurements.py:model_parts]`: Standard NWN part decomposition partitions and hierarchy keys.
- **Animation & Rigging**:
  - `[anim_library.py:build]`: Compiles intermediate animation libraries and generates clip restoration plans.
  - `[anim_library.py:restore]`: Restores compiled animation controllers byte-for-byte from source carriers.
  - `[anim_library.py:repoint]`: Rewrites supermodel references in native model headers.
  - `[anim_library.py:extract_stock]`: Extracts stock animation models from game archives using pinned extractors.
  - `[motion_baseline_v2.py:load]`: Loads and validates native motion baseline clips and bone channels.
  - `[motion_compare.py:compare]`: Compares motion clips against stock baselines, computing drift and inheritance status.
  - `[native_motion.py:Reader]`: Reads and samples native binary MDL animation streams.
  - `[retarget_v2.py:retarget]`: Carrier chain retargeting pipeline for Fit and Large phenotypes over stock animation roots.
  - `[rig_native.py:compare_static]`: Validates static bone hierarchy, node types, and bind transforms between models.
  - `[root_rebase.py:apply]`: Folds root node position offsets into child bone controllers with zero net world transform delta.
- **Model Compilation & Assets**:
  - `[neverblender_mdl.py:compile_folders]`: Headless Blender and Neverblender batch compilation of ASCII models to binary MDL format.
  - `[neverblender_mdl.py:audit]`: Audits compiled binary MDL models against source ASCII definitions.
  - `[neverblender_worker.py:compile_job]`: Headless worker process compilation routine.
  - `[neverblender_worker.py:decompile_job]`: Headless worker process decompilation routine.
  - `[phenomorpher_scene_v15b.py:read_attributes]`: Extracts authored texture coordinates, materials, and source node attributes.
  - `[phenomorpher_scene_v15b.py:export_glb]`: Exports rest and deformed geometries into neutral diagnostic GLB scenes.
  - `[phenomorpher_scene_v15b.py:derived_normals]`: Calculates face-weighted vertex normals for preview rendering.
  - `[convert_model.py:convert_text]`: Parses and transforms ASCII MDL definitions.
  - `[texture_downsample.py:reduce_plt]`: 2:1 downsampling for indexed palette PLT textures.
  - `[texture_downsample.py:reduce_normal]`: 2:1 downsampling for normal/bump map rasters.
  - `[stock_armor.py:extract]`: Extracts stock armor assets from game key/BIF archives.
  - `[stock_armor.py:batch_convert]`: Batch fits armor parts onto target body phenotypes.
  - `[runtime_release.py:adopt]`: Stages release pack assets and generates adopted contract manifests.

## Invariants
- `[morph_anatomy_v15c.py:fit_stage2]`: Morphing must not mutate its frozen Stage 1 input geometry or source meshes (`geometry_hash(first['standingMeshes']) == frozen` and `geometry_hash(meshes) == before`).
- `[fit_anatomy_stage1_v15a.py:fit_stage1]`: Native animation keys must remain unchanged; Human Fit controls (`human_male_fit`, `human_female_fit`) automatically follow the exact identity transform path (`preserve=identity`).
- `[check_connector_surfaces_v15.py:audit]`: Connector tapers must maintain a continuous sloped transition without visible shelves, cuff ledges, or pinches across joint boundaries.
- `[check_connector_surfaces_v16.py:audit]`: Seam points must maintain continuity across neighboring part boundaries within configured epsilon tolerances.
- `[runtime_rules.py:check]`: Staged model roots must reside at the origin with zero rotation, scale, or animation keying; private carriers are forbidden; all animation chains must terminate in stock roots; texture dimensions must not exceed 1024 px.
- `[root_rebase.py:apply]`: Root offset folding into child controllers must produce zero bind or clip world-frame changes above 1e-6 numerical tolerance.
- `[neverblender_mdl.py:audit]`: Compiled binary models must decode cleanly and match source ASCII hierarchies, node counts, and static transforms.
- `[clothing_core.py:require]`: Garment mesh parts must preserve authored topology, UV coordinates, and tangent signs; animated, weighted, or cyclic conversions are rejected.

## Side Effects
- `[neverblender_mdl.py:compile_folder]`: Spawns headless Blender subprocesses (`--background --factory-startup --offline-mode`) to compile models.
- `[neverblender_worker.py:compile_job,decompile_job]`: Reads and writes compiled `.mdl` binaries, ASCII `.mdl` files, and receipt `.json` manifests on disk.
- `[runtime_release.py:adopt]`: Stages release pack files and writes contract metadata to disk.
- `[texture_downsample.py:reduce_plt,reduce_normal]`: Writes 2:1 downsampled `.plt`, `.tga`, and texture images to disk.
- `[stock_armor.py:extract,publish]`: Invokes `resman_extract` and writes extracted stock assets and compiled armor pack files to disk.
- `[phenomorpher_scene_v15b.py:export_glb]`: Writes binary diagnostic GLB documents to disk.

## Verification
- Run: `pytest tools/phenomorpher`
