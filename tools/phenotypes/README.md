# Purpose-built phenotype tools

## Overview
Architectural toolchain for purpose-built and derived Neverwinter Nights character phenotypes. The pipeline covers reference view capture, local ComfyUI multiview generation, mesh fitting, joint connector tapering, material baking, native binary trimesh compilation, and multi-gate automated verification.

Start with [the current runbook](../../docs/phenotype-purpose-built-current-runbook.md) and [production contract](../../docs/phenotype-purpose-built-production.md). The [completed Human male delivery](../../docs/phenotype-human-male-delivery.md) records the selected fourteen-part body, package hashes, actual client results, and practical limits. Older whole-body slicing and stock-surface projection experiments are history; they are not the current production entry point.

### Current Workflow
1. Measure actual installed stock parts, joints and moving overlap; freeze their resources with `freeze_stock_part_inputs.py`. Declare target rig, race slot, physique, height and equipment policy explicitly.
2. Generate coherent purpose-built orthographic reference views. Normalize at shared isotropic scale with `normalize_part_turnaround.py` and preserve images, prompts, ancestry and exact external copies with `freeze_part_references.py`.
3. Prepare an explicit part configuration with `generate_purpose_built_part.py` against the running `SR_NWN_3d_pixal3d_multi_views` workflow. Freeze the actual graph, node schema and camera dependencies. Submit once, preserve job history and all source masters, and recover uncertain dispatches through receipts.
4. Inspect the new donor's anatomy, geometry, normals, UVs and maps. Fit with positive uniform scale, proper rotation and placement first. Local mesh edits require a measured need, bounded scope and protected-attribute proof.
5. Mirror a selected detached donor through actual opposite stock frames with correct winding/tangent signs. Independently validate the opposite side.
6. Follow [material preservation](../../docs/phenotype-body-material-process.md): measure new skin against current neighbours, bake restrained AO into PLT, preserve normal maps and transport ORM-green roughness explicitly. Preserve every accepted neighbour's effective resource bytes.
7. Compile each new part with frozen material dependencies. Decode native geometry/normal/UV/tangent arrays, compose the declared body-only inventory, and prepare a separate isolated stock-comparison HAK/module.
8. Collect the complete offline phenotype, then perform authorized bulk client tests and literal animation reference sheets. Keep camera controls unlocked; distinguish observed results, package identity and remaining practical limits.

Human male keeps the stock male rig, controllers, neck/head, measured 1.9339157 m height and identity equipment sizing. Image-generation poses never modify animation resources. Other races and their equipment profiles need their own target measurements and validation.

### Derived Phenotypes
For racial variants derived from accepted Human master bodies, see:
- [The Derived Workflow Runbook](../../docs/phenotype-derived-workflow.md)
- [Gate Measurement Process & Verification Standards](../../docs/phenotype-gate-measurement-standards.md) (Authoritative engineering thresholds for Gates 0–7)
- [Silhouette Generation & Overlap Audit Runbook](../../docs/phenotype-silhouette-workflow.md)
- [Dwarf Male Pilot Validation](../../docs/phenotype-derived-dwarf-pilot.md)
- [Troll Male Comparison Report](../../docs/phenotype-derived-troll-male-comparison.md)

1. **Target Matrix & Stature Calibration (Gate 0):** `derived_matrix.py` checks target eligibility, prerequisites, and stature calibration.
2. **Rig Retargeting (Gate 1 / CP1):** `derive_rig.py` establishes the target race rig, stature scaling, and 18 rigid connector frames.
3. **Localized Deformation (Gate 2 / CP2):** `localized_refine.py` deforms donor parts via Wendland $C^2$ RBF, enforcing positive Jacobian determinants ($J > 0$) and strict volume conservation while keeping rigid connector rings unchanged.
4. **Joint Connector Overlap Audit (Gate 2b):** `audit_derived_connectors.py` evaluates axial overlap across all 13 primary joint interfaces to ensure zero tearing during animation.
5. **Equipment Audit (Gate 3):** `derived_equipment.py` verifies target attachment locators and derived-body connectors, and inventories installed equipment filenames. Its prerequisite receipt does not certify stock armor geometry or complete Gate 3; armor interfaces and visible equipment fit need separate evidence.
6. **Materials & Native Compilation (Gate 4):** `stage_derived_dwarf.py` stages models referencing shared human normal/roughness maps (`pmh0_*n`, `pmh0_*r`). Models are compiled to native trimesh binaries with `native_compile.py` and verified via `audit_derived_dwarf_native.py`.
7. **Packaging & Comparison Fixture (Gate 5):** `stock_dwarf_control.py` and `build_test_module.py` build standalone HAKs and side-by-side comparison test modules against stock controls.
8. **Client Preflight & Testing (Gate 6):** `preflight_derived_dwarf_client.py` and `run_derived_dwarf_client_test.py` execute and monitor the in-engine inspection sequence.
9. **3-Way Silhouette & Overlap Audit (Gate 7 / CP3):** `build_silhouette_comparison_sheet.py` generates presentation-grade turnaround sheets and `calculate_silhouette_difference.py` computes mathematical DICE/IoU overlap metrics against canonical concept art.

