# Headkit (`tools/headkit`)

## Overview
Comprehensive generation, processing, fitting, UV unwrapping, texturing, quality auditing, and NWN native model compilation toolkit for 3D rigid character heads. Headkit coordinates local ComfyUI/Pixal generative models through strict provenance verifiers, runs an audited multi-stage CPU/GPU repair and fitting chain, enforces watertight geometry and continuous neck tapers ("no shelves"), bakes appearance voxel fields to 1K texture atlases, applies face parsing and PLT encoding, and validates production readiness against automated quality gates and engine model contracts.

## Interface
- Child Subdirectories:
  - [`comfy_nodes`](./comfy_nodes/README.md): Custom ComfyUI runtime adapter, verified model loaders, shape/field checkpoints, and controlled deployment/runtime-file provenance.
  - `examples`: Pipeline configuration and binding examples (`face-masks.json`, `multiview.json`, `texture-rules.json`).
  - `templates`: Workflow JSON templates for ComfyUI generation (`geometry.json`, `appearance.json`, `flux2-design.json`, `calibrate.json`).
- Core Orchestration & CLI:
  - `Runner`: Multi-stage pipeline executor generating immutable, input-hashed stage receipts (`runner.py`).
  - `main()`: CLI entry point coordinating stage batches, node installations, and processing chains (`__main__.py`).
  - `request_stage(name, args)`: Parses and executes an individual pipeline stage from CLI flags (`__main__.py`).
  - `launch_inputs(stage, manifest, paths)`: Compiles input argument dictionaries and evidence pins for a pipeline stage (`__main__.py`).
  - `install_nodes(target_dir)`: Deploys `comfy_nodes` adapter into ComfyUI custom nodes directory (`__main__.py`).
  - `replay(receipt_path)`: Replays historical head generation run from accepted stage receipts (`replay.py`).
  - `benchmark_verification(iterations)`: Benchmarks CPU verification pass hashing and AST analysis performance (`benchmark_verification.py`).
- ComfyUI Dispatch & Generation:
  - `Client`: HTTP client managing ComfyUI prompt submission, queuing, and status queries (`comfy.py`).
  - `CompletionClient`: Polling and collection client retrieving generated latent/image artifacts (`comfy.py`).
  - `compile_graph(template, bindings, model_pins)`: Compiles parameterised ComfyUI workflow JSON graphs (`comfy.py`).
  - `verify_comfy_runtime(client, inventory)`: Queries ComfyUI `/headkit/runtime-identity` endpoint to verify loaded code against disk inventory (`comfy.py`).
  - `verify_loader_models(client, graph, bindings)`: Verifies remote ComfyUI checkpoint loader paths and hashes (`comfy.py`).
  - `submit(client, graph)`: Submits prompt to ComfyUI server under shared GPU lock (`comfy.py`).
  - `collect(client, prompt_id)`: Retrieves execution output files from ComfyUI server (`comfy.py`).
  - `locked(lock_path)`: Context manager acquiring local GPU/ledger file mutex (`gpu_lock.py`).
  - `slot(client, local=None, *, prove=True)`: The one way any toolkit submits to ComfyUI: host GPU lease, proven server, idle queue (`shared_comfy.py`). `gpu_lease`, `live`, `wait_idle`, `status` are its parts.
  - `capture(client)`, `approve(client, snapshot, notes)`, `check(identity, local=None)`, `approval(local=None)`: Approved snapshots of a shared ComfyUI another program started, published in `<tools root>/comfy/shared-comfy.json` (`attestation.py`).
  - `prepare_request(manifest, paths, config)`: Constructs generation request parameters and model bindings (`generation.py`).
  - `compile_design(spec, prompt, template)`: Compiles Flux/Qwen design prompt and generation workflow (`design.py`).
  - `compile_inpaint(spec, prompt, guide, template)`: Compiles face inpainting workflow graph (`design.py`).
  - `GeneratedField`: Voxel appearance sampler for Trellis 6-channel generated fields (`field.py`).
  - `load_generated_field(path)`: Loads and validates NPZ voxel appearance field (`field.py`).
