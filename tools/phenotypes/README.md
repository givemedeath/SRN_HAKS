# Purpose-built phenotype tools

Start with [the current runbook](../../docs/phenotype-purpose-built-current-runbook.md)
and [production contract](../../docs/phenotype-purpose-built-production.md).
The [completed Human male delivery](../../docs/phenotype-human-male-delivery.md)
records the selected fourteen-part body, package hashes, actual client results
and practical limits. Older whole-body slicing and stock-surface projection
experiments are history; they are not the current production entry point.

## Current workflow

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

## Derived phenotypes

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

## Future hands: inspect each new result

Hands use a nearly closed gripping pose with four curled fingers and a credible
thumb. Do not assume another hand will repeat the last Human round's defects.
Sound generated donors proceed through ordinary fitting and material/native
preparation. Shell tracing, SAT512 recovery, leak patches, fairing, normal smoothing
and special retexture graphs are conditional responses to a diagnosed defect.
The previous Human recovery is [case history](../../docs/phenotype-hand-shell-diagnosis.md),
not a mandatory hand recipe or a source of default repair parameters.

## Runtime and continuation

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