### Future Hands: Inspect Each New Result
Hands use a nearly closed gripping pose with four curled fingers and a credible thumb. Do not assume another hand will repeat the last Human round's defects. Sound generated donors proceed through ordinary fitting and material/native preparation. Shell tracing, SAT512 recovery, leak patches, fairing, normal smoothing and special retexture graphs are conditional responses to a diagnosed defect. The previous Human recovery is [case history](../../docs/phenotype-hand-shell-diagnosis.md), not a mandatory hand recipe or a source of default repair parameters.

### Runtime and Continuation
Use the bundled workspace Python, never the Windows Store shim. Generation requires the user's running local ComfyUI/model installation; native tests require the installed NWN:EE tools/client. Blender performs the documented mesh/preview stages. Installation-specific paths and source hashes are explicit configuration inputs, not portable defaults.

The [generation procedure](../../docs/phenotype-purpose-built-part-generation.md) and [orthographic adapter contract](../../docs/phenotype-orthographic-multiview.md) describe preparation, guarded installation and commands. The [client validation guide](../../docs/phenotype-full-body-client-validation.md) describes isolated direct loading, resource audits, actual observation and capture.

Selected receipts and reference sheets under `docs/phenotypes/evidence` are recorded evidence. Their absolute paths and hashes refer to the original worktree; they are not fresh-job configurations. The user-accepted native Human body resources are versioned in `srn_body`, with exact publication pins in [the asset manifest](../../docs/phenotypes/human-male-assets.json). Generation masters, working maps and built HAKs remain outside Git. Reproduction needs the frozen source assets identified by the receipts.
Never rerun a completed job merely because its large outputs are absent in a new checkout. Do not rewrite immutable historical receipts when improving tools.

### PhenoMorpher Toolkit
The maintained measurement, conservative fitting and static clothing-transfer interface is documented in [PhenoMorpher](../phenomorpher/README.md). Its source package is independent of the game-ready body assets. New runs still use the shared-tool launcher and explicit consumed input bindings.

