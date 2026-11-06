# Approved weapon release packs

Build the normal release through the existing pack builder:

```powershell
./tools/Build-Haks.ps1 -Pack @('srn_weapon','srn_2da') -SkipTlk
```

`srn_weapon` contains the approved models, runtime diffuse maps, inventory icons
and eighteen builder blueprints for sixteen weapon designs. `srn_2da` supplies
the native carrier table. No custom TLK is required. The inventory and resource
hashes are in `approved-weapons-v1.json`; the generated combat release manifest
describes the complete resource closure.

| Family | BaseItem / ItemClass | Released designs |
|---|---|---|
| F1 | 22 / WSwDg | Cougar Fineblade Knife; Cougar Fineblade Longblade |
| F2 | 1 / WSwLs | Cougar Fineblade Longsword; Stun Baton; Vibro Blades — Sword |
| F4 | 13 / WSwGs | Katana |
| F5 | 50 / WDbQs | Staff |
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
addresses are selectable (later 121 for the Vibro sword, see below). All other
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

## Separate comparison module

`test-modules/weapon-waves` contains the review module and two fixture-only HAKs.
It depends on the normal weapon/table packs and existing shipped Human body packs.
It carries no duplicate released weapon blueprints. The original approval captures
are retained; grouping migration and test-hook changes have native/package
validation and are not presented as a new client acceptance. No deployment or
automatic game-client launch is performed by this PR.
