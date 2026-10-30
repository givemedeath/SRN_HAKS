# Race heads v1 checkpoint (2026-10-27)

Twenty new candidate heads, two per race and sex, were made on the guarded headkit bootstrap route. The route was a local Flux.2 front design, then a matte, then Pixal geometry and appearance, then the headkit CPU chain with the neck cut, then native compile. Each race was packaged as one trial HAK and module (`build_head_trial.py`, `prefix` list, `motion: true`) and checked in the NWN:EE client.

**Status: client-checked candidates, not production-accepted.** Every head passed its render review, `verify_head_trial` (36/36 actors on `HEAD_FIXTURE_SLOT` in every race) and an in-client look at idle and motion. Production acceptance is the user's call.

The working data stays in the batch folder (`race-heads-v1/`, ignored scratch). It holds the per-head runs, receipts and reviews, the five trial modules with `evidence/` screenshots, `TRACKING.md` (resume ledger and every decision), `RUNBOOK.md` (rows 34-77) and `timings.log`. The runbook rows from this batch are copied to [race-heads-v1-runbook.md](race-heads-v1-runbook.md).

## Heads

Attempts are given as geometry submissions / designs, out of the caps of 5 / 3. The repair, ownership, palette and render columns give the attempts used.

| Head | Slot | Geo/design | Repair | Own. | Pal. | Render | Gate exceptions (all logged) | Client evidence |
|---|---|---|---|---|---|---|---|---|
| human-male-a | pmh0_head084 | 1/1 | 3 | 1 | 2 | 1 | unused accent rows defaulted | human-v1/evidence head3-* |
| human-male-b | pmh0_head085 | 1/1 | 1 | 1 | 2 | 2 | skin row 6 pin | head4-* |
| human-female-a | pfh0_head028 | 1/1 | 1 | 3 (override) | 3 | 3 | brow stud texture-only; ownership budget override | head1-* |
| human-female-b | pfh0_head029 | 1/1 | 4 (override) | 1 | 2 | 2 | reduction bound 1.1%; UV floor 0.28; hair row 75 pin | head2-* |
| dwarf-male-a | pmd0_head015 | 1/2 | 3 | 2 | 2 | 2 | reduction 1.1%; UV floor 0.21 | dwarf-v1/evidence head3-* |
| dwarf-male-b | pmd0_head016 | 2/2 | 2 | 1 | 2 | 2 | reduction 0.7%; skin row 6 pin | head4-* |
| dwarf-female-a | pfd0_head013 | 1/1 | 5 (override) | 2 | 3 | 2 | reduction 1.1%; UV floor 0.28; eye row 19 pin | head1-* |
| dwarf-female-b | pfd0_head014 | 1/1 | 3 | 2 | 2 | 2 | undercut row 15 pin | head2-* |
| elf-male-a | pme0_head020 | 1/1 | 2 | 1 | 1 | 1 | reduction 0.7% | elf-v1/evidence head3-* |
| elf-male-b | pme0_head021 | 1/1 | 1 | 2 | 3 | 3 | hair row 63 pin | head4-* |
| elf-female-a | pfe0_head018 | 1/1 | 2 | 2 | 3 | 2 | reduction 1.2%; skin 0, hair 75, ink 143, eyes 40 pins | head1-* |
| elf-female-b | pfe0_head019 | 1/1 | 2 | 1 | 2 | 2 | reduction 0.5%; skin row 6 pin | head2-* |
| orc-male-a | pmo0_head015 | 4/2 | 3 | 2 | 3 | 2 | skin 3, hair 63 pins | orc-v1/evidence head3-* |
| orc-male-b | pmo0_head016 | 1/1 | 1 | 1 | 3 | 2 | skin row 5 pin | head4-* |
| orc-female-a | pfo0_head013 | 1/1 | 2 | 1 | 2 | 2 | reduction 0.8%; skin row 25 pin | head1-* |
| orc-female-b | pfo0_head014 | 1/1 | 2 | 1 | 2 | 1 | reduction 1.0%; datajack plate texture-only; skin 5, hair 63 pins | head2-* |
| troll-male-a | pmg0_head031 | 1/1 | 2 | 2 | 3 | 2 | cut slope -0.19 (sliver); skin row 124 pin | troll-v1/evidence head3-* |
| troll-male-b | pmg0_head032 | 1/1 | 4 (override) | 1 | 3 | 2 | cut slope -0.25; UV floor 0.27; skin 127, hair 63 pins | head4-* |
| troll-female-a | pfg0_head024 | 1/1 | 2 | 2 | 4 (override) | 3 | fit align profile; slope -0.3; skin 25, hair 103 -32 pins | head1-* |
| troll-female-b | pfg0_head025 | 1/1 | 2 | 1 | 2 | 1 | reduction 1.0%; slope -0.3; skin 79, chin ink 45 pins | head2-* |

No slot was blocked. orc-male-a ended at 4 of 5 geometry submissions and 2 of 3 designs. Design 1 put a dark filled scalp tattoo where Pixal built a recess on two seeds. Design 2's first mesh had inside-out tusks that the wrap lost.

### Open issues for the user's review

These were accepted at render with notes:
- **troll-female-a:** skin reads yellow-olive and hair red-orange; there are skin-coloured gaps in the side hair (Pixal baked a cream band under it).
- **orc-male-b:** orange-tan mottling baked into the scalp texture.
- **orc-female-b:** tusks are texture-only after the 20K reduction.
- **orc-female-a:** two thin braid-end spikes on the bun.
- **elf-male-b:** maroon edges at the sideburns.
- **dwarf-female-a:** Pixal curls at the back, and a khaki hairline strip.
- **troll-female-b:** the hair is a white strand mass, not the designed crown braid.

