# Repository Tools and Build Infrastructure

## Overview
Shared development tools, CI test impact analysis, build scripts, toolchain verification, and pipeline launchers supporting the SRN_HAKS repository. This directory provides deterministic shared tool resolution, regression testing suites, HAK/TLK packaging automation, and coordinates child subsystems for heads, phenotypes, robes, and phenotype morphing.

## Interface

### Shared Tools & Runtime Resolution
- `shared_tools.py`: Deterministic tool resolution, SHA-256 calculation, and atomic non-overwriting JSON storage (`sha`, `read_json`, `write_json`, `resolve_tool`, `resolve_runtime`, `register_run`).
- `SrnTools.psm1`: PowerShell shared tooling module resolving local byte-bound toolchains and managing execution contexts.
- `SrnHaks.Common.psm1`: Shared utility functions for NWN resource processing and file manipulation.
- `Bootstrap-Tools.ps1`: Bootstraps pinned dependency binaries into local `.tools/` directory.

### Continuous Integration & Impact Analysis
- `test_impact.py`: Static impact analysis engine building dependency graphs between repository files, tests, and HAK packs (`catalog`, `select`, `full`, `pack_needs`).
- `ci_scope.py`: PR and commit CI scope planner computing test selection, LPT sharding, and matrix jobs (`changed_files`, `shards`, `plan`, `job_output`, `summary`).
- `ci_result.py`: CI execution result aggregator validating required check runs across platforms (`evaluate`, `read_jobs`, `latest`).

### Packaging & Validation Scripts
- `Test-Repository.ps1`: Core repository validation suite testing file encoding, 2DA formats, JSON schemas, and running helper tests.
- `Build-Haks.ps1` / `Build-Tlk.ps1`: Automates compiling HAK packs and TLK talk tables from source directories.
- `Import-Hak.ps1` / `Import-Tlk.ps1`: Ingests external HAK archives and TLK files into structured source directories.
- `Analyze-ItemBlueprintErf.ps1` / `Analyze-ItemHak.ps1`: Analyzes item blueprints and ERF resources for consistency.
- `Invoke-NwnCrunch.ps1` / `Invoke-NwnMdlComp.ps1`: Subprocess invocation wrappers for NWN texture crunching and model compilation.
- `Invoke-SrnRetirementAudit.ps1`: Read-only retirement audit verifying dependency clearance before worktree retirement.

### Subdirectories & Subsystems
- [Heads Pipeline](./heads/README.md): Head production pipeline, landmark fitting, neck closure/taper auditing, and PBR/PLT material generation.
- [PhenoMorpher](./phenomorpher/README.md): Numerical morphology fitting, continuous mesh morphing, animation library extraction, and static armor retargeting.
- [Phenotypes Toolchain](./phenotypes/README.md): Comprehensive pipeline for purpose-built and derived NWN character phenotypes, ComfyUI generation, RBF deformation, and multi-gate client testing.
- [Robes Pipeline](./robes/README.md): Linear-blend skinning, ASCII model tools, Blender drivers, and trial fixtures for robe modeling.
- [Import Profiles](./import-profiles/README.md): JSON import specifications for MDRNEE audio, item, placeable, tile, and talk table assets.

## Invariants
- `[shared_tools.py:tool]`: Local toolpaths for Python, Blender, and NWN binaries must reside in ignored local runtime bindings (`toolchain.lock.json`); machine-specific absolute paths are strictly forbidden in committed lockfiles.
- `[shared_tools.py:write_json]`: Atomic write operations using `fresh=True` enforce `xb` mode to prevent overwriting existing receipts or execution evidence.
- `[ci_scope.py:main]`: Committed dependency catalog `tools/test-impact.json` must remain byte-synchronized with `test_impact.catalog()`; out-of-sync catalogs fail CI immediately.
- `[ci_scope.py:plan]`: When git comparison base is missing or undiffable, the full test suite must be selected; test selection can never silently default to an empty set.
- `[Test-Repository.ps1]`: Source text files must maintain UTF-8 encoding with consistent newline conventions; 2DA files must maintain balanced column structures and valid line endings.

## Side Effects
- `[shared_tools.py:write_json]`: Writes temporary atomic swap files (`.tmp`) and updates `shared-tools.lock.json` and `toolchain.lock.json`.
- `[ci_scope.py:main]`: Spawns git diff subprocesses and writes planned CI matrix output files to disk.
- `[Build-Haks.ps1]`: Spawns external packaging binaries to assemble and write binary HAK archive files.
- `[Test-Repository.ps1]`: Executes Pester tests and Python test suites across the repository.

## Verification
- Run: `Verify.cmd`
