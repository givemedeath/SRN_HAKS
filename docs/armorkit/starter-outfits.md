# Starter-area outfits: roles, recipes and part requirements

Written 2026-11-24. This reconciles the prioritised concept-sheet looks with the roles the three starter areas
need, and says which Armorkit parts each role's outfit takes. It is a proposal: nothing here is generated,
numbered in the registry or published, and every number, set name and roster row below waits for the user.

The concept sheets guide the look; they are not a build list (user, 2026-11-15). The recipes themselves and the
wardrobe live in SR_NWN ([plan.md](plan.md), Goal and scope). What this document gives SR_NWN is the slot-by-slot
content of each recipe, so that the parts can be made to fit it.

## What exists today

* Published parts: Facility Security 6020 on seven slots, its duty belt 6020 and the logo brassard, shoulder
  1000, on all 20 bodies ([parts-registry.json](parts-registry.json)). It is a guard's outfit at tier 2, not a
  civilian baseline.
* No civilian, workwear or corporate part exists. No recipe exists.
* The starter areas are the three exterior pilots of SRN_SPRAWLER (`docs/PILOT-SELECTION.md`, frozen as
  `checkpoints/pilot-v1`): **Hub** (Council Hall / Café Giovanni, downtown Denver), **Middle** (the Happenstance
  working neighbourhood, South Denver) and **Barrens** (Sable / Alameda mixed-use streets, Aurora). Its ledger is
  three exteriors and no interiors; interior planning is on hold until the new tileset is ready.

## Finding: there is no first-slice NPC roster

The gate asks for the concepts to be reconciled with the first-slice NPC/role roster. No such roster is written
down in any of the repositories looked at:

* SRN_SPRAWLER names the three areas and their anchors and defers NPCs to its Stage 4. The `npc` flags in its
  project file mark routes an NPC may take, not who the NPCs are.
* SR_NWN names roles only for its Phase 3B1 run loop (`design/runs/RUN-LOOP-SPEC.md`, section 2.1): a fixer, a
  street doc, an equipment merchant and two to four perimeter sentries, in a hub safehouse and a run site that
  are not these three areas. It has no mention of Happenstance or Café Giovanni.
* SRN_HAKS has the Happenstance prop set (bar and club furniture) and the civic administration prop kit for the
  Council Hall, which say what the places are, not who stands in them.

The roster below is therefore derived from the area anchors and those documents. Each row says where it comes
from. It is the thing to confirm or correct first; the recipes follow from it.

## Provisional roster

| # | Area | Role | Where it comes from | Needs an interior? |
|---|---|---|---|---|
| R1 | Hub, Middle, Barrens | Citizen on the street | Every exterior needs passers-by; FRFZ catalog "Citizenry (Everyday)" | No |
| R2 | Barrens | Barrens resident | The area's 65% decay setting; streetwear look 06 | No |
| R3 | Barrens | Street vendor | Mixed-use retail streets; informal commerce in the request | No |
| R4 | Middle | Bartender, Happenstance | The bar is the Middle's anchor | Yes |
| R5 | Hub | Café Giovanni staff | The café is one of the Hub's two anchors | Yes |
| R6 | Hub | Office worker | Downtown, commercial sizing; Council Hall staff off the desk | No |
| R7 | Hub | Front desk, Council Hall | The civic administration prop kit has reception desks | Yes |
| R8 | Hub | Guard | Council Hall and corporate doors | No |
| R9 | Middle | Convenience clerk | Only if a retail counter is placed; none is named | Yes |
| R10 | (SR_NWN hub) | Fixer, street doc, equipment merchant | SR_NWN run loop; not placed in these areas | Yes |

R4, R5, R7 and R9 stand indoors, and the areas have no interiors yet. For the exteriors alone the roster is
R1, R2, R3, R6 and R8.

## The concepts against the roster

| Priority | Concept | Role | Verdict |
|---|---|---|---|
| P0 | Streetwear sheet, look 01 "Street Casual" | R1, and R2 by colour | Build first. The one outfit all three areas use |
| P0 | Service sheet, look 02 "Bartender / Dive Bar" | R4, and R5 by colour | Build second. Needed only once an interior exists |
| P0 | Service sheet, look 01 "Convenience Clerk" | R9 | Not built: no retail counter is in the roster |
| P1 | Workwear sheet, look 05 "Street Vendor" | R3 | Build as a torso and a belt piece over shared legs |
| P1 | Workwear sheet, look 10 "Urban Casual" | R1 | Not built: it is Street Casual again with another print |
| P1 | Streetwear sheet, look 06 "Barrens Fashion" | R2 | Deferred. First slice: Street Casual in the Barrens colours |
| P1 | Corporate sheet, look 01 "Wage Slave" | R6, and R7 for now | Build. The Hub's office outfit |
| P1 | Corporate sheet, look 05 "Front Desk" | R7 | Deferred: its belt-slot skirt is not in the first slice (below) |
| — | Facility Security 6020 (published) | R8 | Use as it is, with belt 6020 and shoulder 1000 |
| — | Fixer sheet; service sheet look 06 "Street Doc" | R10 | Outside the request's priorities; needed if R10 is in the slice |

