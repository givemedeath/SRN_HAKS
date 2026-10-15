# PhenoMorpher runtime optimization: stock-structured animation libraries + 1K body textures

## Context
The published body release (remote `codex/phenomorpher-bodies-v1` @ `0866bcaf`, 5 commits on `main` da13a7c) carries runtime bloat:
- 109 private animation-carrier MDLs (147.7 MB).
  - Every non-Human body and every Large body has its own 5–8 link chain ending in `NULL`.
  - Each chain is a renamed full copy of the stock `a_fa > a_ba > a_ba_non_combat > a_ba_med_weap > a_ba_custom > a_ba_casts` chain, many clips stored 2–3 times (e.g. `walk`).
- 25 PLTs and 56 normal/roughness maps at 2048².

Stock NWN instead roots every body on a thin supermodel over the shared `a_ba` chain. Examples: `pmh2 > a_ba2 > a_ba`, `pfd0 > a_dfa > a_ba`, with `setanimationscale` on the root.

Goal: follow that stock structure without the bloat, and cap consumed body textures at 1024 px. Approved shapes, UVs, rig frames, stature, attachments, female posture and skin tone are preserved.

## Start — durable plan copy (before any other work)
1. `git fetch origin codex/phenomorpher-bodies-v1 main` and confirm the heads: bodies `0866bcaf`, main `ba77021a`.
2. Create the runtime worktree `D:/srwt/codex/phenomorpher-runtime-optimization/SRN_HAKS` on branch `codex/phenomorpher-runtime-optimization` from `0866bcaf`.
3. Copy this plan verbatim to `docs/phenomorpher/runtime-optimization/plan.md`, record its SHA-256, and commit it as the branch's first commit.
4. Add a project-memory entry pointing to that file and commit, so later sessions resume from it.
5. Ask you before pushing that plan-only commit to `origin`; pushing makes the copy durable off-machine. The Step 0 CI PR description links to it.
6. If the plan changes later, append a dated revision section to that file. Earlier text is never rewritten.

## Step 0 — CI scope planning and speed-up (separate PR, first; ≈6–10 h)
PR 44 merged on 2026-10-14 (`main` = `ba77021a`). Create a fresh worktree `D:/srwt/codex/ci-scope-planning/SRN_HAKS` on branch `codex/ci-scope-planning` from `origin/main` @ `ba77021a`. This PR is independent of the body/runtime work, and the runtime PR benefits from it. Before editing, re-check the CI findings below against `ba77021a`.

### Research findings (PR 44 head `a4b59d81`, run 38508848142/38508848109)
- **Durations:**
  - Helpers: 11m05s on Windows, 7m26s on Linux.
  - Verify: 1m17s.
- **Phenotype suite dominates:** 489 s on Windows, 322 s on Linux, out of 1581 tests. The rest is small: root tools 58/43 s, toolkit 2 s, robes 1–2 s, heads 3–8 s, gallery 1–2 s, item import 8–10 s.
- **Checkout** with `fetch-depth: 0` costs 46–55 s per job (full history including large binaries).
- **Hotspot modules** (Linux / Windows), from log timestamps:

  | Module | Linux | Windows |
  |---|---:|---:|
  | `test_source_representation_contract` | 37 s | 77 s |
  | `test_shared_female_stock_basis` | 34 s | 42 s |
  | `test_target_body_launcher` (pwsh launches) | 30 s | 23 s |
  | `test_shared_tools` | 24 s | 35 s |
  | `test_test_impact` (rebuilds the full catalog per test) | 14 s | 17 s |
  | Garment/skin staging modules | 15–22 s each | 15–22 s each |

  Slowest single tests: 10–13 s.
- **Scope is discovered independently:**
  - `verify.yml` and `shared-tooling.yml` each diff the base.
  - Both run `Test-ItemImportScope.ps1`/`Test-ItemImportTools.ps1`, so item import runs three times: verify plus Linux and Windows helpers.
  - The helper suites run unconditionally.
