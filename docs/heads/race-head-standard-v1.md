# Race head standard v1 (2026-11-27)

How headkit sizes and places a new library head for each race and sex. It comes from the 1.7.0 review of all published
race heads ([race-necks-c8](../phenomorpher/race-necks-c8.md)), approved by the user ("Approve, elf drop 2 cm"). After
the user confirmed the heads in game, they asked for headkit to "know how to properly scale and position heads for all
races" ("Yes, update headkit"). Data: [`race-head-standard-v1.json`](race-head-standard-v1.json).

## Size

The fit stage still matches a new head to its race's compact reference (profile scale, nose placement) or to reviewed
landmarks. That route gave the published library, and the review found these errors in it:

| Body | Export scale | Pivot | Why |
|---|---|---|---|
| Elf male `pme0`, Elf female `pfe0` | x1.15 | `head_g` | faces 0.87 to 0.90 of Human on taller bodies, about 0.8 of the stock Elf head |
| Troll male `pmg0` | x1.12 (after the Troll allowance x1.5) | the head's own chin | small against the shoulders; the jaw must not sink into the chest |
| Human male `pmh0` | x1.06 | `head_g` | c8 review: faces the size of the female heads at 8.4 heads to the body |
| Human female, Dwarf, Orc, Troll female | x1.0 | `head_g` | consistent; single outliers were rescaled per head |

A manifest opts in with `"raceSizing": "race-head-standard-v1"` and the `raceHeadStandard` input. Headbatch sets both
for every new manifest. Export applies the factor once, after the Troll build allowance. It writes `raceSizing` to the
export result: the standard's hash, the factor, the pivot, how the factor was chosen, and the measured face.

* **Fit frame.** The factor holds for profile and nose fits against the race's compact reference: the `fitFrame` stem,
  which is the same head as `compactFitHead` in `tools/headbatch/races.json`. For Trolls, the Troll allowance decides
  which frames it accepts. Any other reference is refused until its scale is checked against the library and the
  manifest gives `raceSizing.factor` (0.7 to 1.4) with a `reason`. Landmark fits keep their reviewed scale (factor 1).
* **Chin pivot.** The chin is the lowest front-midline point (within 6 mm of the midline, the forward 30% of it), on any
  PLT channel. It matches the review's chin to 0.2 mm on the published Troll male heads.

## Face check

After scaling, export measures the iris centres on the PLT `tattoo1` channel and compares their spacing with the race's
published library (its median, minimum and maximum are in the JSON):

* within 12% of the median: recorded;
* 12 to 25%: recorded as "review": compare the head side by side with its race's library before approving the export;
* beyond 25%: refused. The refusal gives the scale that would reach the median. Set `raceSizing.factor` with a reason,
  or `raceSizing.outsideBand` with the reviewed reason when the design really has wide-set or close-set eyes.

Approved library heads span up to 20% around their median, so the review band, not a tighter refusal, catches the 15%
cases (the 1.7.0 Orc female `013` to `016` and Dwarf male `019` and `026`). Troll designs paint `tattoo1`, so Troll rows
have no band: judge their face size by eye against the library. A head with no irises found is recorded the same way.

## Position

A head is placed by `head_g` alone; the rig carries each body's head height. The 1.7.0 rigs lower `head_g` 3.5 cm on the
Human females, 2 cm on the Elf females and 3.3 cm on the Orc females (`headDropMeters`, for reference). A head never
adds its own offset for that. The front of the neck shows about 0.87% of stature between chin and chest; that is a body
rule (the rig drop), not a head setting.

Neck cuts (`mesh.neck.cut`) draw the stub onto the body's neck part. Make the workspace `bodyNecks` references from the
1.7.0 `srn_body` rigs and necks (`python -m headkit.body_neck`). References from older bodies have the old diamond neck
and, for Elf and Orc females, the old `head_g`.
