# Comfy Nodes (`tools/headkit/comfy_nodes`)

## Overview
Custom ComfyUI extension package and runtime adapter (`custom_nodes/srn_headkit`) providing verified model loaders, lossless shape/field checkpoints, single-primitive GLB transport, and controlled deployment/runtime-file provenance. Startup verifies frozen inventories before importing ComfyUI, uses an empty bytecode-cache location and loopback endpoint, and rechecks the session and files on requests and exit. Trusted plugins and process state are the boundary: production checks do not compare live bytecode, classes or constants to source and cannot detect temporarily changed-and-restored files between checks.

## Interface
- `HeadkitSaveShapeV1`: ComfyUI node saving sparse Pixal Trellis.2 shape latents into validated NPZ archives.
- `HeadkitLoadShapeV1`: ComfyUI node restoring sparse shape latents onto CUDA device with hash verification.
- `HeadkitDecodeShapeV1`: ComfyUI node executing audited Trellis.2 VAE shape decoding with memory chunk throttling.
- `HeadkitSaveFieldV1`: ComfyUI node serializing 6-channel Trellis appearance voxel fields to NPZ.
- `HeadkitLoadMeshV1`: ComfyUI node loading and decoding single-primitive GLB meshes into Torch tensors.
- `VerificationPass`: Context-managed lexical verification boundary tracking file hashes, transient source buffers, and sampled process RSS.
- `verified_loader_mappings(core_nodes, folder_paths)`: Factory wrapping ComfyUI checkpoint loaders with path identity and hash checks.
- `verify_loader_models(expected, folder_paths, graph=None)`: Verifies model pins against folder paths and graph nodes.
- `bind_loader_models(graph, models)`: Replaces core ComfyUI loader nodes in execution graphs with hash-keyed verified adapters.
- `loader_models(graph, bindings, checkpoint_hashes)`: Resolves and hashes bound model paths for execution graphs.
- `model_choices(graph)`: Extracts unique model loader category and filename choices from execution graphs.
- `verify_model_file(category, name, path_identity_value, sha256, folder_paths)`: Validates model existence, path identity, and SHA-256 before loading.
- `path_identity(path)`: Computes normalized filesystem path identity SHA-256 digest.
- `capture_runtime_identity(folder_paths, comfy_source_inventory=None, *, session=None)`: Hashes active Python/Torch runtime files and environment state.
- `same_runtime_environment(current, baseline)`: Compares stable interpreter/runtime pins between execution passes.
- `seal_runtime_identity(payload)`: Computes deterministic fingerprint digest for runtime identity payloads.
- `runtime_members(roots)`: Performs file census across active runtime directories, filtering inactive packages.
- `capture_inventory(core, roots)`: Records canonical file paths and SHA-256 hashes across ComfyUI core and custom node roots.
- `load_inventory(path, expected_core)`: Parses and verifies frozen source roots deployment inventory.
- `verify_inventory(inventory)`: Checks that all files in a source inventory exist and match recorded hashes.
- `same_inventory(left, right)`: Compares two source inventory records for exact equivalence.
- `members(core, roots)`: Traverses source roots bottom-up, enforcing unlinked source file constraints.
- `loaded_source_code(roots)`: Retained legacy object/AST census for research and regression tests; not called by production startup or runtime identity.
- `verification_pass(name)`: Context manager yielding an active `VerificationPass` with automated logging and cleanup.
- `resident_bytes()`: Queries exact current process Resident Set Size (RSS) across Windows and POSIX systems.
- `start(path, receipt, *, execute=None)`: Launches controlled ComfyUI subprocess under pinned Python with isolated environment.
- `verify_deployment(path)`: Validates deployment configuration, runtime interpreter, and source inventories before launch.
- `session_context(expected_core)`: Validates active controlled session tokens, arguments, and deployment configuration.
- `launch_arguments(config)`: Constructs validated CLI arguments and environment flags for controlled ComfyUI launch.
- `validate(arrays, meta)`: Validates schema, coordinate ranges, and array dimensions of Pixal sparse shape latents.
- `read(path)`: Loads and validates sparse shape latent arrays and metadata from NPZ archive.
- `write(path, arrays, meta)`: Validates and writes sparse shape latent arrays and metadata to NPZ archive.
- `load(payload)`: Parses and validates uncompressed single-primitive GLB binary containers.
- `arrays(d, b, p)`: Extracts position and triangle index numpy arrays from validated GLB primitives.
- `accessor(d, b, index)`: Extracts typed numpy array slices from GLB buffer views and accessors.
- `encode(d, b)`: Packs JSON document and binary payload into standard GLB container format.
- `verified_sources(requested_roots, *, session=None)`: Retained legacy execution-proof helper; not part of the active adapter request path.
- `NODE_CLASS_MAPPINGS`: Dictionary registering custom nodes with ComfyUI runtime.
- `HEAVY_VERIFICATION_LOCK`: Reentrant lock guarding concurrent filesystem and memory verification passes.
- `CURRENT_PASS`: Thread/context-local variable storing the active `VerificationPass` instance.
- `STANDARD_MODEL_FIELDS`, `VERIFIED_LOADER_TYPES`, `MODEL_PIN_FIELDS`: Dictionaries defining loader node wrapping specifications.
- `KEYS`: Set of required dictionary keys for Pixal shape latent transport.
- `attested_session(folder_paths)`, `attested_context(folder_paths, session)`, `attested_inventory(folder_paths)`: Attested mode for a server another program started: writes and re-proves the launch record (`<user dir>/headkit/headkit-attested-launch.json`) and captures the core/custom-node source census.
- HTTP Routes (registered on ComfyUI `PromptServer`):
  - `GET /headkit/runtime-identity`: Endpoint returning runtime verification audit reports and active file pins.
  - `GET /headkit/preparation-identity`: Endpoint returning planning runtime baseline identity.
  - `POST /headkit/verify-loader-models`: Endpoint verifying graph model loader choices against reviewed pins.

