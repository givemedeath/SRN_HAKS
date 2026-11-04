# Head batch orchestration

`tools/headbatch` runs many heads through headkit on one machine. Headkit turns one head's manifest into a checked NWN asset; headbatch decides what runs next, holds the CPU and GPU locks, refuses launches that past batches showed would fail, and passes the numeric gates. It adds no approval of its own: every launch still goes through `launch_shared_tool.py`, and every visual gate stays with a reviewer.

Run it with the bundled workspace Python, because `run_headbatch.py` launches with the interpreter that runs it.

## Workspace

A batch lives in one folder outside the repository. Its `workspace.json` holds every machine path, and the code in `tools/headbatch` holds none: `test_no_machine_paths_in_the_package` fails if one is added. Relative paths resolve against the workspace folder. Copy `tools/headbatch/workspace.example.json` to start.

Pass `--workspace DIR` or set `SRN_HEAD_WORKSPACE`.

| Key | Meaning |
|---|---|
| `toolchain`, `migrationReceipt` | Fresh local runtime binding and migration, from `docs/shared-tooling-and-workflow.md` |
| `headBindings` | Headkit bindings copied into each head |
| `designBindings`, `comfy` | Design and GPU work: bindings, ComfyUI `url` and `root` |
| `mdlCompiler`, `palettes`, `bodyNecks` | Per-head inputs for `setup` |
| `fitReferences`, `fitReferenceOverrides` | Decompiled stock heads, plus explicit models for prefixes with none (Trolls) |
| `landmarks` | Optional coarse face marks for the jaw guard; without them the jaw needs a visual review |
| `designReferences` | Optional species reference by race and sex |
| `game`, `trialBase`, `clientSettings` | Client trials: install paths, base HAKs and module, and an optional `settings.tml` |
| `slots` | Slot numbers this batch fills, from `docs/heads/slot-catalog.json`: `"elf-male": [20, 21]` gives `elf-male-a`, `elf-male-b` |
| `headsDirectory`, `hashCache`, `cpuSlots`, `loopBudget` | Optional. A `cpu-slots` file in the workspace changes the limit while launches wait |

Race constants that do not depend on the machine are in `tools/headbatch/races.json`.

## Commands

```text
run_headbatch.py design RACE HEAD:SEED[:BATCH] ...       design proposals from design/designs-RACE.json
run_headbatch.py setup HEAD DESIGN.png --approval TEXT   create a head from the picked design
run_headbatch.py run NAME prepare HEAD                   stages through the matte
run_headbatch.py gpu HEAD [--seed-offset N]              calibrate, geometry with occiput check, appearance
run_headbatch.py manifest HEAD                           rewrite the manifest from overrides.json
run_headbatch.py run NAME STAGES HEAD... [--approve STAGE --notes TEXT]
run_headbatch.py spool [--once]                          auto-advance queued heads
run_headbatch.py trial-spec RACE [--version N]           specs/trial-RACE-vN.json
run_headbatch.py trial NAME [--version N]                build trials/NAME-vN
run_headbatch.py env SCRIPT ARG...                       a probe with headkit and the bound packages on the path
```

## Guards

`run` refuses before taking a CPU slot:

- CRLF in pinned headkit code;
- unpinned files in the bound package tree, after removing stray bytecode;
- a head over its stage loop budget, unless `HEAD/budget-override-STAGE` exists;
- a repair on a head too close to its UV floor;
- an ownership stage with no rules;
- a repair approval whose neck cut can reach the mouth, unless `HEAD/jaw-reviewed` exists.

`gpu` stops at 5 geometry submissions per slot, counted in `gpu/gpu.json`; at the cap, stop and ask the user. A `HEAD/geometry-cap-override` file records the user's exception. `manifest` refuses while a launch of that head is queued or running, because the manifest is a pinned input. An `active-*.json` file in `launches/` left by a killed process names what to clear.

## Spooler

Drop JSON requests into the workspace's `spool` folder and run `spool`. The module docstring in `tools/headbatch/spool.py` gives the formats.

It launches each head separately and advances by itself only on numeric gates: unwrap to bake, palette to export when rows equal the pins in `spool/reviewed-rows.json`, export to native, native to render. Everything else lands in `spool/review.md` or `spool/attention.md`. A launch with no result goes to attention rather than passing silently.

It does not draw review sheets or change manifests. Reviewers make their own sheets with `env`, and set a UV floor or a neck cut in `overrides.json`.

## Before publishing

Run a client trial, then check the four three-quarter views, one motion frame and a second look. See the client trial section of `docs/heads/head-generation-toolkit.md`.

Every confirmed mistake gets a guard and a row in `docs/heads/race-heads-v1-runbook.md`. Runbook rows name the original batch scripts; the table below gives their replacements.

| Batch script | Replacement |
|---|---|
| `hk_batch.sh`, `hk_batch_v2.sh`, `hk.sh`, `hk_slots.sh`, `launch.sh` | `run` |
| `gpu_head.sh`, `gpu_batch.py` | `gpu`, `gpu_job.py` |
| `run_designs.sh` | `design` |
| `setup_head.py`, `make_manifest.py` | `setup`, `manifest` |
| `races.py` | `races.json`, workspace `slots` and reference keys |
| `trial_spec.py`, `trial.sh` | `trial-spec`, `trial` |
| `autospool.py` | `spool` |
| `hk_env.sh` | `env` |
| `jaw_guard.sh`, `jawcheck.py`, `uv_margin.py`, `unwrapcheck.py`, `pkg_extra.py`, `clean_pyc.py` | `guards.py` |
