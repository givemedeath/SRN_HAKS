# Root rebase: client session (contract 1.1.0 vs 1.2.0)

One NWN:EE client session (build 8193.37-17, `nwmain.exe` sha256 `3b7cb125…`) on 2026-10-25 compared
contract 1.1.0 (`fea87f61`) with contract 1.2.0 (`a6401162`), which moves every non-Human rig and
library root offset into the root's children (`root-rebase-receipt.json`). Same module, camera
commands and timing in two isolated profiles. Result: no visible difference, and every foreground
foot line lands on the same pixel row in both versions. This records client observations only; it
creates no asset, motion or production approval.

## Fixture

`output/phenomorpher/client-1.2.0-root-rebase/` (ignored; `fixture.json` sha256 `da693d71…`) holds
one module and two `-userdirectory` profiles that differ only in `srn_body.hak`:

| Profile | `srn_body.hak` | Packed from |
|---|---|---|
| v110 | 665 resources, `bc894460…` (667,871,456 B) | `fea87f61:srn_body`, blob-checked |
| v120 | 665 resources, `b2e71b2c…` (667,871,456 B) | `a6401162:srn_body`, blob-checked |

Between the two, exactly the 16 non-Human rigs and the 8 `srn_an_*` libraries differ, with the from/to
hashes in the receipt. Human rigs are byte-identical and serve as controls. Both profiles share
`srn_body_tex.hak` (`a637a009…`), `srn_2da.hak` (`8f3d498b…`), the floor HAK `srn_rr_floor.hak`
(`618fa7b0…`, stock rural tile with grass density 0) and the module `srn_rootrebase.mod`
(`6d795f86…`), all byte-identical.

The module places all 20 bodies in a 5 × 4 grid. Rows are Dwarf, Elf, Human, Orc and Troll; columns are
F Fit, F Large, M Fit and M Large. Each body has bare parts style 1, stock head 1 and skin 3. Chat commands
(`!rr …`) select a row, set the camera (`cam low`: pitch 87, height 0.25 m), loop a clip in place,
turn the bodies and set the light. `Launch-RootRebase.ps1` hash-checks the profile, requires an empty
override and no running client, and writes a launch receipt (v110 PID 22044, v120 PID 32756). The
client log records all 20 `RR_SPAWN`/`RR_BODY` lines with the expected appearance, gender and
phenotype in both sessions.

## Observations

Per profile, under flat light and the low camera, I looked at each row standing, walking, running
and in a left kick (`!rr anim idle|walk|run|kickl`), plus a dwarf side profile (`!rr face left`):

* Dwarf, Elf, Orc and Troll, both genders and both phenotypes: feet rest on the floor in every
  sampled frame of both versions, with no floating, sinking or sideways shift. The rebased models
  look identical to 1.1.0.
* Human controls: identical, as expected.
* The kick and run poses match frame for frame within sampling jitter.

`client/comparison-sheet.jpg` puts the matching v110 and v120 captures side by side (dwarf side,
run and kick; elf, human, orc and troll idle; troll run).

## Measurement

`client/foot-line-comparison.json` measures, for each body in the idle captures, the lowest
skin-coloured pixel in v110 and v120 (same camera, same command sequence):

| Capture | Bodies matched | Foot-line shift (px) | Mean abs. grey diff |
|---|---|---|---|
| dwarf standing, low cam | 7 | 0 | 0.81 |
| dwarf side profile | 8 | 0 (background ±1) | 0.67 |
| elf | 7 | 0 | 1.03 |
| human (control) | 7 | 0 (background +1) | 1.16 |
| orc | 6 | 0 | 0.89 |
| troll | 5 | 0 | 0.73 |

At this zoom one pixel on a foreground body is about 1 cm, so the dwarf female's −4.8 cm offset
would show as roughly 5 px if the engine treated the old and new rigs differently. The ±1 px
background differences come from idle sway, and the Human controls show the same jitter.

## Limits

* These are sampled frames, not all frames or all clips. Combat-ready, casting and the right kick
  were not captured.
* Bodies are bare (stock head 1, no armour, robes or cloaks).
* The full capture set (26 v110 and 20 v120 images) remains in the ignored fixture folder under
  `evidence/`.
