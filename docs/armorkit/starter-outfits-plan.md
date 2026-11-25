# Starter-area outfits: plan

Written 2026-11-24, from [starter-outfits.md](starter-outfits.md) and the user's answers of the same day. It
is the work in order for the first civilian Armorkit outfits. [plan.md](plan.md) stays the kit's plan; this is
its Phase 2 made concrete for the three starter areas. Revisions are appended as dated sections.

## Decisions (user, 2026-11-24)

1. **A bare slot has no Armorkit model.** A recipe names the body's own part there, which is **part 1**
   (`pmh0_forel001`, `pmh0_handl001`). The user first said part 0; the check below found no part 0 model, and
   the user chose part 1.
2. **First-slice roster: street roles only.** Citizen, Barrens resident, street vendor, office worker, guard.
   Venue staff (bartender, café staff, front desk), the run-loop roles (fixer, street doc, merchant) and the
   convenience clerk are out of this plan.
3. **Numbers accepted:** Street Casual 3010 with its T-shirt variant 3011, street vendor 4020, office 5010,
   badge lanyard neck 2000. Service and retail sit under workwear (4000s). Bar service 4010 keeps its number
   for later.
4. **First stop:** Street Casual on the Human male, seen in the client. Nothing else is built for a set until
   the user has seen its male.
5. **Reference images** are one light-toned local Qwen image per model (`armorkit image`), as Facility
   Security's were.
6. **T-shirt chest prints are designed in this plan,** before the T-shirt is published.
7. **In the first slice as well:** the T-shirt variant 3011 and the badge lanyard.

## What was checked before writing this

| Claim | How it was checked | Result |
|---|---|---|
| The body's bare part is number 1, not 0 | `srn_body` holds `pmh0_<slot>001` models only; `client_fixture.NAKED` dresses a naked actor in part 1 | Part 1. Decision 1 |
| The numbers fit the registry's rules | `registry.validate` on the published registry plus 3010, 3011 (chest, bicep), 4020 (chest, belt), 5010 | Accepted. A variant may exist in only some slots |
| A brief can leave the hands bare | `brief.validate` with `"bare": ["forearm", "hand"]` | **Refused.** `brief.BARE` holds `forearm` only: step A1 |
| Parts of several bakes can be kept as one outfit | `bake.combine` | Yes, when every source was baked for the same `bare` and `skin` slots |
| A belt piece is fitted per body over a worn outfit | `accessory fit` (belt 6020, all 20 bodies) | Yes |
| A torso-bound neck piece can be fitted | `accessory.py`, `headgear` | **No.** Only head-bound neck pieces are fitted: step D2 |
| A logo badge works inside a tinted part | The published brassard, shoulder 1000 | Yes, through the shared material and a shader value |
| The generation work folder and attempt ledger | `.tools/armorkit/corpsec-pilot/trial-ledger.json` in the primary checkout | Present; cap of five per model |
| Pack size | `srn_parts/` is 164 MB on disk for 6020; plan.md gives about 423 MB in the hak | The 2 GB estimate is arithmetic from that, not measured: step F |

Not checked: a long sleeve's wrist end against the body's hand in the client; how a generated open jacket
over a shirt splits; whether one creature can carry two shader values on two materials at once (the print
beside the shoulder logo).

## First-slice recipes

For SR_NWN. A 1 is the body's own part.

| Role | Chest | Bicep | Forearm | Hand | Pelvis, thigh, shin | Foot | Belt | Neck | Shoulder |
|---|---|---|---|---|---|---|---|---|---|
| Citizen | 3010 | 3010 | 3010 | 1 | 3010 | 3010 | — | — | — |
| Citizen, T-shirt | 3011 | 3011 | 1 | 1 | 3010 | 3010 | — | — | — |
| Barrens resident | 3010 or 3011 | same | same | 1 | 3010 | 3010 | — | — | — |
| Street vendor | 4020 | 4020 | 1 | 1 | 3010 | 3010 | 4020 | — | — |
| Office worker | 5010 | 5010 | 1 | 1 | 5010 | 5010 | — | 2000 | — |
| Guard | 6020 | 6020 | 1 | 6020 | 6020 | 6020 | 6020 | — | 1000 |

Roles that share parts are told apart by colour. Every new end is tier 1.

## Models to generate

Ten, each with its own brief, sealed reference folder and at most five geometry submissions, counted in the
shared ledger.

