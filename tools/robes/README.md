# Robes Component Package

## Overview
The `tools/robes` package provides the end-to-end pipeline, kinematics mathematics, Blender automation drivers, and isolated testing fixtures for importing, repairing, fitting, skinning, packaging, and auditing Neverwinter Nights (NWN) robe models. It bridges external generative 3D meshes (e.g., Meshy A-pose exports) and stock game assets to engine-compliant ASCII models (`#MAXMODEL ASCII`), isolated trial HAK fixtures, and runtime packages.

The subsystem enforces strict asset integrity through cryptographic pinning, reproducible non-destructive staging, and decoupled validation gates (ensuring automated tools never grant visual, native, client, or production approvals).

## Interface

### Core Model & Table Formats
- [`mdl_ascii.py`](./mdl_ascii.py): Skin-aware ASCII NWN model reader and writer.
  - `Model`: In-memory model hierarchy, classification, header, nodes, and animation blocks.
  - `Node`: Model nodes (trimesh, skin, dummy, danglymesh) with transformation matrices, scalar properties, and geometry arrays.
  - `read(path)` / `write(path, model)`: Reads and writes ASCII `.mdl` files.
  - `parse(text)` / `dumps(model)`: Parses and serializes model text conforming to `#MAXMODEL ASCII`.
  - `skin_matrix(node)`: Extracts skin weights matrix and bone name list from a skin node.
  - `bind_frames(model)`: Computes world-space bind pose transformation frames.
- [`parts_robe.py`](./parts_robe.py): `parts_robe.2da` reader, column definitions, and position-true writer.
  - `read_2da(path)`: Reads CP1252-encoded `parts_robe.2da` into column headers and row dictionaries.
  - `write_2da(path, columns, rows)`: Position-true writer for `parts_robe.2da` with `2DA V2.0` header and gap padding (`****`).
  - `HIDE`: Tuple of stock body part hide column names (`HIDEFOOTR`, ..., `HIDEHEAD`).

### Kinematics, Skinning & Geometry Mathematics
- [`lbs.py`](./lbs.py): Offline linear-blend skinning of NWN skin nodes over stock animation clips.
  - `Rig`: NWN bone hierarchy and rest matrices for linear-blend skinning.
  - `skin(rig, node, frames, weights, bones)`: Deforms skin vertices using linear combination of bone transformation matrices.
  - `bind_world(rig, node)`: Computes bind-world transformation matrices.
  - `rigid(rig, node, frames)`: Poses rigid body parts with bone transformation frames.
  - `motion_samples(anim_text, fps)`: Generates animated transformation frames from raw animation clips.
  - `chain_for(node)`: Resolves ancestor bone chain to model root.
- [`robe_weights.py`](./robe_weights.py): Skin-weight limiting, normalization, and validation for NWN skin nodes.
  - `limit_and_normalize(weights, max_weights, threshold)`: Prunes low-influence skin weights, enforces maximum bone influences per vertex (default 4), and normalizes weights to sum to 1.0.
  - `validate(weights, bones, max_weights)`: Validates bone count, weight bounds, and normalization constraints.
  - `from_pairs(pairs, bone_index)` / `to_pairs(weights, bones)`: Converts between sparse bone-weight pairs and dense weight matrices.
  - `limb_corrections(weights, bones)`: Corrects cross-limb weight bleeding.
- [`mesh_ops.py`](./mesh_ops.py): Pure-numpy mesh connectivity helpers.
  - `weld_ids(verts, tolerance)`: Identifies coincident vertices within a distance tolerance.
  - `islands(faces)`: Partitions connected faces into disjoint topological mesh islands.
  - `edges(faces)`: Extracts directed and boundary mesh edges.
  - `slice_loops(faces, plane_origin, plane_normal)`: Slices mesh faces along clipping planes to produce boundary contour loops.
  - `neighbours(faces)`: Computes vertex adjacency lists.
  - `geodesic_labels(faces, seeds)`: Computes flood-fill geodesic distances from seed vertices.
  - `smooth_field(field, neighbours, iterations)`: Applies Laplacian smoothing across scalar fields on meshes.
  - `union_find(size)`: Disjoint-set data structure for topological clustering.
