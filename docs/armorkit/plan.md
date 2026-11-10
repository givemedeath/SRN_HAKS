# Armorkit plan

Draft for approval, 2026-11-09. Nothing is built yet. This records the user's decisions from the planning
session, what was proven in the client, and the work in order. Evidence for every "proven" statement is in
[spikes.md](spikes.md). Revisions are appended as dated sections; this text stays as approved.

## Goal and scope

Armorkit makes modular clothing, armor, headgear and accessory **parts** for the 20 SRN bodies (Human, Dwarf,
Elf, Orc, Troll; male and female; Fit and Large) and organises them: part numbers, parts tables, textures and a
registry that describes each part.

In scope here: part creation, race versions, numbering, tables, textures, logos' carrier geometry, headgear,
the registry and the validation gates.

Out of scope here: outfit recipes, the wardrobe/configurator, NPC outfit generation, Shadowrun armor mechanics
and applying logos at runtime. Those live in SR_NWN and consume the registry ([handoff](#handoff-to-sr_nwn)).

Starting points: the Xenomech outfit kit (`xenomech-outfit-kit-2026-10-27.zip`, split/fit/audit tooling) and
the concept sheets in the SRN concept art folder (corporate security, battle armor, gangs, syndicates, magical
response, matrix/rigger, FRFZ catalog).

## Decisions (user, 2026-11-09)

1. Outfits are assembled from parts in the 19 armor slots. Families (corp security, workwear, gangs and so on)
   are tags for recipes, not a compatibility system.
2. Pieces that hang below the waist (hems, tabards, skirts, holsters) go on the **belt** slot. Robes are only
   for garments that truly need them.
3. Seams use deliberate overlap and clipping to stay cross-compatible, not exact ring matching.
4. Accessories may clip heavily in motion. They are judged standing and idle.
5. Full helmets use the helmet slot, which replaces the head. Open headgear goes on the neck slot.
6. Headgear avoids showing faces, keeps exposed skin generic, and is built to fit across heads.
7. Logos live only on shoulders/pauldrons and neck-slot lanyards. Headgear and logos are part of this kit.
8. A generic neck is fine; the neck slot is free for accessories.
9. Mechanical values in the parts tables are nulled out; SR mechanics live in SR_NWN.
10. Geometry is generated with the local Comfy install.

## What is proven

All on NWN:EE 89.8193.37-17 with isolated test modules; details and limits in [spikes.md](spikes.md).

| Fact | Status |
|---|---|
| Part numbers above 255 (tested 300 and 1000) render and persist; model names use the plain number | Proven, chest and belt |
| Items store such numbers in `xArmorPart_*` word fields; the old `ArmorPart_*` byte field loads as 0 | Proven |
| Parts tables must be padded positionally with no gaps | Proven |
| `ACBONUS 0.00` rows give item AC 0 | Proven |
| Belt part with knee-length panels works rigid and as danglymesh | Proven |
| Rigid geometry on a neck part follows head animations but not the automatic look-at | Proven |
| `HEAD_NAME = neck_g` in `appearance.2da` makes the look-at turn the neck, so rigid neck headgear follows | Proven on stock Human and SRN Human, Orc, Troll (male Fit) |
| Skinned meshes inside a neck part follow the head (bound to `head_g`) or torso with default tracking | Proven on SRN Human male with third-party parts |
| Skinned parts compile offline with cleanmodels and load correctly | Proven with recompiled third-party parts |
| `cleanmodels variants` (v4.17.5) makes Dwarf/Elf/Orc/Troll/Large versions against our haks | Proven at overview zoom for a hood and bandolier; close-up fit not reviewed |
| `ReplaceObjectTexture` on the wearer swaps a plain-texture badge per character | Proven on stock Human; lost on re-equip |
| Individual worn parts cannot be scaled by script (head, tail, wings, cloak and whole creature can) | Proven |
| Tintable part plus a material file with a normal map | Already how `srn_body` ships; not yet tried on a new part number |

## Slot rules

| Slot | Use | Mesh |
|---|---|---|
| Chest, pelvis, bicep, forearm, thigh, shin, foot, hand (L/R) | The garment itself | Rigid, cut on the joint planes |
| Belt | Utility belts, holsters, pouches, and everything that hangs: hems, tabards, skirts, coat tails | Rigid, danglymesh, or skinned |
| Shoulder (L/R) | Pauldrons, shoulder plates, **logo badges** | Rigid |
| Neck | The accessory slot: collars, lanyards (logo), scarves, bandoliers, chest rigs, backpacks, slung gear, and open headgear (hoods, masks, respirators, goggles, visors) | Rigid for back/torso gear; **skinned** for anything that must follow the head or wrap the torso |
| Helmet (separate item) | Full helmets that replace the head | Rigid model per helmet |
| Robe | Only closed long coats and full robes that must bend with the body | Skinned; deferred |

Neck-slot rules:

* Every neck part carries the generic neck mesh as well as the accessory, so the neck never disappears.
* Headgear that must follow the head is a skinned mesh bound to the head bone. This needs no table change and
  leaves torso-bound pieces (lanyards, bandoliers) where they belong.
* One neck part per character. Combinations people will want (for example respirator plus backpack) are built
  as combined parts, chosen from recipe demand rather than made exhaustively.
* The `HEAD_NAME = neck_g` change stays unused unless rigid headgear is needed; it turns everything on the neck
  part with the head, lanyards included.

## Part rules

**Numbering.** One number means one design in a slot on all 20 bodies. A set uses the same number in every slot
it covers; variations within a set take the next numbers. Stock rows (0–200) and stock model numbers (up to
255) are never reused; 256–299 stay empty as a buffer. Proposed blocks, with the registry as the source of
truth:

| Block | Use |
|---|---|
| 300–399 | Shared accessories (neck, belt, shoulder items not tied to a set) |
| 400–499 | Civilian |
| 500–599 | Workwear |
| 600–699 | Corporate / business |
| 700–799 | Security and law enforcement |
| 800–899 | Runner and role gear (decker, rigger, samurai, mage) |
| 900–999 | Gangs, syndicates, FRFZ |
| 1000+ | Heavy kits and overflow, after a proof above 1000 |

**Names.** `p<m|f><race><phenotype>_<slot><number>`, lowercase, at most 16 characters (the longest, such as
`pmh0_bicepl1000`, is 15).

**Tables.** `parts_belt`, `parts_bicep`, `parts_chest`, `parts_foot`, `parts_forearm`, `parts_hand`,
`parts_legs`, `parts_neck`, `parts_pelvis`, `parts_robe`, `parts_shin` and `parts_shoulder` are generated from
the registry into `srn_2da`: stock rows unchanged, padded with no gaps, live rows `COSTMODIFIER 0` and
`ACBONUS 0.00`, padding rows `****`. A test fails on a gap, a duplicate or a registry part without a row.

**Textures.**

* One tint texture (PLT) per part, named like the Human model of that gender, holding the whole part.
* A material file of the same name adds the normal map (and roughness where it helps), following
  [the body material process](../phenotype-body-material-process.md).
* Channels: cloth 1/2, leather 1/2 and metal 1/2 for the garment; the skin channel for exposed skin, which
  reuses the body's skin surface. Every channel may use the full shade range.
* Shape carries cut, construction, plates, pockets and silhouette. Colour carries fabric, finish and faction
  palette.

**Logos.** A part that shows a logo carries a small badge mesh with the shared blank texture `srn_logo_0`.
SR_NWN swaps it per wearer. Logo textures are plain (not tintable) and their names are at most 16 characters.
This is a deliberate exception to "one PLT per part" and needs the user's confirmation (open decision 2).

**Budgets (starting values, tuned in the pilot).** Chest up to 4,000 triangles, other body slots up to 1,500,
accessories up to 2,000, a whole worn outfit up to 20,000 (the robe trial's accepted runtime budget). Runtime
textures at most 1024 px.

## Seam rules

Parts are rigid and meet at eight joints: neck, shoulder, elbow, wrist, waist, hip, knee and ankle. Instead of
matching rings, each part end is built to overlap:

* Each joint has a fixed plane and a fixed layering order measured on the locked c7 Human bodies (for example
  the thigh tucks under the pelvis, the chest hangs over the pelvis).
* Each part end declares a **tier**: 0 skin-tight, 1 cloth, 2 padded or armored, 3 heavy.
* The "under" end continues past the joint plane by a minimum overlap and tapers; the "over" end is open and at
  least as wide as its tier's envelope.
* Two parts mix cleanly at a joint when the over part's tier is at least the under part's. Other pairs still
  assemble; the registry marks them so SR_NWN can avoid or allow them.
* Tapered ends follow the repository's no-shelves rule: one continuous slope, no ledge or rolled lip.
* Minimum overlaps and envelope radii per joint and tier are measured in Phase 0 and frozen as the seam
  contract.

## Bodies and race versions

* Author on Human male Fit first, then Human female Fit. The bodies are fixed; parts are fitted around them.
* The other 18 bodies (Large Human and both builds of Dwarf, Elf, Orc, Troll) come from `cleanmodels variants`,
  learning its fit from our own `srn_body` and `srn_armor` haks.
* Hard-surface plates distort under strong non-uniform scaling (Dwarf, Troll). Heavy kits are deferred until a
  per-race plate fit is designed.
* Every part exists on all 20 bodies, so recipes never depend on the wearer.
* Neck-slot headgear must clear the **head envelope** of each race: the outer bounds of that race's published
  heads, measured in Phase 0.

## Toolchain

| Need | Source |
|---|---|
| Generation | The guarded local Comfy engine already used by `tools/headkit` and `tools/itemkit` (shared submission ledger, one dispatch at a time). At most five geometry submissions per model. Smooth clay reference for geometry, detailed colour reference for appearance |
| Split into parts, fit around the fixed body, source and arm/foot shape checks, material labels, stage records | Ported from the Xenomech kit, with its tint-shader output replaced by PLT. Provenance recorded when code is brought in |
| Tint texture encoding | `tools/headkit` palette code |
| Joint and part measurement | `tools/phenomorpher` measurement and connector checks |
| Skin weights for skinned pieces | `tools/robes` weight transfer, in A/T pose |
| Compile, decompile, skin checks, race versions | cleanmodels 4.17.x (needs the shared pin moved from 4.0.0-rc17; open decision 3) |
| Hand authoring | NeverBlender 4.5.1 in Blender 5.2 |
| Client fixtures | A fixture builder grown from the spike scripts: isolated user directory, scripted actors and camera, log lines as evidence |
| Runs and receipts | [Shared tooling and workflow](../shared-tooling-and-workflow.md): pinned tools, declared inputs, immutable receipts |

New code lives in `tools/armorkit/`, documents in `docs/armorkit/`. New parts publish to a new pack (working
name `srn_parts`), separate from the converted stock clothing in `srn_armor`.

## Pipeline for one set

1. **Brief.** Break the concept into slots, a tier for each joint, colour channels, badge positions and
   accessories. Allocate numbers in the registry.
2. **References.** Garment-only, headless, rest-stance Human male: clay for geometry, colour for appearance.
   Review before generating.
3. **Generate** the source on the local engine, recorded in the ledger.
4. **Split** on the Human male body with planar joint cuts and the overlap ends for each tier.
5. **Fit** around the unchanged body: clearance, no body edits.
6. **Materials.** Label regions to channels, write the PLT and material file, mark skin regions, place badges.
7. **Skinned pieces** (hoods, bandoliers, skirts that need it): weights, then compile with cleanmodels.
8. **Offline gates** (below).
9. **Human male in the client:** standing, idle and motion. User review.
10. **Human female:** fit and review.
11. **Race versions** for the other 18 bodies, gates, then a sampled client review on the hardest bodies.
12. **Publish:** models and textures to the pack, table rows, registry entry, publication validation and a pack
    build.

## Gates

Automatic, per part:

* Names, 16-character limit, no clash with `srn_body` or `srn_armor`.
* Triangle and texture budgets.
* Texture closure: the PLT and material file exist and every referenced map resolves.
* Seam contract: each end meets its tier's overlap and envelope against the body joint.
* Clearance: no body surface showing through at rest; no holes or detached pieces.
* Skin checks from cleanmodels: no unbound vertices, at most four influences, every bone in the skeleton.
* All 20 body versions exist, and their table rows exist.
* Headgear clears its race's head envelope.

In the client:

* Human male prototype first; nothing else is built for a set until the user has seen it.
* Fitted parts: standing, idle, walk, run, combat and casting.
* Accessories: standing and idle for appearance; in motion only that they stay attached.
* Mixing: each new part end is checked against one reference part of each tier at that joint, not against every
  other part.
* A numerical pass never approves appearance. A fault found after the gates passed becomes a new gate.

## Phases

**Phase 0: foundation.** No new art.

* Settle the open decisions below.
* Move the cleanmodels pin, if approved.
* `tools/armorkit` skeleton: registry, table generator, fixture builder, tests.
* Measure and freeze the seam contract and the per-race head envelopes.
* Remaining proofs:
  * a part number above 1000, and how the toolset shows new numbers;
  * tint-texture fallback across gender, build and race for a new number, plus per-part colours;
  * race versions of one of our own parts, reviewed close up on all 20 bodies, female included;
  * a skinned part authored here, compiled offline;
  * the helmet slot with our heads and race scales;
  * the logo swap on SRN bodies;
  * whether SR_NWN ships competing parts tables or reads armor AC.

**Phase 1: pilot set.** Corporate security tiers 1–3 from the first concept sheet, because it is rigid-friendly
and needs no robe. It includes a utility belt, a shoulder badge shown as five corporations through palette and
logo, and one skinned neck-slot respirator or balaclava. Human male, then female, then race versions. User
review at references, at the Human male client view and at the all-body sample.

**Phase 2: second family.** Civilian clothing, to prove mixing across families by tier, with a mixing fixture.

**Phase 3: accessories and headgear library.** Backpacks, bandoliers, chest rigs, hoods, masks, goggles,
lanyards, and full helmets.

**Phase 4: remaining families in waves.**

**Deferred:** robe-slot garments (after the all-race robe refit), heavy battle armor (per-race plate fit), a
second accessory slot through head-aligned effects, custom colour palettes, and scalable tail or wing
attachments.

## Handoff to SR_NWN

The kit publishes a registry file with the packs. Per part it gives:

* slot, number, set and family tags;
* tier at each joint;
* coverage (which skin is exposed; whether it is headgear);
* neck-part category (headgear, back, neckwear, torso) so recipes do not double-book the slot;
* colour channels used;
* badge presence and position, for logos;
* the bodies it exists on.

Notes SR_NWN needs:

* Item blueprints must write `xArmorPart_*` fields for numbers above 255.
* A logo swap is applied to the wearing creature and reapplied whenever the item is equipped.
* New chest rows carry no armor value.

## Open decisions

1. **`ACBONUS 0.00` on every new row.** Proposed; confirm.
2. **Logo badges as a separate plain texture,** an exception to one PLT per part. Proposed; confirm.
3. **Move the shared cleanmodels pin to 4.17.x** and use `variants` for race versions of new parts. Proposed
   after the close-up fit proof in Phase 0.
4. **Number blocks** as tabled above. Proposed; confirm or adjust.
5. **Starting budgets** as listed. Proposed; tuned in the pilot.
6. **Pilot set:** corporate security tiers 1–3. Proposed; confirm.
7. **Pack name** for new parts (`srn_parts`), and whether to split it per slot later.
8. **Gendered designs:** default is one design fitted to both genders. Confirm, or name the sets that differ.

## Not covered and risks

* Robes remain the expensive path; the one robe trial had large stretch in motion.
* Dwarf and female bodies were not individually checked in any proof so far.
* Race versions were only viewed at overview zoom, and only for third-party test parts.
* The local generator has not yet produced a garment; quality for clothing is unknown.
* Open headgear over many different heads will clip on some; the head envelope gate limits this but does not
  remove it.
* Part numbers and tables are global to a module. Any other provider of the same tables must be removed or
  merged.
