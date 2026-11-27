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

Roles that share parts are told apart by colour. Every new end is tier 1, but Street Casual's hips, knees
and ankles, which are tier 3 (State, 2026-11-25: its trousers and boots are 3 to 8 cm bulkier than tier 1).

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

**Colour convention for the starter sets** (proposed here; its two metal rows were replaced on 2026-11-25, see
the end of this log: the metal channels hold only metal and what is shiny). A reference image
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

* **Client views of `male-16`** (27 in realistic colours, 13 in the six contrasting ones; the screen grab
  failed part way through both runs). User, 2026-11-25: "pelvis/thigh cuts/joins need improvement pretty bad.
  same with shin/foot. The belt also seems large and tilted", then: the hip cut "should be along brief lines",
  with no crotch on the thigh and the back sloped as the front; "the feet are still looking very rough"; "if
  the footwear rides high into the shin, then the shin should carry that part, cut where it fits the rig".
* **What was wrong, and what the kit does now** (`tools/armorkit`, tests in `test_joins.py`):
  * *Tier.* The outfit's sections stand 3 to 8 cm outside tier 1 at the hips, knees and ankles (hip 17.6 cm
    against 9.6 to 11.0; tier 3 is 13.4 to 14.8), so each under end was drawn in by centimetres and the part
    over it stood out as a hem. A bake takes a tier per joint (`--tier-at JOINT=TIER`, `seams.at`). Street
    Casual is cut at tier 3 with its shoulders and waist at tier 1: at tier 3 the sleeve ends stood 1.7 cm
    outside the chest in a swing, and the waistband was widened so the belt fitted 15% larger. Its registry
    entry has to carry those tiers; what it mixes with at the hips, knees and ankles is tier 3 or heavier.
  * *Hips.* The thigh was cut on the body's own pelvis line, level, 7 to 8 cm below the hip plane. It is now
    cut like briefs (`split.briefs`): 1 cm below the plane at the outside of the hip, down to 1 cm below the
    outfit's own crotch between the legs (9 cm here; the old line left a strip of crotch on each thigh),
    alike before and behind. Outfits baked before this have the level line and would need baking again to
    share parts at the hips with one that has the new.
  * *Ankles.* The ankle plane tilts forward through a heavy boot's toe box. The top of the toe box went to
    the shin, whose closing ran out over the toes as a brim; `split.footed` gives what lies before the shaft
    to the foot. The boot's shaft above the plane stays the shin's. And the end-shaping step read the foot's
    ring from the toe box and drew the toe caps in by 10 cm, a wedge of sawteeth: an under end's ring is now
    read no farther out than what the part is open on (`ends.opening`), in the seam gate too.
  * *Belt.* Levelled by its strap, the innermost surface in each direction, not by all its surface
    (`accessory.level`): the buckle and pouches had tipped it.
* **Bake `male-22`** (tier 3, shoulders and waist 1): **all gates pass**. Belt `belt-10` fitted over it at the
  earlier size (scale 0.585), gates pass.
* **Bake speed** (user: yes to all three). Parts are reduced, laid out and tinted in four processes
  (`--workers`), each part's reduction, maps and texture are kept in a cache (`--cache`, here
  `.tools/armorkit/bake-cache` in the shared tool root) and a bake can go on from a capture without reading
  the mesh (`--resume`, same tiers only). Street Casual from its mesh: 1196 s before, 855 s with an empty
  cache, 530 s with only the waist's tier changed; from the capture with nothing changed, 179 s and the same
  models byte for byte.

