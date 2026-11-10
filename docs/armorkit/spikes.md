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