Nightlife, gang, runner, mage and combat looks stay deferred: no roster row asks for them.

What each look loses or changes to fit the kit's rules:

* **Carried gear comes off the outfit.** Cross-body bags, satchels, headphones, wallet chains and tool rolls
  are accessories (neck or belt slot), made apart and added by a recipe. None is in the first slice.
* **Aprons and anything else that hangs below the waist are belt-slot pieces** (decision 2). A bib above the
  waist is part of the chest.
* **Chest prints.** Street Casual, Urban Casual and the Street Vendor wear a printed T-shirt. A chest print
  exists only on T-shirts and its mechanism is not designed (plan revision 2026-11-15). The first-slice shirts
  are built plain, with the chest front kept smooth so that a print can be added later.
* **Lanyards.** The Wage Slave's badge lanyard is a neck-slot logo piece, the first of the neckwear numbers.
* **No shoulder pads, straps on the middle of a limb only, torso garments clear of the sleeves** (construction
  rules, version 3). None of the four looks needs an exception.
* **Wear.** Baked into the tint texture per outfit, so a recipe cannot make the same parts more worn. The
  Barrens resident in the first slice differs by colour only; a heavier-worn variant is a second bake.

## Proposed sets and numbers

Numbers follow the digit scheme (family, group, set, variant). All are proposals; 6020's number and names were
the user's to approve, and so are these.

| Set | Number | Family | Slots | Tier | Channels (suggested: dark base, one accent) |
|---|---|---|---|---|---|
| `street-casual` | 3010 | Civilian | chest, bicep, forearm, pelvis, thigh, shin, foot | 1 | cloth1 jacket, cloth2 shirt and trousers, leather1 belt, leather2 shoes |
| `street-casual` T-shirt | 3011 | Civilian | chest, bicep (skin shows); forearm bare (part 0) | 1 | cloth2 shirt, skin |
| `bar-service` | 4010 | Workwear | chest, bicep, pelvis, thigh, shin, foot; forearm bare (part 0) | 1 | cloth1 shirt, cloth2 trousers, leather1 bib and straps, leather2 boots |
| `bar-service` apron | 4010 | Workwear | belt | — | leather1 apron, cloth1 towel, metal2 buckles |
| `street-vendor` | 4020 | Workwear | chest, bicep; forearm bare (part 0) | 1 | cloth1 jacket, cloth2 shirt |
| `street-vendor` apron and waist pack | 4020 | Workwear | belt | — | cloth1 apron, leather1 pack, metal2 buckles |
| `office` | 5010 | Corporate | chest, bicep, pelvis, thigh, shin, foot; forearm bare (part 0) | 1 | cloth1 shirt, cloth2 trousers and tie, leather1 belt, leather2 shoes |
| Badge lanyard | neck 2000 | Standalone | neck (logo badge) | — | cloth1 strap; logo cell set by SR_NWN |

Service and retail have no family block of their own. They are placed under workwear (4000s) here, as the
FRFZ catalog's "Workers/Industrial" and "Service/Retail" buckets sit side by side.

Every body-slot end is tier 1 (cloth), so the four sets mix with each other at every joint. Against 6020's
tier-2 ends a civilian over part is the lower tier; the registry marks such pairs and no recipe below uses one.

## Recipes

Slot by slot, for SR_NWN. A slot the outfit leaves bare has no Armorkit model: the recipe names part 0 there
and the wearer shows the body's own part (user, 2026-11-24).

