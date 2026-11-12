# Pilot set: corporate security

Phase 1 of the [armorkit plan](plan.md). This is the brief (pipeline step 1) for the pilot and the order the
work is taken in. Written 2026-11-10 when Phase 1 started. Of the tooling the splitter and the export step exist
(`tools/armorkit/split.py`, `export.py`); no model is generated or built yet. The concept is the
"Corporate Security: Facility & Patrol Uniforms" sheet in the SRN concept art folder. Choices marked
*proposed* were made while drafting and are open to the user's correction.

## What the concept shows

The sheet has four uniform levels. To keep them apart from the seam tiers 0–3 of the plan, they are called
levels here.

| Level | Concept name | What it wears | In the pilot |
|---|---|---|---|
| 1 | Patrol | Short-sleeved shirt with bare forearms, light plate carrier, gloves, duty belt, cargo trousers, boots, cap | Yes |
| 2 | Facility Security | The same shirt and trousers, a carrier with a row of pouches, knee pads and shin guards | Yes |
| 3 | Site Guard | Long sleeves, armored carrier, shoulder, upper-arm and forearm guards, the same knee and shin guards, helmet | Yes, built first, without the helmet |
| 4 | Internal Response | Full armor | No: heavy kits are deferred |

Five corporations wear the same uniform in their own colours with their own logo: Ares, Renraku,
Saeder-Krupp, Wuxing and Mitsuhama.

The first draft of this brief had Facility Security in long sleeves and built it first. That was a misreading
of the small figures; a closer crop shows bare forearms on levels 1 and 2. Site Guard is the level with no
exposed skin, so it is built first (*proposed*).

## Sets and numbers

Security family, block 6000, group 0 (`corpsec`). One set per level, so the tens digit is the level
(*proposed*). Units are left for variants.

| Slot | 6010 Patrol | 6020 Facility | 6030 Site Guard |
|---|---|---|---|
| Chest (male and female cut) | Shirt and light carrier, tier 1 | Shirt and pouch carrier, tier 2 | Armored carrier, tier 2 |
| Bicep | Short sleeve over skin, tier 1 | Uses 6010 | Long sleeve with upper-arm guard, tier 2 |
| Forearm | Bare (body part) | Bare (body part) | Sleeve with forearm guard, tier 2 |
| Hand | Glove, tier 0 | Uses 6010 | Uses 6010 |
| Pelvis, thigh | Cargo trousers, tier 1 | Uses 6010 | Uses 6010 |
| Shin | Trouser leg, tier 1 | Knee pad and shin guard, tier 1 at the knee, tier 2 at the ankle | Uses 6020 |
| Foot | Duty boot, tier 1 | Uses 6010 | Uses 6010 |
| Belt | Duty belt with holster and pouches | Uses 6010 | Uses 6010 |
| Shoulder | none | none | Shoulder guard carrying the logo badge |

"Uses 6010" means no part is made: a recipe in SR_NWN names the Patrol part in that slot. That keeps the
pilot to the parts that differ (*proposed*; the alternative is every level complete in every slot).

A part declares a tier at each of its joints; the table gives one where all its ends are the same. Two under
ends are set low so that every recipe above mixes cleanly, the over end at least the under end's tier
(*proposed*). The 6020 shin goes under the tier 1 trouser thigh, so it is tier 1 at the knee, its knee pad
starts below the seam, and only its ankle end is tier 2. The glove's one end, the wrist, goes under a bare
forearm on levels 1 and 2, so the glove is tier 0, skin-tight.

Standalone pieces (1000–2999), usable with any outfit:

| Slot | Number | Piece |
|---|---|---|
| Shoulder | 1000 | Brassard: a cloth band with the logo badge, for levels 1 and 2 |
| Neck (headgear band) | 1000 | Balaclava, skinned, face covered (*proposed* over the respirator: simpler shape for the first skinned piece) |

Not in the pilot: the cap and sunglasses (they show the face, against decision 6), the helmet (helmet slot,
Phase 3), the back harness, the wrist display and the carried weapons.

## Colour and logos

| Channel | Use |
|---|---|
| Cloth 1 | Uniform base |
| Cloth 2 | Corporation accent: piping, panels, guard stripes |
| Leather 1 | Belts, straps, boots |
| Leather 2 | Gloves, pouches |
| Metal 1 | Armor plates |
| Metal 2 | Buckles and hardware |

As built on 2026-11-11 the Site Guard's reference shows three materials, one of each kind, so each has both
of its kind's channels and they are told apart by garment: cloth 1 the shirt, cloth 2 the trousers, leather 1
the carrier, leather 2 gloves and boots, metal 1 the shoulder and arm guards, metal 2 the knee and shin guards.
Its materials and their kinds are in `tools/armorkit/briefs/corpsec-siteguard-male.json`.

Rebuilt later that day from a second brief (`corpsec-siteguard-male-2.json`, geometry attempt 3 of 5): the plates
are asked for in a clear sky blue, 58 from the cloth in the image where the first were 17, and every strap that
holds a guard or pad on is tan webbing, the gear's material. In the first image the straps were a grey-blue
between cloth and plates and had no material of their own. Leather 2 now takes everything of leather on the
limbs, so all the straps are coloured with the gloves and boots.

