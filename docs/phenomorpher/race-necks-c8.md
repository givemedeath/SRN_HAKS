# c8 necks on the other races and the race head review (2026-11-27)

The user asked to "get the neck onto the rest of the races" after the c8 Human lock
([human-bodies-lock-c8.md](human-bodies-lock-c8.md)), and for "all of the published race heads" to be "reviewed
carefully for scaling and position adjustment needs". The proposal below was approved on 2026-11-27 with one change
("Approve, elf drop 2 cm"). It is published in contract 1.7.0; every changed resource, its 1.6.0 hash, each body's
build numbers and each head's scale are in [race-necks/release-1.7.0.json](race-necks/release-1.7.0.json).

The Human bodies are unchanged (c8). Outfits and armour are not refitted: armorkit owns them.

## Necks

Every Dwarf, Elf, Orc and Troll body (female and male, Fit and Large) gets the c8 anatomical neck in place of the
stock 16-face diamond. Each body's neck is built by the Human c8 builders in a frame normalised to that body's own
old neck: width, depth and `neck_g`-to-`head_g` height each divided by the Human c7 neck of the same sex. The
results map back to the body. Female chests get the Human collar fit in the same frame (Fit bodies the `pfh0`
settings, Large bodies the `pfh2` ones). `neck_g` is unchanged, so stock and armour neck parts still ride it; the Dwarf
`neck_g` is tilted at rest (7 degrees female, 29 degrees male) and the new parts are written in its frame.

| Body | Neck width / depth / height against Human | Head drop | Collar lift (max) |
|---|---|---|---|
| Dwarf female `pfd0` / `pfd2` | 0.86 / 0.88 / 0.66 | none | 2.3 / 0.4 cm |
| Elf female `pfe0` / `pfe2` | 0.98 / 0.98 / 1.06 | 2 cm | 3.5 / 0.8 cm |
| Orc female `pfo0` / `pfo2` | 1.24 / 1.24 / 1.10 | 3.3 cm | 3.7 / 0.7 cm |
| Troll female `pfg0` / `pfg2` | 1.61 / 1.60 / 1.40 | none | 4.8 / 1.1 cm |
| Dwarf, Elf, Orc, Troll male | as in the receipt | none | none (chest unchanged) |

**Head drops.** The Human female drop (3.5 cm) was not copied across. Each race's drop was chosen so the neck shows
about as much as the Human c8 female's does (front of the neck about 0.9% of stature between chin and chest). With
the collar rising, the Dwarf and Troll females already show less, so they keep their head height. Scaling the Human
drop by neck height would have lowered the Troll female head 4.9 cm and hidden her neck entirely. The Orc female
needed 3.3 cm. The Elf female measured at the target without a drop, but her neck still read long in the renders and
the user chose 2 cm. The rest statures of `pfe0`/`pfe2` and `pfo0`/`pfo2` drop by the same amounts. Males keep their
head height, as the Human males do.

**Troll necks fitted inside four heads.** In back and side views the rounder neck showed through the skin of four
Troll heads that carry their own short neck: female `018`, `019` and `020` at the sides of the jaw, male `009` at the
nape behind the braid knot. The Troll necks are pulled in where those heads' skin walls are narrower (up to 2.6 cm on
the female, 0.8 cm on the male), tapered smoothly over the ring grid and left alone at the collar join (a version
that pulled at the join opened a few pixels in `whirlwind`). Hair that the neck passes through is not a wall: only the
heads' skin channel counts. The neck also closes the slit that showed at the nape of Troll male `013` before.

## Heads

All 102 race library heads were measured on their bodies and rendered next to a Human c8 reference framed in
proportion to stature (front and side, back, three-quarter back and from below behind). The measures: eye spacing
(iris centres from the PLT `tattoo1` channel), eye to chin (lowest skin point at the front midline, so beards do not
count) and cheek width. Faces are compared within each race and against the Human heads and the stock head of the
race.

| Race | Finding | Change |
|---|---|---|
| Elf, both sexes | Faces 0.87 to 0.90 of Human on taller bodies, about 0.8 of the stock Elf head | all 18 heads x1.15 |
| Orc female | two batches: `013` to `016` about 20% smaller than `017` to `021` | `013`-`016` x1.2 |
| Orc male | `015` and `018` much smaller than the rest | `015` x1.2, `018` x1.3 |
| Dwarf female | `018` and `021` about 30% larger than the set, `020` about 10% | x0.80, x0.83, x0.92 |
| Dwarf male | `019`, `020`, `022` large, `026` small | x0.87, x0.92, x0.92, x1.10 |
| Troll male | small against the shoulders | all 25 heads x1.12, chin kept at its height |
| Troll female, Human | consistent | none |

