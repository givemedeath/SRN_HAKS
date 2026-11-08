# Head Generation & Production Toolkit (`tools/heads`)

## Overview
The `tools/heads` package provides the production pipeline, numerical fitting, neck closure audits, and native asset export toolchain for Neverwinter Nights character heads. It orchestrates a 200-head production roster across five races (Human, Elf, Dwarf, Orc, Troll) and both sexes through seven sequential acceptance gates (`reference`, `donor`, `fitting`, `assembly`, `native`, `client`, `acceptance`).

The toolchain enforces strict immutable event ledgers, input SHA-256 hash pinning, and mutual-exclusion file locks to regulate paid Meshy AI requests (`multi-image-to-3d`, `remesh`, `retexture`) against hard credit caps. It includes geometry fitting using landmark-based positive similarity transforms, neck rim correction, boundary loop capping, continuous neck taper audits without visible shelves, 1024x1024 PLT/PBR material conversions, rigid MDL export, HAK packaging, and automated in-engine test fixture generation.

## Interface
- `[head_workflow.py:Session]`: Production session manager tracking immutable hash-linked events, spending locks, review gates, and packaging. Key methods:
  - `Session.create(directory, roster, budget=300)`
  - `Session.spending_root()`
  - `Session.spending_lock()`
  - `Session.spending_owner(path)`
  - `Session.adopt_spending(proof_file)`
  - `Session.lock()`
  - `Session.events()`
  - `Session.append(kind, **fields)`
  - `Session.design(identity)`
  - `Session.allocate(roster_file, audit_file)`
  - `Session.reviews(identity)`
  - `Session.fork_revision(directory, identities, from_stage, inputs, *, credit_cap=None, budget_approval=None)`
  - `Session.credit_used()`
  - `Session.reserve(identity, request_id, operation, estimated_credits, inputs, payload)`
  - `Session.record_task(request_id, task_id, resource, result_file, *, launch_problem=None)`
  - `Session.settle(request_id, status, credits, result_file)`
  - `Session.reconcile_rejection(request_id, result_file, history_file)`
  - `Session.review(identity, stage, report_file)`
  - `Session.verify_review_chain(identity, through)`
  - `Session.publication(identities, *, slot_audit=None, repository=None)`
  - `Session.publish(identities, output, *, slot_audit=None, repository=None)`
