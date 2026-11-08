# Headbatch Compatibility

## Overview
Compatibility and validation shims for running headbatch workloads against external runtimes and hardware constraints. This package provides tools to probe ComfyUI safetensors model loaders in an isolated CPU child process before consuming GPU budgets, supervise headbatch design generation under strict GPU VRAM limits and system RAM floors with automated prompt interruption on breach, and apply Windows-native memory mapping patches for safetensors loading.

## Interface
- [`check_comfy_loader.py:sha(path)`](./check_comfy_loader.py#L15-L17): Computes SHA-256 digest of a target file.
- [`check_comfy_loader.py:check_model(path, load, torch)`](./check_comfy_loader.py#L20-L47): Probes safetensors model file headers, tensor metadata, tensor names, dimensions, byte lengths, and byte contents against direct file offsets.
- [`check_comfy_loader.py:main()`](./check_comfy_loader.py#L50-L79): CLI entry point probing safetensors models via bound isolated ComfyUI Python interpreter.
- [`run_design_with_vram_limit.py:request(endpoint, route, data=None)`](./run_design_with_vram_limit.py#L26-L30): Dispatches JSON requests to the ComfyUI HTTP REST API.
- [`run_design_with_vram_limit.py:design_prompts(rows, base, input_root)`](./run_design_with_vram_limit.py#L33-L44): Identifies prompt IDs belonging to a specific head and seed prefix in the active ComfyUI queue.
- [`run_design_with_vram_limit.py:main()`](./run_design_with_vram_limit.py#L47-L148): CLI entry point supervising headbatch design execution under active VRAM and RAM monitoring, interrupting owned prompts if resource limits are exceeded.
- [`comfyui-0.42.5-windows-native-mmap.patch`](./comfyui-0.42.5-windows-native-mmap.patch#L1-L20): Patch enabling Windows-native safetensors memory mapping (`SRN_HEADKIT_NATIVE_MMAP=1`) via `comfy_aimdo.control`.

## Invariants
- `[check_comfy_loader.py:main]`: Bound Comfy interpreter executable must match the recorded `sha256` in startup configuration before child execution.
- `[check_comfy_loader.py:main]`: Subprocess probe execution requires the bound isolated Python interpreter (`sys.flags.isolated` is true).
- `[check_comfy_loader.py:check_model]`: Safetensors header size must satisfy `0 < header_size <= 100_000_000` bytes.
- `[check_comfy_loader.py:check_model]`: Loaded tensor keys and shapes must strictly match the safetensors JSON header metadata without truncation.
- `[run_design_with_vram_limit.py:main]`: `memoryLimitBytes` must be a positive integer and `minimumFreeRAMGiB` must be nonnegative.
- `[run_design_with_vram_limit.py:main]`: Active ComfyUI runtime configuration session must match the startup configuration path and SHA-256 hash.
- `[run_design_with_vram_limit.py:main]`: Queue must be completely empty (`queue_running` and `queue_pending` both empty) before dispatching a design run.
- `[run_design_with_vram_limit.py:main]`: A measured VRAM limit breach, RAM floor breach, or sampler failure triggers immediate cancellation of owned prompt IDs via ComfyUI `/interrupt`.

## Side Effects
- `[check_comfy_loader.py:main]`: Launches child Python subprocesses with `faulthandler` enabled and isolated interpreter flags.
- `[run_design_with_vram_limit.py:main]`: Spawns background `nvidia-smi` sampling process polling memory every 250ms.
- `[run_design_with_vram_limit.py:main]`: Spawns child runner process executing `run_headbatch.py design`.
- `[run_design_with_vram_limit.py:main]`: Creates directory `runtime/vram/{head}-s{seed}/` and writes `samples.csv`, `dispatch.log`, and `summary.json`.
- `[run_design_with_vram_limit.py:request]`: Performs network HTTP POST and GET requests to local ComfyUI API (`/queue`, `/interrupt`, `/headkit/preparation-identity`).

## Verification
- Run: `pytest tools/headbatch`
