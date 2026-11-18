# Approved weapon release packs

Build the normal release through the existing pack builder:

```powershell
./tools/Build-Haks.ps1 -Pack @('srn_weapon','srn_2da') -SkipTlk
```

`srn_weapon` contains the approved models, runtime diffuse maps, inventory icons
and thirty-six builder blueprints for thirty-four weapon designs. `srn_2da` supplies
the native carrier table. No custom TLK is required. The inventory and resource
hashes are in `approved-weapons-v1.json`; the generated combat release manifest
describes the complete resource closure.

| Family | BaseItem / ItemClass | Released designs |
|---|---|---|
| F1 | 22 / WSwDg | Cougar Fineblade Knife; Cougar Fineblade Longblade; Survival Knife; Ceramic Knife; Vibro Blades — Knife; Sai |
| F2 | 1 / WSwLs | Cougar Fineblade Longsword; Stun Baton; Vibro Blades — Sword; Sword; Club; Extendable Baton; Tomahawk; Rapier; Mace; Macauitl |
| F4 | 13 / WSwGs | Katana; Claymore; Baseball Bat; Combat Axe; Nodachi |
| F5 | 50 / WDbQs | Staff; Stun Staff; Spear; Pole Arm |
| F6 | 111 / WWhip | Whip |
| F7 | 61 / WBwSl | Colt L36 (both finishes); Ingram Smartgun X; Ares Predator IV; Fichetti Security 600; Yamaha Pulsar; HK MP-5 TX |
| F8 | 6 / WBwXh | AK-98 and its separate launcher entry; Heavy Crossbow; AK-97; Defiance T-250 |
| F9 | 8 / WBwLn | Bow |
| F11 | 63 / WThAx | Throwing Knife |
| F12 | 56 / AShLw | Riot Shield |

The plan snapshot is retained in `weapon-baseitem-plan-v1/`. This implements the
grouping of these released assets, not the entire proposed catalog or its future
scripted combat rules. Native gameplay fields, ammunition behavior, prices and
item properties are not rebalanced by this publication.

## Existing Cougar and Colt migration

The approved long-blade knife was previously carried on compatibility row 0.
Its `sr_cougar` blueprint now uses F1 / row 22 with dagger appearance 81. Three
equal-length model-name aliases preserve the exact approved position, normal,
UV, shadow and material bytes. The diffuse is unchanged; the new F1 inventory
icons fit the original silhouette into a 32x32 canvas. Original short-sword
model/icon resources and row 0 remain available for existing saved instances.
Existing inventory instances are not automatically rewritten.

The smaller Knife remains F1 / row 22. The full-sized Cougar Longsword remains
F2 / row 1. Both Colt finishes already use F7 / row 61; their native blueprints,
models, textures, appearance addresses and fit remain unchanged. F2's MaxRange
display field is extended from 100 to 111 so its already-approved 101 and 111
addresses are selectable (later 121 for the Vibro sword and 181 for melee wave 2, see below). All other
table bytes remain unchanged.

The Crossbow diffuse is published under the name its approved compiled model
actually references (`sr6abe18c_06`); the pixels and model bytes are unchanged.
The Throwing Knife explicitly includes its approved `wthax_001` projectile.
That native projectile is shared by the F11 carrier; other throwing profiles
are not implicitly qualified by this representative.

## Bodies and animation ownership

The shipped body packs, their geometry, rig, proportions, textures and roots are
unchanged. Approved native weapon geometry and embedded Bow/Crossbow motion data
are retained. The prototype Human body/firing overlays and their event hooks are
**itemkit testing only** and are excluded from every normal release pack.
Production weapon-animation integration belongs to the PhenoMorpher toolkit.
In particular, this asset release does not claim a production replacement for
the Sling carrier's stock throwing motion or a firearm ammunition/reload system.

## Throwing Knife size revision

