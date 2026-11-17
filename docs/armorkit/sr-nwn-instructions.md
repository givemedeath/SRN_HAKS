# Armor parts in SR_NWN: what to do with `srn_parts`

For whoever works in the SR_NWN module repository. It says what SRN_HAKS publishes for modular armor parts, how
an item wears them, and how a logo is put on a wearer. The source of every number here is
[`parts-handoff.json`](parts-handoff.json); read it rather than copying numbers from this page. Evidence for
engine behaviour is in [the spike record](spikes.md), and what was not checked is listed at the end.

## What is published

| Pack | Holds |
|---|---|
| `srn_parts.hak` | Part models, tint textures, material files, maps, inventory icons, and the logo's three files |
| `srn_2da.hak` | `parts_*.2da` with the game's rows unchanged and a live row per published part |

Both are in `hakbuilder.json`; the module lists them as it lists the other SRN packs. The new rows carry no
armor value (`ACBONUS 0.00`): mechanics are SR_NWN's.

Published parts as of 2026-11-17, each on all 20 SRN bodies:

| Piece | Slot | Number | Item fields | Colour channels |
|---|---|---|---|---|
| Facility Security outfit | chest, pelvis, bicep, hand, thigh, shin, foot | 6020 | see handoff | see handoff |
| Duty belt (Facility Security set) | belt | 6020 | `xArmorPart_Belt` | leather1, metal2 |
| Logo brassard (standalone) | shoulder, left and right | 1000 | `xArmorPart_LShou`, `xArmorPart_RShou` | cloth2, leather1 |

The upper-arm part of 6020 shows the body's skin (its `coverage.skin` is true), so the bicep slot is taken.
The shoulder slot is free on 6020, which is why the brassard goes there.

## The handoff file

`docs/armorkit/parts-handoff.json`, kind `srn-armorkit-registry-handoff`. Per part (`parts[]`):

| Key | Use |
|---|---|
| `slot`, `number` | The part. A number in a family block (3000 to 9999) also has `setNumber` and `variant` |
| `set`, `group`, `families` | Tags for recipes and shops; a standalone piece (1000 to 2999) has no set or group |
| `itemFields` | The item's GFF fields that hold the number, left then right for a paired slot |
| `itemModelIndices` | The matching `ITEM_APPR_ARMOR_MODEL_*` indices for script calls |
| `channels` | The colour channels the part's tint textures use: offer a colour for each, and no other |
| `colours` | Optional. The design's own colour per channel, sRGB 0 to 255: a start, to be matched to the nearest palette entry; not a rule |
| `badge` | `null`, or `{positions: [...]}` where the part shows a logo (`left`, `right`, `lanyard`) |
| `coverage` | `skin`: the part shows the body's skin; `headgear`: it covers the head |
| `genderedCut`, `tiers`, `bodies`, `models`, `tintTextures` | What the kit made; not needed to wear a part |

At the top level: `pack`, `tablePack`, `tables`, `icons`, and `logo` (below). `outfits` and `iconFiles` are the
kit's own record of files and hashes; SR_NWN does not need them.

## Wearing a part

A part number above 255 lives in the word field `xArmorPart_*`, not in the old byte field `ArmorPart_*`
(spike record, section 1). Two ways to set it, both seen working in the client:

* **Script.** `CopyItemAndModify(item, ITEM_APPR_TYPE_ARMOR_MODEL, index, number)` with the handoff's
  `itemModelIndices`. This is how every client check of 6020 and of the two accessories wore them.
* **Blueprint.** Write the handoff's `itemFields` as word values in the `.uti`. A blueprint that writes only the
  old byte field loads as part 0 (sections 1 and 10).

In the toolset a new part shows in its slot's list as `Part <number>`, without a name (section 10).

One armor item carries all its slots, so the belt and the brassard are worn by setting their fields on the
same item as the outfit:

```nwscript
// Facility Security with its duty belt and a brassard on both shoulders.
object Dress(object oArmor)
{
    object oNew = CopyItemAndModify(oArmor, ITEM_APPR_TYPE_ARMOR_MODEL, ITEM_APPR_ARMOR_MODEL_BELT, 6020, TRUE);  // TRUE keeps the item's variables
    DestroyObject(oArmor);
    oArmor = oNew;
    oNew = CopyItemAndModify(oArmor, ITEM_APPR_TYPE_ARMOR_MODEL, ITEM_APPR_ARMOR_MODEL_LSHOULDER, 1000, TRUE);
    DestroyObject(oArmor);
    oArmor = oNew;
    oNew = CopyItemAndModify(oArmor, ITEM_APPR_TYPE_ARMOR_MODEL, ITEM_APPR_ARMOR_MODEL_RSHOULDER, 1000, TRUE);
    DestroyObject(oArmor);
    return oNew;
}
```

