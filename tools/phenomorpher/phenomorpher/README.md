# PhenoMorpher Package

## Overview
`phenomorpher` is the core Python package of the PhenoMorpher toolkit. It provides the stable numerical Python API (`phenomorpher.api`), the managed CLI command dispatcher (`phenomorpher.cli`), input declaration and verification helpers (`phenomorpher.inputs`), and JSON schemas for candidate bundles and assembly sidecars.

## Interface
### Public API (`phenomorpher.api`)
- `digest(path)`: Computes SHA-256 digest of a target file.
- `bound(root, row, verified_snapshot=None)`: Verifies path containment within root and checks SHA-256 hash match against snapshot.
- `verify_assets(root, manifest, verified_snapshot=None)`: Validates game-ready body manifest resources, verifying paths, hashes, and byte lengths.
- `fit_candidate(meshes, frames, motion, reference, policy=None)`: Freezes Stage 1 similarity transforms, checks input immutability, and executes Stage 2 morphology fitting.
- `load_recipe(path)`: Deserializes versioned candidate input bundles with typed NumPy arrays.
- `save_recipe(path, data)`: Serializes candidate input bundles and numeric array dtypes to JSON.
- `display_scene(stage, parents, output)`: Exports neutral diagnostic GLB files with derived display normals.
- Re-exported engine symbols: `fit_stage1`, `fit_stage2`, `geometry_hash`, `native_keys_hash`, `audit_connectors`, `assemble`, `rasterize`, `measure`, `cross_section`, `read_attributes`, `export_glb`, `derived_normals`, `convert_text`.

### CLI & Input Dispatch (`phenomorpher.cli`, `phenomorpher.inputs`)
- `cli.main(argv=None)`: Command-line dispatcher supporting subcommands (`doctor`, `catalog`, `verify-assets`, `measure`, `native-info`, `candidate`, `replay`, `convert-clothing`, `anim-library`, `compare-motion`, `downsample-textures`, `adopt-runtime`, `verify-runtime`, `audit-native`, `sweep`, `retarget-v2`, `armor-extract`, `armor-profiles`, `armor-convert`, `armor-publish`, `verify-armor`).
- `cli.snapshot()`: Loads frozen input hash mappings from the `SRN_VERIFIED_INPUTS` environment variable.
- `cli.declared(path)`: Ensures that a consumed file path exists in the frozen launch snapshot.
- `cli.fresh(path)`: Creates output directories, requiring that the target path does not already exist.
- `cli.assembly(root, path)`: Parses assembly sidecar JSON and validates rig and part bindings.
- `inputs.consumed(arguments)`: Computes the complete set of declared data files consumed by a given CLI command invocation.
- `inputs.installed_models(game_root, kinds=(MODEL_TYPE,))`: Resolves installed key files and BIF model references.
- `inputs.rooted(root, name)`: Verifies that a path remains strictly within the declared root directory.

### Subdirectories
- [Engine](./engine/README.md): Internal numerical backends for fitting, morphing, measurement, silhouette rasterization, and animation pipelines.

## Invariants
- `[api.py:fit_candidate]` **Proposal Purity**: API operations produce offline proposals and diagnostics; they never write or modify published body or animation resources.
- `[api.py:fit_candidate]` **Donor Identity**: Human Fit donor references (`human_male_fit`, `human_female_fit`) automatically preserve identity and bypass morphology deformation.
- `[api.py:fit_candidate]` **Motion Immutability**: Source animation keys must remain unchanged across morph operations; verified against `native_keys_hash`.
- `[cli.py:declared]`, `[cli.py:snapshot]` **Verified Execution Gate**: Data operations require launch through `run.py` with verified input pins (`SRN_VERIFIED_INPUTS`); running without declared pins raises an error.
- `[cli.py:fresh]` **Destination Isolation**: Output directories must be fresh and non-existent; existing folders are never overwritten.
- `[inputs.py:rooted]` **Root Confinement**: Consumed input paths must strictly reside inside the designated root directory without escaping.

## Side Effects
- `[api.py:save_recipe]` Writes JSON candidate recipe files to disk.
- `[api.py:display_scene]` Writes neutral diagnostic `.glb` files to disk.
- `[cli.py:main]` Writes measurement masks, candidate proposals, converted clothing models, animation libraries, downsampled textures, and armor packs to specified output directories.
- `[cli.py:snapshot]`, `[inputs.py:consumed]` Inspects filesystem and reads files to compute hashes and verify frozen inputs.

## Verification
- Run: `pytest tools/phenomorpher`
