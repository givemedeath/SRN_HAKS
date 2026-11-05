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

Before the first design, verify the configured URL against the shared GPU scheduler and use the toolkit's controlled startup. An empty queue only shows that ComfyUI is listening. Require a successful `/headkit/runtime-identity` response for the session and startup-configuration hash you just bound. A refused identity blocks design and GPU dispatch. On Windows, the built-in GLSL nodes can prepend the ANGLE DLL directory to `PATH` during import. Measure the change with the pinned interpreter and declare the exact inventoried directory in `comfyStartup.importPathPrefixes` before generating a fresh startup configuration. Preserve each failed launch's evidence.

On the tested Windows ComfyUI 0.42.5 deployment, dynamic VRAM changes `aimdo_enabled` after import. If managed verification reports that specific mismatch, the upstream `--disable-dynamic-vram` option avoids it. Test the actual Flux text encoder in an isolated CPU process before spending a design launch. With safetensors 0.8.0, the static loader crashed inside Torch storage slicing on the first tensor of the large BF16 encoder. For that reproduced combination, the opt-in patch in `tools/headbatch/compat/comfyui-0.42.5-windows-native-mmap.patch` selects Comfy's own file-backed reader for Windows CPU safetensors when `SRN_HEADKIT_NATIVE_MMAP=1` is present in the declared startup environment. Apply only to a fresh private core after checking the original loader SHA-256 (`9320cf5c624e96acc1d9ec92ff120ed6387a2142707f3194cb21dd0d11ac2500`). Preserve the old source snapshot, install and freeze the new one, and check tensor names, shapes and sampled bytes against the actual model files. Run `run_headbatch.py --workspace DIR env tools/headbatch/compat/check_comfy_loader.py STARTUP.json MODEL.safetensors ...` with the actual models. A native crash exits the probe before any design launch. The patch keeps Comfy's dynamic GPU patcher disabled and respects `--disable-mmap`.

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

For a generated candidate, pass its original PNG under the workspace's `design/raw` to `setup`. Setup verifies the output and frozen spec from that proposal's receipt before recording the feature inventory. A later prompt edit can then be used for another seed without changing the earlier candidate's description.

To use the installed smaller text-only stack, set `"profile": "qwen21-int8-v1"` in the race design spec and bind the diffusion model, base encoder and VAE in `designBindings.models`, keyed by their exact filenames with path/SHA256 values. The profile uses 25 Euler/simple steps, CFG 1, 1024 square images and CPU prefix caching. It loads `qwen_image_2.1_int8_convrot.safetensors`, `qwen3vl_8b_int8_convrot.safetensors` and `qwen_image_2.1_vae_bf16.safetensors`. Prompt enhancement and image references are excluded from this profile. The default remains `flux2-turbo-v1`; existing Flux specs and its inpaint route retain their behavior. Each Qwen launch freezes the weight files and records their pins and profile in the proposal receipt. Model choice never resets the slot's attempts.

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

Before the first repair, compare slopes, inspect shells, record any required component selection, then run `review --slot cutdry HEAD`. It rebuilds the uncut master in temporary storage using the current fit, smoothing and shell selection. Use `--attempt attempt-NN` to replay a saved master with current cut settings.

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

`gpu` stops at 5 geometry submissions per slot, counted in `gpu/gpu.json` and, for older ledgers, from ComfyUI's numbering of the head's geometry files; at the cap, stop and ask the user. A `HEAD/geometry-cap-override` file records the user's exception. `design` stops the same way at 3 designs per slot, counting launches, and `design/design-cap-override-HEAD` records the exception. A design exception must be JSON such as `{"head": "troll-male-a", "maximumDesigns": 4, "approval": "the user's exact authorization"}`. Legacy blank/text design exceptions are refused. A refused or invalid design is reported and the rest still run. Every GPU run keeps its own folder under `gpu`, and a shape that fails the occiput check goes to `rejectedGeometry`, so the ledger keeps its shape and appearance pair. `manifest` holds the head lock from its first read to the replace, because the manifest and inputs are pinned, and refuses while a launch of that head is queued or running.

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

## Design VRAM supervision

For a whole-device budget, set workspace `comfy.memoryLimitBytes` in bytes and optionally `comfy.gpuIndex` (default 0). Set `comfy.minimumFreeRAMGiB` for a physical-RAM floor. The supervisor reuses the CPU slot gate's free-memory measurement. Run `run_headbatch.py --workspace DIR env tools/headbatch/compat/run_design_with_vram_limit.py DIR HEAD SEED`. It uses the bound controlled-startup identity, refuses a busy GPU queue, starts the normal headbatch design command, and saves 250 ms NVIDIA samples and a summary under `runtime/vram/HEAD-sSEED`. A measured breach interrupts only the matching prompt belonging to that workspace. It fails the supervised run even if an output was produced. Preserve that spent design attempt.

