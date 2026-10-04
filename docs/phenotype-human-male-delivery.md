# Completed muscular Human male

Updated 2026-10-03. All fourteen purpose-built body parts are selected, native
compiled and tested together in NWN:EE. The gripping hands are finished under
the user's practical quality scope. The package is ready for user review.

## Package and review images

The accepted 72 runtime resources and fourteen body models are versioned in
[`srn_body`](../srn_body), with [per-resource publication pins](phenotypes/human-male-assets.json).
Build `output/srn_body.hak` with `pwsh ./tools/Build-Haks.ps1 -Pack srn_body`.
The original client-tested archive has SHA256:
`01524cd39ad111021d30ba9a7c2241fdf8ef3afc7eb77f04346907d423d9f7c2`.
The stock Human male rig, animations, attachments, neck/head and 1.9339157 m
height remain intact. Human equipment uses stock identity scaling. No production
table changes are needed. All 32 accepted torso/pelvis/thigh/shin resource bytes
remain exact. Test/comparator resources are in a separate isolated HAK/module.

- [Actual in-game animation sheet](phenotypes/evidence/human-male-complete-goal-v1/client-animation-reference-v2/animation-reference-sheet.png)
- [Offline full-body pose sheet](phenotypes/evidence/human-male-complete-goal-v1/offline-animation-reference-v1/animation-reference-sheet.png)
- [Actual client validation receipt](phenotypes/evidence/human-male-complete-goal-v1/client-validation-v1.json)
- [Offline review receipt](phenotypes/evidence/human-male-complete-goal-v1/offline-validation-v1.json)
- [Final preflight](phenotypes/evidence/human-male-complete-goal-v1/final-delivery-preflight-v1.json)

Both sheets cover idle, walk, run, casting, combat, crouching, kneeling and death.
The client sheet uses literal viewport pixels from the tested package. Layout
resizing preserves aspect ratio; poses and colors were not generated or edited.
Original captures, observation receipts, package hashes, settings and logs remain
in the goal output. Historical construction-time readiness flags remain immutable;
the newer client validation establishes current tested readiness.

## Reopen the isolated comparison

Close any running NWN client, then run:

```powershell
& 'D:\srwt\codex\f0b3\SRN_HAKS\output\phenotypes\human-male-complete-goal-v1\Launch-HumanMale.ps1'
```

The default `Motion` mode selects the exact tested skin8/directional-light module
with a 12 m walk/run route. Use `-Mode Gameplay` for the tested skin3 original-light
sword/shield, casting and death/resurrection loop, or `-Mode Kneel` for held side
kneeling. `-NoLaunch` selects a mode without starting the client. The wrapper
verifies frozen inputs and refuses to replace a running client. Camera locks are
disabled. Wheel zoom was observed working; injected keyboard pan was not reliably
verified, so the side inspection used explicit fixture facing.

## Validation and practical limits

The root reviewed eight full-body offline poses and 42 stock/custom comparison
frames, followed by three actual client runs. These covered two skin palettes,
two lighting profiles, close/gameplay views, continuous motion and transitions,
representative armor and weapons/shields, feet/floor and corpse placement.
No new detached parts or empty joint openings were observed in inspected frames.
All three clients were responding when sampled, produced no crash reports and
were stopped after process/command-line ownership checks. Logs retain two
nonfatal empty MODULE.ifo field-label warnings per run; the recorded scan found
no matching missing-resource or fatal errors.

The small scene typically displayed 61 FPS under adaptive vsync. The longest
gameplay run exceeded 17 minutes, with about 568 MiB working set and 2.17 GiB
private memory at the sample. This is not a crowd, GPU-memory or frame-time
benchmark. Native costs are 686,048 triangles, 405,222 vertices and about 503 MiB
of serialized resource payload; hypothetical texture allocations are separately
reported in `native-fourteen-costs-v1.json`.

Known limits remain:

- Deep crouching has the previously accepted pelvis/thigh overlap and prominent
  rounded caps. Close elbow/knee seams and an extreme wrist-cap patch can show.
- The hands retain eight tiny crossing pairs and one pinched vertex link. Their
  edge closure, winding and nondegenerate-face checks pass; they are not claimed
  to be intersection-free. Extreme stock held-axis motion can sweep a weapon
  shaft through the palm, as it also does through the stock mitten.
- Equipment checks are representative. Every robe, glove, helmet, weapon,
  palette, quality setting and production scene has not been tested.

These limits are recorded rather than reopened as new hand-polish gates. The
source masters, selected material dependencies, immutable receipts and current
configs remain preserved. No purge was performed during this goal. Generation
masters remain in the worktree; the accepted native runtime resources are now
versioned in `srn_body`. Original implementation, configs and selected evidence
were committed as `ed74212cf8251fb32c85e74b979d810d1bc3c8f5`. The final package and
sheet pins are in `human-male-complete-goal-v1/final-delivery-v1.json`.
The user accepted this usable Human baseline for repository publication. Further
optional Human polishing yields to the remaining races; Troll male is queued
separately and is not started by this PR packaging task.

## Reusable process

Use [the current runbook](phenotype-purpose-built-current-runbook.md),
[part generation](phenotype-purpose-built-part-generation.md),
[material preservation](phenotype-body-material-process.md) and
[client validation](phenotype-full-body-client-validation.md). The selected
method remains purpose-built orthographic references, stock-frame measurement,
uniform scale/proper rotation/placement first, bounded measured connector edits
only when needed, opposite-frame mirroring, frozen materials, native attribute
checks and cumulative literal visual review. Rejected source trials remain
history and are not copied into current assembly inventories.

The [repository publication check](phenotypes/evidence/human-male-publication-v1/validation.json)
records the 26-pack rebuild, 107 passing unit tests, repository regression check
and exact rebuilt Human payload verification.
