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
| `game`, `trialBase`, `clientSettings`, `trialInspection` | Client trials: install paths, base HAKs/module, optional settings and measured per-race framing |
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

To use the installed smaller text-only stack, set `"profile": "qwen21-int8-v1"` in the race design spec and bind the diffusion model, base encoder and VAE in `designBindings.models`, keyed by their exact filenames with path/SHA256 values. The profile uses 25 Euler/simple steps, CFG 1, 1024 square images and CPU prefix caching. It loads `qwen_image_2.1_int8_convrot.safetensors`, `qwen3vl_8b_int8_convrot.safetensors` and `qwen_image_2.1_vae_bf16.safetensors`. Prompt enhancement and image references are excluded from this profile; headbatch omits configured workspace species references from both its command and consumed inputs. The default remains `flux2-turbo-v1`; existing Flux specs and its inpaint route retain their behavior. Each Qwen launch freezes the weight files and records their pins and profile in the proposal receipt. Model choice never resets the slot's attempts.

## Review tools

`tools/headbatch/review` holds the sheets and read-only diagnostics. Each states its arguments in its docstring, and takes `HEAD` as a name in the heads folder. `--slot` waits for a CPU slot, for the heavy ones. None of them writes into `run`, and a sheet approves nothing.

| Check | Tools |
|---|---|
| Geometry | `repairclay HEAD ATTEMPT OUT.png` compares the before and final meshes with their saved normals in matched front, side, rear and under-jaw views. The spooler queues it for repairs with a staged fit. Use `clay` (uncut/final pair; `--two-sided` tells inverted precluster normals from a real shell), `chinprofile`, `backcount`, `hot`, `boundary`, `jaw` |
| Fit | `fitcheck` compares base profile and nose placements. For an explicit chin-down correction, set `fit.chinDownDegrees` on the head and rerun fit. Positive degrees rotate the fitted head about the head_g attachment in its local frame. An optional positive `fit.scaleMultiplier` scales uniformly. With nose alignment, `fit.realignAfterPose: true` translates the transformed nose back to the reference tip. Compare the exact receipts with `review --slot fitcheck --poses HEAD OLD_ATTEMPT NEW_ATTEMPT OUT.png`. The spooler also queues `review --slot fitcheck --reference HEAD ATTEMPT OUT.png` with matched front and side views of the bound reference and the posed head. Check the mouth seam, chin and eye heights on its millimetre rulers before neck work. If the whole head needs a vertical correction, `fit.heightOffset` shifts the finished pose in head-local metres. A negative value lowers it. To enlarge or shrink the fitted head uniformly while preserving its final XYZ placement and rotation, set `fit.localScaleMultiplier`. This multiplies all three local axes after positioning. Rerun fit and inspect the new sheet. |
| Neck cut, before a repair | `slopescan` (seconds), `cutdry`, `cutreplay` (prints unverified for a skirt or several rings, which need the rewrap), `skirtzone` |
| Shells | `shells`, `cutshells` |
| Texture and rows | `bakeviews` (textured views and iso-line grid), `grid`, `own_draft` (draft ownership rules, no launch), `ownsheet` (a finished attempt's saved atlas), `rowramps`; `irisrows HEAD ATTEMPT --rows N ...` previews explicit iris candidates before another palette pass |
| Face marks | `design_landmarks OUT_DIR HEAD...` writes the `landmarks.json` the jaw guard reads; `OUT_DIR` must be absolute. Check both halves of the sheet. When silhouette registration misses the actual mesh eyes or mouth, supply separate `design` and `front` pixel maps in `--override` and inspect the new sheet. `front` is in the 1536-pixel mesh view. |

After a rejected geometry, a selected replacement clay can use the original slot and diffuse image. Run `reference-check` on the new record and show the pair. Pass that exact check to `setup HEAD ORIGINAL_DESIGN --reference-record NEW_RECORD --revised-clay-check CHECK_JSON --approval WORDS`. This versions the clay under the head's inputs and preserves earlier submissions and conditioning. Run prepare and calibrate again before geometry. Review the new raw mesh before appearance.

When both appearance and clay require correction, use `setup HEAD NEW_DESIGN --reference-record NEW_RECORD --revised-pair-check CHECK_JSON --approval WORDS` after selection and a fresh reference-check. This explicit paired revision versions all three image roles and the feature inventory on the same slot. It preserves original inputs, reviews, rejected GPU submissions and submission counts. A current accepted geometry or unresolved GPU dispatch blocks revision. The clay-only route still refuses a changed design or diffuse image. Run and review prepare, recalibrate, and review the next raw mesh before appearance.

External ImageGen proposals and conditioning edits must write `design/submissions/HEAD/design-NNNN-submitted.json` before dispatch, including failures. Completion receipts do not spend another attempt. These records and legacy external-attempts/HEAD records share the same design cap as local launches; record an attempt in one submission ledger, not both.

Quality-gate prototypes that headkit adopted are not here; nor are one-off audits from past batches.

For a head that already ends at the jaw, compare `review --slot fitcheck --body-neck HEAD ATTEMPT OUT.png` in front, side, rear and under-jaw views. The blue surface is the actual body neck in the head attachment frame. If the uncut assembly is selected, use `setup --no-neck-cut` for a new head, or set the existing headÃ¢â‚¬â„¢s `mesh.neck` override to `null` and rebuild its manifest. Keep the body-neck binding for assembly review. The shell selection and the repair visual gate still apply.

For an uncut head, record the exact fit review before `slopescan` or `cutdry`. Both report the fitted jaw against the body neck and require a current fit approval. The dispatcher refuses a missing, pending, rejected or stale fit review before waiting for a CPU slot. Fit comparison and shell inspection remain available before that review.

For a head that needs a neck cut, before the first repair, compare slopes, inspect shells, record any required component selection, then run `review --slot cutdry HEAD`. It rebuilds the uncut master in temporary storage using the current fit, smoothing and shell selection. Use `--attempt attempt-NN` to replay a saved master with current cut settings. Use `--verify-cut NEW_FOLDER` for a first dry run that needs closure proof. It runs the real cut including any required rewrap and master audit, retains the before and after meshes under `review-evidence`, and stops before reduction. A band measurement or an unverified replay cannot establish closure.

For an unwrap stopped on coverage before face priority, `review --slot uvfinal HEAD ATTEMPT NEW_EVIDENCE_FOLDER` measures the final pack once against that attemptÃ¢â‚¬â„¢s policy and reviewed repair. Compare the two atlas sheets, achieved facial density and the final checks. This diagnostic does not change a floor or launch bake.

For a confirmed near miss, `mesh.uv.refinePacking: true` narrows the pack-density interval to 0.05% and checks for up to 1.5% spare scale when a changed layout fits on the first try. Use this for an explicitly selected retry. The coverage floor applies both before and after face priority.

For a four-view head, bind `profile: pixal-multiview-v1`, the eight measured cardinal inputs and the reviewed 20-degree rig using the toolkit multiview manifest example. Run prepare and review its exact result. Headbatch's calibrate step stages the eight prepared images at their common framing and fixed camera; it submits no MoGe prompt. Geometry requires explicit VRAM and free-RAM limits and `--single-submission`. The occiput and raw review gates apply before saved-shape appearance. A turnaround sheet alone does not establish calibrated camera measurements.

For a multiview Troll with paired horns, inspect the prepared front, left and right geometry and detail canvases before submitting. Mark landmarks in pixels on each prepared image, with origin at the upper left. In `HEAD/review-evidence/cardinal-horns.json`, set `images` to the six exact prepared pins named `geometryFront`, `detailFront`, `geometryLeft`, `detailLeft`, `geometryRight` and `detailRight`. Each of the two role keys (`geometry`, `detail`) has this structure:

```json
{"frontTips":[[165,100],[535,100]],"left":{"nearTip":[305,98],"farTip":null},"right":{"nearTip":[399,98],"farTip":null}}
```

Use measured coordinates for the actual head. Null records a fully occluded opposite tip. If any part of the far tip is visible, mark its coordinates. Headbatch compares the displacements along each image axis with the perspective allowance on the fixed 20-degree camera before spending a geometry submission. Check the ear, eye and jaw silhouettes too.

When a duplicate survives reconstruction, inspect the actual precluster from both enlarged temple profiles and both three-quarter angles. For a reviewed repair, bind the scalp outline to the exact original mesh SHA. A secondary temple restoration additionally binds the horn-corrected mesh SHA and the yaw offset to intact hair. Keep the real jaw and facially attached ears. Preview the bound generated color field with `review --slot gpuclay HEAD --field --precluster attempt-NN OUT.png` before unwrapping. The bake uses the same spatial donor as that preview for locally restored hair. Inspect the later PLT and client colors separately.

For a square chart of the normalized surface coordinates, run `review --slot materialchart HEAD attempt-NN xy OUT.png` for the front or use `zy` for the profile. For materials that overlap in colour, set `ownership.surfaceOutlines.NAME` to an object with `axes` (two of x, y and z, for example `xy`) and `points` (a closed contour expressed as normalized bounding-box pairs, with the closing edge implicit). Reference it as `{"mask":"NAME"}` in the rule. Combine the outline with a depth condition to protect hair behind a horn. Inspect both profiles in `own_draft`.

For a small duplicate material mark on intact geometry, a `paint.operations` entry with `op: heal` takes `target` and `donor` texture predicates and a normalized XYZ `offset` from target to donor. It samples four nearby surface texels, preserves other mapped texels and regenerates padding. On a head with clearly separable hair pigment, `ownership.hairMaskRequiresRule: true` limits brow and hair-lock assignments to already measured channel-1 rules. A conflicting profile needs correction.

A byte-identical, reviewed four-view prepare replay may reuse its original calibration for saved-shape appearance only. The launcher records both sets of pins and verifies all eight images and runtime identities.

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
- a head over its stage loop budget, unless `HEAD/budget-override-STAGE` contains the exact `head`, `stage`, a bounded integer `maximumAttempts`, and the reviewerÃ¢â‚¬â„¢s explicit `approval`;
- a repair on a head too close to its UV floor;
- export or a later stage on palette rows missing from `spool/reviewed-rows.json`;
- an ownership stage with no rules;
- a repair approval whose neck cut can reach the mouth, unless `HEAD/jaw-reviewed` exists.

`gpu` stops at 5 geometry submissions per slot, counted in `gpu/gpu.json` and, for older ledgers, from ComfyUI's numbering of the head's geometry files; at the cap, stop and ask the user. A `HEAD/geometry-cap-override` file records the user's exception as JSON with `head`, an integer `maximumSubmissions` and the exact `approval` words. `design` stops the same way at 3 designs per slot, counting launches, and `design/design-cap-override-HEAD` records the exception. A design exception must be JSON such as `{"head": "troll-male-a", "maximumDesigns": 4, "approval": "the user's exact authorization"}`. Legacy blank/text design exceptions are refused. A refused or invalid design is reported and the rest still run. Every GPU run keeps its own folder under `gpu`, and a shape that fails the occiput check goes to `rejectedGeometry`, so the ledger keeps its shape and appearance pair. `manifest` holds the head lock from its first read to the replace, because the manifest and inputs are pinned, and refuses while a launch of that head is queued or running.

A `run` or `gpu` launch holds a lock on its head from queueing to its end, so a second launch of that head is refused. Head, CPU and GPU locks are held by the system for the process, so a killed launch leaves nothing to clear. Killing `run_headbatch.py` alone frees them while its launcher child and stage keep running: stop the child too, because headkit's own runner lock then refuses a relaunch until the stage ends.

## Spooler

Drop JSON requests into the workspace's `spool` folder and run `spool`; a second spooler on one workspace is refused. The module docstring in `tools/headbatch/spool.py` gives the formats.

It launches each head separately and advances by itself only on numeric gates: unwrap to bake, palette to export when rows equal the pins in `spool/reviewed-rows.json`, export to native, native to render. Everything else lands in `spool/review.md` or `spool/attention.md`. A launch with no result goes to attention rather than passing silently, and so does a bad request file or head: the file moves to `spool/done` and the batch keeps going. An approval names the attempt reviewed per head, and its launch refuses it under the head lock if that is no longer the current attempt. A review closes only when its launch has recorded the approval; a refused approval stays open with the reason. Export and later stages refuse rows missing from `spool/reviewed-rows.json` however they are launched. A queue file changed while its presets ran stays queued and is read afresh, and heads it already launched do not launch again. A stage that later runs closes its attention entry.

Each finished stage gets its evidence before it reaches the review list:

| Event | What the spooler does |
|---|---|
| Repair queued or approved as next | `presets --apply`; a HOLD goes to attention and no launch starts |
| Precluster ran | Queues the eight-view clay sheet of the exact oriented mesh under `spool/sheets` before fit review. |
| Repair ran | Jaw result, stating when nothing could be checked; queues the clay pair in `spool/sheets`, and the skirt zone at its gap and at 3 cm when the head has a skirt |
| Neck cut left several shells | Queues `cutshells` from the uncut master |
| Unwrap failed on coverage | Attention, with the floor `presets --uv-only` proposes |
| Bake ran | Queues `bakeviews` |
| Ownership ran | Queues `ownsheet`: the saved atlas on the mesh it consumed |
| Palette ran | Draws `rowramps`, then checks the pins |

Queued sheets wait for a CPU slot in their own process, so a review line can arrive before its sheet. Each writes a log in `spool/sheets`, and one that exits nonzero goes to attention. A reused stage keeps the sheet it has, except `bakeviews` and `rowramps`, which always redraw. The spooler changes `overrides.json` only through `presets`, and never lowers a UV floor: that records a review, so a person runs `presets HEAD --uv-only --apply --review-floor NOTES`. Any other neck cut is a reviewer's edit.

## Design VRAM supervision

For a whole-device budget, set workspace `comfy.memoryLimitBytes` in bytes and optionally `comfy.gpuIndex` (default 0). Set `comfy.minimumFreeRAMGiB` for the live physical-RAM floor. For geometry with a measured cold-load peak, set `comfy.minimumStartRAMGiB` for headroom before each counted submission. Schedule the run outside competing texture jobs. The supervisor reuses the CPU slot gate's free-memory measurement. Run `run_headbatch.py --workspace DIR env tools/headbatch/compat/run_design_with_vram_limit.py DIR HEAD SEED`. It uses the bound controlled-startup identity, refuses a busy GPU queue, starts the normal headbatch design command, and saves 250 ms NVIDIA samples and a summary under `runtime/vram/HEAD-sSEED`. A measured breach interrupts only the matching prompt belonging to that workspace. It fails the supervised run even if an output was produced. Preserve that spent design attempt.

For design-image generation on the measured 12 GiB RTX 3060 deployment, the lower-memory profile uses upstream `--reserve-vram 3 --disable-async-offload --cpu-vae` alongside static VRAM and the checked native loader. Validate the complete run against the user's budget. Reserved headroom and sampled peaks do not prove an instantaneous allocator-level cap.

When refreshing `tools/test-impact.json` in a sparse worktree, include the complete tracked `docs/` and `.github/` trees before running the catalog builder and CI wiring checks. Missing documentation can otherwise appear as unrelated deleted dependencies. Wait for checkout hydration to finish, regenerate the catalog, and inspect its diff before committing it.

## Before publishing

Check current shipped resources and in-progress reservations before using slot-catalog blocks. The Troll collection now occupies slots 001Ã¢â‚¬â€œ020 for both sexes; see docs/heads/troll-head-reindex-v1.md. For authorized renumbering, use the bounded native renamer and whole-pack validation described there; filename-only changes leave internal model and PLT references behind.

Run the built private trial with `run_headbatch.py client RACE --version N`. This reserves every workspace CPU lane and the shared GPU until the owned client exits; do not run tests, generation or other heavy work alongside it. The private profile automatically enables a 30 FPS foreground / 10 FPS background limiter and a decorated window no larger than 1920x1080. Admission requires 6 GiB free RAM and an idle Comfy queue; the client is supervised at a 4 GiB live RAM floor and the 12 GB sampled device budget. It stops only its own process on unsafe memory, a session STOP file or the 180-second deadline. Session settings, ownership and memory receipts are under trials/client-sessions; runtime/current-client.json identifies the current session. Review four three-quarter views, one motion frame and a second look, move the pointer outside the scene before neutral captures, then close normally before the deadline and verify closure. See the client trial section of `docs/heads/head-generation-toolkit.md`.

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
not approve a camera or silhouette. At a calibration stop, run `gpu-camera HEAD --attempt calibrate` (or the exact retry directory, such as `calibrate-02`) for both normalized crops with their measured angles. The sheet and source hashes remain with that attempt. If the user chooses its in-range diffuse angle, pass `--detail-camera-attempt ATTEMPT --camera-approval "USER WORDS"` to a GPU run including calibration. Headbatch replays calibration to verify the current prepared inputs yield the same normalized pixels, graph and estimates before geometry. Both geometry and appearance then consume the exact reviewed diffuse angle. This spends no additional geometry submission for the camera check.

'setup --quality-profile face-v1' (or workspace headQualityProfile: "face-v1")
opts new heads into face UV density 3, face masks, feature-channel ownership,
face treatment, the quality gate, full shade range, shading-only stretching and
body-skin matching. Bind bodySkinReferences: {"RACE-SEX": "path/to/neck.plt"}
in the local workspace. Existing heads are not migrated. All UV, channel,
quality and visual gates remain; no automatic threshold reduction.

Hair, brows and beards use channel 1; iris only uses 8; Troll/orc horns and tusks
use 9 with the accessory shade distribution. Skin ink, dermal pigment, lips,
lids and eye whites stay on 0. Cyberware uses 2/3; both bind the armor palette.
Inspect both irises and upper lids at native resolution on the projected mask sheet.
If the parser clips an iris or extends a brow onto a lid, set `faceMasks.eyeContours`
in the local overrides. Bind `rgbSha256` to the raw RGB bytes of the exact masks
front render. For each anatomical side (`R` is image left, `L` image right), trace
`opening`, `iris` and `excludeBrow` as polygons of [x,y] pixel coordinates from
the top left. Trace only the visible iris inside the opening. Replay masks and
inspect the projected sheet before ownership. The quality check uses the same
traces against the decoded PLT.
The spooler also queues `review --slot eyereference HEAD ATTEMPT OUT.png` for
face-profile masks. This compares native reference and baked eye crops and saves
a hash-bound registration proposal; it never approves or applies it. Inspect each
opening, lid and iris before selecting the proposed `tone.referenceEyes` recipe and its matching `faceMasks.eyeContours`. The proposal includes source-RGB-bound opening, visible iris and skin-lid polygons and a third native overlay; it never approves them. Select both, then rerun/review masks and ownership before tone. Missing contours refuse before a CPU lane or tone attempt.
If a bake also blackens the lids, `includeLids: true` restores the reviewed
`eyeContours.excludeBrow` skin region with a soft edge and front-depth matching.
Only skin and iris texels change; hair, cyberware and hidden surfaces stay intact.
A changed front render or reference invalidates that recipe.

New face-profile heads enable `ownership.hairEarGuard`. Within confident ear
masks it restores hair-owned texels only when their color is clearly nearer the
skin reference than the hair reference. It preserves hair-colored strands and
cyberware. Inspect the actual ownership sheet; this guard does not approve ears
or replace measured hair and plate boundaries. Existing heads are not migrated.

Choose horn/tusk masks with seeded paint.protrusion and constrain cyberware
with spatial rules. Global colour thresholds alone are poor ownership evidence.

Paint operations also accept {"op":"mask","name":"skin-ink","faces":CONDITION}.
This emits a face mask without recolouring. tone.preserveSkinMasks: ["skin-ink"]
protects mapped skin in that named mask from smoothing and eyebrow-fringe refill.
It does not disable de-light, change channels, exempt quality metrics or preserve
a fixed ink hue across skin palette rows. Review those masks on the actual bake.

When one inferred material region carries excessive baked light, an opt-in
`tone.materialLight` recipe can darken broad lighting toward an intact measured
region of the same channel. Set `channel`, a `reference` predicate in normalized
mesh x/y/z or baked color, and optional `target`, `strength` (greater than 0, at most 1),
`minimumGain` (greater than 0, at most 1) and `neighbours` (32..512). It uses 3D surface neighbors
across chart seams, preserves fine texture, never brightens, and leaves other
mapped channels unchanged. Require at least 32 reference/target texels and inspect
the exact tone and decoded palette sheets. It is deliberately opt-in to preserve
intentional material color variations. No quality thresholds are reduced.

For body-pinned skin with excessive cheek contrast, `palette.skinShadeContrast` scales runtime shades around the body-neck median. Compare the decoded face at game size and retain the span, feature-focus, darkness and seam checks.

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

Geometry and appearance require a controlled server started without `--cpu-vae`. Trellis sends decoder inputs to the GPU. Headbatch checks the live server arguments before a chain reaches calibration or spends a submission. Keep the workspace memory guards enabled when switching from a design server. If model loading exhausts host RAM, a fresh controlled profile can disable host pinning with `--disable-pinned-memory`. Compare the first sample, the minimum available RAM and the peak device bytes in the launch resource receipt. Available RAM while idle does not include model-loading peaks.

New GPU launches verify the current **reviewed prepare** through headkit's Runner,
including manifest/dependency hashes, source version, bindings, outputs and review
bytes. This happens for partial geometry and appearance resumes too. A legacy
calibration without that lineage must be recalibrated; no historical receipt is
rewritten. Recalibration archives and invalidates the old geometry/appearance.
For a user-selected lower geometry grid after a memory stop, use
`run_headbatch.py gpu HEAD --stages geometry --shape-grid 1024 --single-submission`.
This reuses the verified calibration and changes only the Trellis shape upsample resolution.
The saved prompt records the grid even on failure. Single-submission mode suppresses both
the geometry OOM retry and reseed. Review the exact raw sheet before appearance. An open-occiput rejection keeps its own diagnostic sheet. Recover it, if missing, with `review --slot gpuclay HEAD --rejected-geometry geometry-NNNN`. Rejected submissions cannot authorize appearance.

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
Left/right means the character's anatomical side. For curved horns or tusks, also
measure named points along the outer arc (for example horn-left-curve-outer and
horn-left-curve-crown). Local comparison crops include every matching
FEATURE-SIDE-curve-* point as well as the root and tip; endpoints alone can hide
the middle of a curved feature. These points participate in the same bounded
global alignment and must be measured independently on both images.
Preparation writes separate
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

### New Troll defaults

Setup selects face-v1 for a new Troll. Supply the paired reference, body skin and parser bindings required by that profile. The palette stage measures candidate skin contrasts in the game-size face projection and records its decision in `skinFocusSearch`. A numeric reviewed contrast takes precedence. The independent quality gate still measures the exported palette.

Profile and nose fits bind the published r3 Troll build allowance at manifest generation. Export records the reference hash, factor and pivot. The compact references use the sex-specific allowance, while a recognized already enlarged donor uses 1.0. A custom reference requires verification of its scale frame. Landmark-calibrated routes retain their reviewed scale.

The workspace can set `comfy.multiviewGeometryStartRAMGiB` to reserve more host RAM specifically for four-view geometry. The normal admission and live limits still apply. The example reserves 22 GiB after a 17.49 GiB start failed during model loading. It is a measured lower-bound estimate, so the live guard remains necessary.

External proposals and clay/diffuse edits share the same design cap. Record every submission once in design/external-attempts/HEAD/NNN.json, preserving the input, disposition and any resulting image pin. The local design launcher includes these records automatically.

A GPU launch with a live host RAM cutoff waits for this workspaceÃ¢â‚¬â„¢s CPU workers to finish and reserves their lanes until dispatch returns. The CPU review sheet runs after releasing those lanes. The face-v1 setup profile uses refined UV packing at the normal thresholds.

For measured client framing, set workspace `trialInspection.RACE` to an `inspect`
object with per-prefix `height` and camera `distance` in meters. Derive eye height
from the current body skeleton attachment and exact fitted head; retain those
pins and measurements in workspace evidence. `trial-spec` includes the selected
framing automatically. Existing Troll defaults remain when no override is set.

For ordinary face-profile heads, ownership now queues `review --slot roles`
against its exact saved 1K atlas before tone. The preflight checks both iris
channels, whites, brow coverage, facial hair spill, missed locks and the existing game-size speck limit; its
hash-bound report blocks ownership approval/tone when missing, stale or failing.
Read-only `--candidate RULES.json` previews cannot satisfy that guard. Heads with
an existing `sourceHairRoles` audit retain their full-quality source audit.

New face profiles enable `ownership.browSeedGuard`: only semantic brow hairs
within eight front-render pixels of the refined core are restored to hair.
Existing manifests without an explicit reach retain three pixels. Every
feature-channel ownership pass separately protects upper-lid skin after channel
assignment, including when brow recovery is disabled. Early roles and final
quality reject hair on the confident upper-lid core independently of brow recall.
Reviewed eye exclusions, iris and metal ownership remain protected. For beards
whose highlights parsing changes to skin, the existing `overFaceMasks` hair rule
can preserve only hair connected in 3D to intact hair. Inspect candidate roles
and the exact saved ownership before tone; retain the final full quality gate.

New face profiles enable `ownership.lipSkinGuard`: connected beard protection cannot keep the detected mouth/lip interior on hair. Inspect the lip mask against the reference before selecting a correction. The saved ownership roles preflight and final quality check reject hair on its eroded semantic core, independently of upper-face hair spill (RUNBOOK 316).

The spooler also queues `review --slot hairgaps HEAD ATTEMPT OUTPUT` on ownership and `review --slot irisrows HEAD ATTEMPT` on palette. Hair-gap sheets mark source-semantic scalp hair left on skin; `--candidate RULES.json` saves a diagnostic atlas without spending a stage attempt. Preserve intended baldness and ear skin. Iris sheets compare the exact decoded runtime row to source appearance and ranked alternatives, so a saturated tattoo row cannot pass unnoticed in a small full-face sheet. These are evidence, never approval (RUNBOOK 317).

If color rules leave scalp curls on skin, `review --slot hairgaps HEAD ATTEMPT OUTPUT --repair-skin-hair` makes a diagnostic 4K atlas and matching source-hash-bound atlas configuration. It restores only skin-owned hair supported by the current masks, protecting eye/lip masks and other channels. Inspect the candidate sheet, baldness, ears and roles before selecting it. Add the pinned candidate as local input `ownership4k` and select its atlas configuration with `ownership`; normal attempt budgets, saved-ownership review and all downstream checks still apply (RUNBOOK 318). Candidate evidence never approves or spends a production stage attempt.

For GPU studio rendering, set workspace `renderDevice` to `{ "device": "GPU", "backend": "OPTIX", "gpuIndex": 0, "memoryLimitBytes": 12000000000 }` (the new workspace default). `manifest`/`setup` bind the same shared GPU lock and idle ComfyUI endpoint used by generation. An optional exact `deviceId` further restricts selection; PCI identity must match the sampled NVIDIA device. Per-head `render.compute` can explicitly select CPU. GPU jobs retain the normal CPU-slot/RAM admission and four host threads, serialize on the shared lane, and save sampled whole-device VRAM evidence. Failure never falls back to a long CPU render. All cameras, 2K/1K atlases, materials, samples and visual/client gates remain unchanged.

A connected molding rim at the very bottom of long hair can use an explicitly selected `mesh.lowerHairTrim` policy: `{"sourceSha256":"<exact precluster SHA>","heightFraction":0.08,"hairOnlyReviewed":true,"notes":"Describe the measured hair-only band below the complete jaw"}`. It runs automatically in precluster, requires alphaWrap exterior repair, and keeps the original mesh. It refuses more than 10% of height or faces, upper triangles, stale sources, and simultaneous scalp patches. The open trimmed rim is a working result: inspect the repaired closure and long-hair silhouette before accepting it. It does not cut the body neck or approve appearance.

For shoulder context, configure `bodyTorsoReferences` in workspace.json as a prefix-to-native-torso map (for example, pfe0 to your local pfe0_chest001.mdl). Setup stages that exact model as `inputs.bodyTorso`. The spooler automatically queues an upper-body sheet for each fit attempt; `review --slot fitassembly HEAD ATTEMPT NEW_SHEET.png` draws it directly. Its evidence freezes the actual skeleton, neck and torso, rejects inconsistent attachment frames, and leaves visual approval pending. The isolated neck part includes an internal cap, so use shoulder context to judge exposed throat length. `fit.depthOffset` is a body-frame translation in metres (negative moves back, within 5cm); `heightOffset` moves vertically. Both apply after pose/nose placement; `localScaleMultiplier` changes uniform size while retaining that origin. These are per-head measured settings, not race-wide replacement proportions.

For a front-only or rear-only local `paint.operations` heal, declare `headSide: "front"` or `"rear"`. This uses the unposed head GLB frame: +z is front, normalized z0 is rear. The heal checks both actual target and donor surface points before changing color and records their depth range. It retains the 3% target, 5% donor and distance limits. Review the operation on the mesh from front and rear; an atlas alone does not establish which side was selected.
