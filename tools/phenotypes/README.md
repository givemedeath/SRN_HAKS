# Purpose-built phenotype tools

## Overview

Start with [the current runbook](../../docs/phenotype-purpose-built-current-runbook.md)
and [production contract](../../docs/phenotype-purpose-built-production.md).
The [completed Human male delivery](../../docs/phenotype-human-male-delivery.md)
records the selected fourteen-part body, package hashes, actual client results
and practical limits. Older whole-body slicing and stock-surface projection
experiments are history; they are not the current production entry point.

### Current workflow

1. Measure actual installed stock parts, joints and moving overlap; freeze their
   resources with `freeze_stock_part_inputs.py`. Declare target rig, race slot,
   physique, height and equipment policy explicitly.
2. Generate coherent purpose-built orthographic reference views. Normalize at
   shared isotropic scale with `normalize_part_turnaround.py` and preserve images,
   prompts, ancestry and exact external copies with `freeze_part_references.py`.
3. Prepare an explicit part configuration with `generate_purpose_built_part.py`
   against the running `SR_NWN_3d_pixal3d_multi_views` workflow. Freeze the actual
   graph, node schema and camera dependencies. Submit once, preserve job history
   and all source masters, and recover uncertain dispatches through receipts.
4. Inspect the new donor's anatomy, geometry, normals, UVs and maps. Fit with
   positive uniform scale, proper rotation and placement first. Local mesh edits
   require a measured need, bounded scope and protected-attribute proof.
5. Mirror a selected detached donor through actual opposite stock frames with
   correct winding/tangent signs. Independently validate the opposite side.
6. Follow [material preservation](../../docs/phenotype-body-material-process.md):
   measure new skin against current neighbours, bake restrained AO into PLT,
   preserve normal maps and transport ORM-green roughness explicitly. Preserve
   every accepted neighbour's effective resource bytes.
7. Compile each new part with frozen material dependencies. Decode native
   geometry/normal/UV/tangent arrays, compose the declared body-only inventory,
   and prepare a separate isolated stock-comparison HAK/module.
8. Collect the complete offline phenotype, then perform authorized bulk client
   tests and literal animation reference sheets. Keep camera controls unlocked;
   distinguish observed results, package identity and remaining practical limits.

Human male keeps the stock male rig, controllers, neck/head, measured
1.9339157 m height and identity equipment sizing. Image-generation poses never
modify animation resources. Other races and their equipment profiles need their
own target measurements and validation.

### Derived phenotypes

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

### Future hands: inspect each new result

Hands use a nearly closed gripping pose with four curled fingers and a credible
thumb. Do not assume another hand will repeat the last Human round's defects.
Sound generated donors proceed through ordinary fitting and material/native
preparation. Shell tracing, SAT512 recovery, leak patches, fairing, normal smoothing
and special retexture graphs are conditional responses to a diagnosed defect.
The previous Human recovery is [case history](../../docs/phenotype-hand-shell-diagnosis.md),
not a mandatory hand recipe or a source of default repair parameters.

### Runtime and continuation

Use the bundled workspace Python, never the Windows Store shim. Generation
requires the user's running local ComfyUI/model installation; native tests require
the installed NWN:EE tools/client. Blender performs the documented mesh/preview
stages. Installation-specific paths and source hashes are explicit configuration
inputs, not portable defaults.

The [generation procedure](../../docs/phenotype-purpose-built-part-generation.md)
and [orthographic adapter contract](../../docs/phenotype-orthographic-multiview.md)
describe preparation, guarded installation and commands. The
[client validation guide](../../docs/phenotype-full-body-client-validation.md)
describes isolated direct loading, resource audits, actual observation and capture.

Selected receipts and reference sheets under `docs/phenotypes/evidence` are
recorded evidence. Their absolute paths and hashes refer to the original worktree;
they are not fresh-job configurations. The user-accepted native Human body
resources are versioned in `srn_body`, with exact publication pins in
[the asset manifest](../../docs/phenotypes/human-male-assets.json). Generation
masters, working maps and built HAKs remain outside Git. Reproduction needs the
frozen source assets identified by the receipts.
Never rerun a completed job merely because its large outputs are absent in a
new checkout. Do not rewrite immutable historical receipts when improving tools.

### PhenoMorpher toolkit

The maintained measurement, conservative fitting and static clothing-transfer interface is documented in [PhenoMorpher](../phenomorpher/README.md). Its source package is independent of the game-ready body assets. New runs still use the shared-tool launcher and explicit consumed input bindings.

## Interface

### Subdirectories
- [comfy_nodes](./comfy_nodes/README.md) - Custom node packages and extensions for ComfyUI supporting the SRN phenotype generation pipeline.

### Core Modules and CLI Symbols
- **Rigging & Retargeting**:
  - `derive_rig.py`: `derive_stock_family_rig()`, `derive_broadened_scaled_rig()`, `verify_hierarchy_complete()` — Retargets race rigs, stature scaling, and rigid connector frames across phenotypical variants.
  - `derived_matrix.py`: `load_matrix()`, `get_target()`, `evaluate_target_eligibility()` — Validates Gate 0 prerequisite eligibility, configuration schema, and stature calibration.
  - `audit_target_rig.py`: `audit()`, `find_bind()`, `geometry_array()` — Verifies bone hierarchy, orientation, locator anchors, and node bindings against stock references.
