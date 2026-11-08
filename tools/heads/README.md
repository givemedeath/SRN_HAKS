# Head Production & Fixture Tools

## Overview
The `tools/heads` component package provides an end-to-end tooling pipeline for Neverwinter Nights (NWN) rigid character head creation, anatomical fitting, mesh retopology, neck connector compliance, material generation, and game client fixture generation. It integrates external generative workflows (such as Meshy 3D API) through explicit reservation and accounting gates, enforces geometric envelope constraints (including NWN neck connection envelopes and triangle budgets), generates native Aurora engine assets (ASCII MDL and PLT palette textures), and verifies published HAK archives and game test fixtures.

## Interface
- `[head_workflow.py:Session]`: State machine managing multi-stage head revisions, credit reservations, task tracking, and audit chains.
- `[head_workflow.py:MAX_TRIANGLES]`: Global polycount cap constant (20,000 triangles) for runtime heads.
- `[head_workflow.py:TEXTURE_SIZE]`: Runtime texture resolution constant (1024x1024).
- `[head_workflow.py:RACES]`: Supported race prefix mapping dictionary (`human: h`, `elf: e`, `dwarf: d`, `orc: o`, `troll: g`).
- `[head_workflow.py:STAGES]`: Tuple of sequential revision stages: `('reference', 'donor', 'fitting', 'assembly', 'native', 'client', 'acceptance')`.
- `[head_workflow.py:allocate_slots]`: Allocates verified engine slots (1..200) to roster entries based on installed KEY archives and repository inventory.
- `[head_workflow.py:fit_similarity]`: Computes scale-preserving or uniform Umeyama similarity transformations between point sets.
- `[head_workflow.py:pin]` / `[head_workflow.py:verify_pins]`: Cryptographically pins input file paths and sha256 digests.
- `[head_workflow.py:write_fresh]`: Atomic, non-overwriting JSON and asset writer enforcing clean state isolation.
- `[bind_target.py:bind]`: Resolves abstract portable target contracts to local machine paths using explicit hash-pinned bindings.
- `[audit_slots.py:audit]`: Audits game resource keys (bif/key/hak) and repository HAK definitions to persist head slot allocations.
- `[inspect_head.py:inspect]`: Reads raw donor geometry to calculate bounding boxes, vertex counts, and mesh statistics without state modification.
- `[propose_landmarks.py:propose]`: Proposes anatomical reference landmarks (chin, top of head, nose, neck center) from mesh extrema.
- `[fit_head.py:fit]`: Fits candidate landmarks to target NWN head-local space using similarity math.
- `[cap_head_holes.py:cap]`: Caches boundary edge loops and closes open eye, mouth, and neck boundaries.
- `[correct_neck_rim.py:correct]`: Trims neck rim vertices, generates planar closure caps, applies normal smoothing across crease angles, and creates smooth connector tapers.
- `[prepare_materials.py:prepare]`: Translates reviewed 2K PBR diffuse and normal textures into 1024x1024 game textures with optional normal green-channel inversion.
- `[propose_material_masks.py:propose]`: Proposes semantic material masks (skin vs. hair) and normal maps via microface neighborhood analysis.
- `[prepare_palette_assembly.py:prepare]`: Previews PLT palette layers against game palette color lookup tables.
- `[native_reader.py:decode]`: Reads binary Aurora MDL nodes and raw geometry structures into in-memory dictionaries.
- `[head_export.py:export]`: Compiles GLB source geometry and PLT texture definitions into native NWN ASCII `.mdl` models and binary `.plt` textures.
- `[build_head_fixture.py:build]`: Assembles test HAKs, creature blueprints (`.utc`), tileset definitions (`.set`), and game modules (`.mod`) for client verification.
- `[meshy_cli.py:dispatch]` / `[meshy_cli.py:collect]`: Dispatches, tracks, and collects generative tasks from the Meshy CLI adapter with budget reservations.
- `[export_review_evidence.py:export]`: Bundles offline verification images, turntables, and metadata into portable evidence packages.
- `[make_review_sheet.py:compose]`: Merges multi-angle review images into contact sheets.
- `[publish_head_pack.py:publish]`: Registers verified head assets into hakbuilder configuration files.
- `[verify_head_hak.py:verify]`: Verifies compiled HAK archives against publication manifest digests.
- `[verify_retexture.py:verify]`: Detects and rejects unexpected geometric or UV deformation during retexturing.
- `[verify_texture_transfer.py:verify]`: Validates UV and texture coordinate fidelity across mesh topology transfers.
- `[audit_fixture_rig.py:audit]`: Audits fixture animation controllers, node rotations, and bind poses.
- `[audit_native_head.py:audit]`: Verifies compiled native models meet material group and triangle constraints.
- `[audit_neck_closure.py:audit]`: Confirms head donor neck boundaries are completely sealed and within budget.
- `[audit_neck_connector.py:audit]`: Confirms lowered neck caps remain enclosed within stock neck convex hull bounds without shelf formation.
- `[audit_neck_revision.py:audit]`: Asserts upper donor geometry, normals, and UV coordinates are preserved across neck revisions.
- `[roster.json]`: Declarative 200-character roster specification across races and sexes (`schemaVersion: 1`, `kind: "srn-head-roster"`).
- `[target-template.json]`: Template schema for approved head target contracts (`schemaVersion: 1`, `kind: "srn-head-target-template"`).

