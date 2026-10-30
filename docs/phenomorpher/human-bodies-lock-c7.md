# Locked Human bodies: c7 (2026-10-27)

The current locked Human bodies are **c7**: the c6 lock plus the Large Human male `pmh2` from race-sizing build
r3. The user toured `pmh2` in game on 2026-10-27 (r3, `client-1.2.0-root-rebase/profile-combo`) and said "pmh2
looks good. Record the c7 Human lock."

Manifest with every hash: [`human-bodies-lock-c7.json`](human-bodies-lock-c7.json). It references the c6 manifest
by hash. The c6 record ([`human-bodies-lock.md`](human-bodies-lock.md),
[`human-bodies-lock-c6.json`](human-bodies-lock-c6.json)) stays as written.

## What is locked

| Area | Locked state | User review |
|---|---|---|
| Everything in c6 | unchanged: b13 female joins, c6 torso polish, rebuilt skin. All 220 c6 pack files are byte-identical in the c7 stage | c6 record |
| Large male `pmh2` | neck and bicep joint heights back to the Fit (stock) heights, chest refit to them (race-sizing item 2, `largefix.py`). Rest height 1.9339 m, the same as `pmh0` | 2026-10-27 in-game tour: "pmh2 looks good" |

Of the 17 `pmh2` models, only the rig (3 joint heights) and the chest have changed sources. The other 15 have the
same sources as 1.2.0, recompiled with Blender 5.2.1 and Neverblender 4.5.1. All 17 are compiled against the
stock `a_ba` supermodel; every audit passes with no warnings.

That supermodel matters. The r2 compile could not find `a_ba`, and `pmh2` then held one stiff stance in game. The
compiler now refuses that case (900a0633).

Reviewed in the client, r3:
* Clips: idle, castup, conjure1, victoryfr, walk, run, both kicks, sit, worship, meditate and getlowlp.
* Views: front, profile and back.
* Armour: stock full plate and leather, standing and in kick.

Gates: `verify-runtime` passed, and the static sweep shows no change from r2. Details are in
[`race-sizing/plan.md`](race-sizing/plan.md), items 2 and "Build r3".

## Status

* **Locked working selection.** This is the reference for further Human body work. Later changes get a new,
  separately versioned lock, and this record stays as written.
* **Not published.** `srn_body/` and `srn_body_tex/` in git are unchanged. Promotion is the separate publication
  step, with the same requirements as c6: asset manifests, publication validation, and full target and client
  validation. It needs explicit approval and a PR.
* **Where the files are.** They are generated output and ignored by git:
  * the ASCII sources: `output/phenomorpher/race-sizing/c7h-ascii`;
  * the compiled models: `race-sizing/r3-compiled`;
  * the stage and haks: `output/phenomorpher/combo-r3`. These also carry the r3 race candidate, which is not
    part of this lock.
  * the tools snapshot: `race-sizing/tools-snapshot`;
  * the tour evidence: `race-sizing/c7-evidence`.

  The c6 files listed in the c6 record are still needed. Check everything against the manifests before reuse.
  Retiring this worktree first needs a verified durable copy.
