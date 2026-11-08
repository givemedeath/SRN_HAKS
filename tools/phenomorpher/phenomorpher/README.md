# PhenoMorpher Core Package

## Overview
`phenomorpher` is the core package of the PhenoMorpher toolkit. It exposes a stable Python API (`phenomorpher.api`), a strict CLI dispatch runner (`phenomorpher.cli`), and deterministic consumed input enumeration (`phenomorpher.inputs`) for NWN body measurement, phenotype proposal generation, and modular clothing and stock armor conversion.

## Interface
- **Public API (`phenomorpher.api`)**:
  - `[api.py:fit_candidate]`: Computes two-stage phenotype proposal (Stage 1 similarity placement + Stage 2 broad morphology deformation).
  - `[api.py:audit_connectors]`: Audits connector surface continuity, coverage, and penetration gates across body part boundaries.
  - `[api.py:assemble]`: Combines body parts into a unified static rest model.
  - `[api.py:measure]`: Computes bounding dimensions and geometric cross-sections from assembled parts.
  - `[api.py:cross_section]`: Extracts sliced planar polygon contours.
  - `[api.py:rasterize]`: Generates 2 mm/px orthographic silhouette binary masks.
  - `[api.py:read_attributes]`: Extracts native source mesh attributes (UVs, materials, bone weights).
  - `[api.py:convert_text]`: Parses and transforms ASCII MDL text representations.
  - `[api.py:verify_assets]`: Validates game-ready body release manifest against filesystem bytes and sha256 hashes.
  - `[api.py:load_recipe]`: Deserializes JSON candidate input recipes into typed numpy arrays.
  - `[api.py:save_recipe]`: Serializes candidate input recipes preserving numpy array dtypes.
  - `[api.py:display_scene]`: Exports neutral diagnostic GLBs with derived normals.
  - `[api.py:bound]`: Resolves and verifies SHA-256 integrity of root-scoped source bindings.
  - `[api.py:digest]`: Computes SHA-256 hash of a file stream.
- **CLI & Input Dispatch**:
  - `[cli.py:main]`: Entry point for managed CLI commands (`doctor`, `catalog`, `verify-assets`, `measure`, `candidate`, `replay`, `convert-clothing`, `anim-library`, `compare-motion`, `downsample-textures`, `adopt-runtime`, `audit-native`, `sweep`, `mdl-compile`, `mdl-decompile`, `armor-extract`, `armor-profiles`, `armor-convert`, `armor-publish`, `verify-armor`, `retarget-v2`, `verify-runtime`, `rebase-roots`).
  - `[cli.py:Strict]`: Strict ArgumentParser subclass that disallows option abbreviations.
  - `[inputs.py:consumed]`: Strict parser and validator that deterministically enumerates consumed file paths for any CLI invocation.
  - `[inputs.py:installed_models]`: Scans NWN game installation key files and BIFs to resolve model dependencies.
  - `[inputs.py:key_table]`: Parses NWN KEY V1 index headers and BIF routing tables.
- **Subdirectories**:
  - [engine](./engine/README.md): Internal numerical backends for anatomy deformation, silhouette rasterization, connector surface continuity, Neverblender compilation, and runtime rules.

## Invariants
- `[api.py:bound]`: Source bindings must resolve strictly within the declared root and match the recorded SHA-256 digest (`ValueError('Source binding escaped root')` or `ValueError('Escaped or stale source binding')`).
- `[api.py:fit_candidate]`: Morphing must preserve the frozen first pass and source geometry (`geometry_hash` invariant check); source animation keys must remain unchanged; Human Fit controls (`human_male_fit`, `human_female_fit`) automatically follow the exact identity path.
- `[api.py:load_recipe]`: Recipe arrays must be strictly numeric (`biuf` dtypes, itemsize <= 8, size <= 16M elements, finite values with no NaN/Inf).
- `[cli.py:Strict]` & `[inputs.py:consumed]`: CLI options must be spelled in full, once, without abbreviations or `--name=value` assignment syntax; every file accessed during a data run must be pre-declared in `SRN_VERIFIED_INPUTS`.

## Side Effects
- `[api.py:save_recipe]`: Writes JSON recipe files to disk.
- `[api.py:display_scene]`: Exports diagnostic GLB files to disk.
- `[cli.py:main]`: Executes CLI subcommands, creating output directories, writing receipts, JSON summaries, downsampled textures, and compiled model binaries.

## Verification
- Run: `pytest tools/phenomorpher`