- **`test_impact.py --run`** runs `python -m unittest <stem>` from each test's own folder. That breaks package tests that use relative imports (`tools/phenomorpher/phenomorpher/**`). The committed `tools/test-impact.json` lists 168 tests and **no** PhenoMorpher package tests.
- **Docs fall back to full:** catalog literals only cover `.py/.json/.ps1/.psm1`, so any README/Markdown edit is "unknown". Yet `test_verify_published_body` reads checkpoint docs, so docs can't simply be ignored.
- **Cache keys differ:** `srn-tools-linux-…` (verify) vs `srn-tools-${{ runner.os }}` = `Linux` (helpers), so the two never share a cache.
- **No `concurrency`** in either workflow.
- **Required checks:** branch protection requires only "Repository verification" (strict). The helper jobs are not required today.
- **No wheel build in CI;** wheel isolation is recorded only in the toolkit's `validation.json`.

### Design
1. **One scope plan per run.**
   - New entry workflow `.github/workflows/ci.yml` (PR, push to main, `workflow_dispatch` with a `full` input) runs a `scope` job.
   - `verify.yml` and `shared-tooling.yml` become `workflow_call` reusables that consume the plan JSON as an input.
   - Planner `tools/ci_scope.py` reuses `test_impact.catalog/select`. It resolves the base (PR base SHA / push `before`) and publishes:
     - changed files;
     - selected suites with test modules;
     - a reason per suite;
     - an item-import decision (patterns moved from `Test-ItemImportScope.ps1`, which becomes a thin wrapper).
   - Output goes to job outputs, the step summary and an artifact.
   - The catalog is computed live in CI; a check fails if the committed `tools/test-impact.json` is stale.
2. **Package-aware focused runner.**
   - `test_impact.py` finds each test's import root by walking up `__init__.py` files.
   - It runs package tests as `-m unittest phenomorpher.engine.test_x` with `cwd` = top-level dir (`tools/phenomorpher`), and flat tests as today.
   - It keeps `sys.executable`; workflows invoke it with `steps.interpreter.outputs.python-path`.
   - The catalog includes package tests, and is regenerated.
3. **Dependency selection.** Suites are phenotypes, toolkit, robes, heads, gallery and root tools.
   - **Full coverage** on:
     - shared infrastructure: `shared_tools.py`, `SrnTools.psm1`, `SrnHaks.Common.psm1`, both lock files, `requirements.txt`, `launch_shared_tool.py`, `test_impact.py`, `ci_scope.py`, workflows, the composite action;
     - unresolved or unknown dependencies;
     - a missing, all-zero or undiffable base;
     - `workflow_dispatch full=true`;
     - push to main (post-merge safety net).
   - **Markdown/docs:** literal edges extended to `.md` and doc paths, so a doc read by a test selects that test. Docs referenced by no test select **no helper tests**; verify still runs.
   - `srn_*` asset-only changes go to verify plus tests that reference those paths.
4. **Item import:** one owner job `item-import` (Linux), run only when the plan selects it. Verify and helpers no longer run it; the result job checks it.
5. **One tool-cache setup:** composite action `.github/actions/srn-tools` binds `SRN_TOOLS_ROOT` and restores/saves `srn-tools-${{ runner.os }}-${{ hashFiles('tools/toolchain.lock.json','tools/shared-tools.lock.json') }}` with the same root before bootstrapping. All jobs use it, so Linux verify and helpers share one verified cache.
6. **Concurrency:** group `${{ github.workflow }}-${{ github.event.pull_request.number || github.ref }}`, with `cancel-in-progress: ${{ github.event_name == 'pull_request' }}`. Main and release pushes get a per-SHA group, so they are never cancelled.
7. **Measure, then shorten.**
   - Every suite runs with `unittest --durations 0` (Python 3.12), plus a small timing collector that uploads per-suite/per-test JSON.
   - Optimize only the measured hotspots:
     - `test_test_impact`: build the catalog once in `setUpClass`;
     - launcher and shared-tool tests: share immutable fixtures and tool resolution per class, keeping fresh temp dirs per case and real pwsh/Python launches for the behaviour under test;
     - `test_source_representation_contract` and `test_shared_female_stock_basis`: profile and cache immutable inputs.
   - No assertion is removed or weakened.
   - Before/after timings are recorded in the PR.
8. **Bounded jobs:**
   - Helper matrix: OS (Linux, Windows) × shard. Shards:
     - root tools;
     - phenotypes split into 3 duration-balanced shards from the measured timings;
     - toolkit + robes + heads + gallery;
     - wheel.
   - Each job runs only if selected.
   - Final `ci-result` job (`if: always()`, needs all) runs `tools/ci_result.py`. It fails on any failure or cancellation, and on any selected job that is skipped or missing; unselected skips pass.
   - "Re-run failed jobs" then re-runs only the failed shard and re-evaluates the result.