## Interface
- [comfy_nodes](./comfy_nodes/README.md) - Custom ComfyUI nodes including orthographic multiview conditioning.
- `pipeline.py`: Reproducible local ComfyUI multi-view generation for 20 racial/gender body variants (`Comfy`, `digest`, `save_json`, `RACES`, `HEIGHT_TARGETS`, `VIEWS`).
- `target_contract.py`: Hash-bound phenotype target validation (`load`, `validate`, `sha`, `PART_JOINTS`, `BODY_PARTS`, `PAIRS`).
- `derived_contract.py`: Validation and contract enforcement for derived phenotype targets (`load_derived_target`, `verify_target_frames`).
- `derived_matrix.py`: Gate 0 target matrix and stature calibration checks (`load_matrix`, `evaluate_target`).
- `derive_rig.py`: Gate 1 rig retargeting and connector frame derivation (`derive_stock_family_rig`, `derive_broadened_scaled_rig`).
- `localized_refine.py`: Gate 2 localized RBF deformation under volume conservation and positive Jacobian constraints (`wendland_c2`, `calculate_mesh_volume`, `refine_all_parts`).
- `audit_derived_connectors.py`: Gate 2b axial overlap audit across 13 primary joint interfaces (`audit_connectors`).
- `derived_equipment.py`: Gate 3 attachment locator and equipment inventory audit (`inventory_installed_styles`, `audit_hand_dummies`, `audit_stock_armor_compatibility`).
- `stage_derived_dwarf.py`: Gate 4 model staging and shared material linking.
- `native_compile.py`: Gate 4 native compilation bridge invoking NWN:EE modelcompiler with strict override isolation and frozen dependency hashes.
- `audit_derived_dwarf_native.py`: Gate 4 native binary inspection and trimesh verification.
- `stock_dwarf_control.py` & `build_test_module.py`: Gate 5 standalone HAK packaging and comparison module generation.
- `preflight_derived_dwarf_client.py` & `run_derived_dwarf_client_test.py`: Gate 6 in-engine client testing and log monitoring.
- `build_silhouette_comparison_sheet.py` & `calculate_silhouette_difference.py`: Gate 7 3-way silhouette turnaround sheet generation and DICE/IoU overlap calculation.
- `launch_shared_tool.py`: Verified shared CLI tool launcher retaining immutable run receipts and dependency snapshots (`manifest_inputs`, `helper_snapshots`, `tree_files`).
- `tool_runtime.py`: Tool and runtime resolution against repository-level shared tools (`tool`, `runtime`, `record_dependencies`).
- `nwn_ascii_trimesh.py`: ASCII model file parser, manipulator, and validator for NWN geometry, animnodes, texture coordinates, and bounding boxes.
- `connector_surface_math.py`: Rigid connector surface geometry, joint rings, and normal taper mathematics.
- `lean_common.py`, `lean_reduction_core.py`, `lean_single_plt_atlas.py`: Lean pipeline for body parts reduction and PLT atlas generation.
- `bake_body_materials.py`, `compose_target_skin_material.py`: Material baking and composition.
- `Launch-CompleteBodyClient.ps1`, `Launch-DerivedPhenotypeClient.ps1`, `Launch-TargetBodyClient.ps1`: Automated PowerShell client launchers.

## Invariants
- `[target_contract.py:validate]` Schema version must equal 2 and kind must equal `'phenotype-target'`.
- `[target_contract.py:validate]` Target ID must match regex `^[a-z0-9-]+$`.
- `[target_contract.py:validate]` Rig mode must be either `'retargeted'` or `'stock-exact'`; stock-exact requires Human identity (`raceId == 6`, `appearanceRow == 6`, `pmh0`/`pfh0`).
- `[target_contract.py:load]` All frozen input file hashes declared in `frozenInputs` must match their on-disk SHA-256 digest or validation fails.
- `[derived_contract.py:verify_target_frames]` All 16 body part frames must exist in both `working` and `runtime` spaces.
- `[localized_refine.py]` Deformation must enforce positive Jacobian determinants ($J > 0$) and strict volume conservation while keeping 18 rigid connector frames unchanged.
- `[audit_derived_connectors.py]` Axial overlap across all 13 primary joint interfaces must maintain zero tearing during full animation envelopes.
- `[native_compile.py:main]` Native compilation must run in an isolated user directory separate from client-test userdir; override directory must contain only explicitly staged dependencies.
- `[launch_shared_tool.py:manifest_inputs]` Input manifests must be non-empty and every pinned file must match its expected SHA-256 digest with no conflicting pins.
- `[AGENTS.md]` No shelves when tapering connector joints: connector taper must form a continuous sloped transition between measured starting and ending contours without introducing flat shelves, rolled lips, cuff ledges, or secondary shoulders.

## Side Effects
- `[native_compile.py]` Executes the external NWN:EE modelcompiler process, copying staged dependency files into an isolated override directory and writing native compiled models and `native-compile.json` receipts.
- `[launch_shared_tool.py]` Executes shared CLI tools as subprocesses, creates directory `helper-snapshots/`, and writes immutable run receipts via `register_run`.
- `[pipeline.py]` Dispatches HTTP POST requests to the local ComfyUI API (`/prompt`, `/history`, `/view`), allocates GPU tensors, and writes generated images and JSON receipts under `output/`.
- `[build_test_module.py]` Packages compiled assets and GFF structures into game-ready ERF/HAK archives and NWN test module files (`.mod`).
- `[Launch-*.ps1]` Launches the Neverwinter Nights game client (`nwmain.exe`) with dedicated configuration switches and test modules.

## Verification
- Run: `pytest tools/phenotypes`