Design deviations are recorded in each `design-receipt.json` `observedDeviations`. Most are unrequested ear studs.

## Timings

These are per-head totals from `timings.log`, in minutes. GPU is Pixal calibrate, geometry and appearance. CPU is stage runs. Diag is shell diagnostics. Numbers before the one-slot change (2026-10-27 00:04) include some CPU slot waits.

| Race | GPU | CPU | Diag |
|---|---|---|---|
| human (m-a, m-b, f-a, f-b) | 8.7, 6.0, 7.0, 14.8 | 36.7, 43.5, 46.6, 82.2 | 0, 4.2, 3.0, 16.4 |
| dwarf | 11.3, 13.4, 17.6, 7.6 | 62.1, 25.5, 64.3, 98.3 | 16.1, 6.4, 4.6, 5.0 |
| elf | 8.7, 5.8, 24.1, 7.8 | 50.6, 31.4, 35.6, 21.9 | 5.5, 0, 6.8, 2.8 |
| orc | 31.1, 6.0, 10.2, 23.4 | 22.1, 11.3, 15.7, 19.4 | 7.4, 2.2, 2.6, 2.8 |
| troll | 8.7, 12.3, 23.2, 16.8 | 11.4, 49.0, 42.1, 24.3 | 1.1, 1.6, 1.8, 2.6 |

Every head's compute time is under the 2 h target; the longest is dwarf-female-b at about 1.8 h. Wall-clock was dominated by the shared single CPU slot. The 1.3-1.5 GB troll preclusters ran 26-33 min each. The batch native compile took 129-146 s per race of four.

## Pipeline fixes

- **Batch native (`run_headkit.py batch --heads`)** put the interpreter's NumPy first, so every head's native stage failed.
  - Fix 79d0e3cb on `claude/headkit-pipeline-v3`, with a regression test in `test_entry_script_puts_bound_packages_first`, cherry-picked here as b44aa126.
  - Before: the native stage failed on all 8 human and dwarf heads. After: 7 heads compile in one 142 s launch, against 22-36 s per single-head launch.
  - No stage pins `run_headkit.py`, so no head went stale.
- **Shell-table refusal and interiorOnly bubble deletion** (62d303a5, earlier in this batch) were cherry-picked here as f5dc7fd1 after the batch finished. Rerunning a head under them stales precluster, repair, export and native (runbook row 43).

## Optimizations (batch tooling)

- **Bake-scope ownership previews** take 20-25 s and spend no attempt. 11 heads finished ownership in one stage attempt.
- **Pre-set reviewed UV floor alongside the reduction exception.** Twice this avoided a 4-7 min identical repair rerun (elf-female-a, orc-female-a).
- **Pre-render palette pins from `rowramps.py`.** orc-female-b and troll-female-b were approved on their first render.
- **CPU spool.** One queue holds stage, batch and diagnostic jobs at BelowNormal priority. It ended lock starvation, which had cost an 18 min wait for the native batch and 30 min for diagnostics.
- **`cutreplay.py` with the master-audit crossing scan.** It found the clean neck-cut slope for troll-male-b's last repair attempt. `shells.py` now stops at the selection.

Thumbnail sheet of all 20 heads (front and left profile from each approved render): [evidence/race-heads-v1-thumbnails.png](evidence/race-heads-v1-thumbnails.png).

## Toolkit follow-ups

Items 1-5 were fixed on `claude/headkit-pipeline-v3` as 3f937754 (2026-10-27) and replayed on this batch's retained data. They were cherry-picked here as 4222768f, and all 342 headkit tests pass on this branch. Runbook rows 78-82 record them. The 20 heads above were built before these fixes, so rerunning any of them stales repair and every later stage.

1. **Reduction gate: fixed.** All ten failures were hair-strand relief: at most 11 vertices, at most 1.1% of the diagonal across, at most 1.16% error, and at most 0.17% of the surface. The new `mesh.fineRelief` (on by default) passes bounded relief at the strict 0.4% limit.
   - Replay: all 10 heads pass with no exception.
   - A flattened protrusion still fails (regression test).
   - A feature-aware PyMeshLab reduction was also tried. It lowered the error but added 4-56 crossings, so it was dropped.
2. **Repair binds all of `mesh`: fixed.** Repair now binds `mesh` without the UV and bake keys, so a reviewed UV floor stales only unwrap onward.
3. **Palette row selection: not fixed by scoring; replaced with a review step.** Two scorers were measured against the 19 reviewed pins: full-lightness mean colour and a luma-quantile Lab profile. Neither recovered them (median 16 ΔE from the pin, the same as the current scorer).
   - New: `headkit preview --what rows` shows each channel decoded on the head with its manifest row and the top-ranked rows, so rows can be pinned before the palette stage.
4. **Neck cut: fixed.**
   - Sliver vertices snap onto the plane. Replay: troll-male-a at slope -0.2 now passes.
   - Repair checks each cut like the master audit and tries reviewed `cut.slopes` fallbacks.
   - On failure, repair writes `cut-candidates.json` listing the cut variants that pass. Replay: it finds slope -0.25 at troll-male-b's first failure.
5. **Fit references: measured ranking.** `headkit fit-references` ranks candidates by midline depth/height: pfh0_head001 1.64, pfd0_head008 2.02, pfo0_head009 1.97, against 1.23, 1.63 and 1.56 for their replacements.
   - No fit-result number separated the bad fits from good ones, so the ranking is the guard.
6. **Merge to main** when no head is in progress. This branch now carries 79d0e3cb (b44aa126), 62d303a5 (f5dc7fd1) and 3f937754 (4222768f). Merging stales repair and later stages on existing runs (the repair manifest digest changes).