- [`fit_math.py`](./fit_math.py): Pure-numpy outfit fitting, landmark alignment, and lattice clearance.
  - `similarity(source_points, target_points)` / `apply_similarity(points, transform)`: Computes and applies Procrustes similarity transformation.
  - `outfit_landmarks(verts)` / `stock_targets(phenotype)`: Extracts key anatomical landmarks (neck, shoulders, chest, waist, hips, knees, ankles).
  - `proxy_transforms(outfit_joints, stock_joints)` / `proxy_weights(verts, joints)`: Calculates proxy rig transformations and weights for pose retargeting.
  - `lattice_inflate(verts, clearance, lattice_bounds)`: Non-linear lattice volume expansion ensuring clearance over body geometry.
  - `pose_weighted(verts, weights, transforms)` / `blend_dual_quaternion(transforms, weights)`: Poses vertices using dual quaternion or matrix blending.
  - `visible_parts(hide_flags)`: Resolves visible stock body parts given 2DA hide flags.
- [`stock_body.py`](./stock_body.py): Stock phenotype body reference models, landmarks, and chains.
  - `Body`: Loads rigid phenotype body parts (`pmh0` / `pfh0`), mounts parts onto bone transforms, and provides bounding volume checks.
  - `closest_on_triangles(points, tri_verts)`: Vectorized projection finding closest surface points and distances to triangle meshes.
- [`apose_skeleton.py`](./apose_skeleton.py): Rest skeleton generation.
  - `generation_rest(model)`: Generates bone transformation frames matching an A-pose generative outfit.

### Blender Automation Drivers
- [`blender_io.py`](./blender_io.py): Shared Blender import and color sampling helpers (`import_single`, `base_color_image`, `face_colours`).
- [`repair_source.py`](./repair_source.py): Automatic mesh defect repair in Blender (`weld`, `triangles`, `remove_duplicates`, `remove_floating`).
- [`fit_outfit.py`](./fit_outfit.py): Blender driver fitting generative outfits onto phenotype bind poses (`outer_visibility`, `describe`, `main`).
- [`transfer_weights.py`](./transfer_weights.py): Region-restricted skin weight transfer from stock donor robes (`Donor`, `robe_donor_faces`, `cage_part`, `skin_mask`, `main`).
- [`reduce_runtime.py`](./reduce_runtime.py): Decimates weighted outfits to runtime polycount budgets while preserving weights and seams (`build`, `weld`, `decimate`, `read_back`, `main`).
- [`render_review.py`](./render_review.py): Batch renders orthographic review views (front, side, rear) under standardized lighting (`clear`, `material`, `from_arrays`, `entry_sources`, `load`, `lights`, `main`).
- [`blender_roundtrip.py`](./blender_roundtrip.py): Neverblender ASCII model import/export roundtrip validation tool (`clear`, `summary`, `load`, `main`).

### Model Assembly, Fixtures & Packaging
- [`build_robe_model.py`](./build_robe_model.py): Assembles final ASCII robe model from stock bind skeleton and regional skin nodes (`skeleton_nodes`, `node_for_faces`, `axis_angle`, `face_groups`, `generation_rest`, `main`).
- [`build_robe_fixture.py`](./build_robe_fixture.py): Compiles isolated trial HAKs, test UTI items, `parts_robe.2da` rows, and comparison test modules (`field`, `structure`, `stock_hide`, `renamed_model`, `scripts`, `main`).
- [`package_trial.py`](./package_trial.py): Packages trial assets into self-describing standalone distribution folders (`validated_matches`, `row_line`, `row_visibility`, `readme`, `main`).
- [`robe_node_variant.py`](./robe_node_variant.py): Generates structural model variants for client parser testing (`as_kind`, `variant`, `main`).

