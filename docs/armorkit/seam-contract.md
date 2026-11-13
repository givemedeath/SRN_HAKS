# Seam contract and head envelopes (version 2, 2026-11-10)

Measured in Phase 0 of [the plan](plan.md) on the locked c7 Human Fit bodies in `srn_body` (`pmh0`, `pfh0`) and
the published heads in `srn_head`. The numbers live in `tools/armorkit/seam-contract.json` and
`tools/armorkit/head-envelopes.json`; this page says what they mean and how they were taken. They are
measurements and starting rules for the pilot, not asset approvals. A change to either file is a new contract
version, recorded here as a dated section.

Rebuild both files with
`<bundled-python> -B -m tools.armorkit measure --body-pack srn_body --head-pack srn_head --supermodels <stock animation models> --output <folder>`.
`--only heads` rebuilds the head envelopes alone and needs no animation models; `--only seams` rebuilds the
contract alone. The stock animation models (`a_ba`, `a_ba_med_weap`, `a_ba_casts`, `a_fa`) are extracted from
the game install; `a_ba_non_combat`, `a_ba_custom` and `srn_fa_h0` come from `srn_body`. The contract records
the hash of every body model and animation model it was measured from.

## What is frozen

**Joint planes.** Each of the eight joints has one plane per body, in the body's bind pose (metres, body space:
+Y is the character's front, +Z is up). The plane passes through the bone that carries the under part, except
at the waist, where it passes through the torso bone (the pelvis hangs from it). For limb joints its normal runs
along the limb, pointing into the under part; the neck and waist planes are horizontal. Limb joints are recorded
on both sides: the male body is centred, but the female body's right joints sit 0.7 to 0.8 cm from the mirror
image of her left ones. The neck and waist have one side, `c`.

**Layering order.** The part nearer the torso lies over the other, and the chest lies over everything it
touches: chest over neck, bicep and pelvis; bicep over forearm; forearm over hand; pelvis over thigh; thigh over
shin; shin over foot. This matches the plan's two examples and keeps the common cases clean (a sleeve over a
bare hand, trousers over a bare foot). A bulky glove or boot under a thinner sleeve or trouser leg is the pair
the registry marks as not clean.

**Body ring.** The body's own outline at the plane, as the largest distance from the joint centre in 16
directions. Direction 0 is the in-plane axis nearest body +X on both sides, so a right ring is the left ring
mirrored, not the same list; the ring is taken on both skin parts at the plane and 1 cm to each side, because
some skin parts end exactly on the plane. At the neck, shoulder and hip the plane also cuts the torso, so only
the limb's (or neck's) own ring counts, and a torso piece cannot be measured there by a plane section: its neck
hole, armholes and leg holes need a measure of their own (not built yet). The bake cuts an outfit's hips where the body's own pelvis
ends, not on the plane (`split.seated`), so its thigh's end at the plane is the leg, not half of the seat. It cuts the upper arms where
the body's arm comes out of its chest, past the plane only (`split.armholed`), and grows one end from each arm's whole opening there.

**Tier envelopes.** A tier's envelope is the body ring pushed out by a fixed offset: tier 0 (skin-tight)
0.4 cm, tier 1 (cloth) 1.2 cm, tier 2 (padded or armored) 2.5 cm, tier 3 (heavy) 5 cm. An under end must stay
inside its tier's envelope at the plane; an over end must be open and at least as wide as its tier's envelope.
The "envelope radius" in the table is the largest of the 16 directions; the gate (`bake.ends`) uses all 16. The file stores
each tier's numbers and refuses to load when they disagree with its own body rings, tier offsets and swing.

**Minimum overlap.** The under end continues past the plane, into the over part, by at least
`mean envelope radius x min(1, tan(swing))`. A rim point at the plane drops out of the over part by
`radius x tan(angle)` when the joint swings; past 45 degrees a rounded end one radius deep covers every angle.
The swing used is the 95th percentile over every clip the body plays, with twist about the limb left out
(twist turns the under end inside the over end without opening the seam). The continued end tapers in one
slope, with no shelf. The bake shapes the elbow, wrist, waist, knee and ankle ends to their envelope (`tools/armorkit/ends.py`).

## Numbers

