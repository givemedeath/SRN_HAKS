# Armorkit spikes (2026-11-09)

Evidence for [plan.md](plan.md). Every test ran on NWN:EE 89.8193.37-17 in an isolated user directory with a
throwaway module started by `+TestNewModule`; nothing touched the repository packs, `srn_2da` or the user's
game folders. These are engine findings, not asset approvals.

Screenshots are named in *italics* below. They, the spike scripts, the client logs and the downloaded
cleanmodels build were not committed: any non-Markdown file under `docs/` makes the test selector demand the
full suite. On the machine that ran the spikes they are in the ignored folder `.tmp/armorkit-spikes/`
(screenshots under `evidence/`).

## 1. Part numbers above 255

**Question.** Do armor part numbers above 255 work end to end?

**Method.** Stock Human male. `parts_chest.2da` padded to row 1000 and `parts_belt.2da` to row 300 with no
gaps. `pmh0_chest300`, `pmh0_chest1000` and `pmh0_belt300` were stock parts renamed and given a red, green and
blue glow. Items were set by `CopyItemAndModify`, and separately by a blueprint that put a word value in the
old `ArmorPart_Torso` field.

**Result.** Red torso (300), green torso (1000) and blue belt (300) all rendered; the actor whose blueprint
used the old field was bare-chested. *part-ids-above-255.jpg*

```
P255 enter ... chestRows=1001 beltRows=301 chest300=0.00 chest1000=0.00
P255 equipped actor=Script torso 300 ... torso=300 belt=0 ac=0
P255 equipped actor=Script torso 1000 ... torso=1000 belt=0 ac=0
P255 equipped actor=Script belt 300 ... torso=5 belt=300 ac=0
P255 equipped actor=UTI word torso 300 ... torso=0 belt=0 ac=0
P255 gff actor=Script torso 300 ArmorPart_Torso={"type":"byte","value":0} ... xArmorPart_Torso={"type":"word","value":300}
P255 copy actor=Script torso 1000 torso=1000 belt=0
```

* Numbers 300 and 1000 render and survive copying the creature.
* The number is stored in word fields named `xArmorPart_*`, truncated to 16 characters: `xArmorPart_Torso`,
  `xArmorPart_Belt`, `xArmorPart_Neck`, `xArmorPart_Robe`, `xArmorPart_Pelvi`, `xArmorPart_LBice`,
  `xArmorPart_LFArm`, `xArmorPart_LHand`, `xArmorPart_LThig`, `xArmorPart_LShin`, `xArmorPart_LFoot`,
  `xArmorPart_LShou` and the `R` equivalents. The old byte field holds 0.
* A blueprint that writes the old field loads as part 0. A later test confirmed that a blueprint written with
  `xArmorPart_Torso = 300` loads as 300.
* Stock parts tables have rows 0–200. `ACBONUS 0.00` rows give item AC 0.

**Not tested.** Numbers above 1000, toolset display, NWNX calls.

## 2. Belt-slot hanging pieces and a hat on the neck slot

**Method.** Hand-written geometry appended to decompiled stock parts: a box "hat" with a forward bill above the
head on `pmh0_neck300`; knee-length front and back panels on `pmh0_belt301` (rigid) and `pmh0_belt302`
(danglymesh). Actors idled, walked and ran, and one cycled head-turn, look-far and bow animations.

**Result.** *belt-tabards-neck-hat-blueprint.jpg*

* Belt panels render and follow the pelvis, rigid and dangly, standing and moving. Rigid and dangly swing were
  not compared up close.
* The hat follows the head through head-turn, look-far and salute animations
  (*neck-hat-follows-head-turn.jpg*).
* During the automatic look-at (an idle character looks at the nearest creature) the head turned and the hat
  did not. The user saw the same.
* Uncompiled ASCII parts with hand-written nodes load directly.
* On the stock Human the character's front is +Y in part space.

## 3. Making the look-at turn the neck

**Method.** `appearance.2da` has `HEADTRACK`, `HEAD_ARC_H`, `HEAD_ARC_V` and `HEAD_NAME`; these are the only
head-tracking controls in the client, and the script API has none. `HEAD_NAME` was changed from `head_g` to
`neck_g` on the race row.

**Result.** Stock Human: two hat wearers looked toward the camera character and both bills turned with their
faces. *neck-node-tracking-stock-human.jpg*

SRN bodies (rows 15100 Human, 15103 Orc, 15104 Troll, male Fit, built packs from this checkout): the outer two
actors look at the middle one, the middle one looks at the camera character, and every bill points where the
face does. *neck-node-tracking-srn-bodies.jpg*

