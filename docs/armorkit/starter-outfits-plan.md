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
base and one accent. Bags, headphones and chains are not drawn. Each arm is still drawn with a plain glove at
its end, which the bake cuts off: the fit finds the wrist by the palm beyond it (step A, done).

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

2026-11-24, step A done. `brief.BARE` takes `hand`. Nothing else in the kit needed changing: the bake already
makes no part for a slot left to the body, cuts what the outfit has there off on the joint's plane, and closes
and domes the forearm's end at the wrist with no part under it (`bake.hidden`, tested with `left={'handl'}`).
What the kit cannot do is fit an arm that ends at a hem or a cuff with nothing beyond it
(`repose.outfit_joints` refuses it), so a bare-handed outfit's image keeps a plain glove on each arm as the
fit's landmark. Tested on the kit's test tubes only; a real sleeve closed round the body's hand is first seen
in step B6. Next: step B1, the Street Casual brief.

2026-11-24, any slot may be bare (user: "make this compatible with any part being bare"). `brief.BARE` now
holds every slot an outfit fills: chest, pelvis, upper arm, forearm, hand, thigh, shin, foot. Checked on a real
outfit without a new generation: Facility Security's male generation was split again with each slot, and
several together, left to the body beside its own bare forearm, and gated against the body's skin.

| Left bare (beside the forearm) | New gate failures |
|---|---|
| hand; upper arm; upper arm and hand; foot; shin; shin and foot; thigh; thigh, shin and foot | none |
| chest, upper arm and hand; pelvis and thigh; pelvis, thigh, shin and foot | none |
| chest alone, the sleeves kept | both upper arms' ends stand 2.2 and 2.3 cm out of the body |
| pelvis alone, the thighs kept | both thighs' ends stand 2.3 and 2.8 cm out of the body |

So a brief that leaves the chest bare must leave the upper arms too, and the pelvis the thighs
(`brief.WITH`); a slot cannot be both bare and shared with the body's skin. That split, from the 17,000-face
export, has one failure before any slot is left (the left upper arm's end 1.1 cm out of the chest with the arm
turned back), which is the outfit's own and not counted above.

Not checked: the rest of a bake (layout, tint, the written models) with a part missing other than the
forearm; `refit`, `bodies` and `publish` for an outfit with no chest or no pelvis, whose inventory icons are
drawn from those two; any of it in the client. The image is still drawn as a whole figure, with a plain piece
where a slot is left.

2026-11-24, steps B1 and B2 done. Brief `tools/armorkit/briefs/street-casual-male.json`: a zipped bomber
jacket (cloth 1), cargo trousers (cloth 2), a belt (leather 1) and high-top sneakers (leather 2), bare hands,
wear 0.5. The jacket is drawn closed, with no shirt under it and no hood: two cloth channels hold the jacket
and the trousers, and the T-shirt is its own variant, 3011. Sealed in the work folder as
`street-casual-male/reference-v1`; one Qwen image, `run-1/image-0.png`, seed 20261124, on the shared ComfyUI
(user: post it now). Next: stop 1, the user's review of that image.

2026-11-24, stop 1: the user asked for a redraw with more street character, and said that the leather and
metal channels a part has no use for may be used, so that the reference image's colours say what is coloured
on which channel and parts can be coordinated where needed. Two additions to a brief's material, both in
`brief.py`:

* `"tint": "metal"` tints a material on another kind's channels. Its `kind` stays what it is: how it is cut,
  what counts as a plate, how it wears.
* `"channel": 1` or `2` on an outfit's material names its channel, wherever it is worn. Until now only an
  accessory's could; an outfit's channels were told by which material covers more, and a single material of a
  kind was split between torso and legs, which differs from outfit to outfit.

**Colour convention for the starter sets** (proposed here, not yet confirmed by the user). A reference image
uses these colours for these channels, so that parts of different sets worn together are coloured alike:

| Channel | Drawn in | Holds | Facility Security 6020 |
|---|---|---|---|
| cloth 1 | sky blue | the outer garment on the torso and arms | shirt |
| cloth 2 | grey | the garment on the legs | trousers |
| leather 1 | tan | belt, straps, gear | vest and pouches |
| leather 2 | green | footwear | boots and gloves |
| metal 1 | pink | the inner layer: a shirt under a jacket | — |
| metal 2 | yellow | accent panels and trim | plates |

The Street Casual brief was rewritten to it: a thick jacket worn open over a T-shirt, baggy cargo trousers
gathered into heavy boots, a band of the accent round each upper sleeve and a patch over each knee. Sealed as
`street-casual-male/reference-v2`; one Qwen image, `run-1/image-0.png`, seed 20261125. `reference-v1` keeps
the first design's image. Not run: a bake with a tinted or named channel (`bake.tints` reads them through
`brief.channels`; the brief's side is tested). Next: the user's review of the redraw.

## Revision 2026-11-24: jackets are separate, fully skinned robe-slot parts (user decision)

The user decided that jackets are made as their own parts on the robe slot, and, offered sleeves on the rigid
arm slots or one skinned mesh with its sleeves, chose the fully skinned jacket. This replaces the Street Casual
of decision 3 and the model table above where they differ, and supersedes plan.md's deferral of robe-slot
garments for jackets.

What it changes:

* **Street Casual 3010 is the outfit without a jacket:** T-shirt, cargo trousers, belt and boots, bare forearms
  and hands, the upper arms sharing the body's skin. The T-shirt variant 3011 is dropped: 3010 is it. The
  street vendor 4020 and the office 5010 are likewise drawn without a jacket.
* **A jacket is one skinned model with its sleeves, on the robe slot,** worn over whatever fills the fitted
  slots. It bends at the shoulders and elbows. Its row in `parts_robe` hides the upper-arm and forearm parts
  under its sleeves; the chest stays, since an open jacket shows the shirt.
* **One robe to a character.** A jacket and a long coat are not worn together.
* **Numbers.** A set's jacket takes the set's number on the robe slot (robe 3010), a jacket of no set a
  standalone number. Proposed, not confirmed.
* **Channels.** The jacket is tinted by the item's six colours like every part, so the convention holds: the
  jacket on cloth 1, the shirt under it on metal 1.

The citizen's recipe: chest, upper arms, pelvis, legs and feet 3010; forearms and hands the body's (part 1);
robe 3010 for a citizen in a jacket, none without.

Step B for the base outfit is as before. The jacket is a track of its own, **step J**, started once the base
outfit has been seen on the Human male in the client:

1. **Brief and reference for a piece worn on the robe slot.** `brief.ACCESSORIES` takes belt, shoulder and
   neck; a robe piece is added. Drawn alone, in an A-pose, front view.
2. **Fit and weights.** `tools/robes` has the pieces from the Meshy workwear trial (fit to the body, weight
   transfer, an A-pose rest skeleton, a deformation review over the stock clips, a skinned ASCII model).
   Weights are transferred in the A-pose, never the arms-down bind pose. Which of it Armorkit calls and which
   it rebuilds is decided when the step starts.
3. **Gates before the client:** no unbound vertices, at most four influences, every bone in the skeleton
   (cleanmodels); the deformation review's stretch and penetration over the clips the bodies play, with limits
   set from this jacket's first build and the user's client review.
4. **Human male in the client** over 3010: standing, idle, walk, run, combat, the arms raised and forward.
   **A stop for the user.**
5. Then the female, the other 18 bodies (`cleanmodels variants` makes robe versions; unproven here), the
   `parts_robe` rows with their hide columns, publication with approval.

The risk is stated plainly: the one robe built here, the trial's workwear, measured a worst stretch of 26.4
times and 16.7 cm of penetration walking when its review was rerun on fixed code (docs/robes/results.md), and
was approved in the client all the same. A jacket is shorter than that outfit and has no legs, which is the
easier case, but nothing about it is proven until step J4.

State: brief rewritten without the jacket and sealed as `street-casual-male/reference-v3`; one Qwen image,
`run-1/image-0.png`, seed 20261126. `reference-v2` keeps the image with the jacket, `reference-v1` the first
design. Next: the user's review of the `reference-v3` image.
