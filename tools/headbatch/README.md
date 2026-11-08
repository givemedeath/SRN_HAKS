# Headbatch Orchestration

## Overview
Orchestrates multi-head generation, GPU inference, stage progression, and automated spooling through `headkit` on local workstations. Headbatch manages per-head directory lifecycles, enforces runbook invariants and submission limits, supervises GPU memory budgets, provides auto-advancement for numerical gates, and generates client trial modules. Machine paths are strictly isolated in external `workspace.json` configurations.

## Interface
### Subdirectories & Component Blueprints
- [Headbatch Compatibility](./compat/README.md): Runtime compatibility shims, ComfyUI safetensors loader probe, and VRAM limit supervisor.
- [Headbatch Review Tools](./review/README.md): Read-only visual review tools, contact sheet generators, and stage diagnostic scripts.

### CLI Entry Point & Pipeline Execution
- [`run_headbatch.py:main()`](./run_headbatch.py#L48-L219): Top-level CLI entry point managing `setup`, `manifest`, `components`, `ownership`, `run`, `gpu`, `gpu-review`, `design`, `trial`, `spool`, `presets`, `status`, and `review` subcommands.
- [`run_headbatch.py:review(workspace, tool, arguments, slot)`](./run_headbatch.py#L22-L33): Executes a diagnostic review tool from `./review/` within the workspace environment and optional CPU slot lease.

### Workspace & Execution Management
- [`workspace.py:Workspace`](./workspace.py#L52-L136): Encapsulates workspace paths, tool bindings, slot allocation, and isolated Python subprocess environments.
- [`workspace.py:prefix(race, gender)`](./workspace.py#L35-L49): Maps race and gender combinations to NWN model prefixes.
- [`launcher.py:run_stages(workspace, args)`](./launcher.py#L88-L121): Executes stage sequences sequentially with timing metrics and guard verification.
- [`launcher.py:run_gpu(workspace, head, extra)`](./launcher.py#L198-L232): Launches GPU calibration, geometry, or appearance jobs under GPU host leasing.
- [`launcher.py:cpu_slot(workspace)`](./launcher.py#L48-L62): Context manager acquiring exclusive CPU slot lease.
- [`launcher.py:gpu_host_lease(workspace)`](./launcher.py#L65-L75): Context manager securing host-wide GPU execution lease.

### Head Setup & File Management
- [`head_setup.py:set_up(workspace, head, design, ...)`](./head_setup.py#L254-L320): Initializes a head folder from a design receipt, sets up neck cut parameters, and records approval.
- [`head_setup.py:write_manifest(workspace, head)`](./head_setup.py#L125-L162): Generates and writes `manifest.json` synthesizing design receipts, overrides, and GPU outputs.
- [`head_setup.py:revise_clay(workspace, head, replacement_clay, approval)`](./head_setup.py#L231-L248): Replaces geometry clay while preserving GPU ledger history.
- [`head_files.py:write_json(path, data, fresh=False)`](./head_files.py#L18-L32): Atomically writes formatted JSON via temporary file rename.
- [`head_files.py:state(head)`](./head_files.py#L48-L64): Inspects head directory to determine pipeline stage completion state.
- [`head_files.py:fit_matrix(head)`](./head_files.py#L71-L75): Loads reviewed 4x4 coordinate transformation matrix from `fit/matrix.json`.

### Pipeline Invariants & Safety Guards
- [`guards.py:Refused`](./guards.py#L17): Exception raised when a safety precondition fails before dispatch.
- [`guards.py:geometry_cap(head)`](./guards.py#L124-L131): Enforces submission limits (maximum 5 submissions per model).
- [`guards.py:head_lock(head)`](./guards.py#L208-L221): Context manager acquiring file-based mutual exclusion lock on a head directory.
- [`guards.py:only_spooler(workspace)`](./guards.py#L233-L243): Ensures single active spooler process across the workspace.
- [`guards.py:crlf_in_pinned_code(path)`](./guards.py#L52-L68): Rejects files containing CRLF line endings in pinned source directories.
- [`guards.py:clean_stray_bytecode(directory)`](./guards.py#L71-L82): Cleans orphan `__pycache__` and `.pyc` files.

### GPU Contract & Job Management
- [`gpu_contract.py:review_geometry(head, attempt, approval)`](./gpu_contract.py#L205-L213): Records explicit human approval for a geometry attempt.
- [`gpu_contract.py:require_geometry_review(head, attempt)`](./gpu_contract.py#L216-L222): Asserts geometry approval receipt exists before downstream unwrap/bake dispatch.
- [`gpu_contract.py:validate_geometry(head, attempt)`](./gpu_contract.py#L162-L194): Verifies bounding boxes, triangle count limits, and manifoldness.
- [`gpu_job.py:calibrate(comfy, head, seed)`](./gpu_job.py#L78-L101): Executes ComfyUI camera and depth calibration graph.
- [`gpu_job.py:geometry(comfy, head, seed, options)`](./gpu_job.py#L148-L191): Generates GLB shape, validates bounds, and records attempt ledger.
- [`gpu_job.py:appearance(comfy, head, seed)`](./gpu_job.py#L210-L242): Generates multi-view diffuse and normal appearance textures.
- [`resource_budget.py:Watchdog`](./resource_budget.py#L54-L85): Background thread monitoring GPU VRAM against configured thresholds.

### Spooling, Presets & Client Trials
- [`spool.py:Spool`](./spool.py#L18-L188): Auto-advance engine that advances eligible head stages, automatically passing numerical gates and pausing for visual reviews.
- [`presets.py:apply(workspace, head, uv_only, floor_review)`](./presets.py#L90-L108): Applies planned neck-cut slope, reach, and UV margins to `overrides.json`.
- [`trials.py:write_spec(workspace, race, version)`](./trials.py#L125-L162): Generates client test module specification JSON for both sexes of a race.
- [`trials.py:build(workspace, name, version)`](./trials.py#L173-L200): Compiles client trial HAK and module files.

## Invariants
- Machine-specific filesystem paths must reside solely in `workspace.json` and never in committed repository files.
- Geometry submissions are strictly capped at 5 attempts per head (`guards.geometry_cap`); model identity and prior attempts must never be reset to gain extra submissions.
- Stages require explicit prerequisite approvals (`guards.approved_attempt`, `gpu_contract.require_geometry_review`); visual gates are never bypassed or auto-approved.
- All file writes to head manifests and receipts must be atomic (`head_files.write_json`).
- Only a single spooler instance may run in a workspace at any time (`spool.lock`).
- Source code in pinned runtime trees must use LF line endings and be free of stray bytecode (`__pycache__`, `.pyc`).

## Side Effects
- Mutates head directories by creating attempt artifacts, receipts, manifests, and `.lock` files.
- Spawns child processes executing Python tools, ComfyUI client jobs, and NWN packaging tools.
- Sends HTTP requests to local ComfyUI endpoints (`/prompt`, `/history`, `/view`, `/interrupt`).
- Appends execution timing records to `{workspace}/timing.log`.
- Builds compiled NWN trial modules (`.mod`) and HAK archives (`.hak`).

## Verification
- Run: `pytest tools/headbatch`