**Limits.** Everything on the neck part turns with the look, up to the 60° arc. It is per race row. Dwarf, Elf,
female and Large were not checked. In an earlier wide shot the male Dwarf actors had no head, which was not
investigated.

## 4. Scaling parts by script

**Method.** `SetObjectVisualTransform` with scale 1.6 on a worn armor item (base scope and item part 1), and
scale 1.5 on the creature's head scope.

**Result.** The script reported the item values as set, but the worn parts did not change. The head scope
enlarged the head. *scoped-scale.jpg*

The available scopes are the whole creature, head, tail, wings and cloak, and item parts 1–5. Individual worn
armor parts cannot be scaled by script.

## 5. How SWLOR organises accessories

Read from the SWLOR hak sources; categories are a reading of untextured front and side renders of the Human
male parts. One pack per slot, part numbers to about 300, no labels in the tables.

| Category | Slot | Build |
|---|---|---|
| Backpacks, jetpacks, radio packs, slung weapons | Neck | Rigid |
| Bandoliers, sashes, chest rigs, harnesses | Neck | Mostly skinned |
| Hoods, goggles, visors, headsets, masks, respirators | Neck | Skinned |
| Collars, gorgets, mantles, short capes | Neck | Rigid, dangly or skinned |
| Utility belts, holsters, pouches, quivers, scabbards | Belt | Rigid |
| Skirts, kilts, tabards, loincloths | Belt | Rigid, dangly or skinned |
| Pauldrons; a few one-shoulder capes and sleeves | Shoulder | Rigid; skinned for the capes |
| Full helmets, hoods, alien heads | Helmet | Replaces the head |
| Coats, dresses, full suits | Robe | Skinned |

Each neck accessory also carries the plain neck mesh. Tails and wings are the stock community tables and are
not used for gear.

## 6. Skinned meshes inside ordinary parts

**Method.** Five SWLOR Human male neck parts on the SRN Human (row 15100) with `HEAD_NAME` left at `head_g`.
NeverBlender 4.5.1's bundled cleanmodels port (v4.10.0), run outside Blender, decompiled three of them using
the game install for the skeleton and recompiled them; the recompiled files then replaced the originals.

**Result.**

* Bone bindings: hood `head_g` and `neck_g`; glasses `head_g`; bandolier `torso_g`.
* In the client the hood turned with a head looking about 60° aside, the glasses and mask stayed on the face,
  and the bandolier stayed on the torso.
* The recompiled parts were the same size as the originals (not byte-identical) and behaved the same in the
  client, textures intact.

So a head-bound skinned mesh in a neck part follows the look-at with no table change, and skinned parts can be
compiled offline. Screenshots show third-party assets and are kept locally only.

**Not tested.** A skinned part authored here; other races; the Blender import and export screens.

## 7. Per-character logo swap

**Method.** A badge quad textured with a plain blank texture on a neck part, worn by five stock Human actors.
`ReplaceObjectTexture` was called on the creature, on the armor item, and on a creature that then unequipped
and re-equipped the item.

**Result.** *logo-swap.jpg*

* On the creature: works, per character.
* On the item: no effect.
* After re-equipping: the badge was blank again (one run), so the swap must be reapplied on equip.

The replacement must be a plain texture, not a tint texture, with a name of at most 16 characters.

## 8. Race versions with cleanmodels

**Method.** cleanmodels v4.17.5 for Windows, downloaded from the plenarius GitHub release with its published
SHA-256 verified (`f42f674a…2c7c75`). The repository pin (4.0.0-rc17) was not changed.

```
cleanmodels variants --to pmd0,pme0,pmo0,pmg0,pmh2 --compile \
  --resource-dir srn_body.hak --resource-dir srn_armor.hak --resource-dir srn_2da.hak <part>.mdl <out>
```

Sources were three third-party Human male neck parts: a skinned hood, a skinned bandolier and a rigid backpack.

**Result.**

* It found every male body in our packs, Large included, and wrote all 15 versions.
* With only `srn_body.hak` the fit was learned from the stock game's race parts. Adding `srn_armor.hak` made it
  learn from our converted parts ("learned from 6 existing pairs").
* In the client on the SRN bodies, at overview zoom: the hood sits on and follows the head on Elf, Orc, Troll
  and Large Human; the bandolier wraps the torso on all six with no floating or tearing visible.

**Not judged.** Close-up fit; the Dwarf hood (no head in that built pack); the backpack versions; any female
body. Screenshots show third-party assets and are kept locally only.

## 9. Leads from web research, not yet tried here

* A tint texture can carry normal, specular and roughness maps through a material file of the same name with
  the base texture line omitted. `srn_body` already ships this way.
