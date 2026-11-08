# Tools Blueprint

## Overview
Shared toolchains, pipeline runners, test selection engines, and batch orchestration systems for Neverwinter Nights content generation, body phenotyping, garment rigging, character head modeling, and equipment packaging.

## Local Interface & Invariants
- `shared_tools.py`: `resolve_tool`, `resolve_addon`, `resolve_runtime`, `retirement_audit` - Shared cross-worktree binary resolver and migration auditor.
- `test_impact.py`: `catalog`, `select`, `balance`, `run_tests` - Dependency-aware change selection and test impact catalog manager.
- `test_combat_release_manifest.py`: Release verification test suite auditing weapon, shield, and equipment manifest closures.
- `SrnTools.psm1`: PowerShell module exposing `Resolve-SrnSharedTool`, `Invoke-SrnTool`, and environment hooks.

## Subdirectories & Boundaries
- [headbatch](./headbatch/README.md) - Multi-head batch orchestration, GPU inference pipeline, stage progression, submission budgeting, and client trial module builder.
- [headkit](./headkit/README.md) - Character head creation, fitting, UV unwrapping, texturing, quality gate verification, and NWN native model compilation toolkit.
- [heads](./heads/README.md) - Production pipeline, landmark similarity fitting, neck closure audits, and native asset export toolchain for Neverwinter Nights character heads across a 200-head roster and 7 acceptance gates.
- [itemkit](./itemkit/README.md) - Single-image 3D generation, fitting, UV atlasing, texture baking, shadow proxy generation, inspection fixtures, and native equipment packaging for Neverwinter Nights: Enhanced Edition.
- [phenomorpher](./phenomorpher/README.md) - Intermediate blueprint and runner harness for PhenoMorpher body fitting and armor adaptation.
- [phenotypes](./phenotypes/README.md) - Purpose-built phenotype tools for part generation, rig retargeting, volume-conserving RBF mesh refinement, joint connector auditing, material baking, native compilation, and client preflight verification.
- [robes](./robes/README.md) - Automated pipeline for generating, inspecting, fitting, skinning, and packaging custom NWN robes and garments for Human male phenotype 0 (pmh0) via Meshy AI, Blender, and NWN toolchain fixtures.

## Verification
- Run: `pytest tools/`
