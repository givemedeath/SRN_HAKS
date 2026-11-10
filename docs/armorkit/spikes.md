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

**Not checked.** The toolset: it was not opened, so how it lists parts in these ranges is unknown. Part numbers
above 1000 on slots other than chest. A table of this size on a multiplayer server.

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
one.

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

**Result.** *helmets.jpg*

* The helmet replaces the head on all ten bodies and sits on the neck.
* The scale columns are honoured per race row and gender; the Troll helmet at 1.94 is visibly larger than at
  1.05, which looks small on that body.

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
tint texture; or another runtime call that reaches material textures.

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
