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
  exports: outfit `export-5` (200,000 faces), belt `export-3` (4,000 faces). **Always pass `--fill 40` to
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

