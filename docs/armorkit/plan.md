# Armorkit plan

Written 2026-11-09; every decision raised with the draft was settled by the user the same day. Nothing is built
yet. This records the user's decisions from the planning session, what was proven in the client, and the work
in order. Evidence for every "proven" statement is in
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
11. Male and female get their own torso cut at a minimum. Whether other slots also differ depends on the outfit.
12. Every new parts-table row carries `ACBONUS 0.00`.
13. Logo badges use a separate plain texture, an accepted exception to one tint texture per part.
14. The shared cleanmodels pin moves to 4.17.x once the Phase 0 close-up fit proof passes; `variants` then
    makes the race versions of new parts.
15. Part numbers follow the blocks tabled under [Part rules](#part-rules).
16. The triangle and texture budgets listed there are starting values, tuned in the pilot.
17. The pilot set is corporate security tiers 1–3.
18. New parts publish to a new pack, `srn_parts`. Splitting it per slot is revisited if its size calls for it.

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

**Numbering.** One number means one design in a slot, present on all 20 bodies. Where the male and female cuts
differ they share the number, so a recipe never names the wearer's gender. A set uses the same number in every
slot it covers; variations within a set take the next numbers. Stock rows (0–200) and stock model numbers (up to
255) are never reused; 256–299 stay empty as a buffer. Blocks, with the registry as the source of truth:

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
This is the accepted exception to "one PLT per part" (decision 13).

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
* The chest is always authored as a separate male and female cut. Each set's brief says which other slots also
  get their own female cut; the rest are one design fitted to both. Every separate cut is its own generated
  model with its own references and submission count.
* The other 18 bodies (Large Human and both builds of Dwarf, Elf, Orc, Troll) come from `cleanmodels variants`,
  learning its fit from our own `srn_body` and `srn_armor` haks.
* Hard-surface plates distort under strong non-uniform scaling (Dwarf, Troll). Heavy kits are deferred until a
  per-race plate fit is designed.
* Every number exists on all 20 bodies, so recipes never depend on the wearer. A cut designed for one gender
  only still needs a counterpart on the other under the same number.
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
| Compile, decompile, skin checks, race versions | cleanmodels 4.17.x (the shared pin moves from 4.0.0-rc17 once the Phase 0 fit proof passes; decision 14) |
| Hand authoring | NeverBlender 4.5.1 in Blender 5.2 |
| Client fixtures | A fixture builder grown from the spike scripts: isolated user directory, scripted actors and camera, log lines as evidence |
| Runs and receipts | [Shared tooling and workflow](../shared-tooling-and-workflow.md): pinned tools, declared inputs, immutable receipts |

New code lives in `tools/armorkit/`, documents in `docs/armorkit/`. New parts publish to the new pack
`srn_parts`, separate from the converted stock clothing in `srn_armor`.

## Pipeline for one set

1. **Brief.** Break the concept into slots, a tier for each joint, colour channels, badge positions and
   accessories. Name the slots that get a separate female cut (the chest always does). Allocate numbers in the
   registry.
2. **References.** Garment-only, headless, rest-stance Human male: clay for geometry, colour for appearance.
   The same pair on the Human female for each separate female cut. Review before generating.
3. **Generate** the source on the local engine, recorded in the ledger.
4. **Split** on the Human male body with planar joint cuts and the overlap ends for each tier.
5. **Fit** around the unchanged body: clearance, no body edits.
6. **Materials.** Label regions to channels, write the PLT and material file, mark skin regions, place badges.
7. **Skinned pieces** (hoods, bandoliers, skirts that need it): weights, then compile with cleanmodels.
8. **Offline gates** (below).
9. **Human male in the client:** standing, idle and motion. User review.
10. **Human female:** generate, split and fit the separate female cuts; fit the shared slots; review.
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

* `tools/armorkit` skeleton: registry, table generator, fixture builder, tests.
* Move the cleanmodels pin once the close-up fit proof below passes.
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
logo, and one skinned neck-slot respirator or balaclava. Human male, then female with its own torso cuts, then
race versions. User
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
* whether the male and female cuts differ;
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

None. The eight raised with the draft were settled on 2026-11-09 and are decisions 11–18 above.

## Not covered and risks

* Robes remain the expensive path; the one robe trial had large stretch in motion.
* Dwarf and female bodies were not individually checked in any proof so far.
* Race versions were only viewed at overview zoom, and only for third-party test parts.
* The local generator has not yet produced a garment; quality for clothing is unknown.
* Open headgear over many different heads will clip on some; the head envelope gate limits this but does not
  remove it.
* Part numbers and tables are global to a module. Any other provider of the same tables must be removed or
  merged.

## Revision 2026-11-10: wider number blocks

The user asked for wider part-number blocks, accessories most of all, because the item field holds numbers up
to 65535. This replaces the block table under [Part rules](#part-rules), which decision 15 refers to; the
rest of the plan stands. Nothing had been numbered under the old blocks.

| Block | Use |
|---|---|
| 300–2999 | Shared accessories (neck, belt, shoulder items not tied to a set) |
| 3000–3999 | Civilian |
| 4000–4999 | Workwear |
| 5000–5999 | Corporate / business |
| 6000–6999 | Security and law enforcement |
| 7000–7999 | Runner and role gear (decker, rigger, samurai, mage) |
| 8000–8999 | Gangs, syndicates, FRFZ |
| 9000+ | Heavy kits and overflow |

Stock rows 0–200, stock models to 255 and the 256–299 buffer are unchanged. A table is padded up to its highest
part number: about 9,000 rows for a table whose highest part is in a family block, and up to 65,536 rows
(about 1.8 MB) once a part in the open block from 9000 uses the top of the range. The exact widths were chosen while
carrying out Phase 0 and are open to the user's correction; the result of the client proof for numbers in these
ranges is in [spikes.md](spikes.md).

## Revision 2026-11-10: what Phase 0 changed

Phase 0 is carried out; results are in [spikes.md](spikes.md) (sections 10–17) and
[seam-contract.md](seam-contract.md). The plan text above stays as approved. These points now differ from it
and wait for the user to decide before Phase 1:

* **Decision 14 is not met.** The close-up fit proof did not pass: race versions leave a visible waist step on
  Large female bodies and do not fit headgear to Dwarf or Troll heads. The cleanmodels pin was not moved.
* **Race versions.** `cleanmodels variants` is usable for male bodies and Fit female bodies. Large female
  bodies and all headgear need another fit (per race from the head envelopes for headgear).
* **Logos (decisions 7 and 13).** A plain-texture badge inside a tinted part is overwritten by the tint
  texture of the part, and the runtime swap does not reach a badge textured through a material file. A logo
  approach has to be chosen (spikes.md, section 15).
* **Parts tables.** `parts_robe` has stock rows 0–38 and hide columns, not rows 0–200; the generator handles it.
* **Clearance gate.** A worn part replaces the body part in its slot, so the gate that matters is the join with
  neighbouring parts (the seam contract), not skin showing through the part.
* **Toolset.** It lists the new numbers by part number only, with no names, and lists only rows that have a
  model. The test part had no inventory icon and the item picture showed a gap; parts will probably need
  icons (not tested).
* **cleanmodels has no pin today.** The "4.0.0-rc17 shared pin" of decision 14 and the toolchain table is a
  folder in the shared tool root that no lock file names. Adopting cleanmodels 4.17.x adds a new shared-tool
  entry; the Phase 0 compiles and race versions used an unpinned download of 4.17.5.
* **Seam measurement.** The contract (now version 2, see [seam-contract.md](seam-contract.md)) covers under
  ends at every joint and over ends at five of them. A torso piece's neck hole, armholes and leg holes cannot
  be measured by the plane section used here and need a measure of their own before the seam gate can cover
  them.
* **Review fixes (same day).** A code review of this phase found that the first seam contract counted
  animation clips the bodies never play, that the head envelopes missed surface between vertices, and that
  the capture driver could file a picture under the wrong shot, which had spoiled the first helmet sheet.
  All three are corrected and re-measured or re-run; spikes.md section 14 and seam-contract.md say how.
* **Not checked in Phase 0** (each is listed with its proof in spikes.md):
  * tint-texture fallback from a female or Large model to another gender or build (the plan's Phase 0 list
    asks for it; only the race fallback was proven);
  * material files (normal maps) on a new part number;
  * part numbers above 1000 on slots other than chest and bicep, although every family block now starts at
    3000 on all slots;
  * a table of 65,536 rows on a multiplayer server;
  * helmet scales per race, and helmets on Large bodies;
  * motion for any test part: walking, running, combat, a scripted head turn or the automatic look-at;
  * the toolset beyond one Human male armor item, not saved or reopened;
  * SR_NWN branches other than `master`.

## Revision 2026-11-10: a logo picked by a shader value (proof)

The user asked for the untried third logo approach to be tested before choosing one. It passed
([spikes.md](spikes.md), section 18): all logos sit in one strip texture, the badge reads it through a material
file with a small custom vertex shader, and SR_NWN picks the cell per wearer with
`SetMaterialShaderUniformVec4`. The part keeps its tint texture and item colours, the value survives
re-equipping, and it works on rigid and skinned meshes.

The choice between this and one part number per logo is the user's and is not made here. If it is chosen:

* Decision 13 stands in substance (logos are plain, not tintable), but the badge names a material file and a
  shared strip, not a texture of its own.
* The handoff names the material and its parameter and lists each logo's cell. SR_NWN sets the value on the
  wearing creature, not on the item, and does not need to reapply it when the same item is equipped again.
  When it must be set again (login, area change, a player arriving later) is not yet checked.
* The kit ships one custom shader, which includes the stock `inc_standard` and so has to be rechecked on a new
  game build.
* Adding a logo replaces the strip; no part is copied.

## Revision 2026-11-10: logos use the shader value (user decision)

The user chose the shader approach of the revision above over one part number per logo. This replaces the
**Logos** paragraph under [Part rules](#part-rules) and the logo note under
[Handoff to SR_NWN](#handoff-to-sr_nwn). Decision 7 (logos only on shoulders and neck-slot lanyards) stands,
and decision 13 stands as reworded in the revision above.

* A part that shows a logo carries a badge mesh that names the shared logo material. The material reads one
  strip texture holding every logo, and a parameter picks the cell. Cell 0 is blank.
* SR_NWN sets the cell on the wearing creature, and no part is copied per logo. The value belongs to the
  creature, not the item: every logo part the creature wears shows the same logo, and equipping the same
  item again needs no call. SR_NWN sets the cell again whenever the logo to show changes, for example when
  an item with another logo is equipped or an item passes to another character. Two different logos on one
  character at once would need a second material and is not tried.
* Phase 1 builds what the proof only sketched: the shared material, shader and strip as kit resources, the
  strip layout and cell count, the handoff entry (material, parameter, each logo's cell), and a gate that a
  badge mesh names the material and reads the right way round on each side. That gate uses a logo that is
  not symmetric, because a mirrored test badge went unnoticed through two proofs.
* Still to check before logos are relied on: what other players see in multiplayer, including one who arrives
  after the call; whether the value lasts through a save, an area change or a login; the shader on other
  graphics cards and drivers; and the shader on each new game build. The multiplayer check needs a second
  client.

The other points of "what Phase 0 changed" still wait for the user: the fit for Large female bodies and
headgear, adopting cleanmodels, and the number-block widths.
