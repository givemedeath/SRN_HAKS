# Seam contract and head envelopes (version 5, 2026-11-26)

Measured in Phase 0 of [the plan](plan.md) on the locked c7 Human Fit bodies in `srn_body` (`pmh0`, `pfh0`) and
the published heads in `srn_head`; since version 4 the seam contract holds all 20 bodies of `srn_body`, each
measured on its own models (**Version 4** below). The tables on this page are the two Human Fit bodies'. The numbers live in `tools/armorkit/seam-contract.json` and
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
inside its tier's envelope at the plane; an over end must be at least as wide as its tier's envelope there, and
is closed by a dome on past the plane (see **Closed ends**).
The "envelope radius" in the table is the largest of the 16 directions; the gate (`bake.ends`) uses all 16. The file stores
each tier's numbers and refuses to load when they disagree with its own body rings, tier offsets and swing.

**Minimum overlap.** The under end continues past the plane, into the over part, by at least
`mean envelope radius x min(1, tan(swing))`. A rim point at the plane drops out of the over part by
`radius x tan(angle)` when the joint swings; past 45 degrees a rounded end one radius deep covers every angle.
The swing used is the 95th percentile over every clip the body plays, with twist about the limb left out
(twist turns the under end inside the over end without opening the seam). The continued end tapers in one
slope, with no shelf. The bake shapes the elbow, wrist, waist, knee and ankle ends to their envelope (`tools/armorkit/ends.py`).
At the neck, shoulder and hip the over part is the torso, and an under end runs into it no deeper than the
outfit's torso first crosses the joint's axis, less 4 mm (`split.room`); the bake's seam gate asks no more there.
The female shoulder stands less far over its joint than its minimum overlap, even bare, and an upper arm's end
the full overlap deep came out through the top of her shoulder (Facility Security, 2026-11-13).

**Closed ends** (version 3, `ends` in the file). Every end is closed and at least slightly domed, so the two
parts at a joint overlap as they turn and the engine draws whichever surface lies nearer: no end is left open
and none is closed flat. An over part's opening on its joint's plane is closed by a dome on past the plane into
the under part, its pole `domeDepth` (0.3) of the opening's mean distance from its axis past the opening and
`domeMost` (2 cm) at most, in `domeRings` (6) rings; a pad's half on the plane is left open. An under end runs
on past the plane by the minimum overlap, rounded in to its axis. What the split adds to an under end lies no
more than `rest` (5 mm) outside the outfit as the body stands, and with the under part turned about the joint
by the design bend, what of its end lies farther from the joint than its own ring on the plane stands no more
than `bent` (1 cm) outside the over part (`bake.hidden`). The bend tolerance is set from Facility Security male,
which the user saw clean in the client with every end domed: turned, it stands at most 0.7 cm out (its left hip and shoulder).

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

Re-measured 2026-11-18 with the 40 head-library heads (docs/heads/head-library-40-v1.md; user decision). Their long
hair and braids set several envelopes: Orc female now reaches 17.5 cm below the head bone and is 40 cm wide, Orc male
35 cm. How headgear treats hair that hangs below the jaw is decided when headgear is fitted.

Re-measured 2026-11-26 with the c8 Human necks (contract 1.6.0, [human-bodies-lock-c8](../phenomorpher/human-bodies-lock-c8.md)):
the Human male heads are 6% larger, and the Human female head bone is 3.5 cm lower. Only the two Human rows change.

Re-measured 2026-11-20 with the 10 head-library troll heads (docs/heads/head-library-trolls-v1.md; user decision).
Only the two Troll rows change. Troll male now reaches 18.4 cm below the head bone and
27.0 cm in front, and Troll female is 55.2 cm wide.