- **Mesh Deformation & Connector Repair**:
  - `localized_refine.py`: `wendland_c2()`, `calculate_mesh_volume()`, `verify_positive_jacobians()`, `refine_all_parts()` — Executes volume-conserving Wendland C2 RBF mesh deformations preserving connector rings.
  - `armory_rigid.py`: `profile_affine()`, `rigid_frames()`, `fit_residuals()` — Evaluates and fits rigid armor locator frames and equipment attachment nodes.
  - `taper_foot_ankle.py` / `taper_generated_waist_back.py`: Functions applying continuous sloped connector transitions without ledges or shelves.
  - `repair_target_chest_connector.py` / `repair_target_pelvis_upper_connector.py`: Repositioning and smoothing routines for torso and pelvic connector seams.
- **Auditing & Verification**:
  - `audit_derived_connectors.py`: `audit_connectors()` — Evaluates axial overlap and geometry bounds across 13 primary joint interfaces.
  - `audit_derived_dwarf_native.py`: Audits compiled native trimesh binaries against target requirements.
  - `calculate_silhouette_difference.py`: `align_and_compare()`, `evaluate_gate7_compliance()` — Computes mathematical DICE and IoU overlap metrics against canonical silhouettes.
  - `verify_published_body.py`: `manifest_contract()`, `verify()` — Validates published phenotype models and textures against SHA-256 asset manifests.
  - `verify_armory_rigid_tool.py`: Validates armory equipment transform invariants.
- **Generation & Material Pipelines**:
  - `generate_purpose_built_part.py`: `configure_projection()`, `texture_view_order()`, `verify_record()` — Prepares explicit part configurations for Pixal3D multi-view generation.
  - `freeze_stock_part_inputs.py`: `digest()`, `main()` — Freezes stock mesh geometry, connector frames, and moving overlap bounds.
  - `normalize_part_turnaround.py`: Normalizes generated turnaround images to uniform isotropic scales.
  - `freeze_part_references.py`: Records reference images, prompts, ancestry hashes, and verified donor copies.
  - `bake_body_materials.py` / `bake_target_skin_lighting.py`: Headless material baking and skin ambient occlusion passes.
  - `native_compile.py`: `supermodel_chains()`, `main()` — Compiles ASCII trimesh models into engine-native binary models.
- **Tooling Runtime & Launchers**:
  - `tool_runtime.py`: `tool()`, `runtime()`, `record_dependencies()` — Resolves runtime dependencies and records input/output execution receipts.
  - `launch_shared_tool.py`: `tree_files()`, `manifest_inputs()`, `helper_snapshots()` — Managed launcher capturing fresh local migration evidence.

## Invariants
- **Connector Taper Rule (No Shelves)**: Connector transitions must form a continuous sloped gradient between measured starting and ending contours across eligible anatomy; flat shelves, rolled lips, cuff ledges, or secondary shoulder steps are strictly forbidden (`taper_foot_ankle.py`, `taper_generated_waist_back.py`, `AGENTS.md`).
- **RBF Deformation Invariants**: Mesh deformation using Wendland $C^2$ RBF kernels must maintain positive Jacobian determinants ($J > 0$) across all elements, conserve total volume, and leave rigid connector rings strictly unchanged (`localized_refine.py:verify_positive_jacobians`).
- **Joint Overlap Limits**: Axial overlap across all 13 primary joint interfaces must remain within audited gate tolerances to prevent surface tearing during animation (`audit_derived_connectors.py:audit_connectors`).
- **Generation Limits**: Item and part generation permits at most five geometry submissions per model; trial ledgers and uncertain-job reconciliation receipts are immutable (`AGENTS.md`, `generate_purpose_built_part.py`).
- **Hand Topology**: Hands must feature nearly closed gripping poses with four curled fingers and a credible thumb; defect repairs require diagnosed evidence rather than speculative geometry operations (`README.md`, `AGENTS.md`).
- **Weapon Grip Standards**: Firearm grips adhere to `colt-l36-approved-firearm-grip-v1` (scaled uniformly by +15%); melee weapon grips adhere to `cougar-approved-grip-v1` (`AGENTS.md`, `measure_held_equipment.py`).
- **Runtime Execution**: Desktop execution strictly requires the bundled workspace Python interpreter; the Windows Store Python shim is forbidden (`AGENTS.md`, `tool_runtime.py`).
- **Asset Immutability**: Historical receipts, reference sheets in `docs/phenotypes/evidence`, and published body resources in `srn_body` are immutable records (`verify_published_body.py`, `AGENTS.md`).

## Side Effects
- Compiles ASCII models into engine-native binary trimeshes (`.mdl`) and archives them into HAK files (`.hak`) and test modules (`.mod`) (`native_compile.py`, `stock_dwarf_control.py`, `build_test_module.py`).
- Invokes local ComfyUI API on `127.0.0.1:8188` to execute Pixal3D multi-view image conditioning workflows (`generate_purpose_built_part.py`).
- Executes Blender headlessly (`blender -b -P ...`) to perform mesh baking, AO computation, and turnaround rendering (`blender_part_skin_bake.py`, `blender_target_skin_lighting.py`).
- Spawns NWN:EE client or engine test processes to execute automated preflight visual inspection and animation validation (`preflight_derived_dwarf_client.py`, `run_derived_dwarf_client_test.py`).
- Writes receipt logs, manifest hashes, diagnostic CSVs, and rendered turnaround comparison sheets to local disk (`tools/phenotypes/evidence/`, `staging/`).

## Verification
- Run: `pytest tools/phenotypes`