- Mesh, Fit & Alignment:
  - `propose(generated_mesh, reference_mesh)`: Computes rigid transformation (scale, rotation, translation) aligning generated head with reference head midline profile (`fit.py`).
  - `match(profile, reference_profile)`: Calculates profile alignment offsets and residual fitting errors (`fit.py`).
  - `physical(mesh)`: Audits and validates mesh manifold topology, vertex bounds, and closed shells using Manifold3D / LibIGL (`mesh.py`).
  - `checked_fit(mesh, reference)`: Verifies head scale and positional alignment against body neck bounding planes (`mesh.py`).
  - `cut(head_mesh, body_neck_mesh)`: Cuts head neck boundary to match body neck connector contour (`mesh.py`).
  - `taper_scale(z, policy)`: Evaluates smooth continuous connector taper without shelf discontinuities (`neck.py`).
  - `neck_policy(gender, phenotype)`: Loads neck radius, jawline height, and taper limits for phenotype body lock (`neck.py`).
  - `crossing_pairs(triangles_a, triangles_b)`: Computes exact triangle-triangle intersection pairs between mesh components (`intersections.py`).
  - `outer_faces(scene, origins, directions)`: CPU ray-casting triangle visibility queries via Embree4 (`rays.py`).
  - `back_coverage(mesh, camera)`: Measures occipital / back-of-head triangle visibility and coverage (`occiput.py`).
  - `restore(head_mesh, scalp_reference)`: Reconstructs scalp geometry patches beneath hair/horns (`scalp_patch.py`).
  - `smooth(mesh, regions, iterations)`: Applies Taubin smoothing steps over declared head-local regions (`relief.py`).
- UV & Atlas Unwrapping:
  - `unwrap(mesh, charts, rules)`: Unwraps mesh charts into 1024x1024 texture atlas with padding and island packing (`uv.py`).
  - `audit_imported_uvs(uvs, faces)`: Checks UV coordinate validity, winding order, overlap, and boundary margins (`uv.py`).
  - `raster_audit(uvs, faces, size)`: Checks subtexel coverage, chart overlap, and gutter spacing on texture atlas (`uv.py`).
  - `project_ownership(views, atlas_size)`: Maps view-angle pixel ownership to atlas texels via ray visibility (`projection.py`).
- Texture, Painting, Palette & Appearance:
  - `bake(mesh, field, resolution)`: Bakes 3D generated appearance field onto UV texture atlas (`textures.py`).
  - `tone_match(texture, reference_tone)`: Adjusts base skin tone to match NWN palette reference shades (`textures.py`).
  - `front_view(mesh, camera)`: Renders orthographic front face projection for feature parsing (`face_masks.py`).
  - `parse(front_image)`: Extracts soft face masks (eyes, brows, lips, beard, skin) from face landmarks (`face_masks.py`).
  - `treat(texture, masks, palette)`: Encodes PLT colour channels and applies skin preservation rules (`face_encode.py`).
  - `repair_channel(plt_channel, highlights)`: Removes isolated specular highlight halos at brow/ear boundaries (`feature_highlights.py`).
  - `paint(texture, rules)`: Applies configured 3D-selected recolors, seam fills, and region adjustments (`paint.py`).
  - `reconcile_atlas(texture, seams)`: Smooths color discontinuities across neighbouring UV island seams (`skin_seams.py`).
  - `plt_shades(texture)`: Extracts discrete palette shade index assignments from texture map (`palette.py`).
  - `match_shades(source_shades, reference_palette)`: Maps extracted colors to NWN 256-color palette entries (`palette.py`).
  - `quality(plt_texture, thresholds)`: Validates face quality gates (lip hair, upper eyelid hair, seam step ratio, skin median offset) (`quality.py`).
  - `restore(eye_bake, reference_eyes)`: Replaces front-bake eye regions with approved reference eye bitmaps (`reference_eyes.py`).
  - `upper_lids(masks, skin)`: Ensures upper eyelid regions maintain skin pigmentation rather than brow hair (`brow_edges.py`).
- Reusable Local Quality Corrections:
  - hair_base.py: Source-supported hair colour healing with 4K and strict-majority 1K coverage audits.
  - local_seal.py: Source-bound, reviewed local hair tunnel closure with protected geometry/UVs, bounded presets and full topology/cavity checks.
  - stock_encoding.py: Typed palette-index preservation after local repair, with actual geometry, ownership, decode, opacity, range and body-skin calibration checks.
  - Brow/upper-lid and highlight repairs project only onto the visible surface and preserve feature exclusions.