| Body | Heads | Width (cm) | Depth back / front (cm) | Below / above head bone (cm) | Largest radius (cm) | Head bone height (m) |
|---|---|---|---|---|---|---|
| Human male | 7 | 30.2 | 13.9 / 14.7 | 12.8 / 21.3 | 15.4 | 1.753 |
| Dwarf male | 9 | 32.5 | 17.3 / 14.0 | 14.1 / 19.8 | 17.0 | 1.167 |
| Elf male | 9 | 24.2 | 11.6 / 11.4 | 10.8 / 20.4 | 12.2 | 1.902 |
| Orc male | 7 | 34.7 | 22.2 / 14.3 | 6.9 / 27.1 | 18.6 | 1.900 |
| Troll male | 25 | 62.0 | 22.5 / 27.0 | 18.4 / 36.1 | 32.9 | 2.501 |
| Human female | 9 | 30.1 | 12.9 / 12.1 | 13.3 / 23.8 | 15.3 | 1.630 |
| Dwarf female | 9 | 29.8 | 15.6 / 15.1 | 12.8 / 20.3 | 15.7 | 1.115 |
| Elf female | 9 | 27.1 | 12.8 / 12.4 | 11.8 / 18.0 | 13.7 | 1.770 |
| Orc female | 9 | 40.1 | 22.0 / 15.0 | 17.5 / 29.7 | 20.1 | 1.800 |
| Troll female | 25 | 55.2 | 29.8 / 19.1 | 19.2 / 36.6 | 28.5 | 2.301 |

## Limits

* Through version 3 the planes, rings and overlaps were measured on the two Human Fit bodies only. Version 4
  measures all 20. The other 18 bodies still get their parts from the Human parts (`refit`), now held to their
  own rings by the same gates; nothing was generated on them, and the tier offsets, the layering order and the
  rule for closing ends are the ones chosen on the Human pair.
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

## Version 3 (2026-11-13)

The user decided that every joint is at least slightly domed, to make sure of the overlap the parts need as
they turn, relying on the engine's depth test to hide whichever surface lies behind, and accepted the domes
seen in the client on Facility Security male. Version 3 adds the rule for closing every end (`ends`; **Closed
ends** above) and changes no measured number. Version 2 left an over end open: the under part stood in the
opening, and a bend that turned it out showed the over part's inside, while a flat lid tried before showed as
a shelf across the part's end. A dome as deep as the seat line's slant hung below the seat as bulk once the
thigh swung forward, hence the 2 cm most. The bake gates the rule on every outfit (`bake.hidden`, gate
`HIDDEN`), at each joint it cuts: closed but for a pad's half, domed within `domeMost` past the rim, and what
closes an under end hidden at rest and in the design bend.

## Version 4 (2026-11-14)

The user decided that the contract holds all 20 bodies (2026-11-14), after Facility Security was carried from
the Human pair to the other 18 by `refit`, baked and gated on a contract measured for them outside the kit, and
passed a trial publication. `measure` now measures every body of `registry.BODIES`; the file grew from 30 KB to
288 KB. The rows of the two Human Fit bodies are the ones version 3 held, number for number, and the rules
(`tierOffsets`, `designBend`, `ends`) are unchanged.

Each body is measured as the Human pair was: its own joint planes and body rings in its bind pose, and the
swing of the 407 clips it plays, read through its own chain of animation models (`srn_body`'s model for its
race and gender where it has one, such as `srn_an_gm`, then the stock ones). What that gives a body the Human
contract could not:

* **A bake's gates on a race body.** `ends` and `hidden` need the body's rings and bend; on a body the contract
  did not hold they were listed under `notBuilt`.
* **`refit` to a race body.** It scales a part by the rings at its joints on both bodies, and holds its ends,
  caps and domes to the other body's envelope and overlap.
* **The publication's neck gate** turns the neck by the body's own design bend.

Mean body ring (cm) at five joints, and the waist's design bend (degrees), per body:

| Body | | Neck | Shoulder | Waist | Hip | Knee | Waist bend |
|---|---|---:|---:|---:|---:|---:|---:|
| `pmh0` | Human male Fit | 6.4 | 6.6 | 13.7 | 9.4 | 6.1 | 36.9 |
| `pmh2` | Human male Large | 6.4 | 6.6 | 16.7 | 9.4 | 6.1 | 36.9 |
| `pfh0` | Human female Fit | 4.9 | 4.2 | 9.5 | 9.0 | 4.7 | 37.2 |
| `pfh2` | Human female Large | 4.9 | 4.7 | 15.8 | 10.8 | 5.3 | 37.2 |
| `pmd0` | Dwarf male Fit | 5.3 | 6.5 | 15.2 | 8.2 | 5.0 | 38 |
| `pmd2` | Dwarf male Large | 5.3 | 6.5 | 17.8 | 8.2 | 5.0 | 38 |
| `pfd0` | Dwarf female Fit | 4.2 | 4.2 | 10.7 | 8.7 | 4.2 | 39 |
| `pfd2` | Dwarf female Large | 4.2 | 4.7 | 16.4 | 10.5 | 4.7 | 39 |
| `pme0` | Elf male Fit | 6.4 | 6.6 | 13.6 | 9.4 | 6.1 | 37.3 |
| `pme2` | Elf male Large | 6.4 | 6.6 | 16.4 | 9.4 | 6.1 | 37.3 |
| `pfe0` | Elf female Fit | 4.8 | 4.1 | 9.2 | 8.8 | 4.7 | 37.3 |
| `pfe2` | Elf female Large | 4.8 | 4.5 | 15.0 | 10.5 | 5.2 | 37.3 |
| `pmo0` | Orc male Fit | 7.9 | 8.9 | 17.0 | 11.6 | 6.7 | 38.2 |
| `pmo2` | Orc male Large | 7.9 | 8.9 | 20.7 | 11.6 | 6.7 | 38.2 |
| `pfo0` | Orc female Fit | 6.1 | 5.5 | 11.8 | 11.3 | 5.8 | 39.6 |
| `pfo2` | Orc female Large | 6.0 | 6.0 | 19.6 | 13.5 | 6.5 | 39.6 |
| `pmg0` | Troll male Fit | 10.3 | 12.8 | 22.6 | 14.9 | 8.8 | 39.1 |
| `pmg2` | Troll male Large | 10.4 | 12.9 | 29.4 | 15.0 | 8.9 | 39.1 |
| `pfg0` | Troll female Fit | 7.9 | 8.2 | 15.6 | 14.7 | 7.5 | 39.5 |
| `pfg2` | Troll female Large | 7.9 | 9.0 | 26.9 | 17.6 | 8.4 | 39.5 |

A Large body bends as its Fit body does, to a tenth of a degree; its joint planes and rings are its own (a
plane lies up to 8.8 cm from the Fit body's, and the mean radius of the waist ring is 2.6 to 11.3 cm larger). The package's tests hold
every body's planes and rings to the models in `srn_body`, and its animation models to the ones the bends were
sampled from, as they did for the Human pair: a changed body model of any of the 20 now asks for a new
measurement.

## Version 5 (2026-11-26)

Re-measured on the c8 Human bodies (contract 1.6.0, [human-bodies-lock-c8](../phenomorpher/human-bodies-lock-c8.md)).
Only the neck joint of the four Human bodies changes, with the source hashes of their changed models; every other
joint, body and rule is the version 4 number. The new necks are round and fuller than the stock diamond:

| Body | Neck body ring, mean (cm) | Neck under end past the plane (cm) |
|---|---:|---:|
| `pfh0`, `pfh2` | 4.9 -> 5.6 | 5.3 -> 6.3 |
| `pmh0`, `pmh2` | 6.4 -> 6.6 | 7.1 -> 7.3 |

Outfits baked on version 4 are not refitted here; whether a neck piece needs a rebake is armorkit's call (body work
does not rebake outfits, user 2026-11-26).