9. **Wheel validation job:**
   - `pip wheel --no-deps tools/phenomorpher` into `RUNNER_TEMP`, then a fresh venv there and an install of the wheel.
   - Public tests (`test_public_api`, `test_cli_contract`) run from an isolated cwd with `-I`/`-P`.
   - Asserts `phenomorpher.__file__` is inside the venv's site-packages.
10. **Checkout (measured, optional):** try `filter: blob:none` with `fetch-depth: 0` (history without old blobs). Adopt only if timings improve and the diff plus item-import scope still work.

### Required regression tests (safeguards against silently skipping tests)
In `tools/test_test_impact.py`, `tools/test_ci_scope.py` and `tools/test_ci_result.py`:
- **Package discovery:** the catalog includes `tools/phenomorpher/phenomorpher/**` tests. `--run` executes them package-qualified from `tools/phenomorpher` using the given interpreter. Uses a fixture package with relative imports and a deliberately failing test, so a failure propagates.
- **Unknown-change fallback:** each of these selects every suite:
  - an unknown path;
  - an unresolved dependency;
  - a missing, zero or undiffable base;
  - missing comparison data;
  - `full=true`.
- **Documentation-only selection:** an unreferenced README edit selects no helper tests, while verify still runs. A doc read by a test selects exactly that test; a mixed doc + code change unions both.
- **Shared-helper coverage:** a change to each shared-infrastructure file forces full coverage. A shared helper imported across suites selects all transitive dependents across folders, including package tests.
- **Final required-check result:** `ci_result.py` is tested against success, failure, cancelled, selected-but-skipped, selected-but-missing, unselected-skipped and rerun-after-failure states.
- Workflow wiring is checked by a YAML-structure test: every selectable job is in `ci-result.needs`; there is one item-import owner and one cache-key format.