For the measured 12 GiB RTX 3060 deployment, the lower-memory profile uses upstream `--reserve-vram 3 --disable-async-offload --cpu-vae` alongside static VRAM and the checked native loader. Validate the complete run against the user's budget. Reserved headroom and sampled peaks do not prove an instantaneous allocator-level cap.

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

## Paired external references and face delivery

An external image must use 'setup HEAD DESIGN.png --reference-record RECORD.json
--approval "the user's exact selection"'. The record has kind
"headbatch-reference-v1", head, generator, the original prompt, a
design: {path, sha256} pin, and features strings for face, ears, brows, horns,
tusks, hair, beard, cyberware, piercings, tattoo and scars. State absences,
counts and anatomical sides explicitly. Image-left is character-right.
The current race prompt is never provenance for an external image.

For the paired route, add conditioning: {clay: {path, sha256},
detail: {path, sha256}, alignment: {...}}. Image paths resolve relative to the
record. Use transparent images with the same canvas and at least three measured,
named paired landmarks in alignment.landmarks; see headkit's paired-image
contract. 'reference-check HEAD RECORD.json --output NEW_FOLDER' checks pins,
alignment and silhouette overlap without recording approval. Its alignment
overlay remains a visual gate. Do not fabricate landmarks or copy a beauty
image into both roles. Workspace requirePairedReferences: true prevents setup
from falling back to bootstrap when the packet has no pair.

Use a smooth neutral clay for geometry: preserve the major hair forms, horn
curves, tusks, jaw, ears and cyberware silhouette. Remove fine strands, pores,
pigment patterns, ink, growth rings and shine. The detail image preserves identity
and silhouette under diffuse lighting, with restrained dermal contrast and clear
eyes/brows. Keep original selected art immutable. Conditioning edits still obey
the user's submission limits and require review. No source image proves rear
coverage.

Prepare prefers the complete pair even when design remains an input for
palette-row matching; a partial pair is refused. GPU calibration consumes the
reviewed prepare attempt, one shared mask/crop, separate geometry/detail images,
1024 normalization and 1.1 padding. Node 12 is the geometry output; node 13 is
detail. Their hashes survive partial resumes. FOV estimates outside 25-70 degrees
or differing by more than 8 degrees stop for investigation; geometry and
appearance share the detail estimate after that check. This numeric check does
not approve a camera or silhouette.

'setup --quality-profile face-v1' (or workspace headQualityProfile: "face-v1")
opts new heads into face UV density 3, face masks, feature-channel ownership,
face treatment, the quality gate, full shade range, shading-only stretching and
body-skin matching. Bind bodySkinReferences: {"RACE-SEX": "path/to/neck.plt"}
in the local workspace. Existing heads are not migrated. All UV, channel,
quality and visual gates remain; no automatic threshold reduction.

Hair, brows and beards use channel 1; iris only uses 8; Troll/orc horns and tusks
use 9 with the accessory shade distribution. Skin ink, dermal pigment, lips,
lids and eye whites stay on 0. Cyberware uses 2/3; both bind the armor palette.
Choose horn/tusk masks with seeded paint.protrusion and constrain cyberware
with spatial rules. Global colour thresholds alone are poor ownership evidence.

Paint operations also accept {"op":"mask","name":"skin-ink","faces":CONDITION}.
This emits a face mask without recolouring. tone.preserveSkinMasks: ["skin-ink"]
protects mapped skin in that named mask from smoothing and eyebrow-fringe refill.
It does not disable de-light, change channels, exempt quality metrics or preserve
a fixed ink hue across skin palette rows. Review those masks on the actual bake.

With the face profile, render produces 2K source-appearance and actual decoded
1K PLT atlases, clearly distinguished in its receipt, in clay, color-only and
material-lit modes. Four three-quarter views are included. The spooler routes
reviewed palette rows through quality before export. A diagnostic render cannot
be delivery completion; even a reviewed delivery render says it is waiting on
the client trial. Check four three-quarter client views, motion, a second palette
look and armor-controlled cyberware colours before appearance acceptance.

For GPU work, workspace comfy.memoryLimitBytes, minimumFreeRAMGiB and optional
gpuIndex now supervise calibration, geometry and appearance under the existing
single-GPU lock. Samples use whole-device VRAM and physical free RAM. Missing or
stale samples fail closed. A breach interrupts only the submitted prompt and
does not trigger an OOM retry. An unresolved submission leaves
HEAD/gpu/UNRECONCILED and blocks later GPU dispatch until its recorded prompt is
reconciled. Samples are evidence, not a hard allocator ceiling. Every geometry
submission still counts, including failed and reseeded work.


## Quality and efficiency safeguards (2026-11-05)

New GPU launches verify the current **reviewed prepare** through headkit's Runner,
including manifest/dependency hashes, source version, bindings, outputs and review
bytes. This happens for partial geometry and appearance resumes too. A legacy
calibration without that lineage must be recalibrated; no historical receipt is
rewritten. Recalibration archives and invalidates the old geometry/appearance.
Stage lists must be unique and ordered; `calibrate,appearance` is refused.

