# Race stature and build to canon lore

Branch `claude/race-lore-sizing`, cut from the c6 Human lock (17f6dd5c). The brief comes from the lore-audit
session, 2026-10-26: `output/phenomorpher/proportion-fix-prompt.md`. The c6 lock files were verified against
`human-bodies-lock-c6.json` before use (307 files, no mismatch). Canon basis and rejected alternatives:
[`../../phenotype-race-sizing-comparison.md`](../../phenotype-race-sizing-comparison.md).

Working files live under `output/phenomorpher/race-sizing/` (ignored):

| Folder | Contents |
|---|---|
| `src-ascii` | decompiles of the shipped bodies |
| `s1-ascii` | stature-corrected bodies |
| `s2-ascii` | Large males brought back to Fit joint heights |
| `bulk/final`, `bulk/dwarf-half` | lore build, and the halfway Dwarf variant |
| `c7h-ascii` | Human `pmh2` with the item 2 fix |
| `tools-snapshot` | the tools, plus copies of the audit scripts |

## 1. Stature (done, awaiting review together with item 3)

* **Cause.** The derivation fitter (`fit_anatomy_stage1_v15a`) posed the source in `pause1` at t=0. It then
  normalized that standing pose to the target, and its 1% gate also checked the standing pose. Height targets
  are rest-pose crown to sole, and the standing stance is 1.2–1.3% lower. Every non-Human body's standing height
  equals its target to 0.1 mm, measured on its own race library: Elf F matches the old 1.85 m reference
  (2.0444 m).
* **Source fix.** Commit 7d200faf: normalize, gate and report on rest-pose stature, with a regression test.
* **Applying the fix.** The candidate recipes no longer exist, so the 1.0 derivation cannot be replayed. Stage 1's
  normalization is one uniform scale per body, so the fix is applied as that exact rescale (`restature.py`):
  rig, parts, head001, the Troll heads in `srn_head`, and the race library's position keys. Fit and Large share
  one factor per race and sex.

| Body | Rest before | Target | Factor |
|---|---:|---:|---:|
| Elf M | 2.1253 | 2.0997 | 0.98792 |
| Elf F | 2.0892 | 1.9560 | 0.93626 |
| Dwarf M | 1.3434 | 1.3261 | 0.98712 |
| Dwarf F | 1.2997 | 1.2709 | 0.97782 |
| Ork M | 2.1246 | 2.0997 | 0.98825 |
| Ork F | 2.0327 | 1.9892 | 0.97859 |
| Troll M | 2.7956 | 2.7627 | 0.98826 |
| Troll F | 2.5972 | 2.5417 | 0.97864 |

After the rescale every Fit body and every female Large body measures exactly its target.

## 2. Large male joint heights (done, awaiting review)

The pm?2 rigs raise `neck_g` (and the head) by 10–22 mm and the bicep chain by 28–56 mm. They also move them
forward by 17–32 mm and 44–80 mm.

`largefix.py` sets those joints' Z back to Fit and keeps the forward offsets. The Large chest is refit
vertically: full at and above the shoulder pivots, easing out over the upper half of the chest, and blending
from the shoulder drop to the neck drop toward the midline.

All five Large males now measure exactly the Fit height. Human `pmh2` is 1.9339 m (c7 candidate,
`c7h-ascii`).

## 3. Build (standing stage; user review pending)

`bulk.py` applies one sideways scale S to the whole rest-pose assembly about the pelvis centreline: rig joints,
parts and feet. Height is unchanged and every join keeps its fit. The heads are left unscaled; they are
separate work. `bulkfit.py` solves S so that the union-voxel build index (`voxvol` method, 5 mm, / height³)
relative to the same-sex, same-phenotype Human reaches the lore target. The Human baselines are c6 for the
females and c7h for `pmh2`.

| Race | Target | Start M Fit/Large | Start F Fit/Large | S, M | S, F | Final index |
|---|---:|---|---|---|---|---|
| Elf | 0.80 | 0.941 / 0.935 | 0.928 / 0.936 | 0.921 / 0.925 | 0.926 / 0.923 | 0.800 |
| Dwarf | 2.15 | 1.441 / 1.434 | 1.446 / 1.445 | 1.223 / 1.226 | 1.229 / 1.225 | 2.149–2.150 |
| Ork | 1.28 | 1.041 / 1.040 | 0.997 / 1.015 | 1.109 / 1.110 | 1.136 / 1.125 | 1.280 |
| Troll | 1.32 | 1.093 / 1.073 | 1.000 / 1.010 | 1.099 / 1.109 | 1.151 / 1.144 | 1.320 |

The halfway Dwarf (index ≈1.76, S ≈1.11) is kept alongside the full target for the user's choice. Evidence:
`output/phenomorpher/race-sizing/sheet-{elf,dwarf,ork,troll}.png`. Each row shows the Human reference, then the
body before and after (plus the halfway step for Dwarf) in front, side and rear views, at one metric scale.

Next steps, once the user approves the standing shapes:
* motion review;
* item 4 (port the b13/c6 female recipes to each race's females, each reviewed in game);
* rebuild the race animation libraries' derived data;
* compile and run the native gates;
* equipment profiles;
* client height calibration (item 5);
* the c7 Human lock for `pmh2`.