* **Second round in the client (`male-22`), user, 2026-11-25:** "The feet still have major issues", the skin
  in the biceps "should probably be at least a little more centered", the belt "still looks a little tilted
  backwards" and "is still too large", and "there is pants painting on the bottom of the shirt". What changed:
  * *Ankles as drawn* (`bake --as-drawn ankle`). Any tier's envelope moved the boots' rims by 9 cm and more at
    the plane (a collar round the ankle). The two ends are cut on the rig's plane and left as drawn; the seam
    gate reads nothing there. The registry gives those joints tier 3 with no mark of their own: an odd seam where
    a 3010 shin or thigh is worn with another set's tier 3 part is acceptable (user, 2026-11-27). The foot's cap starts 25% inside its
    rim (`ANKLE_TUCK`).
  * *Brief.* Trim is worn on the pelvis and thighs only (its red had been read on the boots' shafts, whose
    brown is the colour the trim shows in the reference), trousers on the pelvis, thighs and shins only (the
    dark underside of the shirt's hem, 370 cm² of the chest, had been drawn as trousers).
  * *Sleeves* (`repose.centred`). Each sleeve is set round its arm, by all of its offset from the hem up to
    40% of the way from the shoulder and by less nearer the shoulder: it had stood 2.5 cm off the arm's line at
    the hem and 5 to 7 cm higher up.
  * *Belt.* Stood by the way its strap's inner faces look (it had still leaned back 9 degrees), its middle the
    middle of its band, and put round the trousers alone (`WORN_UNDER` without the chest). Fitted with
    `--drop 0`, on the waistband: 3 cm lower the trousers widen over the hip pockets and the strap stood 3.3 cm
    farther out a side. The shirt's hem hangs over the top of the band.
* **Bake `male-25`** (from the mesh, 565 s): all gates pass. Belt `belt-12-drop-0.0` over it, gates pass. Seen
  in the client in realistic colours (`male-25b-poses-real`, 48 shots) and, with the earlier belt, in the six
  contrasting ones (`male-25-poses`). Not yet judged by the user.
* **Open, asked of the user:** to keep a few centimetres of the outfit's own surface past each tube joint on the
  under part and fit that hidden leftover to the envelope, in place of the grown dome and the reshaped rims
  (the user's suggestion, 2026-11-25).

* **Leftover ends (`male-26`), 2026-11-25:** the user's suggestion, "cut a little more than needed and use the
  leftover to shape the joint overlap", with "make sure the leftover part gets capped and rounded after any
  shaping so there are no potential holes visible". At a joint cut as drawn the under part's end is now the
  over part's own surface past the plane, up to 3 cm of it, drawn in under the over part, held inside it through
  the joint's bend and then rounded in to a pole (`split.kept_end`, kind `KEPT`, drawn as the outfit is there).
  Street Casual is baked with `--as-drawn ankle --as-drawn knee`; all gates pass, and the client shows clean
  knees and ankles standing, sitting and crouching, in contrasting and realistic colours
  (`output/armorkit/street-casual/review/male-26-joints.jpg`). Ends are also thinned before the surface that
  shows when a part is over its budget: the foot's own surface went from 2,390 to 4,688 triangles, the upper
  arm's from 1,174 to 2,848. Still open: a thin line of another colour across the instep where the foot meets
  the shin; the boots' gloss; elbow and wrist not tried (short sleeves, bare hands here); older outfits not rebaked.

* **Third round (`male-27`, `belt-13`), user, 2026-11-25:** "belt still seems too large", "some mesh issues with
  the crotch area", and the instep line and boot gloss to fix. The belt's strap is now fitted to the waistband
  alone and what hangs from it swings out over the thighs (scale 0.589 to 0.497); a pelvis cut on a brief line
  repeats no strip between the legs (it hung as two flaps); a shin's closing is drawn as the boot it ends in;
  leather keeps 30% of its drawn highlights. Seen in the client: belt, crotch and instep fixed
  (`output/armorkit/street-casual/review/male-27.jpg`). The boots are still glossy: a material file's roughness
  constant 1 and specularity 0.01 changed nothing in the client, and dulled highlights little. A test with a
  roughness map on one boot and a flat normal map on the other (`male-27-rough`) is prepared but not seen: the
  client's screen could not be grabbed twice ("screen grab failed").

* **Boot gloss found (`male-28`, `belt-14`), 2026-11-25:** the game draws a tinted part by its roughness map and
  ignores the material file's roughness number. Of two boots in one client run, the one given a map of
  roughness 1 came out matte and the one with a flat normal map stayed wet. Every part's one roughness (0.8) is
  now written as a small map (`texture.write_relief`); in the client the boots are leather and the trousers
  calmer (`output/armorkit/street-casual/review/male-28.jpg`, realistic colours). Outfits baked before this
  have the number alone and are glossier than meant until rebaked; accessories written through the same
  function get the map on their next fit.

* **Belt at its drawn size (`belt-16`), user, 2026-11-25:** "the belt pouches were not scaled down with the rest",
  then "accessories are allowed to clip a little, and a lot during movement". What hangs below a belt's strap
  keeps its drawn shape and is pushed out only where it would stand more than 2 cm inside the trousers
  (`accessory.HANGS_IN`, my number for "a little"); the strap sits clear on the waistband. 48 cm wide, from 55.
* **Reference colours by type and accent, a trial (`street-casual-typed`), user, 2026-11-25:** "colored by
  material type or accent type instead of by part type", with shirt and trousers still in two colours "for use
  in splitting (not for plt color channel assignment)", and, since parts can be coloured one by one in game, a
  table of channels per slot to follow if the accents come through. Brief `tools/armorkit/briefs/street-casual-typed.json`
  (`"typed": true`, materials may share a channel; `"small": true` on an accent). Found so far: a colour that
  only tiny things wear (violet for buckles and eyelets) made the image model draw large things in it, twice;
  without the floating gloves it drew arms; laces and boot straps came through as their own colour and are 1%
  of the texels, under the 3% a material had to be; the pocket flaps were not found, the boots' dark soles
  taking their place, so materials are to be found from the brief's colours and not from the peaks alone.
  Reference `reference-v3`, geometry attempt 1 of 5, solid export `export-4` (fill 20). Not yet baked whole,
  not compared, per-slot table not built.

2026-11-25, every joint's under end is the leftover of the cut (user: "get fully switched over to the new joint
mechanism before we proceed further. Only revert if we can't get same or better quality"). Until now only the
joints a bake named `--as-drawn` (Street Casual's knees and ankles) had it; the waist was capped from its rim and
the hips and shoulders had seat ends. Now `bake.LEFTOVER` is `split.LEFT_JOINTS`, all eight, whatever is
`--as-drawn`: that flag still says only that a joint is cut to no envelope.

* **Waist (and neck):** a flat cut like a knee's; the end is held inside the chest leaned forward, back and to
  either side by 15 and 30 degrees (`split.leaned`, `LEFT_LEANS`), and runs the contract's whole depth.
* **Hips and shoulders:** the cut is the seat line or the armhole, not the plane. The end starts on that line
  (`split.opening_rim`), follows the pelvis or the chest from there to the plane, has its last kept ring on the
  plane inside the contract's ring, and domes from there to the pole at the contract's depth. It is held inside
  the over part swung as a seat end was; an upper arm's inside the chest with its closings.
* The parts are made the over one first, and an end follows its over part as shaped to the contract.
* What went wrong on the way, each seen as a gate failure on the trial outfit and fixed: the pole clamped to the
  rim's nearest point (knees' rule) left the ends 1 to 5 cm deep where 8 to 14 are asked; following the pelvis
  on past the plane put a thigh's end 4.1 cm out of it swung forward; with no ring on the plane the contract's
  `bent` measure had nothing to measure on one side and too little on the other.
* **Result on the typed trial** (`typed-5`, belt `belt-18`): all gates pass, ten models compiled. In the client,
  set beside the captures before the switch (`typed-3`) pose by pose, nothing is worse and nothing is visibly
  better at the distances the pose shots are taken from (`review/all-joints-before-after.jpg`). The contrast
  run lost shots 41 to 47 to a stalled grab; the realistic run has all 48. No close shot yet looks into an
  armpit with the arm raised or under a thigh swung forward: those are the refinement pass's first views.
* Also today: a wall across a limb (the hem wall of a solid export) is no cover over the body's skin beside it
  (`measure.round_limb`). The trial's looser sleeves were refused at "would move 3.2 cm" for it.
* The typed brief works in the client: pocket flaps on cloth 2, laces and straps on leather 2, shirt and
  trousers on cloth 1 by the brief's word.

2026-11-25, the typed trial supersedes the first Street Casual (user: "this one supersedes male-28"). Street
Casual 3010 on the Human male is now the model `street-casual-typed` (brief `street-casual-typed.json`, bake
`typed-5`, belt `belt-18`), and the female, the 18 bodies and publication go on from it. `male-28` and its brief
`street-casual-male.json` stay as they are, as the record of the first generation; nothing further is baked from
them. Seen close in the client before the hold: the shoulders, level with the old ends in all six poses
(`review/sh-cmp-a.jpg`). Not seen: the hips close (`poses --preset hips`, new), and contrast shots 41 to 47.
The user put client boots and Toolset use on hold the same day, until further notice. Its shirt and trousers share
cloth 1 by the brief, and that stands: the game colours each part on its own, so a player colours the chest and
upper arms apart from the thighs and shins with no change to the channels (user, 2026-11-25). No per-slot channel
table is needed for it. Only the pelvis holds both, the shirt's hem and the trousers' top, on the one channel.

2026-11-25, Human female begun (step C1), and stopped at her chest.

* Brief `street-casual-typed-female.json` (model `street-casual-typed-female`): the typed brief with the T-shirt
  cut over a full bust, as Facility Security's female brief words it. Sealed in the work folder
  (`street-casual-typed-female/reference-v1`). **No image and no generation yet:** the image request was refused
  because the shared ComfyUI differs from its approved snapshot (one saved workflow added,
  `user\default\workflowsudio_minimax_music_3.json`), and the user then halted all ComfyUI use. Nothing
  was submitted; no geometry attempt is used.
* The male's other nine parts are carried to her (`female-1-refit`, from `typed-5-kept`): pelvis, both upper
  arms, thighs, shins and feet, each sleeve held over her arm with nothing left short. Not baked or gated on her
  yet: that waits for her chest (`refit --seat-in`, `combine`).
* Found on the way, open: carried together with the male's chest, an upper arm is refused ("would move 5.2 cm").
  It is the same with the parts from before the joint switch (5.8 cm), so the switch is not its cause. Carried
  with a chest, the arm's end is drawn in under it (`bent_under`); the body's skin beside the sleeve is then
  kept from the shoulder down (from 2.6 cm before the plane, where alone it begins 15.7 cm along the arm), and
  her arm stands 5 cm out of the end near the shoulder, where the chest covers it anyway. To look at when her
  own chest exists and the arms are seated in it.

### 2026-11-26: Street Casual on the Human female passes every gate

The ComfyUI and client holds are lifted (user, 2026-11-26). Her chest was generated (one geometry attempt of
five, `street-casual-typed-female`), baked on her (`female-own-1`), the male's other nine parts carried to her
and seated in it (`female-3-refit`), the two combined (`female-3-kept`) and baked as one (`female-3`): **all
gates pass**, ten parts compiled. Not yet seen in the client; her belt is not fitted yet.

Causes found and fixed on the way (each with a test), rather than limits lifted:

* **A refit shaped every end at tier 2**, whatever the bake's. Street Casual is cut at tier 3 with shoulders
  and waist at 1, so her pelvis stood 1.2 cm outside the waist envelope all round, both sleeves 0.9 cm at the
  shoulder, and a shin 0.7 cm outside the thigh. The tier a bake cuts at is now listed with its kept parts
  (`baked.json`), a refit reads it and says it on, `combine` refuses folders cut at different tiers, and
  `bake --kept` refuses to gate parts at another tier than theirs. `refit --tier`/`--tier-at` say it for
  folders kept before (typed-5-kept).
* **Gauntlets beside a short sleeve** read as an arm ending 28 cm short ("needs a glove"): the hand pieces of a
  drawn figure standing apart from the sleeve are now told apart (`repose.outfit_joints`).
* **A sleeve refused to move 3.8 cm over the skin**: three causes. The funnel inside a sleeve's mouth and a
  steep rolled hem counted as cloth over the arm (`measure.round_limb`: `END_DOWN` 0.5, `END_ON` 0.7, signed);
  and skin under the chest at the armpit was kept as shown (`bodyskin.shown`: a top piece made only of faces
  the split added joins the next, and a sleeve piece hides what lies above it across neighbouring sectors).
  This also cleared the refusal carried open above (5.2 cm with the male's chest).
* A refused push now says where it is (cm out, cm along the bone, whose face) and `ARMORKIT_DUMP=<folder>`
  saves the part for a look.

### 2026-11-26 (later): her boots, bust and collar after the first client look

User, on the first client shots of `female-3`: the breasts are too large, the feet are wrong, and the female
necks look long. State now: `female-6` (the male's whole outfit carried to her, `female-6-refit`) passes every
gate with belt `belt-f4`; client shots in `female-6-poses` (contrasting) and `female-6-poses-realistic`.
Her own generated chest (`female-own-1`) is set aside, its one geometry attempt used.

* **Feet.** A foot was scaled along the body foot's own axes, which run heel-top to toe 20 degrees off the
  ground: the boot came out sheared, its toe a wedge, 4.2 cm off the ground. A foot is now carried in the
  ground's frame, its sole on the ground (`refit.grounded`). The outfit is cut as drawn at ankle and knee, and
  the refit shaped and stretched those ends all the same: the drawn joints are now listed with the kept parts
  like the tier, no end there is shaped or deepened, and the end is seated in the part over it.
* **Bust.** The female brief asked for a full bust and the generated shirt stood 6 to 10 cm off her. The
  male's shirt carried to her keeps its standoff over her own shape. The female brief's wording is to be
  changed before any further generation from it.
* **Collar.** Heights above the neck joint followed the curve through neck, shoulders and waist, which rises
  0.16 at her neck: a 4.3 cm collar came to 0.7 cm. Above the neck they are now carried as they are
  (`refit.risen`): 3.5 cm.
* **Open: her shoulders read square.** Her shoulder joints lie 4 cm under her neck's plane, the male's 12 cm,
  so the shirt's yoke is carried a third as tall and 0.69 as wide and its slope flattens.
* **Open, the user's call: her neck.** 11.1 cm between neck and head joints against his 7.7 cm, 7.9 cm wide
  against 12.7. It is the locked c7 body; changing it is a new lock and a republished body pack.

### 2026-11-26 (evening): both Human versions rebaked with the current process and reviewed shot by shot

User: carry the male's shirt (not her own generated one), round her shoulders, slim the belly, then rebake both
with the latest process, review carefully and fix what is found in a reusable way. Done in the carry
(`refit`) and the bake, each with a test; the female is the male's ten parts carried to her, nothing generated.

Carry (`refit`), all bodies:

* **Yoke.** Above the shoulder line a vertex stands as high over the other body's shoulders, read from above
  (`shoulders`), as it stood over the source's, where both face up (`YOKE_STEEP`). By the joints alone her
  yoke came a third as tall and 0.69 as wide, flat and square as a shelf.
* **Collar.** From the shoulder line up the scales across come to the neck's own (`collar`): her neck is 0.80
  as deep as his, her chest 0.54 on the shoulder line, and the collar cut 1.3 cm into her neck, its rim in saw
  teeth. Heights above the neck plane are carried as they are after 5 mm (`COLLAR_EASE`).
* **Belly.** On a body narrower at a height than the source, the standoff is scaled with the rest: the shirt's
  7.5 cm of blousing stood whole round a waist 0.69 as wide. On a wider body it is still carried whole. This
  bends "the pouches keep their depth" (user, 2026-11-14) on narrower bodies only; the user was told.
* **Limbs.** A part between two joints is as wide at each joint as the other body is there (`limbed`), so two
  parts meet at a joint by one scale. By their means a thigh came 0.85 as wide and a shin 0.73 at a knee that
  is 0.77: a second hem round the knee.

Bake, every outfit:

* **Collar.** `bake.collared`, run on the parts as they are written (a carried chest meets its own body's
  neck), takes every face of the chest that enters the body's neck anywhere (read at 3 mm points, not by
  corners or middles), every face over the neck's plane within 1 cm of the neck (`COLLAR_HUG`), and the teeth
  that leaves on the rim; the rim runs down to one vertex inside the neck. Male 186 faces, female 175; the
  chest stays under 16,000 triangles (`bake.json` records `collar`). Before it the neck stood through the
  collar's folds and the lid, and the front of the collar rose 2.5 cm up the neck within 7 mm of it: in the
  client, flat shards before the neck with a notched edge (user: cut back to the ribbing).

Final folders under `output/armorkit/street-casual/`: male `typed-10` (kept `typed-10-kept`, belt `belt-23`,
with belt `typed-10-belt`), female `female-14` (carried `female-14-refit`, belt `belt-f12`, with belt
`female-14-belt`); every gate passes on both. Views `-shoulders` and `-realistic` of these (the realistic
female set has 46 of its 48 shots); the full `-poses` and `-hips` sets are of `typed-8` and `female-12`,
whose parts differ from these at the collar only. `typed-7` and `female-11` are over the triangle budget;
`typed-8`/`female-12` and `typed-9`/`female-13` are earlier collar forms.

Review (client, contrasting and realistic colours, body, shoulders and hips presets; 144 shots a body):
no holes, no skin where cloth belongs, nothing see-through on either body. Left as they are:

* In sit and crouch the ends inside the knees and the seat show as smooth rounded patches, alike on both
  bodies, far less in realistic colours.
* The generated shirt's collar has a notch at centre back, 1 mm tall there; his hair hides it, hers does not.
* On the male, close up from the front, a band of level cloth 2 to 4 cm wide still lies between the
  ribbing and the neck: the top of the generated collar's roll, standing more than 1 cm off the neck. The
  neck now meets it on one clean line. Cutting it as well was tried at 2, 3 and 4 cm, all of it or its level
  faces only, closed by the fan or by a skirt dropping each rim vertex to the neck's axis: the shirt is a
  solid, and with its top taken the undersides of the folds show; 3 cm leaves a notch at the back, and on the
  female, whose yoke rides high beside the neck, every form cut into the ridges. Left at 1 cm, and the band
  left as it is (user, 2026-11-26).
* The belt's buckle and a pouch clip the shirt hem and thigh in the sit (accessories may clip in motion).

### 2026-11-26 (night): belt pouches keep the shape they were drawn in

User: "i don't like that the pouch is getting deformed on the belt. Again accessories (belt and neck slots
should allow clipping, especially in motion)." The fit (`accessory.wrap`) moved each direction round the body
as its own column, pushed what hangs below the strap out level by level, and made a hoop whose band is drawn
thin taller and deeper but no longer round; on the Human female (hoop 0.36, made 1.38 taller) the pouches came
out flared and sheared.

* **Rigid pouches.** What hangs below the strap (`accessory.hanging`: below the strap's own height measured
  down from the hoop's top in each direction, a strap sags at the front; pieces of 50 vertices or more,
  vertices at one place joined across texture seams) is put back as drawn, at one scale every way (the hoop's
  times how much taller its band was made, so a pouch is the same size on both bodies), turned and moved with
  the strap vertices it hangs from. The strap is fitted as before.
* **Lean, not bend.** A pouch that would sink more than `HANGS_IN` (2 cm) into the trousers at rest is
  turned whole about where it hangs, its foot out, 2 degrees at a time, 40 at most (`accessory.tilted`):
  male 18 and 12 degrees, female 34 and 28. In sit and crouch the pouches sink into the thighs, as allowed.
* Belts `belt-25` (male) and `belt-f14` (female) pass every gate; client views `pouch-m-realistic`,
  `pouch-m-hips2`, `pouch-f-realistic`, `pouch-f-hips` (outfits `pouch-m-belt`, `pouch-f-belt`: typed-10 and
  female-14 with these belts). The first male hips run lost a shot to a stalled client and was taken again.

### 2026-11-26 (late): accessories clip by design; the pouch lean is gone

User: "Again, clipping is fine for belt and neck slot accessories and is expected. Fixe it and make sure that
is remembered." The lean above (and the 2 cm `HANGS_IN` allowance it served) was a clearance push by another
name. Superseding it:

* What hangs from a belt is placed rigidly as drawn (one scale, turned and moved with the strap it hangs from)
  and nothing else: no lean, no level-by-level swing, no allowance. `accessory.tilted`, `_sunk`, `HANGS_IN` and
  the swing in `accessory.wrap` are removed. Only the strap is fitted on the waistband, as before.
* `accessory.gates` still measures how deep what hangs stands inside the outfit (`inside.hanging`) but no
  longer fails on it; the strap's own `INSIDE` gate stays. Tests: a pouch over a thigh comes out where it
  would without the thigh, and a box 5 cm into a thigh below the strap passes the gates while the same box at
  strap height fails.
* Neck slot: `headgear` fits a piece to the head envelope it is worn on and gates only against that; it has
  no outfit clearance push or clip gate, so nothing changed there.
* Rule recorded in `plan.md` decision 4.
* Belts `belt-26` (male) and `belt-f15` (female) pass every gate, pouches 4.4 and 6.8 cm into the trousers at
  rest. Outfits `clip-m-belt`, `clip-f-belt` (typed-10, female-14 with these belts); client views
  `clip-m-realistic`, `clip-m-hips2`, `clip-f-realistic`, `clip-f-hips` (the first male hips run lost 18 of
  24 shots to a stalled client).

### 2026-11-26 (late): the other 18 bodies

User: "Start the bodies now." `bodies` from `typed-10-kept` (male) and `female-14-refit` (`--female-from`;
the female has no chest of her own), `--only` the 18 race bodies, three at a time, each about 6 minutes.

* `bake --kept` with no tier now takes the tier and as-drawn joints its kept folder lists (`cut_at`): `bodies`
  passes none, and at the default tier 2 every body of an outfit cut at tier 3, shoulders and waist at 1,
  ankles and knees as drawn, would have been refused.
* First run (`bodies-1`): 12 of 18. Fixed in `refit`, all bodies built again each time:
  * `seated` drew the sleeve's shoulder cap into the chest along the chest's surface, which at the armpit
    runs across the joint: the Large Dwarf male's (pmd2) end stood 2.4 cm out of the tier 1 envelope, three
    more bodies 2 to 5 mm. A seated point is now never carried wider of the joint's axis.
  * `over_skin` read the cloth once and the check after it read it again as pushed: a hem wall the push
    tilted became cloth, and the Dwarf female (pfd0) was left 3 mm through it. Each pass reads it afresh.
  * The Troll Large male's (pmg2) arm, 1.86 times a Human's, needed his hem 3.3 cm wider, over the 3 cm a
    push may move. The limit now grows with the body's width (`across`), in the refit's push and the skin
    bake's.
* Second run (`bodies-2`): 16 of 18; the skin bake's push still had the Human limit (pmg2), and the
  pelvis's dome at the Troll Large female's (pfg2) waist stood 5 mm out of her chest at rest: `hidden_at_rest`
  now holds what the split added past an under end inside the part carried over it.
* Third run (`bodies-3`): **all 18 pass every gate.** Belts fitted on each over its own bake
  (`bodies-3/<body>-belt`): all pass; pouches hang as drawn, 1.6 to 8 cm into the trousers at rest.
* Client views, outfit and belt (`bodies-3/<body>-worn`), of the hardest: both Troll Large bodies, the
  Large Dwarf male and the Dwarf female, `shoulders` in contrasting colours and `body` in realistic ones. No
  holes, skin where cloth belongs or open seams; sleeves, waist and boots hold in all six poses. The pmd2
  shoulders run lost shots 22 and 23 to a stalled client; its realistic body sheet covers the same poses.

### 2026-11-27: Street Casual published at 3010

User: "Yes, publish." The outfit and its belt at 3010, set `street-casual`, group `street`, civilian family
(set and group names are mine; the user gave none).

* Baked again at 3010 (`publish-3010`). The female side comes from `female-14-refit`, the female the user
  saw (`publish-3010-f`): refit from the male again with today's code, the Troll Fit female's sleeve cap
  stood 5 mm out at the shoulder, a route not taken further. Belts fitted on each, all pass.
* Publication gates found three things, fixed: a brief's material drawn only on a bare slot (the gloves, cut
  off with the hands) is no longer read as a wrong brief; the registry's channels per part as the textures
  have them; the Troll Large male's neck 2 mm through his shirt below the collar, cut after the refit had
  lifted the chest: the bake now lifts its cut collar over the neck as the publication reads it (pmg2 baked
  again, `publish-3010-g`). The old hanging test still expected pouches pushed out over the thighs and now
  holds them as drawn.
* Trial publication (`output/armorkit/street-casual-trial-1`) passed; its packs worn in the client
  (`wear-trial-1`, six bodies in contrasting colours; `wear-trial-1-real`, both Humans in realistic ones):
  outfit, belt and boots from the packs, nothing missing. The item's examine window is black, as known.
* Published with `--build`: 7 new parts, 503 files in `srn_parts` (379 MB), row 3010 in seven tables,
  registry, handoff and copies; `PROVENANCE.md` entry. `Test-Repository.ps1 -ChangedSince main` passed.
  `srn_parts.hak` is 968 MB, under the 1.5 GB split line.
* c8 bodies (PR 206, the female neck) are not in this branch; when they land the outfit's neck and
  shoulders need a fit check on them.

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

2026-11-24, redraw asked for again: less colour blocking, more detail and gear (user). The brief now has the
accent only on the leg pockets' flaps, and adds a chest pocket, rolled sleeve hems, raised seams, stitched knee
panels, shin pockets, belt pouches, a strap round each thigh and buckled boots. Sealed as
`street-casual-male/reference-v4`; one Qwen image, `run-1/image-0.png`, seed 20261127. Seen in it and not yet
judged by a split: the thigh straps sit high, near the line the hips are cut on, and the leg pockets came out
yellow whole, not their flaps alone. Next: the user's review of the `reference-v4` image.

2026-11-24, the chest pocket dropped (user), the chest drawn broad, flat and smooth. No spot for the chest
print is drawn: the print is a badge mesh of its own that the kit lays on the chest's front, as the brassard's
badge is laid on its band, and a patch drawn in the image would be baked into the shirt's tint. Sealed as
`street-casual-male/reference-v5`; one Qwen image, `run-1/image-0.png`, seed 20261127 as for v4. In it only the
leg pockets' flaps are yellow, with a thin yellow edge round each pocket. Next: the user's review.

2026-11-24, export at 200,000 faces by default (user: implement it now, the outfit in progress included).
`generate export` without `--faces` now exports 200,000, and the bake reduces each part to its budget
(`reduce`), as Facility Security's male was cut; step B4's "about 17,000 faces" is superseded. Street Casual
has both exports of its first geometry: `export-1` at 17,000 and `export-2` at 200,000, and is baked from
`export-2`.

A larger reference image, asked for with it, is not built, because it would change nothing: `calibrate` crops
every reference to its subject at 1,024 by 1,024 pixels (`ImageCropToMask`, in the engine's shared graph)
before geometry or appearance sees it, and a 1,024-pixel reference already fills that crop. More pixels would
have to come from the graph's own crop size, which headkit and itemkit share, and from what the engine's
image encoder takes; neither is looked at here.

2026-11-24, step B3 to B5, geometry attempt 1 of 5 (from `reference-v5`): calibrated (field of view 41.4
degrees), generated, exported (`export-1` 17,000 faces, `export-2` 200,000) and given its appearance. The mesh
looks right in clay views (`geometry-1/views.jpg`): pockets, belt pouches, thigh straps and boots are there;
the shirt's back has a fold the generator invented. **It does not bake.** From either export the fit refuses
the sleeves ("the sleeve is one surface with the torso down to the elbow"): the T-shirt is boxy with a low
armpit, each sleeve ends about 5 cm of sections past where it starts, still joined to the torso, and the
outfit's shoulder joint is estimated 8 to 10 cm outside its surface. A fallback in `split.sleeve` for a sleeve
that ends while joined was tried: the fit then passed and the split refused the sleeve at the shoulder plane
("does not cross the sleeve as it was cut"), so the fallback was taken out again and is not in the kit.

The brief now asks for sleeves set in at the shoulder and reaching just above the elbow; sealed as
`reference-v6`, one Qwen image, seed 20261127. The image shows a short sleeve over a long one to the wrist,
which was not asked for. Next: the user chooses between that layered sleeve (the brief then covers the
forearm and leaves only the hands bare) and a redraw with a plain elbow-length sleeve, before geometry
attempt 2.

2026-11-24, the user: "teach the kit loose short sleeves". Done, with attempt 1 as the case (bake `male-4`
from `export-2`):

* `repose.outfit_joints`: a short, wide sleeve's ring line points in toward the torso, and the shoulder read
  from it stood 8 to 10 cm outside the mesh. A shoulder more than `SHOULDER_OFF` of the outfit's height from
  the body's own place for it is put there instead. The joints of Facility Security (male, female) and Site
  Guard are unchanged.
* `bake.over_own_skin`: the arm kept beside the sleeves stood 1.7 and 2.4 cm out through them under the
  armpit. A bake now pushes a sleeve out over the body's skin where that gate would fail (`refit.over_skin`,
  with the ends the seam contract measures held still) and turns out the faces the push bares. Checked on the
  kept parts: seams, cover, skin and facing gates pass.
* Still failing on attempt 1: the pelvis at 2,914 triangles for a budget of 2,900, cut from the 200,000-face
  export. Not fixed, since attempt 1 is not used (below); look at it if the next geometry does the same.

2026-11-24, the user: "The belt is supposed to be generated as a separate part." Attempt 1 has the belt and
its pouches in the outfit, so it is not taken further. The brief now draws Street Casual without belt, pouches
or gloves (plain waistband with empty loops; the tan thigh straps stay, leather 1), and the belt is its own
accessory brief, `street-casual-belt.json` (belt slot, number 3010, tan leather 1, buckle and two hip
pouches, three-quarter view). Keeping the thigh straps on the trousers is my choice, not confirmed. Next:
seal and draw `reference-v7` and the belt's reference on the shared ComfyUI once the user says to post, a
stop at both images, then geometry attempt 2 of 5 for the outfit and attempt 1 for the belt.

2026-11-24, the user: "Drop thigh straps too", so the outfit is T-shirt, trousers and boots (four colours;
leather 1 is free for the belt piece). References drawn, one Qwen image each, neither accepted yet:

* Outfit `reference-v7` (seed 20261128, elbow-length wording) and `reference-v8` (seed 20261130, the
  `reference-v5` short-sleeve wording back): both show a long pink sleeve to the wrist under the short one and
  a yellow pocket on each sleeve, neither asked for. `reference-v5` drew the short sleeves right with the two
  gloves floating beyond them; without gloves in the image the long sleeves come back.
* Belt `street-casual-belt/reference-v1` (seed 20261129) and `reference-v2` (seed 20261131, "one single
  band"): band, buckle and two pouches as asked, but a second loop of strap hangs under the band, and v2 has
  a second buckle at the back.

Next: the user's choice of how to get the short sleeves (gloves back in the image as an anchor, cut off by
the bare hands as in attempt 1, or the long undersleeve accepted and the forearm covered), then geometry.

2026-11-25, the user: "Gloves back as anchor". The brief draws the two tan gloves again (their own material,
leather 1; the bare hands cut them off in the bake) with the `reference-v5` pose wording. Sealed as
`reference-v9`: run 1 (seed 20261132) drew four gloves; run 2 (seed 20261134) is the candidate: short rolled
sleeves, two gloves, plain waistband, no belt. Not asked for in it: a yellow tab on each shoulder and a yellow
patch or pocket on each sleeve, the two sleeves unlike. Belt `street-casual-belt/reference-v3` (seed
20261133) is the candidate: one ring, one front buckle, a pouch at each hip; the buckle is drawn grey and a
small buckle sits at each side. Next: the user's word on both images, then geometry attempt 2 of 5 for the
outfit and attempt 1 for the belt.

2026-11-25, the user: "Yes, generate both", and "make sure the grey parts of the belt get mapped to a metal
channel".

* Belt brief: a second material, `buckles` (metal 1, grey steel: the buckle and the pouch studs). Redrawn and
  sealed as `street-casual-belt/reference-v4` (seed 20261133): one ring, one buckle, two pouches; the band's
  inner face is drawn near-black. Metal 1 is also the shirt's channel on this outfit; which metal channel the
  buckle takes is the user's to confirm.
* The shared ComfyUI refused a job after `comfy.settings.json` changed (UI preferences only). Captured as
  `capture-20261125-010040.json` and approved on the user's "Approve snapshot" (`approved-cbea00c79d4d`).
* Outfit, geometry attempt 2 of 5 (`calibrate-2`, field of view 34.0; `geometry-2`, `export-3` at 200,000
  faces, `appearance-2`): short rolled sleeves standing clear of the torso, plain waistband, two gloves apart,
  no belt (`geometry-2/views.jpg`).
* Belt, geometry attempt 1 of 5 (`calibrate-2`, field of view 28.4; `geometry-1`, `export-2` at 4,000 faces,
  `appearance-2`), prepared: `output/armorkit/street-casual/belt-1-prepared`, 3,386 triangles. Not fitted yet:
  `accessory fit` wants the outfit compiled.
* **Attempt 2 does not bake yet.** Its sleeves are wider and shorter than attempt 1's and stand out from the
  arm. First the fit refused them ("one surface with the torso down to the elbow"): the arm line through the
  sleeve's middle put the left elbow 5 cm outside the arm, and the right sleeve's own line reached the
  shoulder's height 7 cm behind it. `repose.outfit_joints` now runs a loose sleeve's arm from the body's
  shoulder toward the glove and reads the shoulder front to back too (`SHOULDER_BEHIND`); both attempts then
  pass the fit and the sleeve cut, and the joints of Facility Security (male, female) and Site Guard are
  unchanged. Then the split refuses it (bake `male-6`): "The l sleeve stays joined to the torso: 0% of it goes
  with the arm". The trough gives the arm 13,883 faces, so a strip still joins sleeve and chest after the
  cuts; a wider shoulder cut (radius up to 20 cm) does not part it. Where the strip is has not been found.

2026-11-25, the user: "Keep on the split". What was found on attempt 2, with nothing new committed in code:

* The strip that joins sleeve and chest is at the back of the left shoulder: the wall behind the arm ends
  2.3 cm under the shoulder plane (traced as the shortest path from sleeve to chest across the cuts). The
  gloves of this mesh hang 12 cm in front of its sleeves, so an arm line run toward the glove leans forward,
  the trough leans with it, and its back wall drops.
* Tried and taken out again: a trough reaching higher for a sleeve whose seam is far from the arm's line (this
  seam is 7.5 cm away, so it never applied); the arm line kept at the sleeve's own depth (the fit then refuses
  the sleeve again, "one surface with the torso down to the elbow").