The second mesh first built with its upper sleeves on the chest part: the cut that parts a sleeve from the
torso stopped 2 cm short of the shoulder plane behind each shoulder, and the forearms lifted out of sleeves
that stayed put. The cut now reaches 10 cm above the shoulder joint, and a build whose sleeve stays joined to
the torso is refused.

In the client the crotch then showed two flat plain patches with a black hole above them, and the seat a hole
when the body sat or crouched. The game stands a body with its thighs turned out, which opens the cut between
the legs at the front; the patches were the thighs' flat inner walls and the hole the pelvis, open on both hip
planes. The pelvis is now closed on both planes and repeats a strip of the trousers along the crotch, just
under the thighs. A cap keeps the materials its rim shows without their streaks, so the knee between the two
halves of its pad is the pad, and the thighs' inner walls are drawn as the trousers they close.

The knee and elbow pads are cut in two on their joint planes, and sitting, the upper half of a knee pad lay
along the top of the thigh with trousers showing between the halves. Giving the whole pad to the shin or the
forearm was tried and taken back: it swung off the thigh at any bend and stood out behind a bent elbow. The
shin's and the forearm's caps now carry the pad's rim round the joint's hinge, in the pad's material, so the
gap a bend opens between the two halves is filled out to their cut edges.

A polishing round followed a review of the build in the client (eleven poses, four views each). The arm
plates were grey in the middle with a rim of their colour: a plate that catches the light is paler and less
coloured, and was read as cloth; a highlight is now still its material. Piping and flecks of the plates'
colour on the sleeves, four texels across or less, are drawn as the sleeve. What the split makes (closings,
caps) is drawn at the cloth's lit shade, not its middle shade, and a cap is lit as the surface it rounds off:
the tops of the thighs stood out of the seat as darker flat patches, standing and in every crouch. A thigh's
cap starts a little inside its rim, the crotch strip ends in a point, and flat closings carry no relief.

A second round took up what that one left, with walking, running and unarmed combat added to the captures
(fifteen actors, four views each). The reference draws a grey tab in a frame of the plates' colour under each
shoulder pad. At 12,000 faces the frame was a band one to three faces wide: part of it joined the pad and
went to the shoulder part as a strip hanging down the arm, and the pad was cut out along the teeth of its
outline, which left the chest's edge round the armhole ragged under a lifted arm. A line of metal too narrow
to be a plate is now trim and is given to the cloth it lies on, before the outfit is cut; and a plate is
drawn on its own faces and nowhere else, which took the specks a pad left on the sleeve under its edge and
the blots and tails along the elbow plates' outlines. The walk showed the tops of the thighs again: flat pale patches in the crotch at every step, the
thigh's cap on the leg swinging forward and the pelvis's lid in front of the leg swinging back. A thigh's cap,
its inner wall and the pelvis's lids are now shaded as the cloth round them, vertex by vertex. Left as they
are: the reference's elbow guard is two plates with a strap between them, and a bent arm shows the sleeve
between the two as a wedge; a plate's outline now runs along face edges where its colour ran past them,
in short straight runs; and where a thigh's top leaves the pelvis its outline against the trousers' folds is
jagged. The accent and
hardware uses in the table need materials of their own in a reference (two of a kind) and are not built.

Each corporation is a palette over these channels plus one cell of the logo strip. The five logos are not in
the repository; the logo art has to be supplied or made before the brassard is reviewed in the client.

## Models to generate

Each is one generated model with its own references and at most five geometry submissions.

| Model | Covers |
|---|---|
| Human male Site Guard outfit | 6030 chest, bicep, forearm, shoulder; 6020 shin; 6010 hand, pelvis, thigh, foot. One model gives a whole covered body |
| Human male Patrol top and lower leg | 6010 chest, bicep with its exposed skin, shin |
| Human male Facility carrier | 6020 chest |
| Human female torso, one per level | The three female chest cuts |
| Duty belt | 6010 belt |
| Balaclava | Neck 1000 |

The brassard is a simple band and is authored by hand.

## Order of work

Nothing beyond step 3 is built for a later model until the user has seen the Human male Site Guard outfit in
the client, as the plan requires.

1. This brief.
2. References for the Human male Site Guard outfit: garment only, headless, rest stance, a clay image for
   geometry and a colour image for appearance. User review.
3. Split and fit tooling written against the seam contract. It takes the Xenomech kit's method, not its code
   or its recipe per outfit, and uses tint textures in place of the kit's tint shaders. The splitter and
   the export of parts as compiled models are built; reading a source, fitting and materials are not.
4. Generate, split, fit, write materials, compile. Offline gates.
5. Human male Site Guard outfit in the client: standing, idle and motion. User review.
6. The remaining male models, then the female chest cuts. User review.
7. Race versions with shape factors for the 18 other bodies, the checks section 19 of the spike record left
   open (other slots, Large male), gates, and a sampled client review on the hardest bodies. User review.
8. Belt, brassard and balaclava; the shared logo material, shader and strip; the headgear fit per race.
9. Publish to `srn_parts` with the registry and the SR_NWN handoff.

## Reference images

The user chose the Codex app's image generation, run through its command line under the user's login
(2026-11-10). It has a usage limit, which was reached that day before the first image. Prompts, inputs and
each call are kept with the model's working files under `output/armorkit/corpsec-pilot/`, outside the
repository.