### Quality Assurance, Comparison & Review
- [`compare_skin_models.py`](./compare_skin_models.py): Structural, attribute, weight, and deformation model diffing (`compare_mesh`, `reverse_weight_error`, `reference_coverage`, `verdict`, `dense_nearest`, `neighbour_lists`, `smoothing_edges`, `corners`, `compare`, `animation_content`, `main`).
- [`deformation_review.py`](./deformation_review.py): Samples skin deformation over the animation motion matrix, evaluating stretch, compression, and body penetration (`measures`, `penetration`, `skin_nodes`, `pose`, `areas`, `merged`, `donor_cache_key`, `donor_baseline`, `main`).
- [`contact_sheet.py`](./contact_sheet.py): Assembles orthographic review renders into labeled contact sheet PNGs with hash receipts (`main`).
- [`freeze_tolerances.py`](./freeze_tolerances.py): Freezes export tolerances based on measured stock control round-trips (`invariant_changes`, `measure`, `main`).

### Ingestion, Stock Extraction & Materials
- [`meshy_robe.py`](./meshy_robe.py): Reservation-first Meshy CLI adapter and credit session manager (`Session`, `validate_request`, `dispatch`, `wait`, `collect`, `load_binding`, `invoke`, `model_formats`, `task_fields`, `main`).
- [`prepare_reference.py`](./prepare_reference.py): Reference artwork cleaning and conditioning (`content_rows`, `subject_block`, `subject_bottom`, `main`).
- [`prepare_robe_materials.py`](./prepare_robe_materials.py): PBR material conversion to NWN fixed-color materials and skin-only PLT textures (`plt_bytes`, `tga`, `main`).
- [`extract_stock_robes.py`](./extract_stock_robes.py): Extracts stock robe assets and rig hierarchy from game data (`Extractor`, `main`).
- [`inventory_stock_robes.py`](./inventory_stock_robes.py): Analyzes stock robes and classifies garment donor classes (`landmarks`, `classify`, `skin_report`, `main`).

### Pipeline Execution & Client Verification
- [`robe_common.py`](./robe_common.py): Shared cryptographic pinning, fresh file operations, and validation flags (`pin`, `read_pinned`, `verify_pins`, `merge_pins`, `write_fresh`, `fresh_directory`, `require`, `sha`, `read`, `skin_colour`, `utc`, `FLAGS`).
- [`run_robe_migration.py`](./run_robe_migration.py) / [`finalize_robe_migration.py`](./finalize_robe_migration.py): Executes and finalizes migration smokes (`launch`, `finalize`, `main`).
- [`smoke_robe_tools.py`](./smoke_robe_tools.py): Bundled-Python dependency and weight math smoke test.
- [`Launch-RobeTrialClient.ps1`](./Launch-RobeTrialClient.ps1): Launches the NWN client for trial module testing, verifying pins before and after execution (`Get-TaskPin`, `Test-TaskPins`).

### Subdirectories
- `configurations/`: Contains JSON configuration schemas, allocation registers, fixture definitions, and package specifications for robe tests and trials.