The user approved the 50% Throwing Knife on 2026-11-04 after seeing the candidate.
All three parts were scaled uniformly about the native grip origin with
`resize-corners`, then recompiled offline; UVs, normals, texture and icons are
unchanged. `wthax_001` carries the same scale in its vertex floats only, so its
flight, impact and emitter data stay byte-identical. It remains the projectile for
every Base 63 throw. Length is now 0.252 and midpoint grip depth about half the
melee reference, a deliberate departure from it. No client validation record or
production acceptance is created here.

## Vibro Blades — Sword and Ares Predator IV (2026-11-05)

Both designs come from the SR4 catalog through the itemkit pipeline (clay and detail
references, saved-shape appearance, donor export, fit, reduce, unwrap, bake, native
package). Models, diffuse maps, icons and blueprints are the exact bytes of the
accepted native packages (`sr421b34c6h.hak`, `sr3ab64906h.hak`); hashes are in
`approved-weapons-v1.json`. The user approved each after seeing it in the NWN:EE
client on both shipped Human bodies ("predator looks good", "sword looks good too").

| Item | Family | Blueprint | Appearance |
|---|---|---|---|
| Vibro Blades — Sword | F2 / row 1 (Cougar melee grip standard) | `sr421b34c6` | `wswls_*_121`, diffuse `sr421b34c6_12` |
| Ares Predator IV | F7 / row 61 (Colt firearm grip standard) | `sr3ab64906_5` | bottom `065`, top/middle `015` (hidden), diffuse `sr3ab64906_065` |

The Predator uses colour address 5 because 1–4 collide with the published Colt and
Ingram placeholders. Its depth/width/usable-length fit and the Cougar-standard
sword fit are recorded with the private itemkit run, not in this repository.

Table changes are appearance-picker extensions only: F2 `MaxRange` 111 to 121 and
Sling row 61 `MaxRange` 52 to 65 (the earlier 50 to 52 and `ModelType` 0 to 2
changes stand). No gameplay, price or item-property field changes. The Predator
keeps Sling rules, animations and ammunition; no firearm reload or ammunition
system is published. The itemkit client checks used per-item private fixtures
(screenshots and logs retained locally); they are not the production animation
or exhaustive equipment acceptance. The comparison module below gained a
reviewer pair for each, with the Predator included in the test-only F7 motion
mapping. In this module's client the selector stages both new pairs and both
bodies hold the weapon (static inspection); their 60-second attack tests were not run.

## Melee wave 1 (2026-11-13)