| Joint | Over | Under | Body | Swing p95 / max (deg) | Body ring mean / max (cm) | Envelope radius T0-T3 (cm) | Minimum overlap T0-T3 (cm) | Body skin past plane: under / over (cm) |
|---|---|---|---|---|---|---|---|---|
| neck | chest | neck | male | 18 / 55 | 6.4 / 8.2 | 8.6 / 9.4 / 10.7 / 13.2 | 2.3 / 2.5 / 3.0 / 3.8 | 7.1 / n/a |
| neck | chest | neck | female | 19 / 55 | 4.9 / 5.9 | 6.3 / 7.1 / 8.4 / 10.9 | 1.8 / 2.0 / 2.5 / 3.3 | 5.3 / n/a |
| shoulder | chest | bicep | male | 101 / 148 | 6.6 / 10.5 | 10.9 / 11.7 / 13.0 / 15.5 | 7.0 / 7.8 / 9.1 / 11.6 | 6.3 / n/a |
| shoulder | chest | bicep | female | 101 / 151 | 4.2 / 5.2 | 5.6 / 6.4 / 7.7 / 10.2 | 4.6 / 5.4 / 6.7 / 9.2 | 2.6 / n/a |
| elbow | bicep | forearm | male | 109 / 150 | 4.5 / 5.3 | 5.7 / 6.5 / 7.8 / 10.3 | 4.9 / 5.7 / 7.0 / 9.5 | 4.1 / 4.3 |
| elbow | bicep | forearm | female | 109 / 146 | 3.1 / 3.4 | 3.8 / 4.5 / 5.9 / 8.3 | 3.5 / 4.3 / 5.6 / 8.1 | 2.0 / 0.5 |
| wrist | forearm | hand | male | 51 / 105 | 3.8 / 4.3 | 4.7 / 5.5 / 6.8 / 9.3 | 4.2 / 5.0 / 6.3 / 8.8 | 1.7 / 3.2 |
| wrist | forearm | hand | female | 52 / 107 | 2.6 / 2.8 | 3.2 / 4.0 / 5.3 / 7.8 | 3.0 / 3.8 / 5.1 / 7.6 | 0.9 / 1.1 |
| waist | chest | pelvis | male | 37 / 96 | 13.7 / 15.9 | 16.3 / 17.1 / 18.4 / 20.9 | 10.6 / 11.2 / 12.2 / 14.1 | 0.0 / 3.0 |
| waist | chest | pelvis | female | 37 / 96 | 9.5 / 11.9 | 12.3 / 13.1 / 14.4 / 16.9 | 7.5 / 8.1 / 9.1 / 11.0 | 4.9 / 6.1 |
| hip | pelvis | thigh | male | 67 / 152 | 9.4 / 9.8 | 10.2 / 11.0 / 12.3 / 14.8 | 9.8 / 10.6 / 11.9 / 14.4 | 6.9 / n/a |
| hip | pelvis | thigh | female | 67 / 149 | 9.0 / 9.7 | 10.1 / 10.9 / 12.2 / 14.7 | 9.4 / 10.2 / 11.5 / 14.0 | 11.2 / n/a |
| knee | thigh | shin | male | 81 / 153 | 6.1 / 8.4 | 8.8 / 9.6 / 10.9 / 13.4 | 6.5 / 7.3 / 8.6 / 11.1 | 4.4 / 0.3 |
| knee | thigh | shin | female | 80 / 154 | 4.7 / 5.3 | 5.7 / 6.5 / 7.8 / 10.3 | 5.1 / 5.9 / 7.2 / 9.8 | 4.0 / 4.0 |
| ankle | shin | foot | male | 48 / 86 | 4.7 / 6.1 | 6.5 / 7.3 / 8.6 / 11.1 | 5.1 / 5.9 / 7.2 / 9.7 | 6.4 / 3.8 |
| ankle | shin | foot | female | 48 / 87 | 3.4 / 4.0 | 4.4 / 5.2 / 6.5 / 9.0 | 3.8 / 4.6 / 5.9 / 8.4 | 1.7 / 1.3 |

The numbers are the left side (the wider side sets the tier numbers; the two differ by less than 0.1 mm here).
The last column is how far the body's own skin parts run past each plane. It is context, not a rule: the bodies
join by matched rings, and several skin parts overlap far less than the clothing rule asks (the male pelvis stops
on the waist plane). It has no "over" figure at the neck, shoulder and hip, where the over part is the torso.

Swing was sampled over the 407 clips each body plays (every key time and the midpoints between keys). A clip
name carried by several models in the body's chain plays from the nearest one; the 138 (male) and 189 (female)
copies behind those are not sampled. The worst clips are `dodgelr` (neck, knee), `throw_gren_df` (shoulder),
`plstab` and `victorymg` (elbow), `reload_smg_dm` (wrist), `whirlwind` (waist), `mount1start` (hip) and
`gustandf` (ankle). Only the neck and waist stay under 45 degrees at the 95th percentile, so every other under
end needs the full rounded end.

## Where the tier offsets come from

The converted stock clothing was the reference. The Human bodies wear the game's own Human parts (`srn_armor`
holds only the other races), so the stock Human Fit models of the fitted slots were read from the game install
and their rings compared with the c7 body rings at every joint; 670 joint ends could be measured, and 129
models were skipped because they are skinned, animated or empty.

* A typical stock part sits 0 to 1 cm outside the body ring at a joint (median over directions; stock seams are
  matched rings).
* The widest tenth of directions on a typical part reaches 1.5 to 2 cm at wrists, elbows and knees.
* Flared cuffs and boots reach 3 to 7 cm (the widest tenth of parts at the elbow, wrist and knee).
* The stock armor class of a chest piece does not change its clearance at the joints.