## Invariants
- `[transport:validate]` Requires exact shape latent keys `{'samples', 'coords', 'coord_counts', 'coord_resolution', 'type', 'model_frame'}`; `type` must be `'trellis2'`; `model_frame` must be `'z_up'` or `'y_up'`; `coord_resolution` must be a positive integer; coordinate batch index must be zero; coordinates must lie within `[0, coord_resolution)`.
- `[gltf:load]` Reject multi-mesh, transformed scene nodes (`matrix`, `rotation`, `translation`, `scale`), multiple scenes, skins, animations, and non-whitelisted extensions. Exactly one visible mesh and one primitive mode 4 (triangles) allowed.
- `[model_resolution:verify_loader_models]` Model choices must be simple filenames (no directory separators or relative segments). Loader nodes must exactly match pinned SHA-256 hashes and normalized path identities.
- `[runtime_identity:capture_runtime_identity]` Symlinks and Windows reparse directory/file junctions are strictly prohibited in runtime and source trees.
- `[managed_startup:session_context]` Process must run under pinned Python with isolated flags (`-I -B`). Controlled listen host is restricted strictly to loopback `127.0.0.1`.
- `[verification:VerificationPass]` Verification passes are isolated boundaries; pass cannot be reopened or queried once closed. Source retention buffer is capped at 32 MiB total and 1 MiB per file.
- `[managed_startup / runtime_identity]` Frozen deployment membership and file hashes, declared runtime files and controlled session must match on startup, request and exit checks. Hot reload is unsupported. The retired object/AST census does not define the production contract.
- `[attested]` A server with no controlled session (Comfy Desktop) reports an attested identity: launch record, source census and runtime census, re-proved on every runtime-identity request. It is usable only through an approved snapshot (`tools/headkit/attestation.py`); a failed controlled session never falls back to it.

## Side Effects
- `[transport:write]` Creates new NPZ archive with shape latent arrays and metadata; fails if destination file exists (`'xb'` mode).
- `[nodes:HeadkitSaveShapeV1.save]` Writes NPZ checkpoint to ComfyUI output directory and validates roundtrip integrity.
- `[nodes:HeadkitDecodeShapeV1.decode]` Temporarily patches `flexgemm.get_recommended_chunk_mem` during decode execution and restores it in `finally` block; writes decode diagnostic JSON report to disk.
- `[nodes:HeadkitSaveFieldV1.save]` Serializes Trellis 6-channel appearance voxel field to NPZ in ComfyUI output directory.
- `[verification:verification_pass]` Spawns background thread sampling process RSS every 50ms; logs audit pass timings and memory counters.
- `[managed_startup:start]` Binds local loopback socket `127.0.0.1:port` with `SO_EXCLUSIVEADDRUSE` to probe port availability; modifies `os.environ`, `sys.argv`, and `sys.path`; creates temporary directories for bytecode and writes startup JSON receipt to disk.
- `[verified_startup:main]` Retained legacy execution-audit trampoline; the supported managed startup uses `runpy.run_path` after verifying the deployment.
- `[__init__]` Registers HTTP routes on ComfyUI `PromptServer.instance.routes` for runtime identity and model verification endpoints.

## Verification
- Run: `pytest tools/headkit`
