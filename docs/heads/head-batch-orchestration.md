# Head batch orchestration

`tools/headbatch` runs many heads through headkit on one machine. Headkit turns one head's manifest into a checked NWN asset; headbatch decides what runs next, holds the CPU and GPU locks, refuses launches that past batches showed would fail, and passes the numeric gates. Every stage, GPU and design launch goes through `launch_shared_tool.py`; `review` and `env` run read-only tools and probes directly. Every visual gate stays with a reviewer. A manifest states some reviews before they can happen, because the toolkit loader requires them: `route_declarations` in `head_setup.py` lists each one and the gate that checks it.

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
| `landmarks` | Optional coarse face marks for the jaw guard; until the file exists the jaw needs a visual review |
| `designReferences` | Optional species reference by race and sex |
| `game`, `trialBase`, `clientSettings` | Client trials: install paths, base HAKs and module, and an optional `settings.tml` |
| `slots` | Slot numbers this batch fills, from `docs/heads/slot-catalog.json`: `"elf-male": [20, 21]` gives `elf-male-a`, `elf-male-b` |
| `headsDirectory`, `hashCache`, `cpuSlots`, `loopBudget` | Optional. A `cpu-slots` file in the workspace changes the limit while launches wait |
| `ramGates` | Optional `{slot: free GB}` a slot needs to start a job; replaces the defaults of 10, 13, 16 and 16 GB for slots 3 to 6 |
| `repairDefaults` | Optional replacement for the fine relief `presets` applies |

Race constants that do not depend on the machine are in `tools/headbatch/races.json`.

## Commands

```text
run_headbatch.py design RACE HEAD:SEED[:BATCH] ...       design proposals from design/designs-RACE.json
run_headbatch.py setup HEAD DESIGN.png --approval TEXT   create a head from the picked design
run_headbatch.py run NAME prepare HEAD                   stages through the matte
run_headbatch.py gpu HEAD [--stages S] [--seed-offset N] calibrate, geometry with occiput check, appearance
run_headbatch.py manifest HEAD                           rewrite the manifest from overrides.json
run_headbatch.py components HEAD --notes TEXT             record the reviewed shell selection
run_headbatch.py ownership HEAD RULES.json                record a reviewed ownership rule set
run_headbatch.py run NAME STAGES HEAD... [--approve STAGE --notes TEXT [--approve-attempt ATTEMPT]]
run_headbatch.py spool [--once]                          auto-advance queued heads
run_headbatch.py trial-spec RACE [--version N]           specs/trial-RACE-vN.json
run_headbatch.py trial NAME [--version N]                build trials/NAME-vN
run_headbatch.py presets HEAD... [--uv-only] [--apply] [--review-floor NOTES]
                                                         plan or apply the repair policies; exit 1 on HOLD
run_headbatch.py status                                  one line per head; flags WAITING ON REVIEW
run_headbatch.py review [--slot] TOOL ARG...             a sheet or diagnostic, run in the heads folder
run_headbatch.py env SCRIPT ARG...                       a probe with headkit and the bound packages on the path
```

## Review tools

`tools/headbatch/review` holds the sheets and read-only diagnostics. Each states its arguments in its docstring, and takes `HEAD` as a name in the heads folder. `--slot` waits for a CPU slot, for the heavy ones. None of them writes into `run`, and a sheet approves nothing.