The offsets follow these bands: 0.4 cm clears the skin, 1.2 cm is ordinary stock clothing, 2.5 cm covers the
wider stock pieces, and 5 cm the flared ones. They are starting values to tune in the pilot.

## Head envelopes

Per race and gender, the union of every published head (hair, horns and tusks included) in the head bone's own
space: the bounding box, and per 2 cm of height the largest radius in 16 directions about the vertical line
through the box centre. The radii are taken from the head surfaces sampled every 3 mm, not from vertices alone.
Heads are published for the Fit build only. Neck-slot headgear must clear the envelope of each race it is built
for.

| Body | Heads | Width (cm) | Depth back / front (cm) | Below / above head bone (cm) | Largest radius (cm) | Head bone height (m) |
|---|---|---|---|---|---|---|
| Human male | 2 | 22.6 | 9.9 / 13.9 | 7.5 / 17.4 | 12.7 | 1.753 |
| Dwarf male | 4 | 32.5 | 12.8 / 14.0 | 14.1 / 19.8 | 17.7 | 1.167 |
| Elf male | 4 | 23.3 | 11.6 / 11.2 | 9.5 / 20.4 | 12.1 | 1.902 |
| Orc male | 2 | 22.2 | 14.3 / 14.3 | 5.7 / 18.6 | 14.5 | 1.900 |
| Troll male | 20 | 62.0 | 22.5 / 23.7 | 13.9 / 36.1 | 32.4 | 2.501 |
| Human female | 4 | 23.3 | 11.7 / 12.1 | 7.3 / 23.8 | 13.1 | 1.665 |
| Dwarf female | 4 | 24.1 | 15.6 / 12.6 | 11.0 / 16.1 | 14.5 | 1.115 |
| Elf female | 4 | 25.5 | 12.8 / 11.8 | 11.8 / 18.0 | 12.8 | 1.770 |
| Orc female | 4 | 24.6 | 12.4 / 13.5 | 4.7 / 24.6 | 13.0 | 1.800 |
| Troll female | 20 | 54.4 | 29.8 / 19.1 | 19.2 / 36.6 | 28.5 | 2.301 |

## Limits

* The planes, rings and overlaps are measured on the two Human Fit bodies only. The other 18 bodies get their
  parts from race versions of the Human parts, so they inherit the contract through that fit; they have no
  measured rings of their own. The contract format takes more bodies; none has been added.
* The measurement covers under ends at every joint and over ends at the elbow, wrist, waist, knee and ankle. It
  does not cover the chest's neck hole and armholes or the pelvis's leg holes.
* The layering order and the tier offsets are rules chosen here from the plan and the stock measurements. They
  have not been tried on a generated part.
* The overlap rule treats each joint as a hinge about its centre with a round section. The waist and shoulder
  are far from round, so their overlaps are generous.
* A head envelope is the union of all heads of a race, so one wide head sets it. The Troll envelopes are
  dominated by horns: headgear that clears them will float on a hornless Troll head. Dwarf male has one wide
  head (beard or hair) that sets its 32 cm width.
* New heads change the envelopes. The file lists the heads it was measured from, and the package's test fails
  when the published heads differ from that list or an animation model in `srn_body` differs from the one the
  swing was sampled from: re-measure then. The stock animation models are not in the repository, so a change
  to those is not noticed.
* Heads that `srn_body` ships for its own builds (the Large bodies' `head001`) are not in the envelopes.
* Swing percentiles weight every key equally, so long idle clips count more than short attacks.

## Version 2 (2026-11-10)

Version 1, frozen earlier the same day, was replaced after review before anything used it:

* **Swing.** Version 1 sampled every clip stored in every model of a body's chain, 545 for the male body and 596
  for the female, including copies the body never plays. Version 2 samples the 407 clips each body plays. The
  95th percentile fell at the neck (21 to 18 and 19 degrees), waist (40 and 42 to 37), hip (72 to 67), knee
  (98 and 97 to 81 and 80) and ankle (50 to 48); the neck and waist minimum overlaps fell with it, by 0.2 to
  2.1 cm. The worst shoulder clip was a copy that is never played (`1hreach`, 176 degrees); it is now
  `throw_gren_df`, 148 and 151 degrees.
* **Sides.** Limb joints are recorded on both sides instead of the left alone.
* **Torso openings.** The "over" run past the plane is no longer recorded at the neck, shoulder and hip, where it
  measured the torso wall (36 cm at the shoulder).
* **Head envelopes.** Radii come from sampled surfaces. Version 1 used vertices alone and recorded up to 12 cm
  too little in cells a triangle crossed without a vertex (195 of 2,832 cells rose by more than 5 mm). The boxes
  and largest radii in the table did not change.
* **Sources.** The contract records the hash of each animation model, and the head envelope file its sampling
  step.
