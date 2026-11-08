# Item Toolkit (tools/itemkit)

## Overview
The `tools/itemkit` package provides single-image 3D generation, geometric fitting, UV atlasing, texture baking, shadow proxy generation, client inspection fixtures, and native equipment packaging for Neverwinter Nights: Enhanced Edition. It supports composite melee weapons (shortswords, daggers, longswords, greatswords, staves, throwing knives), rigged weapons (bows, whips), whole-skinned weapons (crossbows), rigid longarms and slings (firearms), shields, and catalog objects. Mutating generation and processing workflows operate through immutable execution snapshots and receipts managed by a dedicated stage runner.

## Interface
- `[__main__.py:main]` - Command-line entry point dispatching intake, input pin extraction, preflight checks, ComfyUI generation requests, stage runs, reviews, and native packaging.
- `[__main__.py:intake]` - Initialize a fresh item workspace directory with reference images, family configuration, and asset manifests.
- `[__main__.py:preflight]` - Read-only validation of runtime bindings, ComfyUI client connectivity, camera calibration, and conditioning reviews.
- `[__main__.py:consumed_inputs]` / `[__main__.py:consumed_pins]` - Resolve and verify SHA256 input pins consumed by an item stage or pipeline run.
- `[contracts.py:manifest]` - Parse and validate portable item asset manifests (`item-asset` schema version 1) against schema and preset constraints.
- `[contracts.py:family]` - Parse and validate item family profiles (`item-family` schema version 1) including routes, material routes, runtime texture size, and polygon budgets.
- `[contracts.py:native_contract]` - Validate native equipment contracts, content-stack namespaces, baseitem entries, donor models, frames, and grip coordinates.
- `[contracts.py:reserve]` - Allocate collision-free appearance and model indices (1..25) within content-stack resources.
- `[contracts.py:all_pins]` / `[contracts.py:code_pins]` / `[contracts.py:source_version]` - Enumerate pinned assets and compute cryptographic version hashes of itemkit source code and configuration.
- `[generation.py:request_stage]` - Prepare generation requests (`calibrate`, `geometry`, `appearance`, `export`) for the Pixal engine.
- `[generation.py:initialize_trial]` / `[generation.py:set_trial_limit]` - Manage shared item trial policies and enforce geometry attempt limits.
- `[generation.py:shared_ledger]` - Resolve and validate the shared submission ledger binding.
- `[runner.py:Runner]` - Orchestrate immutable stage execution, ancestor dependency validation, retry budgeting, and review decisions.
- `[runner.py:Runner.execute]` - Execute an item processing stage (`prepare`, `inspect`, `donor`, `fit`, `reduce`, `unwrap`, `finish`, `bake`, `shadow`, `render`, `native`, `fixture`, `client`).
- `[runner.py:Runner.review]` - Record human approval or rejection review decisions for completed stages.
- `[routes.py:ROUTES]` / `[routes.py:Route]` / `[routes.py:Carrier]` - Registry of supported equipment families, adapter types (`composite`, `rigged`, `whole-skinned`, `whole-rigid`, `shield`, `none`), and carrier specifications.
- `[geometry.py:check_budgets]` / `[geometry.py:topology]` / `[geometry.py:protected_checks]` - Verify triangle counts, manifold closed-wound topologies, and intentional opening preservation.
- `[grip.py:calibration]` / `[grip.py:affine_corners]` - Calibrate item geometry to native hand attachment origins and transform corners while preserving UV coordinates.
- `[firearm_grip.py:measured_fit]` - Measure firearm grips along their natural axes against `colt-l36-approved-firearm-grip-v1` standard without distortion.
- `[donor.py:build]` - Bake raw appearance onto source geometry and construct diffuse textured donor meshes.
- `[reduction.py:reduce]` / `[reduction.py:validate]` - Bounded mesh decimation preserving exact multipart mating contours and source surface tolerance.
- `[atlas.py:unwrap_parts]` / `[source_atlas.py:unwrap]` - Generate bounded UV unwraps and packed runtime texture atlases.
- `[textures.py:finish_bake]` / `[transfer.py:finished_colour]` - Material palette assignment, unmapped margin dilation, and projection-miss colour transfer.
- `[shadow.py:build_candidates]` / `[shadow.py:silhouette_proxy]` - Generate planar projected shadow proxies within 500-triangle budgets and >= 0.95 silhouette IoU.
- `[fixture.py:build]` - Construct private inspection modules and creature UTC donors for visual review.
- `[native.py:compile_package]` / `[native.py:ascii_model]` / `[native.py:write_verified_hak]` - Export diffuse composite models, compile binary MDLs, and assemble verified HAK archives.
- `[firearm_package.py:compile_package]` - Compile isolated Sling multipart firearm packages with per-color whole meshes.
- `[shield_native.py:compile_package]` - Compile single-model shield packages with opaque fittings and alpha panes.
- `[skinned_native.py:audit]` / `[onehand_fire_motion.py:build]` - Export and verify skinned native weapon models and firing animations.
- `[verification.py:VerificationPass]` - Operation-local byte verification pass avoiding persistent unverified caches.