| Check | Tools |
|---|---|
| Geometry | `clay` (uncut/final pair; `--two-sided` tells inverted precluster normals from a real shell), `chinprofile`, `backcount`, `hot`, `boundary`, `jaw` |
| Fit | `fitcheck` (profile and nose placements side by side) |
| Neck cut, before a repair | `slopescan` (seconds), `cutdry`, `cutreplay` (prints unverified for a skirt or several rings, which need the rewrap), `skirtzone` |
| Shells | `shells`, `cutshells` |
| Texture and rows | `bakeviews` (textured views and iso-line grid), `grid`, `own_draft` (draft ownership rules, no launch), `ownsheet` (a finished attempt's saved atlas), `rowramps` |
| Face marks | `design_landmarks OUT_DIR HEAD...` writes the `landmarks.json` the jaw guard reads; `OUT_DIR` must be absolute |

Quality-gate prototypes that headkit adopted are not here; nor are one-off audits from past batches.

## Presets

`presets` covers failures already known before a repair runs. It writes `overrides.json` with notes and regenerates the manifest, only with `--apply` and only when a policy changed something:

- **UV floor:** when the newest unwrap came within .01 of its floor or under it, `presets` proposes coverage minus .011 rounded down to .01. Lowering the floor records a review, so it takes `--review-floor NOTES`, saying what you checked, as well as `--apply`. With `--uv-only`, a floor under .20 reports HOLD: the head needs fewer charts. Otherwise the repair changes the mesh, so the new unwrap decides.
- **Neck reach:** when `landmarks` is set, `slopescan` finds the jaw. If it sits above the chin limit, the largest reach of .06, .04 and .03 that passes is used, otherwise HOLD. `HEAD/jaw-reviewed` skips this.
- **Fine relief:** the user-approved wide profile applies to non-Human heads that declare none. Workspace `repairDefaults`, `{"fineRelief": {...}, "skipRaces": [...]}`, replaces either key.

`--uv-only` is for a head whose repair is already approved: fine relief and the cut are repair keys, and changing them stales the repair (RUNBOOK 106).

## Guards

`run` refuses before taking a CPU slot:

- CRLF in pinned headkit code;
- unpinned files in the bound package tree, after removing stray bytecode;
- a head over its stage loop budget, unless `HEAD/budget-override-STAGE` exists;
- a repair on a head too close to its UV floor;
- export or a later stage on palette rows missing from `spool/reviewed-rows.json`;
- an ownership stage with no rules;
- a repair approval whose neck cut can reach the mouth, unless `HEAD/jaw-reviewed` exists.

`gpu` stops at 5 geometry submissions per slot, counted in `gpu/gpu.json` and, for older ledgers, from ComfyUI's numbering of the head's geometry files; at the cap, stop and ask the user. A `HEAD/geometry-cap-override` file records the user's exception. `design` stops the same way at 3 designs per slot, counting launches, and `design/design-cap-override-HEAD` records the exception. A refused or invalid design is reported and the rest still run. Every GPU run keeps its own folder under `gpu`, and a shape that fails the occiput check goes to `rejectedGeometry`, so the ledger keeps its shape and appearance pair. `manifest` holds the head lock from its first read to the replace, because the manifest and inputs are pinned, and refuses while a launch of that head is queued or running.

A `run` or `gpu` launch holds a lock on its head from queueing to its end, so a second launch of that head is refused. Head, CPU and GPU locks are held by the system for the process, so a killed launch leaves nothing to clear. Killing `run_headbatch.py` alone frees them while its launcher child and stage keep running: stop the child too, because headkit's own runner lock then refuses a relaunch until the stage ends.

## Spooler

Drop JSON requests into the workspace's `spool` folder and run `spool`; a second spooler on one workspace is refused. The module docstring in `tools/headbatch/spool.py` gives the formats.

It launches each head separately and advances by itself only on numeric gates: unwrap to bake, palette to export when rows equal the pins in `spool/reviewed-rows.json`, export to native, native to render. Everything else lands in `spool/review.md` or `spool/attention.md`. A launch with no result goes to attention rather than passing silently, and so does a bad request file or head: the file moves to `spool/done` and the batch keeps going. An approval names the attempt reviewed per head, and its launch refuses it under the head lock if that is no longer the current attempt. A review closes only when its launch has recorded the approval; a refused approval stays open with the reason. Export and later stages refuse rows missing from `spool/reviewed-rows.json` however they are launched. A queue file changed while its presets ran stays queued and is read afresh, and heads it already launched do not launch again. A stage that later runs closes its attention entry.

Each finished stage gets its evidence before it reaches the review list:

| Event | What the spooler does |
|---|---|
| Repair queued or approved as next | `presets --apply`; a HOLD goes to attention and no launch starts |
| Repair ran | Jaw result, stating when nothing could be checked; queues the clay pair in `spool/sheets`, and the skirt zone at its gap and at 3 cm when the head has a skirt |
| Neck cut left several shells | Queues `cutshells` from the uncut master |
| Unwrap failed on coverage | Attention, with the floor `presets --uv-only` proposes |
| Bake ran | Queues `bakeviews` |
| Ownership ran | Queues `ownsheet`: the saved atlas on the mesh it consumed |
| Palette ran | Draws `rowramps`, then checks the pins |

Queued sheets wait for a CPU slot in their own process, so a review line can arrive before its sheet. Each writes a log in `spool/sheets`, and one that exits nonzero goes to attention. A reused stage keeps the sheet it has, except `bakeviews` and `rowramps`, which always redraw. The spooler changes `overrides.json` only through `presets`, and never lowers a UV floor: that records a review, so a person runs `presets HEAD --uv-only --apply --review-floor NOTES`. Any other neck cut is a reviewer's edit.

## Before publishing

Run a client trial, then check the four three-quarter views, one motion frame and a second look. See the client trial section of `docs/heads/head-generation-toolkit.md`.

Every confirmed mistake gets a guard and a row in `docs/heads/race-heads-v1-runbook.md`. Runbook rows name the original batch scripts; the table below gives their replacements.

| Batch script | Replacement |
|---|---|
| `hk_batch.sh`, `hk_batch_v2.sh`, `hk.sh`, `hk_slots.sh`, `launch.sh` | `run` |
| `gpu_head.sh`, `gpu_batch.py` | `gpu`, `gpu_job.py` |
| `run_designs.sh` | `design` |
| `setup_head.py`, `make_manifest.py` | `setup`, `manifest` |
| `set_components.py`, `set_ownership.py` | `components`, `ownership` |
| `ram_gate.ps1` | `ramGates`, read each time a job asks for a slot |
| `races.py` | `races.json`, workspace `slots` and reference keys |
| `trial_spec.py`, `trial.sh` | `trial-spec`, `trial` |
| `autospool.py` | `spool` |
| `hk_env.sh` | `env` |
| `preset_policy.py` | `presets` |
| `status.sh` | `status` |
| `bakeviews.sh` | `review bakeviews` |
| `review-kit/*.py`, `own_draft.py` | `review TOOL`, except `stagepins` and `uvtrial`, which were not moved |
| `jaw_guard.sh`, `jawcheck.py`, `uv_margin.py`, `unwrapcheck.py`, `pkg_extra.py`, `clean_pyc.py` | `guards.py` |
| `pyc_guard.ps1` | `run` cleans before queueing and again on taking its slot; no watcher runs during a stage |