Heads scale uniformly about `head_g`, except the Troll males: they scale about the point on `head_g`'s vertical at the
head's own chin height, so the jaw does not sink into the chest. 56 heads change (receipt: `raceHeads`). Their PLTs,
UVs and materials are unchanged. `publish_library.py verify` needs this receipt as a `--revision` beside
`neck-c8/release-1.6.0.json`. New heads get the same corrections at headkit export:
[race-head-standard-v1](../heads/race-head-standard-v1.md).

## Review

* **Offline sheets:** every head before and after (`prop-*`), all heads of each race on the new necks (`heads-*`),
  back views of every head (`back-*`) and close-ups of every head the show-through scan flagged. The scan compared
  the new neck with the old one per head and view. Most of what it flagged is neck seen through gaps in hair, which is
  normal; the four Troll heads above were the real cases.
* **Motion:** no new holes in `pause1`, `whirlwind`, `plslashr`, `2wslasho`, `kdfntdmg`, `worship`, `castup`, `sit`,
  `victoryfr` or `getlowlp` on any of the 16 race bodies (one head each; four heads on the Troll bodies after the fit).
  The few pixels on the female bodies in `victoryfr` and `worship` were there with the old necks.
* **Client:** see [Client check](#client-check).
* Evidence images: [`race-necks/evidence/`](race-necks/evidence/) (head scales before and after per race, the Troll
  fit close-ups, motion sheets and the client sheets).
* **Gates:** `verify-assets` (937 resources) and `verify-runtime` (structural) pass on contract 1.7.0, run as direct
  calls of the PhenoMorpher engine functions (not managed `run.py` launches). Every compiled body matches its build
  to the micrometre, the drops are exact and every head matches its planned scale. `publish_library.py verify` passes
  on the built `srn_head.hak` with both revision records.
* **Armorkit:** `seam-contract.json` (version 6) and `head-envelopes.json` are re-measured on the new packs.

## Client check

Repository-built HAKs (`srn_body`, `srn_head`, `srn_body_tex`, `srn_armor`, `srn_2da`) in an isolated fixture, frame
limiter on, keyholing off. One library head per race body, bare, standing, from the front three-quarter, the side and
the back three-quarter: Elf `pfe0` 021 and `pme0` 025, Orc `pfo0` 014 and `pmo0` 018, Dwarf `pfd0` 018 and `pmd0`
019, Troll `pfg0` 020 and `pmg0` 009 (two of the fitted heads), and the Large Troll and Orc females (`pfg2` 019,
`pfo2` 017). The necks are continuous with the chests, the scaled heads sit on them at the measured sizes and no neck
shows through a head. The pale patch at the nape of Troll male 009 and the dark patch on the back of Troll female
020 are those heads' own textures. Sheets: [client-1.jpg](race-necks/evidence/client-1.jpg),
[client-2.jpg](race-necks/evidence/client-2.jpg).

The user confirmed the heads after these checks (2026-11-27, "Yes, update headkit"); headkit now applies the same
corrections to new heads ([race-head-standard-v1](../heads/race-head-standard-v1.md)).

## Known limits

* Long hair on some heads (for example Dwarf female `018`) now meets the raised collar higher up; long hair already
  sat in the shoulders before. Elf heads with hair hanging behind the neck have a little of that hair inside the
  fuller neck.
* Troll male `025` has a hole in its hair at the back; the neck showed through it before too.
* Small skin nubs at the base of some Elf and Orc heads poke out of the neck surface by a millimetre or two; both are
  skin-coloured.
* Stock heads (skinmeshes) were not checked offline.

## Where the files are

Ignored by git, under `output/phenomorpher/race-necks/`: the pre-1.7.0 packs the builds start from (`base`, from
`git archive`), the race decompiles (`src-ascii`, `heads-src`), the builds (`bodies`, `heads-new` with
`scale-plan.json`), the review sheets, the client fixture (`client`), the armorkit measurement (`armorkit-v6`) and the
tools snapshot (`tools`, with `SHA256SUMS`). Check them against the receipt before reuse.
