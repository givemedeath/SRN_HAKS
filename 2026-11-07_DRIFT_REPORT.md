# EGM Drift Report (2026-11-07)

## README.md
No drift detected.

## tools/README.md
- Documented symbols `require_tool` and `verify_manifest` were absent from `tools/shared_tools.py` (actual resolution functions are `resolve_tool`, `resolve_runtime`, and `register_run`). *Resolved in contract.*
- Documented symbols `evaluate_run` and `parse_jobs` were absent from `tools/ci_result.py` (actual functions are `evaluate` and `read_jobs`). *Resolved in contract.*

## tools/heads/README.md
No drift detected.

## tools/phenomorpher/README.md
No drift detected.

## tools/phenomorpher/phenomorpher/README.md
No drift detected.

## tools/phenomorpher/phenomorpher/engine/README.md
- Documented function `clothing_core.convert_clothing(...)` diverged from actual function signature `clothing_core.convert(...)`. *Resolved in contract.*

## tools/phenotypes/README.md
- Documented symbols `retarget_rig` and `export_rig_frames` were absent from `tools/phenotypes/derive_rig.py` (actual functions are `derive_stock_family_rig` and `derive_broadened_scaled_rig`). *Resolved in contract.*
- Documented symbols `deform_mesh` and `wendland_rbf` diverged from `tools/phenotypes/localized_refine.py` (actual functions are `wendland_c2`, `calculate_mesh_volume`, and `refine_all_parts`). *Resolved in contract.*
- Documented symbol `measure_joint_overlap` was absent from `tools/phenotypes/audit_derived_connectors.py` (actual entry point is `audit_connectors`). *Resolved in contract.*
- Documented symbols `audit_equipment` and `check_attachment_locators` were absent from `tools/phenotypes/derived_equipment.py` (actual functions are `inventory_installed_styles`, `audit_hand_dummies`, and `audit_stock_armor_compatibility`). *Resolved in contract.*

## tools/phenotypes/comfy_nodes/README.md
No drift detected.

## tools/phenotypes/comfy_nodes/srn_orthographic_multiview/README.md
No drift detected.

## tools/robes/README.md
No drift detected.