- `[head_workflow.py:make_roster]`: Generates the canonical 200-head roster specification across 5 races and 2 sexes.
- `[head_workflow.py:validate_roster]`: Validates a roster schema against expected `schemaVersion: 1` and unique identities.
- `[head_workflow.py:model_name]`: Formats native 16-character model identifiers (`{prefix}_{slot:03d}`).
- `[head_workflow.py:allocate_slots]`: Allocates contiguous slot blocks per race/sex appearance category.
- `[head_workflow.py:validate_target]`: Validates target body cranial envelope, neck geometry, and pinned dependencies.
- `[head_workflow.py:fit_similarity]`: Computes positive uniform scaling similarity matrix from source and destination landmarks.
- `[head_workflow.py:verify_package_payload]`: Verifies HAK archive contents against publication resource hashes.
- `[audit_slots.py:audit]`: Audits game installation and repository HAK files to allocate safe, contiguous head slots.
- `[audit_slots.py:verify_publication_inventory]`: Verifies published resources do not collide with existing inventory.
- `[audit_fixture_rig.py:audit]`: Validates parent-first fixture rig hierarchy and node bind transforms.
- `[audit_native_head.py:audit]`: Verifies compiled native MDL binary geometry, normals, UVs, and material byte transport.
- `[audit_neck_closure.py:audit]`: Verifies neck openings are completely closed with 0 boundary edges.
- `[audit_neck_connector.py:audit]`: Validates lowered neck cap position against stock neck convex envelope.
- `[audit_neck_revision.py:audit]`: Ensures new neck revisions preserve existing textured upper skull surfaces.
- `[bind_target.py:bind]`: Resolves target body parameters into local machine runtime bindings.
- `[build_head_fixture.py:build]`: Compiles single-head test fixture modules and HAK archives.
- `[build_head_trial.py:build]`: Compiles multi-head trial HAKs and test module with automated spawn scripts.
- `[cap_head_holes.py:cap]`: Detects boundary loops and adds closed caps without moving donor vertices.
- `[client_capture_review.py:check_captures]`: Verifies client game screenshot and log coverage.
- `[collect_fixture_inputs.py:collect]`: Extracts stock creature templates and floor tiles for isolated fixtures.
- `[collect_head_family.py:collect]`: Extracts stock head models and textures for target race/sex prefixes.
- `[correct_neck_rim.py:correct]`: Trims neck geometry, smooths normals, and generates tapered caps.
- `[export_review_evidence.py:export]`: Packages offline review artifacts with portable SHA-256 hashes.
- `[finalize_head_migration.py:finalize]`: Verifies isolated Python/Blender environment migrations.
- `[fit_head.py:fit]`: Executes landmark similarity fitting against target cranial frames.
- `[head_export.py:export]`: Exports glTF/GLB models to ASCII NWN MDL, binary PLT palettes, and MTR materials.
- `[import_derived_body.py:import_body]`: Imports receipt-pinned derived racial bodies into isolated local storage.
- `[inspect_head.py:inspect]`: Performs read-only geometry inspection and boundary analysis.
- `[make_review_sheet.py:compose]`: Composes multi-view turntable frames into review contact sheets.
- `[meshy_cli.py:dispatch]`: Dispatches credit-reserved Meshy API tasks via local CLI adapter.
- `[meshy_cli.py:wait]`: Polls task status until terminal completion.
- `[meshy_cli.py:collect]`: Downloads and verifies task result assets and consumed credits.
- `[meshy_cli.py:reconcile_rejection]`: Releases reservation on validated API 400 rejection proofs.
- `[native_reader.py:decode]`: Re-exported native MDL decoder function from `headkit.native_reader`.
- `[prepare_assembly.py:prepare]`: Compiles clay assembly scenes combining body, neck, and head.
- `[prepare_derived_target.py:prepare]`: Proposes target contracts for derived racial bodies.
- `[prepare_fixture_rig.py:prepare]`: Prepares rig hierarchy serialization for fixtures.
- `[prepare_human_target.py:prepare]`: Extracts and measures Human male stock neck and head frames.
- `[prepare_materials.py:prepare]`: Resizes 2K PBR source maps into 1024 runtime textures and semantic masks.
- `[prepare_meshy_input.py]`: Decimates oversized masters below 50MB Meshy upload limits without altering neck geometry.
- `[prepare_palette_assembly.py:prepare]`: Generates offline head/neck PLT color comparison atlases.
- `[prepare_runtime_head.py]`: Decimates donor meshes to runtime budget while preserving UVs and normals.
- `[prepare_runtime_lod.py]`: Reconstructs voxel surfaces and bakes normal maps for skull LODs.
- `[prepare_stock_head_control.py:prepare]`: Builds stock comparator models.
- `[propose_landmarks.py:propose]`: Proposes anatomical reference landmarks along principal axes.
- `[propose_material_masks.py:propose]`: Computes skin/hair microface masks and palette row selections.
- `[publish_head_pack.py:publish]`: Stages verified assets and updates head pack manifests.
- `[reindex_head.py:rename_native]`: In-place binary renaming of model and texture node references in MDL/PLT files.
- `[render_assembly.py:mesh]`: Blender script rendering assembled clay turnaround scenes.
- `[render_donor.py]`: Blender turntable script rendering 12-angle 512x512 clay frames with fixed 4 threads.
- `[retopologize_head.py]`: Blender voxel remeshing and smart-project UV generation.
- `[smoke_head_tools.py]`: Dependency smoke test verifying numpy, pillow, and similarity fitting.
- `[verify_head_hak.py:verify]`: Verifies rebuilt HAK archive byte payloads against publication manifests.
- `[verify_head_trial.py:check]`: Analyzes client game logs to confirm head spawning and palette rows.
- `[verify_retexture.py:verify]`: Validates that retextured models preserve original vertices and UV coordinates.
- `[verify_texture_transfer.py:verify]`: Validates texture atlas transfers when topology or vertex counts shift.
- `[roster.json]`: Canonical 200-head roster specification conforming to `srn-head-roster` (`schemaVersion: 1`).
- `[target-template.json]`: Target template specification conforming to `srn-head-target-template` (`schemaVersion: 1`).