| Model | Kept from it | Left bare |
|---|---|---|
| `street-casual-male` | chest, bicep, forearm, pelvis, thigh, shin, foot | hand |
| `street-casual-female` | chest | hand |
| `street-tee-male`, `street-tee-female` | chest, bicep (skin shows) | forearm, hand |
| `office-male` | chest, bicep, pelvis, thigh, shin, foot | forearm, hand |
| `office-female` | chest | forearm, hand |
| `vendor-male`, `vendor-female` | chest, bicep | forearm, hand |
| `vendor-apron` | belt | — |
| `badge-lanyard` | neck | — |

Every brief has `wear` (0.5 for street and vendor clothes, 0.3 for the office) and suggested colours, a dark
base and one accent. Bags, headphones, chains and gloves are not drawn.

## The work in order

### A. Kit readiness (no art)

1. `brief.BARE` takes `hand`; the bake makes no hand part for it and finishes the forearm's wrist end, or the
   bare forearm, against the body's hand. Tests beside the change; focused Armorkit tests, and
   `tools/test_impact.py --write-catalog` if a test's imports change.
2. No helper under `tools/` changes between a generation request and its collection.

### B. Street Casual 3010, Human male

1. Brief, then `brief --seal`. Construction version 3.
2. Reference image with `armorkit image`. Ask which ComfyUI to use first; one job at a time, and not while a
   client check runs.
3. **Stop 1: the user reviews the reference image.**
4. Geometry, export at about 17,000 faces, appearance.
5. Bake under a test number (300–999), every gate.
6. Client pose sheet on the Human male, six channels in six contrasting colours, a handful of usable views.
   Check for a running client first.
7. **Stop 2: the user reviews the outfit in the client.** This is the representative outfit of the request's
   acceptance.

### C. Street Casual to publication

1. Female chest from her own generation; the male's other parts carried to her (`refit`, `combine`). Done by
   the stop rule of plan.md: every gate passes and the six-pose sheet shows no holes, no skin where cloth
   belongs, nothing see-through.
2. The other 18 bodies (`bodies`), gated; a client look at the hardest (`wear`).
3. **Stop 3: the user approves publication** (number, names, provenance text).
4. `publish` at 3010: models, tables, icons, registry, handoff, `PROVENANCE.md`, pack build,
   `tools/Test-Repository.ps1`.

### D. T-shirt 3011 with its print, and the lanyard

1. **Print proof, before any T-shirt art.** A second strip and material beside the logo's, with its own shader
   value, so that a print has no tie to the shoulder or lanyard logo (user, 2026-11-15). A flat badge mesh on
   the chest front of a test part. In the client: the part keeps its tint, the print and a shoulder logo show
   different cells on one wearer, and the print reads the right way round. The result goes into
   [spikes.md](spikes.md).
2. **Stop 4: the user decides on the mechanism and on the first prints' art.**
3. `street-tee-male` and `-female`: briefs, references (stop for review), generation, bake, chest and bicep
   kept, the print's badge placed, client check, 18 bodies, publication with approval.
4. `badge-lanyard`, neck 2000: an accessory brief for the neck slot; a new fit for a piece that lies on the
   chest and round the neck over what is worn, carrying the body's neck and a badge that names the logo
   material. Seen over 3010 and 5010; standing and idle only.

### E. Office 5010 and street vendor 4020

Each as B and C: male first, a stop at the reference image and at the male client view, then the female
chest, the 18 bodies and publication with approval. The vendor keeps only chest and bicep; its apron and waist
pack are one belt piece (`accessory prepare`, `accessory fit`), drawn in three-quarter view.

### F. Pack and handoff

1. Measure the built `srn_parts` hak after each publication. Split it into several haks before it passes
   1.5 GB.
2. [sr-nwn-instructions.md](sr-nwn-instructions.md) gains the recipes above, the part 1 rule and the print's
   value. SR_NWN must list any new hak.

## Validation

Chosen from the changed files, as AGENTS.md asks: focused Armorkit tests for a kit change, the full helper
suite when a shared helper changes, a pack validation and rebuild of `srn_parts` and `srn_2da` at each
publication. Client checks use Human bodies first, with the frame rate capped, keyholing off and the fog clip
at 9999.

## What needs the user each time

A reference image before generation; a male outfit in the client before anything else of its set; a
publication; a push or pull request; a sixth geometry submission for any model.

## Not in this plan

Bar service 4010 and its apron, the front desk's skirt, the convenience clerk, the fixer and street doc looks,
a heavier-worn Barrens variant, carried gear (bags, headphones), prints on anything but T-shirts.

## State

2026-11-24: plan written and committed on `claude/armorkit-starter-outfits-849d10`. Nothing is generated.
Next: step A1.