### Verification and handoff
- The full helper suite plus the new tests pass locally, with the bundled Python.
- The planner is dry-run on historical diffs (#40, #41, #42, PR 44) to show selections and reasons.
- The PR's own CI run is full, because workflows changed. A follow-up docs-only commit demonstrates the scoped path, then is reverted or kept.
- Report before/after wall-clock time per job.
- Repository settings stay with you: switching the required check from "Repository verification" to the new `ci-result` is a branch-protection change. I'll give exact instructions and won't change settings without your explicit OK.
- Commit, push and PR creation each wait for your approval.

## Measured facts (binaries at `0866bcaf` vs installed game, decoded with toolkit `native_motion.Reader`)
- **Human Large** chains (`p25l04_*`, `p25l05_*`) are controller-identical to stock `a_fa`/`a_ba` plus `srn_fa_h0` (pause1/2 posture). The one exception is female `2hslashl`, already authorized to use the Fit (stock) clip.
- **Non-Human** chains: every clip that keys head/neck/legs carries constant per-node rotation offsets matching the approved rig frames.
  - Offsets: neck/head 7.15°, shins/feet 1.3–3.4°, thighs 0.3–0.4° (Dwarf F).
  - Positions are a uniform scale of stock (Dwarf ×0.714).
  - Of 172 effective clips:

    | Bodies | Bit-identical | Scale-only | Within 0.1 mm / 0.05° | Override |
    |---|---:|---:|---:|---:|
    | Dwarf | 0 | 0 | 3–4 | ≈163–166 |
    | Elf, Orc, Troll | 0 | 0 | 25 | ≈142–144 |

  - Female chains add 2 posture clips. Stock `a_ba_custom` (3 mount/custom clips) is ASCII and needs a separate check.
- Fit vs Large non-Human chains match except female `2hslashl`. The Large position difference is 3 cm, discarded as authorized.

## Decisions (from interview)
1. **Human: no library.**
   - Repoint `pmh2 → a_ba` and `pfh2 → srn_fa_h0` (identical to Fit).
   - Fit roots stay unchanged.
   - Retire `p25l04_*` and `p25l05_*`.
   - Approved Large Human keeps Fit motion; stock `a_ba2`/`a_fa2` are not adopted.
2. **8 non-Human libraries**, Dwarf/Elf/Orc/Troll × M/F, each shared by Fit and Large:
   - Female libraries inherit **stock `a_fa`**, male libraries **stock `a_ba`** (the actual donors).
   - Each holds only clips that can't be inherited, plus the female posture clips and the Fit `2hslashl`.
3. **Inheritance rule: tolerance.** A clip is dropped (stock supplies it) only when all of these hold:
   - identical structure: node set, controller types, key counts/times, length, transition, events;
   - every position key within **0.1 mm**;
   - every rotation key within **0.05°**.

   Every inherited clip's measured deltas are recorded as an explicit, approved motion change. Default safeguard: the assembled worst-case end-effector/attachment drift (hands, feet, head, robe/cloak/impact nodes) is also measured, and a clip stays in the library if that drift exceeds **1 mm**. Easy to change at approval.
4. PR 44 (toolkit) is merged (`main` = `ba77021a`). The runtime branch starts from the bodies branch `0866bcaf` and merges `origin/main`, plus the Step 0 CI PR once it lands.
5. Texture scope is 1K downsampling only. The following are out of scope:
   - removing unreferenced PLTs;
   - sharing duplicate PLT payloads;
   - greyscale roughness;
   - DDS maps;
   - E1/zstd HAKs;
   - cross-race library sharing;
   - key reduction and empty-node removal.

   All texture names, MTRs, bitmap fields and PLT file sets stay as published.
6. External cleanup tools are not used:
   - **CleanModels:** absent from the toolchain. Its recompile would rewrite geometry, normals/tangents and animation keys.
   - **nwn_crunch:** no PLT support. Its DDS output is lossy, and generic resizing would skip normal renormalization.

   Models compile only through the EE client; textures go only through `downsample-textures`.

Result layout:
- 20 roots, each with only its supermodel name changed (fixed-width field).
- 8 libraries plus existing `srn_fa_h0`, over the installed-game chain.
- 0 private carriers left.
- Library names: `srn_an_<race><g>` (`dm, df, em, ef, om, of, gm, gf`; Troll uses its G slot), after a collision check against repo packs and the installed game.

## Reuse: toolkit (PR 44, `tools/phenomorpher`) + `main` helpers
| Need | Existing piece |
|---|---|
| Managed launches with declared, frozen inputs | `tools/phenomorpher/run.py`, `launch_shared_tool.py` (`manifest_inputs`, `helper_snapshots`) |
| Migration (Python-only) | `tools/phenomorpher/finalize_runtime.py` |
| Contract hash verification | `phenomorpher verify-assets`, `catalog`, `native-info` |
| Native decode and pose sampling | `engine/native_motion.py` (`Reader`, `sample`, `sample_times`) |
| Chain precedence, controller signatures, root-token proof | `engine/rig_pose_audit.py`, `engine/rig_controller_audit.py`, `engine/shared_female_native_contract.py`, `engine/target_animation_overlay.py` |
| EE client compile | `tools/phenotypes/native_compile.py` |
| PLT/TGA/MTR I/O, normal encode, palette render | `single_plt_part_contract.py`, `lean_common.py`, `lean_normal_maps.py`, `prepare_effective_body_preview.colorize_plt` |
| Matched views (Blender, 4 threads) | `render_lean_gate3_views.py`, `compose_lean_gate3_sheets.py` |
| Packs | `tools/Build-Haks.ps1`, `tools/Test-Repository.ps1` |

New code only where nothing exists. Three toolkit commands in `tools/phenomorpher/phenomorpher/engine/`:
- `anim_library.py` (`anim-library`): inventory, clip classification, library build, root repoint.
- `motion_compare.py` (`compare-motion`): a wrapper over `native_motion`.
- `texture_downsample.py` (`downsample-textures`).

## Phase 1 — Isolated baseline (1–2 h)
1. Setup:
   - The worktree and plan commit already exist from Start. Re-confirm the remote bodies head is `0866bcaf`, otherwise stop to reconcile.
   - Then `git merge origin/main`: `ba77021a` (toolkit included), plus the Step 0 CI PR if it has landed.
2. Read that checkout's `AGENTS.md`, `docs/shared-tooling-and-workflow.md`, `docs/phenomorpher/*`.
3. Create a fresh `.tmp/runtime-bindings/` binding (python, blender, nwn), migration smokes and a finalized receipt.
4. Freeze the baseline with `verify-assets` + `catalog`, then `anim-library inventory`. Output `docs/phenomorpher/runtime-optimization/baseline.json` containing:
   - root → chain → effective clip owner;
   - the stock effective set from `resman_cat --no-ovr`, including ASCII `a_ba_custom`;
   - the static node sets;
   - real PLT/TGA header dimensions;
   - the texture usage graph.

## Phase 2 — Pilot libraries: Dwarf M/F (3–5 h)
**`anim-library build`:**
1. Resolve the effective clips of the Fit chain.
2. Swap in the Fit `2hslashl` for females (already the Fit winner).
3. Classify each clip against stock `a_fa`/`a_ba` (decision 3, including the assembled-drift safeguard).
4. Emit the library from the decoded arrays:
   - geometry/dummy node tree copied from the source carriers (verify they agree);
   - only non-inherited clips;
   - exact events/animroot/length/transtime;
   - supermodel `a_fa`/`a_ba`.
5. Compile with the EE client (`native_compile.py`).
6. Decode with `native_motion.Reader` and **restore the original controller payload bytes** into the decoded ranges (the `srn_fa_h0` precedent). A key-count/column mismatch is a hard failure, never a resample.
   - Fallback: a relocating binary writer built on the `NativeFixture` layout.

**`compare-motion`** (old chain vs new library + stock) checks:
- every effective clip;
- byte-exact keys for retained clips and recorded deltas for inherited ones;
- assembled world transforms at keys, midpoints and loop boundaries;
- events/timing;
- attachment-node motion.

Root repoint is proven by `verify_root_token` semantics.

Gate: both pilots are exact for retained clips, with inherited deltas within the rule. Otherwise stop and report.

## Phase 3 — All libraries and Human repoint (2–4 h)
- Build the remaining 6 libraries.
- Verify Fit and Large non-Human chains are controller-identical except female `2hslashl`; any other difference blocks and is reported.
- Human: repoint `pmh2`/`pfh2` and prove the assembled motion equals the old Large chain except female `2hslashl`.
- Unkeyed nodes:
  - Verify in a native client probe that they take the root's own frames, not the supermodel's.
  - If not, report before changing anything; roots and rigs stay untouched.
- Check the female posture (hips level + original upper lean/breathing) in all 10 female assemblies.

## Phase 4 — 1K textures (3–5 h)
**`downsample-textures`**, integer 2:1 area reduction:
- **PLT:**
  - Layer = deterministic coverage mode per 2×2, ties broken by fixed priority (skin 0 > cloth 4/5 > others > lowest id).
  - Intensity = mean within the winning layer only.
  - Header W/H rewritten.
- **Normal:**
  - Decode R/G to vectors, Z rebuilt as the shader does.
  - Average, renormalize.
  - Re-encode with `lean_normal_maps` semantics: no green flip, Z ≥ 0.02.
- **Roughness:** linear per-channel mean, no gamma.
- Always: orientation, names, formats and MTRs unchanged; textures ≤1024 untouched; each unique payload converted once.

Pilots: Human M/F chest, pelvis and legs. Checks:
- layer histograms and per-island dye preservation;
- skin↔cloth contamination at gutters (4 px at 1K);
- 2K vs 1K renders through stock palettes at the release tone;
- normal length and roughness ranges.

Then the full set (header scan decides; expected 25 PLT + 56 maps). Each unique payload is converted once, and the result is written to every resource name that carries it.

## Phase 5 — Generate and package (2–3 h)
- Batch through `run.py` with `--input-manifest` = baseline: 8 libraries, 20 repointed roots, texture derivatives; record hashes, settings and timings, and re-verify frozen inputs after each batch.
- Remove from `srn_body`/`srn_body_tex`, only after a closure check proves them unreferenced:
  - the 109 carriers;
  - the replaced 2K files.
- Write contract `docs/phenomorpher/game-ready-assets.json` v1.1.0 (v1.0.0 referenced at `0866bcaf`).
  - Add `installedGameDependencies` for the full `a_fa`/`a_ba` chain.
  - Update `retired-runtime-resources.json`, `ASSETS.md` and `README.md`.
- Build and check: `tools/Build-Haks.ps1 -Pack srn_body,srn_body_tex` (`srn_2da` untouched), then `tools/Test-Repository.ps1 -ChangedSince 0866bcaf`, then `verify-assets` on the new contract.

## Phase 6 — Offline verification (2–3 h)
- Body-part MDLs byte-identical; roots differ only in the supermodel field.
- `compare-motion` across all 20 assemblies, with a delta report of inherited clips and `2hslashl`.
- Textures:
  - headers ≤1024; routing closure; PLT layer validity; normal and roughness stats;
  - matched 2K/1K front/side/rear plus neck, shoulder, waist, thigh, knee, ankle and close leg views (Blender, 4 threads).
- Tests:
  - new unit tests beside the new modules, with `NativeFixture` and synthetic PLT/TGA fixtures;
  - `test_cli_contract.py` updated;
  - the full toolkit package suite;
  - `test_impact.py` focused runs;
  - the full helper suite only if `tools/phenotypes` helpers change.
- Review index: `docs/phenomorpher/runtime-optimization/review.md`.

## Phase 7 — Client verification, one session (3–5 h)
- Fresh fixture in this worktree, with isolated `-userdirectory` profiles for baseline vs candidate HAKs; the normal install is untouched.
- Coverage:
  - all 20 bodies;
  - idles, walk/run, kicks, melee/ranged, casting, sit/kneel, knockdown/death;
  - clothing, robes, cloaks, weapons, shields;
  - outdoor and white/warm interior light;
  - tone, dye and close leg views;
  - Fit/Large side by side.
- Screenshots go in `docs/phenomorpher/runtime-optimization/client/`. Needs your approval for computer-use access to the NWN client.

## Phase 8 — Handoff (1–2 h)
- Final manifests and actual before/after resource and HAK sizes.
- Rollback: `0866bcaf` plus the v1.0.0 contract.
- Checkpoint `docs/phenomorpher/runtime-optimization/checkpoint.md` with explicit ledger bindings.
- Commit on `codex/phenomorpher-runtime-optimization`. Push/PR only with your explicit approval.

## Stop points
- Remote head moved, or an inventory gap.
- Compile/restore mismatch with no working fallback.
- A Fit/Large difference other than female `2hslashl`.
- Human Large not equal to stock + `srn_fa_h0`.
- Unkeyed nodes taking supermodel frames.
- A visible seam or dye contamination at 1K.
- A client regression vs baseline.

## Critical files
- New: `tools/phenomorpher/phenomorpher/engine/{anim_library,motion_compare,texture_downsample}.py` plus tests; `docs/phenomorpher/runtime-optimization/*`.
- Modified:
  - `tools/phenomorpher/phenomorpher/{cli.py,api.py}`, toolkit `README.md`, `source-lineage.json`;
  - `docs/phenomorpher/{game-ready-assets.json,ASSETS.md,retired-runtime-resources.json,README.md}`;
  - `srn_body/*` (20 roots, 8 libraries, 25 downsampled PLTs; carriers removed), `srn_body_tex/*` (56 downsampled maps);
  - pin consumers found in Phase 1.

## Revision 2026-10-14 — Phase 3 unkeyed-node gate

User decision after Phase 3: the native client probe for unkeyed nodes moves into the
Phase 7 client session instead of a separate Phase 3 module. Phase 3 records the stock-game
evidence instead ([libraries.md](libraries.md)): stock `pmd0 > a_da > a_ba` plays `a_ba` walk/talk
with dwarf shins that differ by 157 mm from both `a_da` and `a_ba`, so unkeyed nodes take
the root frames. Phase 7 adds an explicit stop-gate on inherited clips: Troll, Elf and Orc
`walk_swordr`/`run_swordl`, talk (`tlknorm`), `salute`, `greeting`, and Dwarf `torchl`, baseline
vs candidate. A visible difference there stops the work as the original stop point does.

## Revision 2026-10-14 — read-only check sweep and toolkit upfit

User decisions after Phase 5 (interview):

### Phase 6 addition — read-only PhenoMorpher check sweep (before the client session)
Run every PhenoMorpher check read-only on all 20 contract 1.1.0 bodies, and the same checks on
contract 1.0.0 at `0866bcaf`:
* contract: `verify-assets`, `catalog`; per model `native-info`;
* geometry: `audit_geometry` (coincident triangles/roots), connector surface coverage and
  penetration, terminal minimum clearance, `measure` (static stature, masks);
* rig/animation: rig pose and controller audits, female posture contract, `anim-library inventory`,
  `compare-motion`, and connector checks over sampled motion.

Report every finding as new in 1.1.0 or pre-existing in 1.0.0 (geometry is unchanged, so most
are expected to be pre-existing), and class each as **adjust in assets**, **adjust in tooling** or
**inspect in client**. Every inspect-in-client finding becomes an explicit Phase 7 checklist
item, alongside the inherited-clip stop-gate. The sweep changes no asset.

### Phase 9 — PhenoMorpher toolkit upfit for the supermodel requirements (separate follow-up PR)
After Phase 8, in its own branch and PR:
* **Generate:** new or regenerated bodies use root > shared `srn_an_<race><gender>` library > installed
  `a_fa`/`a_ba` chain. `anim-library build`, EE compile, `restore` and `compare-motion` become pipeline
  steps. Fit and Large share one library; the authorized female Fit `2hslashl` rule is explicit.
  `candidate` and `convert-clothing` motion baselines read the library chain, not private carriers.
* **Enforce:** contract validation fails on private carriers, non-stock-terminated chains,
  libraries not parented on `a_fa`/`a_ba`, Fit/Large library divergence, retained clips without exact
  restoration evidence and body textures above 1024 px. `adopt-runtime` and `downsample-textures` are
  the release path.
* Tests and documentation follow the toolkit conventions; the published assets are not regenerated by this step.

## Revision 2026-10-15 — Phase 9 execution plan (after an in-depth code review)

Phase 9 runs on branch `codex/phenomorpher-toolkit-upfit` from `main` `9e6d507`. A code review of the
first draft corrected it. Results and ledger bindings are in [phase9.md](phase9.md).
* **Enforce — `verify-runtime`** (new `engine/runtime_rules.py`). Structural mode reads stock names and
  parents from the contract's `installedAnimationChain`, so no game install is needed. A deep mode
  also checks installed bytes against an extracted stock manifest. Rules:
  * no private carriers, except declared posture layers (role `rig-inheritance`, parent `a_fa`/`a_ba`,
    only `pause1`/`pause2`, i.e. `srn_fa_h0`), with no name hard-coded;
  * at most one pack layer before the stock chain, and the first installed link is `a_fa` (female) or `a_ba` (male);
  * the installed chain reaches `a_ba`;
  * each library has one gender and the matching parent, plus `restorationSHA256` evidence;
  * Fit and Large of one slot share their immediate supermodel;
  * every PLT/TGA is at most 1024 px, and any other format is an error.

  The female `2hslashl` authorization does not apply in 1.1.0, because Fit and Large share a
  supermodel. A structured field is added only in the next contract version, so the 1.1.0 bytes stay.
  `adopt-runtime` checks the staged release (staged files over the root) before writing anything.
* **Generate.** New `engine/retarget_v2.py` fits motion once, from the Fit body, over `a_fa`/`a_ba`. The
  Large root names the same top carrier, so Fit and Large share one library. `retarget.py` stays as it is.
  `adopt-runtime` gains `baseKind: intermediate`, which drops never-published carriers without a
  retirement record, and a configurable `libraryAnchor`.
* **Motion baselines.** New `engine/motion_baseline_v2.py` resolves the published chain. The pinned
  v13/v14a loaders and `shared_female_native_contract` stay unchanged, because historical receipts depend on them.
* **Rig audits on published binaries.** New `engine/rig_native.py` and the `audit-native` command compare
  decoded controllers with quaternions up to sign. `rig_controller_audit` and `rig_pose_audit` stay
  ASCII-only for retarget sources.
* **F5 and F6.** New `engine/check_connector_surfaces_v16.py`:
  * neck links chest–neck and neck–head, where neck–head uses `head001` and is diagnostic only;
  * penetration on closed, oriented surfaces, including non-manifold ones;
  * a lineage mismatch makes only that link unavailable.

  The review corrected F6: the female parts have no open rims. Their pelvis and feet have
  non-manifold edges whose directed uses still cancel, and only the links opposite those parts
  were affected. v15 and `LINKS` stay as they are.
* **Sweep.** The Phase 6 script becomes `engine/body_sweep.py` and the `sweep` command, using v16.
* The armour palette question is closed separately: client proof on 2026-10-15 found no defect, so no fix is needed.