### Subdirectories & Data Assets
- `examples/` - Reference JSON manifests (e.g. `cougar.json`, `firearm-sling-blocked.json`) for intake configuration and testing.
- `profiles/` - Reference family profiles (e.g. `cougar-shortsword.json`) defining polygon budgets, part mappings, and resource names.

## Invariants
- `[contracts.py:resref]` - NWN resrefs must be lowercase alphanumeric/underscore strings at most 16 characters matching `^[a-z][a-z0-9_]{0,15}$`.
- `[contracts.py:family]` - Material routes are restricted to diffuse only (`materialRoute == 'diffuse'`); source bake size must be 4096; runtime texture size must be 512, 1024, or 2048 (firearm packages must use 1024).
- `[contracts.py:family]` - Visible polygon budget is 10,000 triangles and shadow budget is 500 triangles for firearm and shield routes; inactive firearm slots require hidden placeholder parts (`visible: 4, shadow: 0`).
- `[contracts.py:native_contract]` - Native frame rotation matrix must be a valid 3x3 orthonormal rotation with positive determinant (`det > 0`, `R.T @ R == I`).
- `[contracts.py:native_contract]` - Native grip origin must be finite 3D coordinates, and grip length must be a finite positive number.
- `[conditioning.py:validate_pair]` - Clay and detailed reference images must share identical canvas dimensions and framing, with at least 4 paired landmarks aligned within 0.02 normalized frame distance (2%).
- `[reduction.py:validate]` - Constrained mesh reduction must remain closed and outward (`closedWound`), preserve mating contours at join planes within `2e-6`, and stay within 0.003 units of the source surface (`MAXIMUM_SOURCE_DISTANCE = 0.003`).
- `[shadow.py:silhouette_proxy]` - Projected shadow proxies must satisfy closed-wound topology, stay within 12..500 triangles, and achieve at least 0.95 intersection-over-union (`minimumIoU >= 0.95`) against the projected source silhouette.
- `[runner.py:Runner.execute]` - A maximum of two failed attempts is permitted for an identical input snapshot before requiring input or code changes; completed stages are idempotent and reused when input hashes match.
- `[runner.py:Runner.result]` - Dependent stages require approved human review decisions on all ancestor stages before execution.
- `[generation.py:set_trial_limit]` - Shared submission ledger strictly caps geometry generation attempts at 5 attempts per model; trials cannot be reset or repeated to gain attempts.
- `[native.py:ascii_model]` - Per-corner normals must be unit vectors (`norm == 1 +/- 1e-4`), UV coordinates must be bounded in [0, 1], and shadow proxies must be closed and outward.

## Side Effects
- `[runner.py:Runner.execute]` - Writes immutable stage attempt directories, `intent.json`, `receipt.json`, execution logs, and updates `state.json`.
- `[generation.py:request_stage]` - Communicates over HTTP with local ComfyUI instance (`comfyUrl`, default `127.0.0.1:8188`) to queue generation workflows and verify runtime fingerprints.
- `[runner.py:Runner.worker]` / `[native.py:compile_with_client]` - Spawns external processes through `launch_shared_tool.py` including Blender 4.0 workers, Neverwinter client compiler, and NeverBlender.
- `[native.py:write_verified_hak]` / `[fixture.py:build]` - Writes binary HAK archives (`.hak`), ERF archives, compiled UTI blueprints (`.uti`), and test module files (`.mod`).
- `[runner.py:Runner]` - Acquires filesystem lock (`comfy.locked`) on runner directory to prevent concurrent mutations.
- `[__main__.py:intake]` - Creates directory trees and writes fresh `asset.json`, `family.json`, and reference image files.

## Verification
- Run: `pytest tools/itemkit`