* A sweep of the upper arm's angle from the body's shoulder, in the sleeve's own depth: the sleeve cut is found
  at 30, 65 and 75 degrees from vertical and refused at 40 to 60 and at 70 on attempt 2; on attempt 1 at 30
  only. So `split.sleeve`, which sections the arm along an estimated line and looks for where the sections
  come clear of the torso, is not steady on a short sleeve whose shoulder joint lies well inside a boxy shirt:
  small changes of the line flip it. A fix is a different way to find where such a sleeve leaves the torso
  (from its hem ring inward, say), not another adjustment of the line.
* As committed (`51c6b8dfd`), attempt 1 and attempt 2 pass the fit; attempt 2 fails the split; attempt 1 has
  not been split again since the arm line was changed to run toward the glove.

2026-11-25, the user: "Rework sleeve finding", then "put the buckle on metal 2".

* **My export mistake.** Attempt 2 (`export-3`, `export-4`) and the belt (`export-1`, `export-2`) were exported
  without `--fill 40`, which every earlier outfit used: a hollow, double-walled shell instead of a solid. That
  left every part over its triangle budget, the 20,000-face export full of holes, and the split's own surfaces
  5 cm outside the outfit at every joint; it very likely caused the split's refusal of the sleeves too. Solid
  exports: outfit `export-5` (200,000 faces), belt `export-3` (4,000 faces). (Corrected 2026-11-25: `--fill` is the price of closing an opening, not a size; a lower one closes larger openings, and the typed trial's mesh was hollow at 40, 80 and 160 and solid at 20. A hollow export is now refused, `repose.solidity`.) **Always pass `--fill` to
  `generate export`**; a default for it is not built.
* **Sleeve finding** (`split.sleeve`, committed `75410a3a5`): a section short of the body's middle is the web
  under the armpit for `SLEEVE_WEB` sections at most, then the sleeve is free; up to `SLEEVE_LOST` sections
  with no curve round the arm are passed over. `repose`: a loose sleeve's arm keeps the sleeve's depth. The
  sleeve is found at every upper-arm angle from 25 to 75 degrees on attempts 1 and 2 (attempt 1, a solid, was
  found at 30 only before); the cuts of Facility Security (male, female) and Site Guard are identical.
* **Unworn materials** (`brief.baked`, `unworn`): the gloves beyond the short sleeves are generated and cut
  off with the bare hands, and are not counted among the baked outfit's materials. The brief also records the
  colours as generated (`shown`): flaps ochre, boots olive.
* **Belt:** buckle and studs on metal 2; adopted as `street-casual-belt/reference-v5` (same image, colours
  as drawn on record); prepared from the solid export, one piece, no holes, 3,998 triangles
  (`output/armorkit/street-casual/belt-4-prepared`). Not fitted yet.
* **Bake `male-12`** (attempt 2, solid): every part within budget (34,094 triangles); trousers cloth 2, shirt
  metal 1, flaps metal 2, boots leather 2. One gate fails: at each shoulder what the split added stands 1.0
  and 1.1 cm outside the outfit at rest (the sleeve's closing shows at the front of the shoulder).
* **Client pose check, Human male** (`male-12-poses/sheet.jpg`, 48 shots): the outfit loads and follows the
  body. Seen: the shirt and the flaps, on metal channels, are drawn with a metal's shine; a thin sliver stands
  out of each boot at the ankle; dark gaps under the thigh pocket flaps; a brown patch on each sleeve (the
  shoulder tab the image added); the seat tears open sitting; the crouching shots are framed off the body.
  Stop 2: the user's review.
* The stock parts tables the pose check reads were gone from the main checkout's `.tmp`; copied from the
  worktree `head-generation-options-5b1c4b` into this one's ignored `.tmp/armorkit-phase0/stock`.

2026-11-25, the user, on the client sheet: "we need to reserve metal channels for metal or otherwise shiny
parts". This replaces the metal rows of the colour convention above and the use of a metal channel for a
shirt or trim anywhere in this plan.

| Channel | Drawn in | Holds |
|---|---|---|
| cloth 1 | sky blue or the brief's own | the garment on the torso and arms |
| cloth 2 | grey | the garment on the legs |
| leather 1 | tan | belt, straps, gear; a cloth accent where the outfit has no gear of its own |
| leather 2 | green | footwear and gloves |
| metal 1 | — | metal and shiny parts only: plates |
| metal 2 | — | metal and shiny parts only: buckles, studs, hardware |

* **Guard** (`brief.validate`): a material of another kind tinted on metal is refused unless it is marked
  `"shiny": true`. A material marked `unworn` takes no channel and names none, so the gloves cut off with
  the bare hands leave leather 1 free.
* **Street Casual:** shirt cloth 1, trousers cloth 2, pocket flaps leather 1 (`"tint": "leather"`), boots
  leather 2. The belt's strap is leather 1 too, so the flaps take the belt's colour; its buckle stays metal 2.
* **Open:** a jacket on the robe slot is coloured by the same six channels as the shirt under it, and both
  were to differ (jacket cloth 1, shirt metal 1). With metal reserved, the jacket and the shirt share cloth 1
  unless the jacket takes leather 1. To settle at step J.

2026-11-25, the user: "we are going to need to increase our poly counts further as well. Double them please".
`bake.BUDGET`: chest 16,000, other slots 5,800, a whole outfit 80,000 (plan.md, Budgets). The accessory's
4,000 doubles too, to 8,000 (user, same day: "Yes, 8,000"; `accessory.BUDGET`, `brassard.BUDGET`). The belt's
4,000-face export (`export-3`) and `belt-4-prepared` predate it.

* **Bake `male-14`** (attempt 2, solid export, new budgets and channels): 68,197 triangles, every part at its
  budget, ten models compiled. Channels as above, nothing on metal. The flaps' `shown` colour is now the
  whole mesh's ([156, 120, 70]): with the cut parts' it could not be told from the gloves there. The shoulder
  gate still fails (1.1 cm each side). Offline view `review/street-casual-male-14-render.png`.
* Not done: the client view of `male-14` (another session's client was running), the belt's fit.
* **Belt at 8,000** (user: "Yes, re-export"): `export-4` (solid, 8,000 faces), prepared as `belt-5-prepared`
  (7,992 triangles, one piece, no holes), fitted over `male-14` as `belt-5` (`pmh0_belt310`): gates pass,
  nothing inside the outfit, compiled. No geometry attempt used.
* **Belt channels, not right yet:** the generated colours show two materials only, tan (leather 1, 80% of
  the texture) and near-black [34, 34, 32] (metal 2, 20%). The near-black is the buckle and studs together
  with what the single reference view never showed: the strap's inner face and the backs of the pouches,
  which the generator painted dark. So those leather faces are on metal 2 and will draw shiny where they
  show (`review/belt-5-channels.png`). Colour alone cannot part them from the buckle. Not seen in the client.

2026-11-25, the user: "Yes, fix it" (the belt's unseen faces), then "please check for other issues with the plt
painter and fix them". Every tint texture of `male-14` and the belt was looked at beside its colours.

* **A belt's faces turned toward the body are no metal's** (`accessory.body_side`, `BODY_SIDE`): they take the
  commonest material tinted on no metal, at their own shade. Belt `belt-6`: metal 2 on 5% of the texture
  (studs, buckle, and thin lines along the strap's dark edges, which face up and down and are left), from 20%.
* **Found: a boot was two thirds pocket flap.** A texel's material was the nearest in colour among all the
  outfit's materials, and a boot's dark leather has the tone of the flaps in shadow: 67% of each foot was on
  the flaps' channel (two-coloured boots in the client), as were the tan tab on each sleeve (22% and 13% of
  the upper arms, the brown patches of the first client sheet) and 2% of the chest.
* **Fix: a material lists the slots it is worn on** (`"slots"` in the brief, `brief.on`; `texture.labels` and
  `tint_maps` take `among`): a part is tinted in the materials its slot wears and no other, and a closing takes
  the first of those. Street Casual: shirt chest, upper arms, pelvis; trousers chest, pelvis, thighs, shins;
  flaps pelvis, thighs, shins; boots shins, feet.
* **Guard:** where 1% or more of a part's own surface has the colour of a material its slot leaves out, the
  bake says so and records the share (`elsewhere` in `bake.json`). My first list left the pelvis out of the
  flaps' slots and the hip pockets' flaps were drawn as shirt; that line is what shows such a slip.
* **Looked at and left:** shades run from about 96 to the ceiling of 240, with 0.4% to 5% of a part's texels at
  the ceiling (most on the shins); layers are clean inside charts after the fix; padding between charts is
  filled.
* **Bake `male-15`** (the kept parts of `male-14`, tinted again): boots all leather 2, sleeves all cloth 1,
  flaps leather 1 on pelvis, thighs and shins. Belt fitted over it. Neither seen in the client. The shoulder
  gate still fails.

2026-11-25, the user: "Yes, shoulder gate".

* **What failed.** The points 1.0 and 1.1 cm outside the outfit were the middle of each sleeve's closing toward
  the torso, 8 cm down the arm: on a loose sleeve that wall stands off the chest's side. The chest's lids over
  its armholes were worse and unmeasured (an over part's are not): up to 2.1 cm out in front of the left
  sleeve, 1.7 cm the right.
* **Fix: `bake.tucked`** (after `skinned`, at the shoulders, `TUCKED`): a vertex only what the split added
  uses, outside every other part by more than half the contract's `rest`, is set 2 mm under the nearest
  other part. The under part's are all brought in, the over part's flat closings only. Street Casual: 113
  and 53 points of the chest, 55 and 27 of the sleeves. A second pass moves nothing.
* **Bake `male-16`** (`male-16-kept`: the kept parts of `male-14` with `tucked` applied, tinted again): **all
  gates pass**, the shoulders' `rest` 0.2 cm each side, 68,197 triangles, ten models compiled. Belt `belt-7`
  fitted over it, gates pass. A fresh bake from the mesh runs the same step in the same place and has not
  been run.
* **Still to see in the client:** with the arm at rest a patch of the closings, about 8 by 7 cm, faces the
  viewer in front of each armpit (30 cm² of the chest's, 26 cm² of the sleeve's, by rays cast from the left
  front). That is by design, not a protrusion: the box sleeve is cut from the chest with the arms at 45
  degrees, and lowering the arm parts the two edges there. It is drawn in the shirt's edge colours. The
  sleeves as generated are as deep front to back as the chest (26 cm).
* Tried and taken back: capping the trough's walls at the free sleeve's width. It moved Street Casual's walls
  6 mm, not the cause, and moved Facility Security female's left wall 2 mm.