Colours are the item's ordinary armor colours (`ITEM_APPR_TYPE_ARMOR_COLOR`), one per channel the part lists.
The brassard's band is on cloth2 and its trim on leather1, so it takes those two colours from the item it is on,
along with whatever else on that item uses them.

Inventory icons exist for the chest, pelvis, belt and shoulder parts (`icons` in the handoff); the game picks
them up by name. An icon shows no logo.

## Putting a logo on a wearer

A part with a `badge` has a badge mesh that reads one cell of a shared strip texture. Which cell is a shader
value on the **wearing creature**, not on the item. The handoff's `logo` gives everything needed:

```json
"logo": {"material": "srn_logo", "parameter": "LogoCell", "strip": "srn_logos",
         "cells": {"ares": 1, "renraku": 2, "saeder-krupp": 3, "wuxing": 4, "mitsuhama": 5, "aztechnology": 6,
                   "evo": 7, "horizon": 8, "neonet": 9, "shiawase": 10, "lone-star": 11}}
```

```nwscript
// nCell: a value of logo.cells; 0 is the blank badge, which is what a creature shows until this is called.
void SetLogo(object oCreature, int nCell)
{
    SetMaterialShaderUniformVec4(oCreature, "srn_logo", "LogoCell", IntToFloat(nCell));
}
```

Rules that follow from how the value works (spike record, section 18):

* **Call it on the creature.** The same call on the armor item does nothing.
* **One logo per creature.** Every badge a creature wears reads the same value. Two different logos on one
  creature at once are not possible with this material.
* **The item must remember its logo.** The value is not stored on the item, so SR_NWN keeps the cell with the
  item (a local variable on it, for example) and sets it on the wearer when the item is equipped. Equipping the
  same item again needs no new call, but an item with another logo does, and so does an item that passes to
  another character. Setting it on every equip is the simple rule.
* **Order does not matter.** A value set before the part is worn shows once it is.
* **Store the cell's number or its name, either works.** A cell once published keeps its name and number for
  good; new logos take free cells (12 to 15 are free now, and the strip can grow). When a logo is added,
  SRN_HAKS replaces the strip and the handoff's `cells` gains an entry; nothing else changes and no part is
  republished.
* **Unequipping.** Nothing is needed: the badge leaves with the part. Reset to 0 only if a later badge on the
  same creature should start blank.

A minimal hook, assuming the cell is kept on the item as the local integer `SRN_LOGO_CELL` (the name is
SR_NWN's to choose):

```nwscript
// Module OnPlayerEquipItem
void main()
{
    object oItem = GetPCItemLastEquipped();
    object oPC = GetPCItemLastEquippedBy();
    if (GetBaseItemType(oItem) != BASE_ITEM_ARMOR) return;
    SetMaterialShaderUniformVec4(oPC, "srn_logo", "LogoCell", IntToFloat(GetLocalInt(oItem, "SRN_LOGO_CELL")));
}
```

An NPC is set the same way from its spawn script.

## Not checked: decide or test in SR_NWN

Every client check so far was one local client, one area, one session. These are open, and the first two
decide where else the logo call has to be made:

1. Whether the value lasts through an area change, a save and load, and a new login. Until it is tested, set it
   again on client enter and on area enter for the armor the character wears.
2. What other players see, including a player who arrives after the call was made.
3. The toolset's preview and the character sheet and inventory views of a badge.
4. Other graphics cards and drivers, and other game builds: `srn_vslogo.shd` includes the game's stock
   `inc_standard`, so it is rechecked on a new build (game build 89.8193.37 was used).
5. A brassard on one shoulder only. Both sides were worn in every check; leaving the other side's field at 0
   should show nothing there, and that was not looked at.
6. The belt and the brassard were looked at over Facility Security 6020 only. Over another outfit or a bare
   body they may stand off it or sink in.

## Known limits

* On the female bodies the 6020 vest has a piece over the left upper arm that hides the upper part of the left
  band while the arm hangs down. It is the vest's, and stays so for now (user, 2026-11-17).
* The duty belt's band slants across the back on the Large Orc female.
* The respirator of the same work is not published; it is on hold.
