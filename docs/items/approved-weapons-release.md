# Approved weapon release packs

Build the normal release through the existing pack builder:

```powershell
./tools/Build-Haks.ps1 -Pack @('srn_weapon','srn_2da') -SkipTlk
```

`srn_weapon` contains the approved models, runtime diffuse maps, inventory icons
and twenty-seven builder blueprints for twenty-five weapon designs. `srn_2da` supplies
the native carrier table. No custom TLK is required. The inventory and resource
hashes are in `approved-weapons-v1.json`; the generated combat release manifest
describes the complete resource closure.

| Family | BaseItem / ItemClass | Released designs |
|---|---|---|
| F1 | 22 / WSwDg | Cougar Fineblade Knife; Cougar Fineblade Longblade; Survival Knife; Ceramic Knife |
| F2 | 1 / WSwLs | Cougar Fineblade Longsword; Stun Baton; Vibro Blades — Sword; Sword; Club; Extendable Baton; Tomahawk |
| F4 | 13 / WSwGs | Katana; Claymore; Baseball Bat |
| F5 | 50 / WDbQs | Staff; Stun Staff |
| F6 | 111 / WWhip | Whip |
| F7 | 61 / WBwSl | Colt L36 (both finishes); Ingram Smartgun X; Ares Predator IV |
| F8 | 6 / WBwXh | AK-98 and its separate launcher entry; Heavy Crossbow |
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

The user's in-game checks did not cover every case. There was no close view of the Claymore hand fit and no two-hand
grip or attack frame. The Club's female hand fit and the Knife's male close view and attack frame were not seen either.
None of these was requested as a change. All four appearance numbers already fall inside their rows' `MaxRange`, so wave
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

## Separate comparison module

`test-modules/weapon-waves` contains the review module and two fixture-only HAKs.
It depends on the normal weapon/table packs and existing shipped Human body packs.
It carries no duplicate released weapon blueprints. The original approval captures
are retained; grouping migration and test-hook changes have native/package
validation and are not presented as a new client acceptance. No deployment or
automatic game-client launch is performed by this PR.