## Invariants
- `[head_workflow.py:MAX_TRIANGLES]`: Total runtime head polycount must not exceed 20,000 triangles (`len(triangles) <= 20000`).
- `[head_workflow.py:TEXTURE_SIZE]`: Runtime exported textures must be exactly 1024x1024 pixels.
- `[head_workflow.py:Session.reserve]`: All external credit-consuming calls require an explicit pre-reservation recorded in `spending-owner.json` before execution.
- `[head_workflow.py:require]`: Output destinations must not pre-exist; overwriting existing revision folders or files without a fresh revision is strictly forbidden.
- `[audit_neck_connector.py:audit]`: Connector tapers must maintain a continuous downward slope (`taperDepthMetres > 0`) and fit within the convex envelope of the protected stock neck (`len(planes) >= 4`).
- `[audit_neck_closure.py:audit]`: Sealed neck cuts must have zero remaining open boundary loops (`boundaries == 0`).
- `[audit_neck_revision.py:audit]`: Position, normal, and UV differences on donor surfaces above the neck cut must not exceed `2e-06` between revisions.
- `[verify_retexture.py:verify]`: Vertex position, normal, and UV coordinate deviation after retexturing must remain within strict float tolerance (`error.max() <= tolerance`).
- `[verify_head_hak.py:verify]`: Packaged HAK archives must conform to `HAK V1.0` header format, and resource digests must match publication pins exactly.
- `[head_workflow.py:verify_review_chain]`: Heads cannot advance to subsequent stages without valid preceding review receipts recorded in the session event ledger.

## Side Effects
- `[head_workflow.py:write_fresh]`: Writes atomic JSON session ledgers (`session.json`, `events/*.json`), lock files (`spending-owner.json`), and stage artifacts.
- `[head_export.py:export]`: Writes ASCII MDL model files (`.mdl`), binary PLT palette files (`.plt`), and GLB intermediate geometry.
- `[prepare_materials.py:prepare]`: Writes 1024x1024 PNG diffuse and normal maps to disk.
- `[build_head_fixture.py:build]`: Writes ERF/HAK native archives, creature blueprints (`.utc`), tileset blueprints (`.set`), and module files (`.mod`).
- `[publish_head_pack.py:publish]`: Modifies repository `hakbuilder.json` to register new head HAK entries.
- `[meshy_cli.py:dispatch]`: Invocates external Meshy CLI / API network services and consumes account credits.
- `[render_assembly.py:mesh]` / `[render_donor.py]`: Spawns Blender background processes for clay turntable rendering and multi-angle capture.
- `[Session.lock]`: Acquires single-process execution locks on `spending_lock()` to prevent concurrent credit-consuming API invocations.

## Verification
- Run: `pytest tools/heads`