## Invariants
- **Approval Gate Boundaries** ([`robe_common.py:FLAGS`](./robe_common.py)): Automated tool receipts explicitly record all review status flags (`referenceApproved`, `nativeValidated`, `clientValidated`, `productionAccepted`, `gameClientTesting`) as `False`. Automation never constitutes visual, native, client, or production approval.
- **Client Evidence Separation** ([`Launch-RobeTrialClient.ps1`](./Launch-RobeTrialClient.ps1)): Launching a client test session records launch telemetry only; client evidence strictly requires observed screenshots and logged actor rows.
- **Freshness & Non-Destructive Writes** ([`robe_common.py:write_fresh`](./robe_common.py), [`robe_common.py:fresh_directory`](./robe_common.py)): Output files and staging directories must be created fresh (using `'x'` file open mode) to prevent silent overwriting of previous artifacts or evidence.
- **Cryptographic Input Pinning** ([`robe_common.py:verify_pins`](./robe_common.py), [`Launch-RobeTrialClient.ps1`](./Launch-RobeTrialClient.ps1)): All input files are pinned by their SHA-256 digests. Multi-step operations and client sessions verify pins before and after execution; any modification aborts the task immediately.
- **Positional 2DA Indexing** ([`parts_robe.py:write_2da`](./parts_robe.py)): The NWN engine resolves rows in `parts_robe.2da` by zero-based position rather than line label. Gaps between row IDs must be padded with `****` lines to prevent row index shifts.
- **Skin Weight Constraints** ([`robe_weights.py:limit_and_normalize`](./robe_weights.py)): Skin vertices must not exceed the maximum allowed bone influences (typically 4), low-influence weights below threshold are pruned, and bone weights per vertex must sum strictly to 1.0.
- **Model Hierarchy Conformance** ([`mdl_ascii.py:parse`](./mdl_ascii.py), [`build_robe_model.py:main`](./build_robe_model.py)): Models must parse and emit valid `#MAXMODEL ASCII` format, maintaining correct node hierarchy, geometry array counts, and cyclic triangle face windings.
- **Generative API Guardrails** ([`meshy_robe.py:validate_request`](./meshy_robe.py)): Paid Meshy requests must reserve credits against an explicit ceiling before dispatch, limit concurrent paid tasks to one, require recorded reference approval, enforce textured 4K PBR in A-pose, require GLB output, restrict remesh polycounts to <= 100,000 triangular faces, and maintain UV preservation on retexturing.
- **Test Fixture Isolation** ([`build_robe_fixture.py:main`](./build_robe_fixture.py)): Robe trial HAKs, 2DA rows, and test modules are created exclusively inside isolated staging and client user directories; they must never modify repository packs, `srn_2da`, or `hakbuilder.json`.
- **Client Execution Preconditions** ([`Launch-RobeTrialClient.ps1`](./Launch-RobeTrialClient.ps1)): Client trial launches verify that the test user directory's `override/` directory is empty and abort if an active `nwmain` process is already running.

## Side Effects
- **File System Creation & Modification**:
  - Reads and writes ASCII `.mdl` models, `parts_robe.2da` tables, UTI items, ERF/HAK archives, and NWN modules (`.mod`) ([`mdl_ascii.py`](./mdl_ascii.py), [`parts_robe.py`](./parts_robe.py), [`build_robe_fixture.py`](./build_robe_fixture.py), [`package_trial.py`](./package_trial.py)).
  - Reads and writes PNG, TGA, and binary PLT image and texture files via Pillow ([`prepare_robe_materials.py`](./prepare_robe_materials.py), [`prepare_reference.py`](./prepare_reference.py), [`contact_sheet.py`](./contact_sheet.py)).
  - Writes atomic JSON receipts, SHA-256 pin manifests, comparison reports, and deformation metric summaries ([`robe_common.py:write_fresh`](./robe_common.py), [`compare_skin_models.py`](./compare_skin_models.py), [`deformation_review.py`](./deformation_review.py)).
- **External Subprocess Execution**:
  - Spawns headless Blender instances (`bpy`, `bmesh`, `mathutils`) for automated geometry cleaning, bind-pose fitting, weight transfer, decimation, and orthographic rendering ([`fit_outfit.py`](./fit_outfit.py), [`repair_source.py`](./repair_source.py), [`transfer_weights.py`](./transfer_weights.py), [`reduce_runtime.py`](./reduce_runtime.py), [`render_review.py`](./render_review.py)).
  - Spawns the Neverwinter Nights game client executable (`nwmain.exe`) with isolated user arguments ([`Launch-RobeTrialClient.ps1`](./Launch-RobeTrialClient.ps1)).
- **Network Requests**:
  - Makes outbound HTTPS requests to the Meshy REST API to submit generation, remesh, and retexture tasks, and downloads generated 3D assets and textures ([`meshy_robe.py`](./meshy_robe.py)).
- **Blender Scene Graph State Changes**:
  - Modifies Blender scene nodes, creates materials, binds vertex groups, alters BMesh geometry, and positions cameras and lights during headless runs ([`blender_io.py`](./blender_io.py), [`repair_source.py`](./repair_source.py), [`render_review.py`](./render_review.py)).

## Verification
- Run: `pytest tools/robes` (or `python -m unittest discover tools/robes`)