- Render & Native Compilation:
  - `render(blend_file, cameras, output_dir)`: Coordinates 4-thread Cycles GPU inspection renders (`blender_render.py`).
  - `lease(device_id)`: Claims exclusive Cycles GPU render device with VRAM memory watch (`render_device.py`).
  - `preview(stage_receipt, outputs)`: Generates quick diagnostic previews of texture rules and relief maps (`preview.py`).
  - `prepare(head_mesh, skeleton)`: Prepares head model geometry for NWN binary MDL export (`native.py`).
  - `audit_native(mdl_path)`: Verifies compiled NWN model hierarchy, node naming, and bounding volumes (`native.py`).
  - `decode(mdl_stream)`: Decodes NWN binary and ASCII MDL model structures (`native_reader.py`).
  - `model_contract(graph, bindings, checkpoints)`: Verifies ComfyUI checkpoint and loader model bindings against reviewed profiles (`model_contract.py`).
- Common Contracts & Utilities:
  - `verification_pass(name)`: Context manager running hash verification pass on required assets (`common.py`).
  - `require(condition, message)`: Assertion utility enforcing pipeline invariants (`common.py`).
  - `pin(path)`: Computes `{path, sha256}` dictionary for filesystem asset (`common.py`).
  - `bindings()`: Loads local runtime bindings from `local-bindings.json` (`common.py`).
  - `manifest(path)`: Loads and validates pipeline manifest JSON against `manifest.schema.json` (`common.py`).

## Invariants
- `[neck:taper_scale]` Connector tapers must form a continuous sloped transition between measured starting and ending contours; no flat shelves, rolled lips, cuff ledges, or secondary shoulder ledges are permitted at neck/body join boundaries.
- `[mesh:physical]` Meshes must be watertight, 2-manifold triangle meshes with no non-manifold edges, zero self-intersections, and positive oriented face volume.
- `[comfy:submit]` Only one generation job may hold the local GPU mutex at a time; concurrent dispatches to the ComfyUI server are strictly rejected.
- `[comfy:verify_comfy_runtime]` ComfyUI session, deployment membership and runtime file hashes must match the reviewed frozen inventories before dispatch. This assumes trusted plugins; it does not verify live Python objects against source.
- `[uv:audit_imported_uvs]` UV coordinates must be normalized to `[0, 1]`, with positive winding orientation and minimum gutter margins of 4 pixels at 1024x1024 resolution to prevent cross-island bleeding.
- `[quality:quality]` Head texture PLT maps must satisfy all numeric thresholds in `quality-thresholds.json`: lip hair contamination <= 0.02, upper lid hair contamination == 0, seam step ratio <= 1.25, and skin median offset within tolerance.
- `[native:prepare / audit_native]` Final head models must adhere strictly to the 20,000-triangle budget, exact node hierarchy with geometry parented to `neck` bone, and valid single-material palette texture references.
- `[model_contract:model_contract]` ComfyUI loader model choices must resolve to simple filenames without path traversal, matching exact reviewed SHA-256 checkpoint hashes and path identities.
- `[runner:Runner]` Stage receipts are immutable once written; subsequent pipeline stages must verify the SHA-256 digests of all declared input receipts before execution.

## Side Effects
- `[runner:Runner.run]` Executes pipeline stages, writing stage receipts, modified GLB/OBJ models, 1024x1024 TGA/PNG textures, and diagnostic JSON reports to the designated output directories.
- `[gpu_lock:locked]` Creates and locks filesystem mutex files (`gpu.lock` / ledger files) to coordinate access to local GPU resources.
- `[shared_comfy:slot]` Holds `<tools root>/locks/gpu-<index>` while proving the server and waiting for an idle queue; sets `SRN_GPU_LEASE` for children while held. `comfy.Client` refuses `/prompt` outside a slot.
- `[attestation:approve]` Writes the approved snapshot under `<tools root>/comfy/approved/` and replaces the shared registry `<tools root>/comfy/shared-comfy.json`.
- `[comfy:submit]` Dispatches HTTP POST requests to local ComfyUI server at `http://127.0.0.1:<port>` and writes received latent NPZ and image files to disk.
- `[blender_render:render]` Spawns Blender subprocesses in headless background mode (`blender -b`) using 4 Cycles render threads to write multi-view diagnostic PNG renders.
- `[native:prepare]` Spawns MDL compiler tools / NeverBlender scripts writing compiled binary `.mdl` and `.wok` models to workspace directories.
- `[__main__:install_nodes]` Copies or links `comfy_nodes` package into the configured ComfyUI `custom_nodes/srn_headkit` directory.

## Verification
- Run: `pytest tools/headkit`
