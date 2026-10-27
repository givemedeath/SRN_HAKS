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

User, 2026-10-26: "The standing shapes look right; take the full lore Dwarf build forward and continue with
motion review and the female joins." The full-target Dwarf is used; the halfway variant stays as evidence only.

### Motion review (all renders on the GPU, RTX 3060; no CPU pass)

`bodymotion.py` poses every part and head001 from the body's own rig and race library chain (`srn_an_*`, then
stock), with the engine's rules: orientation keys are absolute local rotations, node positions follow the body's
own bind offsets, and the root takes its key relative to the owning animation model's rest. Ten poses (pause1,
walk, run, nwkickl, castup, conjure1, victoryfr, sit, worship, getlowlp) × front, left, rear, 5.5 mm/px.
Visible back faces count as holes. Rest geometry for ASCII rigs comes from `walkrender.rig_model`, because the
ASCII loader leaves it at zero.

* Males (r1): 0–2 px per pose, the same level as the shipped Troll male.
* Human c6 females, as reference: 0–3 px per pose.

## 4. Female joins port (in-game review pending)

`portjoins.sh` ports the Human b13 hip/knee joins and the c6 torso polish to each non-Human female:

* Scale the body uniformly to the c6 Human female rest height (exact, `restature.py`).
* Run the Human recipes with their fixed lengths. Thigh poses come from the body's own rig and race library
  (`RIGDIR`). The toolkit now honours race bind rotations on thigh, shin, foot, neck and head.
* Scale back.

Hole-fix renders must log a GPU pass; a CPU fallback aborts the port. Hole-fix history (px), every pass on the GPU:

| Body | History | Body | History |
|---|---|---|---|
| pfe0 | 384 → 7 | pfe2 | 325 → 16 (worse last pass reverted) |
| pfd0 | 0 | pfd2 | 7 → 0 |
| pfo0 | 131 → 10 | pfo2 | 60 → 9 |
| pfg0 | 111 → 8 | pfg2 | 51 → 12 |

The Fit females showed new holes in motion, at the rear waist, in kick, run and victory (pfg0 kick 3 → 15).
The Large females did not. The cause is the c6 pelvis-top rear roll. On the Fit bodies the pelvis top stands
29–40 mm outside the chest at the back, so the roll moves it in by up to 40 mm. That tuck opens when the wider
race torsos twist. The cornerround has no effect on the holes. `c6var.sh` replays the c6 stage with a weaker
rear weight; the replay of the unchanged recipe reproduces the port byte for byte. For each Fit body the
strongest weight kept was the one whose motion stays within 2 px of the pre-port body per pose:

| Body | Rear weight (140°, 180°) | Rear roll at edge | Motion holes per pose, pre-port → final |
|---|---|---:|---|
| pfe0 | 0.9, 0.8 | 23 of 29 mm | kick 0 → 2, run 4 → 5, others equal |
| pfd0 | 0.9, 0.8 | 32 of 40 mm | kick 1 → 2, others equal |
| pfo0 | 0.9, 0.8 | 29 of 37 mm | kick 3 → 4, others equal |
| pfg0 | 0.8, 0.6 | 24 of 39 mm | run 1 → 2, others equal |

The Large females keep the full c6 recipe; their motion equals pre-port. A rear crest of 6–15 mm remains on the
Fit bodies, where the Human keeps about 1 mm. The remaining extra pixels in the zoomed hip renders sit at the
raised buttock in kick: the b13 hip join in deep flexion. This is the behaviour the user accepted on the Human.

Evidence in `output/phenomorpher/race-sizing/`:
* `motion/motion-*.png`: final motion sheets.
* `motion-pre/`: pre-port motion sheets.
* `joins-review/{pre,port}/motion-pf*.png`: hip to knee at about 2 mm/px, pause1, walk, kick and sit.
* `r2-variants.txt`.

### Build r2

* `r2-ascii`: r1 with the eight ported females.
* `r2-compiled`: 307 models, audit 0 failures, inputs pinned and unchanged.
* `combo-r2`, made by `buildrace.sh`: the locked combo-c6 stage with 297 r2 models overlaid. Human bodies and
  shared skin are unchanged. Race parts share the Human skin PLTs and maps through their UVs, so there is no
  re-bake. The extra Troll heads in `srn_head` are not in the review profile.
* Installed into `profile-combo` (hardlinks, hash-checked).

In-game tours (`!rr show <race>`, white light; front, left and back, 4 s each; clips idle, castup, conjure1,
victoryfr, walk, run, nwkickl, sit, worship, meditate, getlowlp):
* Dwarf (pfd0, pfd2, pmd0, pmd2), 2026-10-26. User: "Looks good". The Dwarf bodies are the user-reviewed r2 stature, build and female joins.
* Elf (pfe0, pfe2, pme0, pme2), 2026-10-26. User: "Elves look good". The Elf bodies are the user-reviewed r2
  stature, build and female joins.
* Ork (pfo0, pfo2, pmo0, pmo2), 2026-10-26. User: "Orks look good". The Ork bodies are the user-reviewed r2
  stature, build and female joins.
* Troll (pfg0, pfg2, pmg0, pmg2), 2026-10-26: idle, castup, conjure1, victoryfr, walk and run shown. User:
  "Trolls look good" (given mid-tour). The Troll bodies are the user-reviewed r2 stature, build and female joins.