The usual `gpu HEAD` now stops with exit 3 after successful geometry/occiput
validation. Headbatch releases the shared GPU lease, acquires a RAM-gated CPU
slot, and draws `HEAD/gpu/geometry-review/geometry-NNNN/sheet.png`. Check horns,
jaw/chin, neck absence, rear skull and stray shells. The sheet is diagnostic clay,
not an anatomy pass. Hair below the jaw is allowed.

After the user reviews that exact submission:

```text
run_headbatch.py gpu-review HEAD --attempt geometry-NNNN --approval "USER WORDS"
run_headbatch.py gpu HEAD --stages appearance
```

The approval records `attempts: {HEAD: geometry-NNNN}`, the geometry/camera identity
and the exact sheet receipt. Changed shapes, calibration or evidence invalidate it.
A failed sheet can be retried with `review --slot gpuclay HEAD`, without spending
another GPU submission. Never write the approval for the user.

All headbatch workspaces use the shared tools root's `locks/gpu-INDEX` lease.
`toolsRoot` may explicitly bind that root in workspace.json; otherwise use normal
shared-tools resolution. Other GPU consumers must participate in the same device
lease or existing scheduler; this cooperative lock is not an OS-wide GPU quota.
Both GPU and design submission refuse a busy Comfy queue. No scheduler/server is
started or reconfigured by these changes.

CPU slot floors are now 6/8/10/13/16/16 GiB for slots 1-6. Workspace `ramGates`
may raise these floors, not remove them. GPU budget cancellation has an independent
watchdog and bounded control requests; it verifies the running prompt before using
the interrupt endpoint. Sampled device memory is still not an allocator hard limit.
Resource receipts include sampling cost and maximum observed sample interval.

For new Troll `face-v1` references, `alignment.featureChecks` must be
`{"horns":2,"tusks":2,"neck":"none","hairBelowJaw":true}`. Provide measured
`horn-left-root`, `horn-left-tip`, `horn-right-root`, `horn-right-tip`,
the equivalent four `tusk-*` marks, and `jaw-left`, `jaw-chin`, `jaw-right`.
Left/right means the character's anatomical side. Preparation writes separate
clay/detail/overlay crops and silhouette overlap for each feature, including below
the chin. These are review aids, not automated neck or horn acceptance. Old raw
references and earlier alignment receipts remain immutable; revised measurements
belong in a new reference record.

The face render profile supplies explicit diffuse diagnostic material constants
(roughness .8, metallic 0, opacity 1). A map may replace a constant only after removing
that constant. Missing or conflicting material inputs fail before Blender. Material-lit
renders are studio diagnostics, not an exact reproduction of NWN lighting.

New heads bind **both** `pal-armor01.tga` (metal1/layer 2) and `pal-armor02.tga`
(metal2/layer 3). An older head without the second palette needs an explicit local
binding before manifest regeneration; the tool never substitutes armor01 for it.
The actual SRN client palette still needs visual validation.

Each face-profile palette attempt draws row ramps and `review gamesize HEAD ATTEMPT`
evidence. The small sheet shows five views of the decoded 1K shade/layer maps, varying
skin, hair, iris, bone and used metal channels independently. Its 128px head framing
is an approximation, not a measured client distance. It always waits for visual
review before quality/export, even when the row numbers were approved earlier.
A failed sheet cannot advance the stage. Full delivery rendering stays at four
threads and retains every required view/resolution.

CPU receipts separate package verification, preflight, processing and post-verification
time, and record cumulative worker peak RSS. Launch profiles separate queue/guards,
input preparation, child runtime and launch overhead. GPU resource receipts record
sampled peaks. Use these measurements before proposing a persistent worker, more
concurrency, more UV density or a larger model. No persistent worker is enabled
without evidence that its benefit exceeds the extra state/invalidation cost.

Client trials add independent iris and bone palette looks. `anim` logs a
`HEAD_MOTION` event. Verify capture coverage with:

```text
run_headbatch.py env tools/heads/verify_head_trial.py --manifest RUNTIME.json --log CLIENT.log --captures CAPTURES.json --output REPORT.json
```

`CAPTURES.json` has kind `head-client-captures-v1`, exact `manifest` and `log`
path/SHA256 pins, and `captures`. Each capture supplies `actor`, `view`, a pinned
`frame`, and `inspectionEvent` (zero-based index in the parsed last session's entry
texts, after timestamp removal). A motion frame also supplies `motionEvent`.
Required per head: primary-look `three`, `threeleft`, `backright`, `backleft`, a
motion frame and a different palette look. The validator checks images, log events,
colours/slots and unchanged built HAK/module files. Coverage never writes a visual
approval or production acceptance.

New headbatch trial specs set `captureCoverageRequired: true`, carried into the
runtime manifest. Their verifier fails when `--captures` is omitted even if
slots and colours pass. Legacy manifests retain the separate log-only check.
Every report still requires human visual approval.