## Invariants
- `[head_workflow.py:STAGES]`: Review progression strictly follows seven sequential stages: `reference` -> `donor` -> `fitting` -> `assembly` -> `native` -> `client` -> `acceptance`. No stage can be skipped or selected out of order.
- `[head_workflow.py:MAX_TRIANGLES]`: Total runtime head and accessory budget capped at 20,000 triangles (`MAX_TRIANGLES = 20000`).
- `[head_workflow.py:TEXTURE_SIZE]`: Runtime texture resolution strictly enforced at 1024x1024 (`TEXTURE_SIZE = 1024`).
- `[head_workflow.py:fit_similarity]`: Similarity transform must enforce positive uniform scaling (`scale > 0`) and proper rotation with determinant `det(rotation) > 0` (reflections rejected); requires $\ge 4$ non-coplanar corresponding landmarks.
- `[head_workflow.py:Session.spending_lock]`: File-based mutual exclusion lock (`spending.lock` and `operation.lock`) prevents concurrent modifications, duplicate requests, or race conditions during credit reservation and event logging.
- `[head_workflow.py:Session.reserve]`: Enforces operation pricing (`COSTS`), available credit headroom under `creditCap` (default 300), and limits `multi-image-to-3d` to at most two attempts per design.
- `[head_workflow.py:verify_pins]`: Consumed input files must match declared SHA-256 hashes prior to processing; any change aborts execution.
- `[audit_slots.py:audit]`: Head appearance slots must be allocated from audited lowest contiguous unassigned blocks across installed game and repository packs, bounded by engine byte limits (`0 <= slot <= 255`).
- `[audit_neck_closure.py:audit]`: Neck cuts must have 0 open boundary edges and 0 uncapped closed loops (`neckCutBoundaryEdges == 0`, `uncappedClosedNeckLoops == 0`).
- `[audit_neck_connector.py:audit]`: Lowered neck caps must remain fully enclosed within the stock neck convex hull (`capInsideStockNeckConvexEnvelope is True`) without visible shelves or ledge steps.
- `[render_donor.py:scene.render.threads]`, `[render_assembly.py]`: Blender preview rendering must be capped at 4 fixed threads (`threads = 4`).
- `[reindex_head.py:rename_native]`: Resource and node names in native binary MDL/PLT files must not exceed 16 characters.

## Side Effects
- `[head_workflow.py:Session.append]`: Appends atomic, hash-linked JSON records to `events/{index:06d}.json`.
- `[head_workflow.py:Session.lock]`: Creates and removes `operation.lock` and `spending.lock` file descriptors in the session root.
- `[meshy_cli.py:run_cli]`: Dispatches authenticated HTTP requests to the external Meshy AI service and consumes account credits.
- `[head_export.py:export]`: Writes ASCII NWN model files (`.mdl`), binary palette files (`.plt`), and material definitions (`.mtr`) to the filesystem.
- `[build_head_fixture.py:build]`, `[build_head_trial.py:build]`: Compiles and writes NWN HAK archives (`.hak`), compiled scripts (`.ncs`), and module files (`.mod`).
- `[render_donor.py]`, `[render_assembly.py]`: Executes background Blender processes writing rendered PNG turntable frames to output directories.
- `[publish_head_pack.py:publish]`: Copies verified assets to destination pack directories and writes publication manifests (`manifest.json`).

## Verification
- Run: `pytest tools/heads`