| Role | Chest | Bicep | Forearm | Hand | Pelvis, thigh, shin | Foot | Belt | Neck | Shoulder |
|---|---|---|---|---|---|---|---|---|---|
| R1 Citizen | 3010 | 3010 | 3010 | 0 | 3010 | 3010 | — | — | — |
| R1 Citizen, warm day | 3011 | 3011 | 0 | 0 | 3010 | 3010 | — | — | — |
| R2 Barrens resident | 3010 or 3011 | same | same | 0 | 3010 or 4010 | 4010 | — | — | — |
| R3 Street vendor | 4020 | 4020 | 0 | 0 | 3010 | 4010 | 4020 | — | — |
| R4 Bartender | 4010 | 4010 | 0 | 0 | 4010 | 4010 | 4010 | — | — |
| R5 Café staff | 4010 | 4010 | 0 | 0 | 5010 | 5010 | 4010 | — | — |
| R6 Office worker | 5010 | 5010 | 0 | 0 | 5010 | 5010 | — | 2000 | — |
| R7 Front desk (first slice) | 5010 | 5010 | 0 | 0 | 5010 | 5010 | — | 2000 | — |
| R8 Guard | 6020 | 6020 | 0 | 6020 | 6020 | 6020 | 6020 | — | 1000 |

Colours tell roles apart where the parts are shared: R2 in faded earth colours against R1's dark base and one
accent; R5 in a light shirt and dark apron against R4's black shirt and brown leather; R7 tidier and darker
than R6. Each bake records suggested colours for SR_NWN to start from.

## What has to be made

Thirteen generated models, each with its own brief, references and at most five geometry submissions:

| Model | Kept from it |
|---|---|
| Street Casual, male | all seven slots |
| Street Casual, female | chest (and arms if her own sleeves come out whole) |
| Street Casual T-shirt, male and female | chest, bicep |
| Bar service, male | all six slots |
| Bar service, female | chest |
| Bar apron | belt |
| Street vendor, male and female | chest, bicep |
| Vendor apron and pack | belt |
| Office, male | all six slots |
| Office, female | chest |
| Badge lanyard | neck |

That is five male outfit models, five female cuts and three accessories; the T-shirt and the vendor torso are generated as whole outfits and only their upper slots are kept (`combine`). Each is then
carried to the other 18 bodies (`bodies`), gated and published.

Kit work the recipes depend on, none of it built:

1. **Bare hands in the brief.** A bare slot needs no model, only part 0 in the recipe. The brief's `bare` list
   takes only `forearm` today (`brief.BARE`), so it has to take `hand` as well, for the bake to make no hand
   part and to finish the wrist against the body's hand. Three of the four looks have bare hands; Facility
   Security always had gloves.
2. **A long sleeve ending at the wrist with no glove.** Street Casual's jacket sleeve meets the body's own hand;
   the forearm's wrist end has only been built against a glove, so it is checked in the client first.
3. **A neck-slot piece that is not headgear.** The lanyard is torso-bound and carries the logo badge. The
   brassard proved the badge on the shoulder; the neck slot has had only the respirator, which is on hold.
4. **Pack size.** One full outfit on 20 bodies is about 423 MB in the hak. The three full sets beside
   6020 come to about 1.7 GB, and the two torso-only sets and the accessories take it to about the 2 GB limit
   of a hak (an estimate from 6020's size, not measured). `srn_parts` has to be split before the last of them
   is published; plan revision 2026-11-15 expected the split before about ten outfits.
5. **Later, not first slice:** a T-shirt chest print; a skirt over bare legs (Front Desk): the legs are part 0 and need no
   model, but `bare` has to take `thigh` and `shin` and the skirt is a belt-slot piece; a heavier-worn Barrens variant.

## Order and the representative outfit

1. Confirm or correct the roster and the numbers above.
2. Street Casual 3010 on the Human male is the representative outfit: it is P0, it is on every exterior, and it
   brings the two kit changes most recipes need (bare hands, a sleeve ending at the wrist). Brief, reference
   review, generation, bake, client pose sheet, user review.
3. Its female cut, then the 18 other bodies, then publication.
4. Office 5010 and the lanyard, for the Hub's exterior.
5. Street vendor 4020, for the Barrens' exterior.
6. Bar service 4010, when an interior exists to put it in.

## Acceptance, as asked

| Condition | State |
|---|---|
| Concepts reconciled with the first-slice roster | Done against a provisional roster; no roster existed. Waits for the user's confirmation |
| Recipes and part requirements written for each required role | Done here, as proposals |
| A representative outfit validated in the client | Not done. No civilian part exists; step 2 above |

Evidence: the concept sheets are in `SRN_Concept_Art/Metahumans/Clothing` (`10_outfits_streetwear_01.png`,
`10_outfits_service_01.png`, `10_outfits_workwear_01.png`, `10_outfits_corporate_01.png`,
`FRFZ Faction Outfit Catalog.png`), outside this repository. The published parts are in
[parts-registry.json](parts-registry.json) and [parts-handoff.json](parts-handoff.json).