All four races are user-reviewed in game (r2, combo-r2). Human `pmh2` (c7h) has not yet had its own in-game review.

### Native gates (2026-10-27)

User: "Go straight to native gates and equipment profiles." Every step ran through `pheno.sh` (inputs pinned
before the run and re-checked after: "inputs unchanged" every time). Every compile and decompile used Blender
5.2.1 LTS with Neverblender 4.5.1 (cleanmodels v4.10.0) in headless batch mode. The client compiler was not used.

* Candidate contract `r2-release/game-ready-assets.json`, version `1.3.0-r2-candidate`, not accepted. It is the
  1.2.0 contract re-pinned to the combo-r2 stage: 513 re-pinned resources, plus the four skin-rebuild Large chest
  maps, 935 resources in all. The 2DA tables are unchanged.
* `verify-runtime` (structural): passed, no violations.
* `sweep` (static), all 20 bodies, one run per body:
  * no degenerate or coincident cross-part triangles;
  * no clearance gate false;
  * Fit and Large share one body height per race and sex.
* Compared with the shipped 1.2.0 (baseline sweep of pfg0, pmg0, pfo0):
  * Every female, the locked Human pfh0/pfh2 included, has 3 self connectors unavailable. The c6/b13 pelvis has
    open edges (the two-sided brief), so solid penetration against it is undefined. Those joins are covered by the
    GPU motion and hole renders above.
  * Donor comparisons: 1.2.0 measured 52 per Fit body; r2 measures 0–3 on the Fit bodies. The locked Human Fit
    donors no longer share topology with the race Fit parts. The Large males still measure 55 against `pmh2`.
    This is a gap in the gate's coverage, not a defect it found.

### Equipment profiles (stock armour onto the 16 race bodies)

The chain is `armor-extract`, `armor-profiles`, then `armor-convert` per Human source. Each body then gets one
batch `mdl-compile`, followed by `armor-publish` and `verify-armor` into a staging root
(`gates/equip/publish`). Nothing was written to `srn_armor/`.

* Profiles: median fit residual per body 6.2–14.9 mm (largest on the Troll bodies). Flagged above 2.0 anisotropy:
  `pmd0:belt` and `pmd0:pelvis` at 2.06, from the wider Dwarf build.
* Conversion: 6,180 models, 764 of them danglymesh. Worst world-transform error 5e-11 m.
* Compile: 16 receipts, each complete with its inputs unchanged.
* Publish and verify: 6,180 resources for 16 targets, verified. The same resource names as the shipped 1.2.0
  pack; every binary differs (refit, and the Neverblender compiler).
* A review `srn_armor.hak` is packed in `combo-r2/hak`; it is hardlinked into `profile-combo` for the client review below.

The first runs exposed two toolkit bugs. Both are fixed with regression tests in 3c6d93db, which also
corrects f776bec2's wrong exponent claim:
* The Neverblender decompiler indents node lines, and three `stock_armor` patterns were anchored at column 0.
  Because of that, the inventory recorded no mesh types for 1,431 of 1,561 models (32 danglymesh instead of
  191), and the `pmh2_footl014` duplicate-name rename stopped working.
* NWNArmory 1.3.4 skips a scale or translate whose components all lie within 1e-4 of identity. The raw-output
  proof assumed it always applies them, and failed on `pme0` neck002 (translate 2.3e-5 m). The proof now models
  the skip; the baked output still uses the exact profile.

### Armour client review (2026-10-27)

`srn_rrarmor.mod` is a variant of the review module (`armour-review/armormod.py`, receipt `armormod.json`). It keeps the
same area, bodies and `!rr` commands, adds `srn_armor` to the hak list after `srn_body_tex` (the two packs share
no resource names), and adds `!rr armor <1-12|nw_aarclNNN|none>`, which equips a stock armour item in the chest
slot. Every part of the twelve stock items `nw_aarcl001`–`012` exists for all 16 race bodies, in `srn_armor` or as
a part-1 body model in `srn_body`.

The tour ran under white light, and full plate also under flat light. It used three stock items on all 20 bodies,
and the client log records 60 of 60 equips:
* `nw_aarcl007` (full plate, torso 14): front, profile and back at idle, plus the right kick, on Dwarf, Elf, Orc
  and Troll.
* `nw_aarcl004` (scale and chain, torso 32): fronts on every race row. On the Dwarf males (the flagged
  `pmd0` belt and pelvis) it was also checked in kick, profile and back.
* `nw_aarcl001` (leather, torso 16, bare part-1 hands): fronts on every race row, plus the Troll kick.

No gaps, floating plates, skin poking through or missing parts are visible at review distance. The `pmd0` belt and
pelvis stretch (anisotropy 2.06) can't be resolved at this camera distance in the dark plate, so it stays a
watch item, not a visible defect. Screenshots and the client log are in `armour-review/`.

**User approval, 2026-10-27:** "Armour looks good." This approves the r2 armour as reviewed in the client. It
does not promote anything into `srn_armor/` or approve publication.

Next:
* client height calibration (item 5);
* in-game review and the c7 Human lock for `pmh2`.