* A non-Human part falls back to the Human part's tint texture, according to the cleanmodels documentation.
* The current game version loads custom palette images per module from haks.
* Head-aligned visual effects (`visualeffects.2da` columns `Imp_HeadCon_Node` and `OrientWithObject`) are a
  known way to add head accessories as a second slot; the effect function accepts scale, offset and rotation.
* `SetMaterialShaderUniformVec4` sets a shader value per object and could drive glow colour.

Sources: [plenarius/cleanmodels](https://github.com/plenarius/cleanmodels),
[ReplaceObjectTexture](https://nwnlexicon.com/ReplaceObjectTexture),
[SetTextureOverride](https://nwnlexicon.com/SetTextureOverride),
[EffectVisualEffect](https://nwnlexicon.com/EffectVisualEffect),
[material files](https://nwn.wiki/x/moRGAg), [head-aligned effects](https://nwn.wiki/x/R4dGAg),
[patch 8193.37 notes](https://nwn.wiki/x/AwDmC), [NWNX:EE item functions](https://nwnxee.github.io/unified/group__item.html).

# Phase 0 proofs (2026-11-10)

Run with the `tools/armorkit` fixture builder on NWN:EE 89.8193.37-17, each in its own user directory, against
the five packs built from this checkout that day (`srn_2da`, `srn_head`, `srn_armor`, `srn_body`,
`srn_body_tex`). Evidence is the `ARMORKIT ...` log lines and window captures; contact sheets named in
*italics* and the run scripts are in `.tmp/armorkit-spikes/evidence/phase0/` on the machine that ran them.
These are engine and tool findings, not asset approvals.

The test parts were made by hand for these proofs and are not art: a chest shell (the body chest pushed out
1.2 cm, numbers 6000, 9002 and 65535), a shoulder plate with a badge quad (300 and up), and a skinned hood
built from the measured neck ring and head envelope, carried on a neck part with the generic neck (300). The
Human male and female Fit sources were written as ASCII and compiled with cleanmodels 4.17.5; the other 18
bodies came from `cleanmodels variants`.

## 10. Part numbers above 1000 and the generated tables

**Method.** `tools/armorkit/tables.py` generated `parts_chest` (65,536 rows), `parts_shoulder` and
`parts_neck` (301 rows) from a registry: stock rows unchanged, padding rows `****` in both columns, live rows
`0` / `0.00`. Chest 6000 and 9002 were set by `CopyItemAndModify`; chest 65535 came from a blueprint with
`xArmorPart_Torso = 65535`.

**Result.** *numbers-tint-fallback.jpg*

```
ARMORKIT actor=pmh0 ... worn=1 ac=0 parts=1,1,1,1,1,1,1,6000,0,300,1,1,1,1,300,300,1,1,0
ARMORKIT actor=X script chest 9002 ... ac=0 parts=...,9002,...
ARMORKIT actor=X blueprint chest 65535 ... ac=0 parts=6,6,16,16,4,4,17,65535,0,1,...
```

* 6000, 9002 and 65535 render and read back, by script and by blueprint. 65535 is the top of the word field.
* Padding rows written as `****` in both columns work (the earlier spike used `0` / `****`).
* The 65,536-row table loaded and the fixture started in its usual time (not timed).

**Not checked.** Part numbers above 1000 on slots other than chest and bicep (see the upper limit below). A
table of this size on a multiplayer server.

**Toolset.** The toolset (same build) was started with `-userDirectory` on a copy of this proof's user
directory and opened the fixture module; a new armor item from the Item Wizard was opened on its Appearance
tab. *toolset-part-lists.jpg*

* The Torso list holds 65 entries, not 65,536: only rows that have a model are listed. The new parts appear
  as `007 (Part 65535)`, `008 (Part 9002)` and `009 (Part 6000)`, among the other parts of armor value 0.
* The lists carry no names, only the part number, and are not in number order.
* Choosing `Part 6000` showed the test chest in the 3D preview and Armor Class 0.
* The Left Shoulder list shows `001 (Part 300)`.
* The inventory picture of the item lost its chest area with Part 6000 chosen. The test part ships no
  inventory icon (inferred cause, not tested).

Limits: Human male preview only; the item was not saved, placed or reopened; lists for the other slots and
the female lists were not read.

**Upper limit.** Tested the day before by the planning session on the stock Human male (scratch script and log
`spike5/` in `.tmp/armorkit-spikes/`, *part-number-limit.jpg*), not rerun here:

```
P9 tables chestRows=70001 bicepRows=65536 chest65535=0.00 chest65536=0.00 chest70000=0.00
P9 actor=Chest 32768 want=32768 torso=32768 lbicep=1 stored={"type":"word","value":32768}
P9 actor=Chest 65535 want=65535 torso=65535 lbicep=1 stored={"type":"word","value":65535}
P9 actor=Chest 65536 want=65536 torso=0 lbicep=1 stored={"type":"word","value":0}
P9 actor=Chest 70000 want=70000 torso=4464 lbicep=1 stored={"type":"word","value":4464}
P9 actor=Chest 1000 want=1000 torso=1000 lbicep=65535 stored={"type":"word","value":1000}
```

* Chest 1000, 2000, 5000, 9999, 10000, 32767, 32768 and 65535 rendered and read back.
* 65535 is the hard limit: 65536 is stored as 0 (a bare chest) and 70000 as 4464, while `CopyItemAndModify`
  still reports success. The registry refuses numbers above 65535 for that reason.
* `pmh0_bicepl65535`, a 16-character model name, rendered on the bicep slot.
* Tables padded to 65,536 and 70,001 rows loaded; each is about 1.7 to 1.8 MB.

## 11. Tint textures: names, fallback and colours

**Result.** *numbers-tint-fallback.jpg*, *badge-tint-texture-name.jpg*

* The tint texture named like the part model is applied to **every mesh in that part**, whatever texture each
  mesh names (see section 15 for what this does to badges).
* A Dwarf male model whose mesh named `pmd0_chest9002`, with only `pmh0_chest9002.plt` present, rendered with
  the Human texture and the item colours: the race fallback works.
* Race versions from cleanmodels keep the Human texture name of their gender in the mesh, so they do not rely
  on the fallback. They rendered tinted on all 20 bodies, Large included.
* Item colours apply to the new parts. A per-part colour override changed the chest alone, and the left
  shoulder alone.
* A tint texture under a name other than the model name is drawn, but not with the item colours (the plate in
  *badge-tint-texture-name.jpg*, case 302, is dark).

**Not checked.** Fallback from a female or Large model to another gender or build. Material files (normal maps)
on a new part number.

## 12. Race versions of our own parts, close up on all 20 bodies

**Method.** `cleanmodels variants --to <the nine other bodies of that gender> --compile --game-dir <install>
--resource-dir srn_body --resource-dir srn_armor --resource-dir srn_2da`, from the Human male and Human female
sources. All 72 versions were written without errors. Each of the 20 bodies wore chest 6000, shoulder 300 and
neck 300 over bare skin parts and was captured from the front and rear quarter, then cropped at capture
resolution around the torso. The chest shells were also compared offline with the chest of each body.

**Result.** *race-versions-h/d/e/o/g.jpg*, *race-versions-torso-fit.jpg*, *race-versions-torso-large.jpg*

| Bodies | Chest shell in the client | Offline (shell against the chest of that body) |
|---|---|---|
| Human male and female Fit (the sources) | Sits as built | Median gap 1.2 cm |
| Male Fit: Dwarf, Elf, Orc, Troll | Looks right; hem meets the pelvis | Median gap 1.1–2.7 cm; under 7% of points inside the body |
| Male Large: all five | Looks acceptable; hem meets the pelvis | 21–50% of points inside the body; waist ring up to 2.2 cm narrower than the body ring |
| Female Fit: Dwarf, Elf, Orc, Troll | Usable; the hem is slightly narrower than the waist below it | About 38–40% of points inside the body; median gap 0.2–0.6 cm |
| Female Large: all five | **Visible step at the waist**: the bare belly and hips stand out below the hem | 31–60% of points inside; waist ring 2.6–5.6 cm narrower than the body ring |

* A worn part replaces the body part in its slot, so "inside the body" does not show as skin poking through.
  What shows is the mismatch at the joints with the neighbouring parts.
* The shoulder plates stayed on the shoulders on every body.
* The skinned hood (section 13) did not fit Dwarf heads and was poor on Troll heads.

**Verdict.** Not a pass. `variants` is good enough for male bodies and for Fit female bodies at this zoom, and
not for Large female bodies or for headgear on Dwarf and Troll. The shared cleanmodels pin was therefore **not**
moved (plan decision 14); `tools/shared-tools.lock.json` has no cleanmodels entry today, so the move would add
one. The "repository pin (4.0.0-rc17)" of section 8 and of the plan is a folder in the shared tool root that
no lock file names: adopting cleanmodels is a new shared-tool entry, not a version move, and every compile and
race version in these proofs used the unpinned 4.17.5 download.

**Limits.** One hand-made, skin-tight chest shell and one shoulder plate; no limb parts. Standing poses only.
The female shell is faceted because of how it was made, which is not a race-version fault. The offline
"inside" figure uses the nearest body point and is rough (the Human female source itself scores 7%).

## 13. A skinned part authored here, compiled offline

**Method.** The hood is a `skin` node inside `p?h0_neck300`, vertices in the neck part space, weighted to
`torso_g`, `neck_g` and `head_g`, with no bones in the part. `cleanmodels compile --game-dir <install>
--resource-dir srn_body` compiled it; no client compile was involved.

**Result.** It loaded and stayed on the head through idle movement on Human, Elf and Orc of both genders and
builds, including a Large Troll leaning back. The race versions were too small for the Dwarf male head (a cap
on the back of the head), sat above the Dwarf female head, and were too small for the Troll male head, with
the horns pushing through.

So a skinned part can be authored and compiled offline here, but headgear cannot get its race versions from
`variants`: it has to be fitted per race from the head envelope of that race.

**Not checked.** A scripted head turn or the automatic look-at with this hood (section 6 covered that with
third-party parts). Walking, running and combat.

## 14. The helmet slot on SRN heads

**Method.** A stock helmet (`nw_arhe001`) equipped on the ten Fit bodies, once on the published race rows
(`HELMET_SCALE_M 1.05`, `HELMET_SCALE_F 0.85` on all five) and once on copies of those rows with trial scales
taken from head envelope depth (Dwarf 1.13 / 1.18, Elf 0.96 / 1.03, Orc 1.2 / 1.09, Troll 1.94 / 2.05).

**Result.** *helmets.jpg* (second run, see below)

```
ARMORKIT helm actor=pmg0 helm stock worn=1 appearance=15104
ARMORKIT helm actor=pfg0 helm trial worn=1 appearance=15109
```

* The helmet replaces the head on all ten bodies and sits on the neck, at the stock scale and at the trial
  scale. All 20 actors reported the helmet worn.
* The scale columns are honoured per race row and gender. The Troll helmets at 1.94 and 2.05 are visibly larger
  than at the stock 1.05 and 0.85, which look small on those bodies; the Dwarf helmets at 1.13 and 1.18 are
  larger than at stock.

**The first run's sheet was wrong.** The driver then saved each capture under the shot number of a log line
without checking that the game had not moved on. The client stalled for 11 seconds during that run, four shots
fired back to back, and eight of the twenty helmet pictures showed a later actor under an earlier label (male
bodies under three of the female stock-scale labels; four stock-scale bodies were missing). It was found in
review by comparing log times with file times; that sheet is kept as *helmets-run2-mislabelled.jpg*. The bullets
above were first written from it and are now supported by the second run, made with a driver that lets each
shot schedule the next and refuses a capture taken after a later shot began (twenty captures, no two alike,
script `run6.py`). The bare-neck and side-view logo captures of the first run were taken after the driver was
back in step (by the same comparison of times); the other five runs show no such gap.

**Limits.** One stock helmet, standing, front quarter only. The right scale for each race was not settled; it
needs one of our own helmets. The scale is per race row and gender, so Fit and Large share it. Large bodies were
not captured.

## 15. Logo badges on SRN bodies

**Method.** A badge quad on the shoulder plate, in six builds of the part, swapped with
`ReplaceObjectTexture(wearer, "srn_logo_0", <logo>)`.

**Result.** *badge-tint-texture-name.jpg*, *badge-reapply.jpg*, *badge-material-file.jpg*

| Part build | Badge shows | Swap |
|---|---|---|
| Tint texture named like the model; badge mesh names `srn_logo_0` (compiled or ASCII, either node order, with or without glow) | The tint texture of the part | No effect |
| Tint texture under its own name; badge mesh names `srn_logo_0` | The blank logo | Works, per wearer; the plate loses the item colours |
| Tint texture named like the model; badge textured through a material file (`texture0 srn_logo_0`) | The blank logo, plate tinted | No effect |

* The earlier logo proof (section 7) worked because that part had no tint texture of its own name.
* After unequipping and re-equipping, the badge is blank again. Calling the same replacement again does
  nothing, even 12 seconds later. Restoring first (`ReplaceObjectTexture(wearer, "srn_logo_0", "")`) and then
  setting it works, and so does setting a different logo.
* Where it works, it works on SRN bodies as on stock ones (Human male).

**Verdict.** The badge as planned (a plain-texture mesh inside a tinted part, swapped at runtime) does not
work as written. No build gave a tinted part and a swappable badge together. Ways forward, none tried: one part
number per logo with the logo in a material file (the wide number blocks allow it); a badge-only part with no
tint texture; or another runtime call that reaches material textures. The third was tried afterwards and
works: see section 18.

## 16. SR_NWN: competing tables and armor value

Read from `SR_NWN` at its `master` branch (commit `9bb8169bf`, 2026-11-02).

* The only `parts_*.2da` files are stock reference copies under `content/reference/nwn-ee/` and one source
  file in a Troll spike folder. No table is shipped from outside those folders.
* Nothing under `src`, `tools`, `ops` or `tests` reads item armor value, parts tables or armor appearance
  (searched for `GetItemACValue`, `ACValue`, `BaseAC`, `ACBONUS`, `ArmorPart`, `ArmorModel`,
  `ItemAppearance`, `ITEM_APPR_`).

**Limits.** Only `master` was read; the repository has many other branches. `OLD_SR_MOD_ASSETS` was not
searched.

## 17. Seen in passing

* **Heads on Large bodies.** Published heads exist for the Fit build only. A Large body asks for the head model
  of its own build first: Large Trolls showed the `p?g2_head001` that `srn_body` ships instead of published
  head 1, and the Large Human female showed a stock head 28. Large bodies whose head number has no Large model
  fell back to the published Fit head (Human male 86).
* **Necks.** The neck bone is the same share of head-bone height in every race (about 4.4% male, 6.7% female),
  and Elf heads reach lower than Human heads, so Elf necks are not longer by measurement. The neck part is a
  low-polygon tube wider than a narrow jaw, which shows as a ring under the head on Human and Elf alike
  (*bare-necks.jpg*).
* **Human clothing.** `srn_armor` holds no Human parts; the Human bodies wear the stock game parts.
* **Stock tables.** `parts_robe` has rows 0–38 and 19 `HIDE*` columns; the other eleven tables have rows 0–200.

## 18. A logo picked per wearer by a shader value

**Method.** The third way forward of section 15, tried at the user's request. One strip texture holds four
logo cells side by side. The badge mesh names a material file with the strip as `texture0`, one parameter
`LogoCell` and a custom vertex shader; the fragment shader is the stock `fslit`. The vertex shader is the stock
`vslit` with one added line, which moves the badge's 0–1 texture coordinate into the chosen cell:

```
ApplyStandardShader();
vVertexTexCoords.x = (vVertexTexCoords.x + LogoCell) / 4.0;
```

The part keeps its tint texture named like the model. A script on the wearer calls
`SetMaterialShaderUniformVec4(wearer, "ak_logo", "LogoCell", <cell>)`. Human male, the shoulder plate (rigid)
and the hood (skinned) of section 13, game build 89.8193.37-17 (scratch scripts `run7.py`, `run8.py`,
`run9.py`).

**Result.** *logo-shader-before.jpg*, *logo-shader-after.jpg*, *logo-shader-cases.jpg*,
*logo-shader-reequip.jpg*

| Case | Seen |
|---|---|
| No call | Cell 0 (the blank logo); the plate takes the item colours |
| Three wearers of the same part set to cells 1, 2 and 3, the third with other item colours | Each shows its own logo, and each plate its own item colours |
| Unequip and re-equip, no further call | The logo is still shown. Run 9 logged the item off and on again and captured the bare shoulder in between |
| Re-equip, then the same call again; or reset, then set | The logo is shown |
| The call made on the armor item instead of the wearer | No effect |
| Value set while the part is not worn, part worn afterwards | The logo is shown |
| Set to one logo, 14 seconds later to another | The second logo |
| Left and right shoulder | Both show the logo |
| The skinned hood on the same material and shader | The chosen cell, on a standing wearer; no head turn or other motion was run |
| Hood and plate worn together, one call | Both show the logo |

* The client logs record no shader error.
* The badge of the test shoulder plate was mapped mirrored from the start. The sheet of section 15 already
  shows a reversed "B" in its "set a different logo" case, and that was not noticed then. Run 8 flips the
  coordinate. This was an error in the scratch part, not an effect of the shader.
* One custom shader served both the rigid and the skinned mesh. The shared stock include `inc_transform`
  switches skinning on a `skinmesh` value, so a skinned mesh needs no shader of its own. (The stock
  `vslit_sk` differs from `vslit` only in its environment-map setting.)
* The value belongs to the creature and the material name, not to the item. Every part a creature wears
  that uses the material shows the same logo, and a value set before the part is worn is used when it is.

**Verdict.** This gives what section 15 could not: a tinted part and a logo chosen per wearer together, on
rigid and skinned meshes, with nothing to reapply when the same item is equipped again. Because the value
sits on the creature, an item that carries a different logo needs a new call when it is equipped.

Not checked: two different logos on one creature at once (that needs a second material); what other players
see in multiplayer, including a player who arrives after the call; whether the value lasts through a save, an
area change or a new login; other graphics cards and drivers; other game builds
(the custom shader includes the stock `inc_standard`); the toolset preview and the inventory and character-sheet
views; more than four cells, and how large the strip may be; a badge that also needs a normal map (that needs
a shader made from `vslit_nm`); bodies other than Human male (the shader does not depend on the body).

## 19. Why race versions under-fit Large female bodies, and shape factors

**Method.** Offline first. In body space, horizontal sections of the chest and pelvis skin parts and of the
test chest shell of section 12 were measured from the waist joint centre: half width, front depth and back
depth. The same was done for the Fit and Large chest parts of the stock game, for every chest in `srn_armor`
against the body it was made for, and for the bare outline across the join. The published clothing was then
viewed in the client on Large female bodies with a bare pelvis and with the matching pelvis piece. Scratch
scripts `waist_profile.py`, `chest_compare.py`, `armor_compare.py`, `run10.py`.

**Result: the cause.**

How much wider the Large Human female chest part is than the Fit one, by height above the waist joint:

| Height | SRN Large ÷ Fit | Stock game Large ÷ Fit | Test shell, Large ÷ Fit (what `variants` applied) |
|---|---|---|---|
| Waist | 1.79 | 1.69 | 1.38 |
| +8 cm | 1.44 | 1.67 | 1.44 |
| +12 cm | 1.31 | 1.66 | 1.40 |
| +20 cm | 1.20 | 1.46 | not measured |

* `variants` fits by scaling about the skeleton, close to one factor for the whole chest. The SRN Large female
  grows far more at the waist than at the ribs, which the stock Large female does not. The shell, meant to
  stand 1.2 cm outside the body, came out 2.3 cm inside it on each side at the waist and 2.8 cm outside it
  at the ribs.
* Between the ribs and the shoulder blades the SRN Large female torso sits 3–4 cm further back on the skeleton
  than the Fit one (the stock Large stays within 1.5 cm). Scaling cannot follow a shift: the shell was
  about 4 cm inside the body at the back.
* On Large female bodies the chest part stays the outer surface well below the waist joint. The pelvis takes
  over 2–5 cm below the joint at the sides and 4.5–10.5 cm below it at the back, deepest on the Troll and
  shallowest on the Dwarf (Human: 3.5 and 6 cm). On all five Fit female bodies it takes over at the joint at
  the sides. A top authored on Fit ends its hem on the widest part of the body.
* Large male bodies differ among themselves. On the Human the shell is loose where it is wrong, up to 4.8 cm
  proud at the front at the waist. On the Dwarf, Elf, Orc and Troll it is 2–6 cm inside the body on each side
  from the waist to 5 cm above it, and on the Elf, Orc and Troll to 10 cm above it. That is the same inward
  error as on Large female bodies, although section 12 found them acceptable at its zoom. None was rerun with
  shape factors.

**Result: the bodies and the published clothing.**

* The bare outline across the chest and pelvis join changes by at most 1.5 cm per centimetre of height on all
  20 bodies, and Large female bodies are no worse than Fit ones. No fault was found in the bodies.
* On the four Large female bodies that have clothing in `srn_armor`, the median chest (36 each) sits 1.5–2.8
  cm inside the body on each side and 3–5 cm inside at the front at the waist. Fit female and Large male
  chests sit outside. Fit male chests are level with the body at the sides but 4.5–7.5 cm inside it at the
  front at the waist; that was not looked at in the client. On Large female bodies the shortfall reads as a
  slightly pinched waist over a bare pelvis and is hidden by the matching pelvis piece (*published-clothing-
  pfo2.jpg*, *published-clothing-pfh2.jpg*, with the Fit Orc female for comparison in *published-clothing-
  pfo0.jpg*).

**Method: shape factors.** `variants` takes `--shape` with a factor for each of shoulders, chest, waist and
hips. The factors were taken from the bodies themselves: the source body's own chest skin part goes through
`variants` as a probe, and where the probe is narrower or wider than the target's real chest part is the
factor that region needs (two rounds of correction). The factors were then applied to the test shell, measured
against the body, and viewed in the client on the five Large female bodies over a bare pelvis. Scratch scripts
`shape_fit.py`, `run11.py`.

**Result: shape factors.** *large-female-shape-factors.jpg*

Factors found: hips 1.38–1.41, waist 1.29–1.42, chest 0.88–0.93, shoulders 0.91–1.06. Shell error in half
width, in cm, against where the shell was meant to sit, which is 1.2 cm outside the body. A negative value is
short of that position; it is inside the body only when it is below −1.2.

| Body | Waist before | Waist after | Hips before | Hips after |
|---|---|---|---|---|
| Human Large female | −3.5 | +0.9 | −4.6 | −0.2 |
| Dwarf Large female | −5.1 | +0.9 | −6.1 | −0.1 |
| Elf Large female | −4.7 | +0.6 | −5.9 | −0.6 |
| Orc Large female | −5.9 | +1.3 | −6.6 | +0.5 |
| Troll Large female | −7.3 | +2.0 | −7.6 | +1.7 |

* In the client the hem now meets the pelvis on all five, front and rear, with no step.
* What the factors do not reach: on the Human Large female the shell stays 1.8–4.5 cm short at the back from
  the hips to the ribs, the backward set described above. On the other four the back is within 2.3 cm from
  the hips to the ribs, and 2.1–4.3 cm proud at shoulder height (Troll most).
  Outlines of body and shell are drawn in *large-female-back-outlines.png*; in the client her back reads
  slightly flatter in the shell than bare, with no gap, because a worn part replaces the body part
  (*large-female-back-views-pfh2.jpg*, scratch scripts `back_diagram.py`, `run12.py`).
* Expected but not tried: a back-mounted accessory made the same way would also sit about 3 cm forward on
  the Human Large female, which over bare skin means sunk into the back.
* At shoulder height the shell is 3.3–4.9 cm short at the front on the four non-Human bodies. That was so
  before the factors as well and they do not change it.

**Verdict.** The step of section 12 comes from the fit method meeting a body that is not a scaled Fit body. It
is not a fault of the bodies. Shape factors measured from the bodies remove it for this shell.

Not checked: slots other than the chest; Large male bodies with factors, four of which show the inward error;
Fit bodies with factors; a looser or a skin-tight real garment; a pelvis piece made the same way under the
chest; motion; the three client sheets of run 10 not named above.

## 20. The under end of a split part: a rounded cap, not a copy of the over part

Checked in the client on 2026-11-10 (Phase 1; scratch script `overlap_view.py`). The outfit was a stand-in:
the Human Fit male's 15 skin parts pushed out 1.2 cm and joined, then cut by `tools/armorkit/split.py` with
the tier 1 overlaps of the seam contract. Every part was tinted unlike its neighbours, so one part showing
through another is a patch of the wrong colour. Poses: standing, sitting, crouching (get low), conjure and
worship, as stills.

| Under end | Standing | Sitting, crouching |
|---|---|---|
| Band: a copy of the over part's surface past the plane, 15% narrower at its far end (the splitter's first form) | Patches of the under part show through the over part at the waist, shoulders and knees | Large areas show through: the pelvis over much of the back, the thighs through the pelvis |
| None | Clean colours, an open gap at every joint | The gaps widen |
| Dome grown from the under part's own rim, about the joint centre | No gaps; slivers at the shoulder tops and knees | Clean |
| The same dome drawn in a further 30% of its radius by its far end (`split.cap`, `LEAN`) | No gaps, no slivers seen | Clean |

Why the band fails: it lies almost on the over part's surface at rest, and it is as deep as the contract's
minimum overlap, so it swings out of the over part when the joint turns. At the contract's design bends that
is 3.1 cm at the wrist to 8.2 cm at the hip beyond its 15% narrowing; only the neck stays inside. A dome
about the joint centre turns inside itself, which is what `seams.minimum_overlap` assumes.

Seen in passing: tint textures loaded only as one texture per part, named like its model, on a mesh with real
texture coordinates. One flat tint texture shared by all parts, with every texture coordinate at zero, drew
every part as chrome. Section 21 rules out the zero coordinates; the cause is not known.

Not checked: the Human Fit female and the other 18 bodies; a generated garment in place of the stand-in,
whose parts carry the body's own nested ends and show ragged edges at the knees with any under end; motion;
parts of different sets or tiers worn together; a loose garment whose rim is far from the joint centre. The
band run's captures were not kept: a later run cleared the folder.

## 21. Parts written by the export step, in the client

Checked on 2026-11-10 (scratch script `export_view.py`). The stand-in of section 20 was split with caps and
written by `tools/armorkit/export.py`: models in bone space with normals taken on the whole outfit before the
split, one tint texture per part named like its model, compiled with cleanmodels 4.17.5. Human Fit male,
standing and sitting, 12 stills.

* **Tint texture rows.** Each part's texture coordinates ran 0–1 up its own height, and its texture held one
  colour channel in the first half of its rows and another in the second. Every part showed the first
  channel on its lower half. The first row stored is the row at v = 0.
* **Normals.** The shading runs on across the waist, shoulders, elbows and knees with no crease at the
  seams.
* **Texture coordinates all at zero.** The same parts with every coordinate at zero drew in the flat colour
  of the texture's first pixel, not as chrome. So the chrome of section 20 did not come from the zero
  coordinates.

Not checked: a texture that is not square or not 64 pixels; which way u runs; parts on any other body;
shadows, which these parts cast for the first time.