Four designs from the first melee wave (the 35-design melee plan of 2026-11-09, not the original weapon waves 1 and 2),
published with wave 2 below. Each package is the exact bytes of the native HAK,
and each blueprint the exact bytes from the fixture module, of the run the user approved in the NWN:EE client ("Yes,
keep it" for each). Hashes are in `approved-weapons-v1.json`. The Spear is not included: only its clay is approved.

| Item | Family | Blueprint | Appearance | Length |
|---|---|---|---|---|
| Survival Knife | F1 / row 22 | `sr1243dd1a` | `wswdg_*_091`, diffuse `sr1243dd1a_09` | 0.47 m |
| Sword | F2 / row 1 | `sr47885d5d` | `wswls_*_131`, diffuse `sr47885d5d_13` | 1.10 m |
| Club | F2 / row 1 | `sr0eabace5` | `wswls_*_141`, diffuse `sr0eabace5_14` | 0.76 m |
| Claymore | F4 / row 13 | `srf91fc563` | `wswgs_*_081`, diffuse `srf91fc563_08` | 1.45 m |

The Sword was generated bowed and straightened along its centreline; the Club was straightened, its end caps squared and
its handle kept round. The Claymore blade was thinned to half its generated depth, and the user chose its 1.45 m length
over the 0.98 m the hand-depth rule gives. All four use the Cougar melee grip standard, with the recorded departures for
the round Club handle and the thick Claymore grip. The Sword's in-game approval was of its shortened 1.10 m size.

The original in-game checks missed the Claymore hand close-up and the Club's female hand. Scripted idle captures of
rebuilds of the same fits show both grips in hand on both Human bodies. The rebuilds differ from the published packages
by about 30 bytes per model and at most one colour level. The user approved the hand fit from those captures ("Hand fit
is fine", 2026-11-13). No two-hand Claymore grip or attack frame, and no Knife male close view or attack frame, was
reviewed. All four appearance numbers already fall inside their rows' `MaxRange`, so wave
1 needs no table change. The comparison module gained a reviewer pair for each (`sw6_`), not run in its client.

## Melee wave 2 (2026-11-13)

Five more SR4 catalog designs went through the same itemkit pipeline. Geometry came from the colour detail image
through the shared ComfyUI. Each package is the exact bytes of its reviewed native HAK; each blueprint is the exact
bytes from its private fixture module. Hashes are in `approved-weapons-v1.json`. The user approved each after seeing it
in the NWN:EE client on both shipped Human bodies ("knife and bat look good", "baton looks good", "staff looks good",
"tomahawk looks good too"), then asked for publication ("Yes, publish them").

| Item | Family | Blueprint | Appearance | Length |
|---|---|---|---|---|
| Ceramic Knife | F1 / row 22 | `srd6342080` | `wswdg_*_111`, diffuse `srd6342080_11` | 0.40 m |
| Extendable Baton | F2 / row 1 | `srd1aaa8cd` | `wswls_*_171`, diffuse `srd1aaa8cd_17` | 0.65 m |
| Tomahawk | F2 / row 1 | `sre99544ae` | `wswls_*_181`, diffuse `sre99544ae_18` | 0.55 m |
| Baseball Bat | F4 / row 13 | `sr1d8f6e60` | `wswgs_*_091`, diffuse `sr1d8f6e60_09` | 0.95 m |
| Stun Staff | F5 / row 50 | `sr05afd23e` | `wdbqs_*_081`, diffuse `sr05afd23e_08` | 1.90 m |

The knife and the sword-family pieces are sized from the Cougar melee grip standard. The baton and tomahawk keep a round
handle, the bat uses the two-hand uniform fit, and the staff is thinned evenly to a user-chosen 41 × 49 mm grip. The
staff bakes with a reviewed colour-only patch that the user approved in chat. The tomahawk is turned half a revolution
about its axis so the blade faces forward. These fit records stay with the private itemkit runs.

Table changes are appearance-picker extensions only: F1 `MaxRange` 100 to 111 and F2 `MaxRange` 121 to 181. F4 (091)
and F5 (081) already fall inside their ranges. No gameplay, price or item-property field changes. Like the earlier
itemkit blueprints, these keep the fixture description text and have zero cost and no item properties. The comparison
module below gained a male/female reviewer pair for each (`sw5_`), but those pairs have not been run in its client. The
items were reviewed in their own scripted fixtures, which is not production animation or exhaustive equipment
acceptance.

## Melee wave 3 and the Spear (2026-11-13)

Wave 3 adds three SR4 catalog designs through the same pipeline: geometry comes from the colour detail image through
the shared ComfyUI. It also adds the wave-1 Spear, which was meshed from its colour side view with
`tools/itemkit/profile_mesh.py` and not generated. All four went in through `drive publish`. Each package is the exact
bytes of its reviewed native HAK, and each blueprint is the exact bytes from its private fixture module. Hashes are in
`approved-weapons-v1.json`. The user approved them after seeing unattended in-client captures on both shipped Human
bodies: "Approve all three" for wave 3, and "Yes, keep it" for the Spear, which publishes "With wave 3".

| Item | Family | Blueprint | Appearance | Length |
|---|---|---|---|---|
| Vibro Blades — Knife | F1 / row 22 | `sr42aae67c` | `wswdg_*_121`, diffuse `sr42aae67c_12` | 0.43 m |
| Rapier | F2 / row 1 | `sr84ad1333` | `wswls_*_191`, diffuse `sr84ad1333_19` | 1.10 m |
| Combat Axe | F4 / row 13 | `sr9849b566` | `wswgs_*_101`, diffuse `sr9849b566_10` | 1.00 m |
| Spear | F5 / row 50 | `sr2febc2a8` | `wdbqs_*_071`, diffuse `sr2febc2a8_07` | 2.20 m |

- **Vibro Knife:** sized from the Cougar melee grip standard. It was refitted after the user reported it looked wrong:
  the first fit had turned it a quarter about its long axis, so the blade showed its edge. Its lanyard hole is colour
  only ("Drop it").
- **Rapier:** uses a 2048 runtime texture, which the user chose.
- **Combat Axe:** carried as a two-hand greatsword. Its round haft is a user-authorised departure from the grip
  standard.
- **Spear:** kept at the stock Staff length. Its head is a flat blade, with no depth from the side view.

The fit records stay with the private itemkit runs.

Table changes are appearance-picker extensions only:

- F1 `MaxRange` 111 to 121
- F2 `MaxRange` 181 to 191
- F4 `MaxRange` 100 to 101

F5 (071) already falls inside its range. No gameplay, price or item-property field changes. The comparison module
gained a male/female reviewer pair for each (`sw7_`), but those pairs have not been run in its client.

## Melee wave 4 (2026-11-14)

Wave 4 adds five SR4 catalog designs through the same pipeline: geometry comes from the colour detail image through
the shared ComfyUI. All five went in through `drive publish`. Each package is the exact bytes of its reviewed native
HAK, and each blueprint is the exact bytes from its private fixture module. Hashes are in `approved-weapons-v1.json`.
The user approved them after seeing unattended in-client captures on both shipped Human bodies: "Approve all five".

| Item | Family | Blueprint | Appearance | Length |
|---|---|---|---|---|
| Sai | F1 / row 22 | `sr6a19234a` | `wswdg_*_131`, diffuse `sr6a19234a_13` | 0.62 m |
| Mace | F2 / row 1 | `sr4c45ec83` | `wswls_*_201`, diffuse `sr4c45ec83_20` | 0.75 m |
| Macauitl | F2 / row 1 | `sr994ca81b` | `wswls_*_211`, diffuse `sr994ca81b_21` | 1.11 m |
| Nodachi | F4 / row 13 | `sr36b5c592` | `wswgs_*_111`, diffuse `sr36b5c592_11` | 1.50 m |
| Pole Arm | F5 / row 50 | `src3ccd3b0` | `wdbqs_*_091`, diffuse `src3ccd3b0_09` | 2.00 m |

- **Sai:** the user chose a shorter Sai. To keep the standard grip, only the cord handle was lengthened ("just stretch
  the handle part if needed"). After the first capture, the prong arms were shortened so the spread is 20% narrower
  ("the side blades fan out too wide"); the tips keep their shape.
- **Mace:** made from the third geometry attempt, straightened through its head (`straighten --whole`). Four target
  faces bake with a reviewed colour patch that the user approved.
- **Macauitl:** its ring pommel stays open through a reviewed opening probe. Six faces at the paddle base bake with a
  reviewed patch, and the colour transfer reaches 3.8 mm; the user approved both.
- **Nodachi:** carried as a two-hand greatsword. Its round grip is a user-authorised departure from the grip standard.
- **Pole Arm:** the staff carrier sizes the whole section from the grip, so the design is stretched 2.3x along its
  length, axe head included, as the user chose. Its colour transfer reaches 4.2 mm, which the user approved.

The fit records stay with the private itemkit runs.

Table changes are appearance-picker extensions only:

- F1 `MaxRange` 121 to 131
- F2 `MaxRange` 191 to 211
- F4 `MaxRange` 101 to 111

F5 (091) already falls inside its range. No gameplay, price or item-property field changes. The comparison module
gained a male/female reviewer pair for each in the `sw1_` row (`sw8_`), but those pairs have not been run in its
client.

## Melee wave 5 (2026-11-14)

Wave 5 adds three SR4 catalog designs through the same pipeline: geometry comes from the colour detail image through
the shared ComfyUI. All three went in through `drive publish`. Each package is the exact bytes of its reviewed native
HAK, and each blueprint is the exact bytes from its private fixture module. Hashes are in `approved-weapons-v1.json`.
The user approved them after seeing unattended in-client captures on both shipped Human bodies: "Looks good".

| Item | Family | Blueprint | Appearance | Length |
|---|---|---|---|---|
| Katar | F1 / row 22 | `srdaa6941e` | `wswdg_*_141`, diffuse `srdaa6941e_14` | 0.60 m |
| Tonfa | F2 / row 1 | `srb8bdf709` | `wswls_*_221`, diffuse `srb8bdf709_22` | 0.54 m |
| Telescopic Staff | F5 / row 50 | `sr893e13e4` | `wdbqs_*_101`, diffuse `sr893e13e4_10` | 1.80 m |

- **Katar** and **Tonfa** are side grips: the fist closes on a grip that crosses the weapon (the Katar's crossbar, the
  Tonfa's side handle), so each takes one uniform scale from its chosen length. Both handles are user-authorised
  departures from the grip standard.
- **Katar:** the fist is on the crossbar and the blade points forward past the knuckles ("Fist on crossbar"). The first
  fit held it backwards and was turned half a turn about the crossbar before the user saw it.
- **Tonfa:** the shaft runs along the back of the forearm at the little-finger end of the fist, and the knob points
  forward past the thumb. The first capture was too long and held back to front ("Tonfa is too long and not facing the
  right direction"). Only the long arm of the shaft was shortened ("Shorten shaft only"), so the handle keeps its
  0.75 fit scale. Its shadow mesh is a simplified copy bounded at 8 mm from the shaft.
- **Telescopic Staff:** meshed by turning its profile about the long axis, then the tubes were stretched to 1.80 m
  ("1.8 m, tubes only").

The fit records stay with the private itemkit runs.

Table changes are appearance-picker extensions only:

- F1 `MaxRange` 131 to 141
- F2 `MaxRange` 211 to 221
- F5 `MaxRange` 100 to 101

No gameplay, price or item-property field changes. The comparison module gained a male/female reviewer pair for each
in the `sw1_` row (`sw9_`), but those pairs have not been run in its client.

## Melee wave 6 (2026-11-15)

Wave 6 adds four SR4 catalog designs through the same pipeline and `drive publish`. Each package is the exact bytes of
its reviewed native HAK, and each blueprint is the exact bytes from its private fixture module. Hashes are in
`approved-weapons-v1.json`. The user approved them after seeing unattended in-client captures on both shipped Human
bodies: "Approve all three" for the Kris, Jupiter Taser Club and Monofilament Sword, then "Approve the Rattan" after the
Rattan Stick was rebuilt. The Sap is on hold and the Bottle was dropped ("drop the bottle"); neither is published.

| Item | Family | Blueprint | Appearance | Length |
|---|---|---|---|---|
| Kris | F1 / row 22 | `sr8070eecb` | `wswdg_*_151`, diffuse `sr8070eecb_15` | 0.60 m |
| Monofilament Sword | F2 / row 1 | `sr79104ee8` | `wswls_*_151`, diffuse `sr79104ee8_15` | 0.96 m |
| Jupiter Taser Club | F2 / row 1 | `srd88e01a2` | `wswls_*_161`, diffuse `srd88e01a2_16` | 0.75 m |
| Rattan Stick | F2 / row 1 | `sr48d86616` | `wswls_*_231`, diffuse `sr48d86616_23` | 0.70 m |

- **Kris:** the handle was stretched 3x to take the standard hand ("Stretch handle 3x, 0.57 m"). With the handle
  sized to the hand the fitted Kris is 0.60 m, not the 0.57 m that option named. Its guard openings are measured
  through that stretch.
- **Monofilament Sword:** chosen at 1.0 m ("Sword 1.0 m"), it fits at 0.96 m: the grip is sized to the hand and the
  pommel cannot extend further. The curled crossguard arms were levelled back into the blade plane ("and the sword
  crossguard too"). Its eight crossguard slits are closed in the working shell ("Close the slits"). The bake could not
  colour the closed slits or the shell's blade edge, so the donor carries matching plug faces there in the nearest donor
  colour ("Plug the donor too", "Plug the edge too"). With the edge plugged it needs no colour patch.
- **Jupiter Taser Club:** the clay was straightened ("Straighten Jupiter first"). The user chose a stretched grip for a
  round 0.75 m club ("Stretch grip 1.3x, 0.75 m"); the measured stretch that fills the hand is 1.42x, and the user
  approved that fit's preview ("Approve both fits"). The tip notch stays closed.
- **Rattan Stick:** a round 0.70 m stick at the grip depth, about 3.0 cm. The first in-game look was "a little too
  thick" with defects at one end ("3.0 cm", "Trim and repaint"). The tip end is cut past a stub and capped, and the
  broken wrap there is black all the way round. The colour model's grey patches on the hidden side are repainted wood
  ("Repaint them wood").

On this release record the user said "the sizes are fine": the four lengths in the table are the approved ones.
The fit records stay with the private itemkit runs.

Table changes are appearance-picker extensions only:

- F1 `MaxRange` 141 to 151
- F2 `MaxRange` 221 to 231

The release validation now counts 29 `srn_2da` resources, up from 22. The seven others are 2DA files other packs added
on main since wave 5; this wave changes only `baseitems.2da`.

No gameplay, price or item-property field changes. The comparison module gained a male/female reviewer pair for each
in the `sw1_` row (`sw10_`), but those pairs have not been run in its client.

## Firearm wave 1 (2026-11-17)

Five SR4 catalog firearms through the itemkit firearm route, published with `tools.itemkit.publish` from their firearm
packages (`--effects` for the firing-effect models). Every file but the shown model is the exact bytes of its reviewed
native HAK. The shown model ships as its firing-effect build: the package model plus the muzzle flash and casing
emitters and fire clips of `firearm-fx-pilot.md`, compiled by the game's own compiler; the record keeps the package
model's hash as `preEffectsSha256`.

| Item | Family | Blueprint | Appearance | Size |
|---|---|---|---|---|
| Fichetti Security 600 | F7 / row 61 | `sr186f9abc_6` | bottom `076`, others `016` (hidden), diffuse `sr186f9abc_076` | 0.22 m, 14,986 triangles |
| Yamaha Pulsar | F7 / row 61 | `sr4ec98e3a_7` | bottom `077`, others `017` (hidden), diffuse `sr4ec98e3a_077` | 0.23 m, 14,988 |
| HK MP-5 TX | F7 / row 61 | `srade01f23_8` | middle `038`, others `018` (hidden), diffuse `srade01f23_038` | 0.44 m, 24,988 |
| AK-97 | F8 / row 6 | `sr32dc7d7e_7` | top `017`, others `017` (hidden), diffuse `sr32dc7d7e_017` | 0.68 m, 37,488 |
| Defiance T-250 | F8 / row 6 | `sr65882fcd_8` | top `018`, others `018` (hidden), diffuse `sr65882fcd_018` (+ `.txi`) | 0.75 m, 29,988 |

- **Approval:** the user saw the first fits of all five in unattended client captures on both Human bodies ("Looks
  good, do effects"). The Fichetti, Pulsar, MP-5 TX and Defiance were then refitted square to their own middle plane
  (they leaned 2.9 to 6 degrees sideways in the hand), the effects were added, and Claude fired all five in the firing
  test module on the Human male. The user accepted them without a further in-game look ("accepted, finish everything
  up"). The Defiance's muzzle flash was not caught on a frame after its refit.
- **Sizes:** the pistols and the MP-5 TX are sized by grip thickness to the Colt firearm grip standard. The AK-97 and
  Defiance are two-handed on the Heavy Crossbow carrier; the Defiance is sized by length ("Full, 0.75 m") and its
  wrist departs from the standard thickness in the user's words.
- **Colour patches:** MP-5 TX 29 faces (27 approved by the user, "Approve patch (Recommended)"; 2 added on Claude's
  review), Fichetti 4, Pulsar 8, Defiance 2, all inside the reviewed scope.
- **Effects:** flash and casing on four guns. The Pulsar is a taser: an electric flash (nine blue-white sprites from
  stock `fxpa_elect`) and no casing. The Defiance's metal is darkened at bake and its texture carries a reflection
  mask, so it ships a TXI naming `chrome1`.
- **Budgets:** the firearm cap is 37,500 visible triangles (user, 2026-11-17: "raise the firearm cap to 37,500").

Table change: F7 `MaxRange` 65 to 77 (appearance picker only). Row 6 already reaches 100.

The same change set stands the published Ares Predator IV, Colt L36 (both finishes) and Ingram Smartgun X upright:
they leaned 3.8, 2.6 and 2.1 degrees. Each shipped shape is turned rigidly about the grip point by the effects build
(`STRAIGHTEN`), with the same size, proportions and texture (user: "Refit published"); their records carry
`sidewaysLeanStraightened`. Fired in game on the Human male from the ASCII build.

No gameplay, price or item-property field changes. The comparison module gained a male/female reviewer pair for each
(`sw11_`, holding bullets or bolts), but those pairs have not been run in its client. No production acceptance.

## Publishing a client-approved design

`tools/itemkit/publish.py` publishes designs the user has approved in the client. It replaces the ad-hoc scripts the
melee waves used. Run it through the item driver, which takes the runs and the NWN:EE install from the item workspace:

```powershell
python -m tools.itemkit.drive publish sr4-ceramic-knife-7f77d5dd6c:fit-v1 sr4-baseball-bat-202ef7e755:fit-v1 `
  --statement 'knife and bat look good' --statement 'Yes, publish them' --review 'Melee wave 2 reviewed in the client.' --dry-run
```

Use `python -m tools.itemkit.publish ITEM=RUN_DIR ... --nwn-root DIR` for run folders outside the workspace. Each
`--statement` is the user's approval in their own words. The command never records an approval it was not given, and
never grants production acceptance. `--dry-run` surveys and plans without writing anything.

For each item, the command:

1. **Surveys the package.** It takes the run's `native.json` and the HAK beside it, and checks the HAK's recorded hash.
   It reads the blueprint UTI from the run's fixture module, or from the latest refixture when there is no first
   fixture. It refuses the item if the UTI's base item or model parts disagree with the package.
2. **Refuses collisions.** Any file name already in `srn_weapon`, any name listed twice, and any item already in
   `approved-weapons-v1.json` stop the whole run before anything is written. With the NWN:EE install (always through
   the driver, and with `--nwn-root`), it also reads the install's KEY indexes (`data` and `lang/en/data`). A package
   file the base game holds is refused unless the package's contract recorded it as a stock replacement
   (`allocation.replacesStock`, from `drive contract --replace-stock`; see `item-generation-toolkit.md`). A recorded
   replacement is copied over the stock name like any other file, including its BioWare DDS icon twins (a package
   must carry every recorded name). The item's record gets `replacesStock` (the
   contract's list), its overriding resources get `"replacesStock": true`, and the policy text names them. The plan
   shows them per item and says whether the stock check ran (`stockCheck`); a direct `--dry-run` without
   `--nwn-root` skips it. Stock slots lie inside every carrier's `MinRange`..`MaxRange`, so they never change the
   table.
3. **Copies byte-exact.** Every HAK resource and the UTI go into `srn_weapon` unchanged. That includes the BioWare
   DDS twins newer packages carry beside each icon and diffuse TGA (NWN Crunch, `item-generation-toolkit.md`). A DDS
   without its TGA in the same package is refused. So is one whose header is not a three- or four-channel BioWare
   DDS, whose payload is not a whole mip chain, or whose size differs from its TGA (`tools/itemkit/dds.py`). Each is
   recorded in
   `approved-weapons-v1.json` with its source archive and hash. The item's family is taken from the grouping plan.
4. **Extends the table only when needed.** If an appearance number is above its row's `MaxRange`, only that token in
   `srn_2da/baseitems.2da` changes. A longer number takes the padding after it, and no other byte of the table moves.
5. **Adds reviewers.** It adds a male and a female reviewer per item to `test-modules/weapon-waves` in groups of five
   (`sw8_`, `sw9_`). Each group stands together, 3.5 m apart, after the last reviewer of the first row with room for
   all of it: the southern row (`sw3_` to `sw7_`, y 5/9, one more pair fits), then the `sw1_` row (y 15/19) and the
   `sw2_` row (y 27/31), with room for ten more pairs each after their five (user, 2026-11-13: "Fill sw1_/sw2_
   rows"). Reviewers are copied from the last group's first pair with only tag, name and position changed. The command
   also adds the equip lines to `sw2_enter.nss` and regenerates
   `sw_pairs.nss`, the pair table `c.nss` and `sw_review.nss` include. Then it recompiles the module scripts. Before
   anything is written (and in `--dry-run`, as `plannedReviewers` and `plannedReviewerPositions`) it refuses if no
   row has room for a group (a row past the area's edge, or with any other object within half a step of a spot, is
   skipped), or past group `sw99_`. The selector reads a group up to the tag's first underscore (it read only the
   first four characters, `sw1_` to `sw9_`, until wave 6 needed `sw10_`). A firearm package (`firearm-package-*`) is published with its carrier's ammunition for the reviewers and, with `--effects ITEM=DIR`, its firing-effect models; other ranged weapons are refused: a bow's equip lines are written by hand.
   So are items that are not three-part (b/m/t) models or cannot go in the right hand, such as shields.
6. **Rebuilds and verifies.** It rebuilds `srn_weapon`, `srn_2da` and the comparison module. It checks that each
   built archive holds exactly its source files and repeats the DDS twin check on every DDS in `srn_weapon`
   (`ddsTwinsChecked` in the release validation; `imagesChecked` still counts the TGAs). It refreshes the release
   validation, the module manifest and the module
   validation (a new `extension` entry, not run in the client), and regenerates the combat release manifest.

If any step fails, the command puts every tracked file it touched back as it was and removes the files it added, then
reports the error. Archives already built in `output/` may then be stale; rebuild them before using them.

A reproduction from the commit before melee waves 1 and 2 (`a07d2dc0`) gave `srn_weapon`, `srn_2da`, the module
reviewers, the GIT, the scripts and the item and resource records byte-identical to the hand-made publication. Only
the summary text, the statement list and the release validation's `additions` layout differ. Check new reviewers in
the client before calling an extension reviewed.

## Separate comparison module

`test-modules/weapon-waves` contains the review module and two fixture-only HAKs.
It depends on the normal weapon/table packs and existing shipped Human body packs.
It carries no duplicate released weapon blueprints. The reviewer selector in `c.nss` and `sw_review.nss` reads its
pair groups from the generated `sw_pairs.nss`; `test_combat_release_manifest.py` checks that table against the placed
reviewers. The original approval captures
are retained; grouping migration and test-hook changes have native/package
validation and are not presented as a new client acceptance. No deployment or
automatic game-client launch is performed by this PR.
