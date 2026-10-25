# Female hip and knee joins: geometry fix plan (draft, 2026-10-25)

Status: **proposed, not approved.** No asset changes until the user approves this plan and its open
decisions. Baseline: contract 1.2.0 on `main` @ `769673e7`.

Evidence lives under `output/phenomorpher/skin-pilot/evidence/` (ignored):
* `legs-back/`: client captures under white, warm and flat light;
* `joins/join-sections.png`: side sections through the left leg in bind pose.

## G1 pilot status (2026-10-25)

Approved decisions: A (shared envelope), B (knee shared envelope), C (pilot first), D (geometry before skin),
E (male knees audit only). The pilot covers `pfh0` and `pfh2`. `pfh2` was added because it shows the band
most clearly in the client. Outputs are under `output/phenomorpher/joins-pilot/` (ignored).

* **Round trip:** the NeverBlender decompile and recompile is geometry-exact. Every triangle keeps
  identical corner positions, normals and UVs (to 1e-5). The compiler only merges exact duplicate vertices.
* **Edit (v3 config):**
  * hip: shared Hermite envelope from the thigh at −8 cm to the pelvis at +1 cm about the thigh axis, with
    the seam at −1.2 cm;
  * knee: from the shin at −6 cm to the thigh at +4 cm, with the seam at −0.5 cm;
  * the hip edit is weighted to the outer side and back (full to 110° from the outer side, zero at 150°)
    because the inner, crotch side inverts.
  * No inverted faces, and all 10 models pass the compile audit.
* **Measured on `pfh0`:**
  * the rear hip groove is filled: the visible radius stays at 99–103 mm through the seam, where it
    previously dipped from 99 to 88 mm;
  * the visible knee crease drops from 51–53° to 27–32°.
* **Client, `pfh2` against shipped:**
  * the band is gone under flat light and much reduced standing from behind;
  * a short crease remains on each cheek toward the inner back, where the weighting fades out;
  * widening the weight (to 130/160°) reintroduces inversions near the cleft, so v3 is the method's limit.
* **Not yet run:** the motion sweep across all clips, and pilot tooling as phenomorpher commands (the
  pilot used scratch scripts with pinned inputs).
* **v6 (inversion-aware), the user's follow-up request:**
  * Each surface point gets a displacement weight. Points on faces that would turn more than 75° lose
    displacement, and the reduction spreads softly over the welded 1-ring.
  * The hip edit covers the front, outer side, back and inner back, with no edit in the front-inner
    groin sector (−100° to −40°, 20° blends).
  * Only 23–40 pelvis points per hip are reduced; thighs, shins and knees keep the full edit.
  * The inner back now moves 10–12 mm (v3: 2 mm) and the groin 0–5 mm. All 10 models pass the compile
    audit with no inverted faces.
* **Client v6:** close to v3 at normal viewing distance. The short line left on each cheek is the
  buttock's own lower curve meeting the thigh (about a 15–20° fold at the seam), which is part of the
  approved pelvis sculpt. Softening it further would reshape buttock anatomy, and that needs a separate
  decision.
* **v7 (buttock softening, which the user approved as an anatomy change):**
  * a second pass on the back only, with no edit on the front half and full weight from 120° outward;
  * it uses a longer envelope, from the thigh at −8 cm to the pelvis at +4 cm;
  * it trims the buttock underside by 2–3 mm on average (5 mm at most) between −2 and +2 cm, fading out
    by +3 cm;
  * all 10 models pass the compile audit.
  * In the client the change is barely visible: the fold under each cheek still reads in the
    three-quarter rear and walk views. The radius already sits near the envelope there. The crease comes
    mostly from the downward-facing normals of the buttock overhang, which a radial envelope barely
    changes.
* **v8 (fold shading, user-approved, built on v7):**
  * vertex normals of the visible pelvis and thigh skin at the back of each hip are blended toward a
    smooth cross-part normal field: Gaussian with σ 1.5 cm within 3.5 cm, strength 0.85;
  * the blend fades from the back (full beyond 125°, zero at 100°) and over a band from 3.5 cm below to
    5 cm above the seam;
  * inner sheets (the double wall and floor) are excluded by an outer-surface test, and positions are
    unchanged;
  * about 220 vertices per hip change: median 3°, with 40–55° at p95 in the fold itself;
  * all 10 models pass the compile audit.
  * Client: the buttock-to-thigh transition reads clearly softer than v6 and v7 in the three-quarter
    rear view. In the walk view a faint, lower-contrast line remains under one cheek.
* **Shin marks (user question):** the fine dark lines and the V-shaped marks on the back of the female
  shins come from the shipped shin PLT. 56% of its UV island border texels sit next to gutter pixels at
  least 30 values darker (the darkest is 18 against a skin value of 128), 4,389 of them on rear-facing
  skin; the thigh has the same issue (46%). Texture filtering and mipmaps bleed them in. The skin
  rebuild's 16 px padding removes them (skin pilot v4); the join profile still uses the shipped
  textures.
* **v8 with the skin pilot (combined client check):** the skin pilot was re-baked on the v8 geometry and
  packed with it.
  * The shin marks are gone.
  * There are two new shelf defects, both caused by the hip edit:
    * **Front:** a horizontal step across the top of the thigh, just below the brief. The v6–v8 front
      edit put the thigh top outside the pelvis, where shipped keeps it 8–24 mm inside.
    * **Rear:** a jagged flap under the brief on the lower buttock. Over ±4 mm around the seam the
      thigh and pelvis share one surface (`overlap`), so a small thigh rotation in the idle pose makes
      them cross at a shallow angle.
  * **Posed check:** the thigh is rotated rigidly about its hip pivot. The table counts uncovered cells
    where the thigh pushes through the pelvis, and uncovered cells where the two are within 1.5 mm.

    | Pose | Measure | Shipped | v8 | v9 |
    |---|---|---|---|---|
    | 20° flexion | front push-through cells | 19 | 178 | 20 |
    | 10° extension | rear near-coincident cells | 30 | 64 | 40 |
    | Standing | rear near-coincident cells | 36 | 13 | 9 |
* **v9 (shelf fix, built from shipped):**
  * Both hip passes are limited to the rear: no edit within ±100° of the front, full edit beyond 125°.
    The front and sides stay as shipped.
  * There is no shared band at the seam (`overlap` 0). The parts tuck past each other more steeply
    (`tuck` 0.8, `margin` 3 mm), so they cross cleanly instead of coinciding.
  * The v8 fold normal blend is applied on top.
  * All 10 models pass the compile audit.
  * **Trade-off:** the rear envelope dip is 10–11 mm, against 7–8 mm in v8 and 21–22 mm shipped.
    The visible crease is unchanged.
  * **Client:** the jagged rear flap is still there.
* **Root cause of the flap: the design pose.** The client never shows the bind pose.
  * In `pause1` the thighs sit 15–21° forward of the pelvis: left 21° forward and 18° out, right 15°
    forward and 4° out.
  * Flexing drops the back of the thigh away from the buttock and exposes the pelvis edge that v6–v9
    tuck inward. The colour-per-mesh renders at 20° flexion show this.
  * The jagged pelvis sub-mesh borders (p2/p3) are not the cause. They are welded and unchanged from
    shipped.
* **v11:**
  * The hip join is shaped with each thigh in its `pause1` pose (`designPose`), and the fold normals
    are blended in that pose too.
  * The pelvis gets a rounded quarter-ellipse lower edge (`highCapLength` 2 cm) instead of an inward
    tuck.
  * The edit stays rear-only, as in v9.
  * Client: the flap becomes a rounded cheek edge, close to shipped.
* **v12:** v11 plus the front, with only the groin left out (v6 gap).
  * Client front: the right thigh top is smooth. The left keeps a fainter horizontal line under the
    brief.
  * Shipped has front ledges on both thighs.
  * Rear: the rounded cheek edge, as in v11.
  * v11 and v12 were checked with the v9 skin bake, not re-baked.
* **Comparison:** `evidence/hip-shelf-ship-v8-v9-v11-v12.jpg`.
* **v12 notch (measured in the idle pose):**
  * The thigh target fell off a cliff just above the seam, back to its own profile 15–25 mm smaller.
  * The pelvis target jumped about 11 mm at the seam, because it was capped at its original size below.
  * The 5 mm s-smoothing of the scale field turned both into a V-notch 5–9 mm deep all round the seam.
  * At the front of the left thigh that is the line; at the back it is the cheek edge.
* **v13 (user-approved direction: refine v12):**
  * The thigh leaves the envelope on a cosine (`lowFall`).
  * Both parts hold 3 mm under the envelope for 10 mm past the seam before they drop (`lowHold`,
    `highHold`). The pelvis may fill that hidden hold zone; its rounded cap starts after it.
  * Design-pose dip: 0–2 mm at the rear and 1–3 mm at the left front-lateral, against 5–9 mm in v12.
* **v14:**
  * Shading-only renders of the v13 geometry still showed a ragged crossing line, where the two parts
    meet with different normals.
  * The fold normal blend now runs all round (except the groin) with full strength within 8 mm of the
    seam (`normBlend`), so both parts carry the same normal where they cross.
  * Design-pose motion sweep (thigh ±15–30° flexion, ±12° abduction from idle), measured in the posed
    thigh frame:
    * The side and rear notches track shipped.
    * The thigh pokes through the buttock only at +15–30° extra flexion: 9–30 rear cells.
  * The old bind-frame posed check is invalid for large rotations: it counts visible thigh skin as
    push-through.
  * **Client (skin re-baked on v14; `evidence/hip-v14-client.jpg`):**
    * Front: the left-thigh line is softer than in v12, but a faint lateral edge remains under the
      brief.
    * Three-quarter rear: an angular patch remains on the near lower buttock, weaker than v12.
    * Rear and walk: a soft fold line under the right cheek, with no jagged flap and no visible
      push-through in the walk frames captured.
    * Not yet clean enough to approve.
* **v15:** the shared envelope is the upper convex hull of the shipped visible profile (`hullEnvelope`).
  It fills grooves and never pushes past the shipped outline. This targets the 7–20 mm hermite bulge on
  pfh2.
* **v16:** v15, with the shading blend reaching 9 cm up the buttock to soften the shipped pfh2 facets.
* **Front of the hip in the walk (user report; offline renders of the stock `a_fa` walk,
  `evidence/walk-front-pfh2-ship-v14-v16.png`):**
  * In the walk the thigh moves from −12° to +32° relative to the pelvis; idle is about +20°.
  * On the back swing the thigh top drops away from the front of the pelvis. That exposes the thigh's
    open top rim and the pelvis's hidden hold and cap surfaces, which are lumpy.
  * Shipped also shows the thigh rim and dark gaps at the front in the walk, but without the lumpy pelvis
    surfaces.
  * One design pose cannot cover a 44° range at the front.
* **v17/v18 (user decision: the pelvis covers at the front, v16 at the back):**
  * The rear passes are limited to |phi| > 100°.
  * A front pass (`front`, phi −55° to +100° with 20° ramps) is shaped at the walk's middle pose (10°
    flexion), using the hull envelope:
    * The pelvis owns the visible surface from the skirt bottom (−50 mm) up, with a 1 mm cover and a
      12 mm rounded curl.
    * The thigh owns it below, and tucks 3 mm under the skirt just below its edge (v18 `underlap`).
    * Above the skirt bottom the thigh tapers into a dome 12 mm deep over 30 mm.
  * The normal blend is rear-only again.
  * Front walk coverage: thigh-through-pelvis cells over 12 walk frames.

    | Body | Shipped | v16 | v18 |
    |---|---|---|---|
    | pfh0 (left/right) | 982/852 | 2798/2607 | 554/487 (v17) |
    | pfh2 (left/right) | 758/664 | 2692/2510 | 536/484 |

    The remainder sits near full flexion, where the visible thigh rises into the groin crease.
  * Renders: `evidence/walk-front-pfh2-ship-v16-v18.png`, `walk-front-pfh0-v17-v18.png`.
    * The front edge of the pelvis is smooth and rounded; the lumpy pelvis patches are gone.
    * A ragged thigh top still shows near full flexion.
* **Skin:** the pilot's micro-bump is off from the v18 bake on (`bump_deg` 0). The user saw the chest
  pebbling: fine-detail p90 tilt 5.2° against 3.5° shipped on the chest, and 4.3° against 1.7° on the thighs.

## 1. What causes the band (measured)

On every female body, a dark band runs below the buttocks and a fainter line sits behind the knee. They
show under directional, warm and flat light alike. Neither changes when the skin texture changes (shipped
1.2.0 vs skin pilot v4), so they come from geometry where the parts meet. No male body shows the hip band.

**Hip (pelvis/thigh)**
* The female pelvis skin mesh `p?h0_pelvis001p1` is a closed cup with a double wall: an outer skin, a
  second layer about 5 mm inside it, and a floor closing the leg opening.
* The thigh is a closed tube whose rounded top reaches 75–108 mm up inside the cup, depending on the body.
* At the back, the pelvis hem curls inward and crosses the thigh at about z 0.98 m (`pfh0`). Just above
  the crossing, the visible pelvis surface faces straight back. Just below it, the visible thigh surface
  tilts upward where its top curls in.
* Across the crossing the two visible surfaces face 89–127° apart. Measured per body:

| Body | Thigh into pelvis | Rear bands with the hem outside the thigh | Max angle |
|---|---|---|---|
| pfh0 / pfh2 | 75 mm | 5/8, 6/8 | 89° / 92° |
| pfd0 / pfd2 | 88 / 89 mm | 6/9 | 127° / 110° |
| pfe0 / pfe2 | 85 mm | 5/9, 6/9 | 122° / 118° |
| pfo0 / pfo2 | 84 mm | 5/9, 6/9 | 118° / 114° |
| pfg0 / pfg2 | 108 mm | 7/11 | 103° / 102° |
| all male bodies | 101–216 mm | 0 (pelvis stays inside the thigh) | — |

**Knee (thigh/shin)**
* The female thigh ends in a rounded bulb that narrows before the shin emerges from under it at the back.
* The surfaces there face 36–62° apart, over 4–8 rear bands.
* The male knees show sharp angles too, but over only 1–3 bands, and no line was visible on them in the
  client. They are audited but out of scope.

In short, this is a rolled lip at the hip and a narrowing shoulder at the knee. Both are what the
connector rule "no shelves when tapering" forbids.

## 2. Scope

* **Bodies:** all 10 female bodies (`pf[hdeog][02]`).
* **Models:** pelvis, both thighs (`legl`/`legr`) and both shins (`shinl`/`shinr`) for each body, which is
  50 models. The non-Human Fit models carry the Human node names they were built from; Large models are
  separate geometry.
* **Changes:** vertex positions near the joins only, with normals and tangents transported.
* **Unchanged:**
  * UVs, faces, materials, PLTs and maps;
  * every garment mesh (brief, bra), which is read-only;
  * the rig, stature and joint frames;
  * every vertex outside the join windows (bit-exact);
  * male bodies, which are controls.

## 3. Method

The math comes from `tools/phenotypes/fair_target_shared_junction.py` ("two-part no-shelf junction"). It
uses one shared Hermite envelope per angular column, and each terminal is tucked inside its partner, so
the visible surface is one continuous slope. That tool reads GLB descendants. The published bodies are
native binaries with no ASCII masters in the repo, and the PM25 sources aren't on disk. So:

**Step 0: Baseline and round trip**
* `mdl-decompile` (Blender 5.2 + NeverBlender) the 50 models and the 10 rigs.
* Recompile them unchanged with `mdl-compile`, and require the source audit to pass with identical
  geometry. This proves the edit route adds nothing.
* Decompile the stock `pfh0_pelvis001`/`legl001`/`shinl001` the same way, as the reference stock join
  layout. The strict native decoder rejects stock BioWare binaries.

**Step 1: `join-audit` command (read-only)**
* Productionise the scratch measurement scripts (`joins.py`, `overlap.py`, `section.py`) as a
  `phenomorpher join-audit` command: managed launch, declared inputs.
* Per join it reports:
  * the visible-surface crossing (which part is outermost per height and angle);
  * the normal angle across the crossing;
  * the per-column envelope slope and its second difference (shelf detector);
  * overlap depth and garment clearance;
  * front, side and rear section images.
* It writes the acceptance numbers for step 4.

**Step 2: `join-taper` command (the edit)**
* Port the shared-junction math into a phenomorpher engine module:
  * `Cylinder` outer profiles about the bind-pose centre curve between the joint pivots;
  * `shared_targets`;
  * Gaussian-smoothed radial scale fields;
  * injectivity and no-inverted-face checks;
  * normal/tangent transport.
* A parity test against the phenotypes implementation on a fixture (same targets within float32) keeps
  the two from drifting.
* Per join, one config pins:
  * the input hashes;
  * the low and high reference heights, with the seam at the existing natural crease: gluteal fold at
    the hip, back of the knee at the knee;
  * the tuck margin and cover offset;
  * the angular weighting.
* Only the two parts at a join move. The pelvis edit is limited to its lower hem: the double wall and
  floor stay inside and must keep at least 2 mm clearance. The brief and bra must stay at least 2 mm
  outside the skin everywhere.

**Step 3: Compile**
* `mdl-compile` the edited ASCII. The audit checks header, hierarchy, bind transforms and clips, and roots
  stay at the origin.
* Normals at the seam are recomputed from the shared envelope, so both parts report the same normal at
  the visible crossing.

**Step 4: Validate before anything is published**
* `join-audit` after the edit:
  * the angle across the visible crossing is at most 15° (currently 89–127° at the hip, 36–62° at the
    knee);
  * no envelope second-difference spike at the seam (no shelf or lip);
  * outer-part coverage holds over the full rear;
  * no inverted faces;
  * clearances hold;
  * protected vertices are bit-exact.
* `sweep --motion` worst case across every clip that bends the hip and knee (walk, run, kicks, sit, kneel,
  crouch, death, knockdown): no gap and no new penetration relative to 1.2.0.
* Before/after sections at front, side and rear for every body.
* Client: reuse the fixture with self-referencing profiles. Earlier pilot sessions silently loaded the
  shipped HAKs because their `nwn.ini` aliases pointed at `profile-v120`; new profiles get all aliases,
  including `HD0`, rewritten, and the launcher must verify this.
  * All 10 female bodies plus male controls, at front, side and back.
  * White, warm and flat light.
  * Idle, walk, run and both kicks, with close-ups of hips and knees.
  * Shipped vs fixed side by side.

**Step 5: Publish**
* Contract 1.3.0, with new rows and lineage for the 50 models.
* Then `verify-runtime`, HAK rebuild, PR and the client gate. 1.2.0 stays the rollback anchor.

## 4. Gates

1. **G1 – Pilot:** `pfh0` hip and knee, both sides. Sections, the `join-audit` table, the motion sweep and
   one client session for user review. Nothing broader runs until it is approved.
2. **G2 – All 10 female bodies:** sections and audit tables.
3. **G3 – Client:** full fixture pass.
4. **G4 – Publication:** PR.

Numerical success does not approve anatomy (AGENTS.md). Each gate needs visual review in matched front,
side and rear views and in motion.

## 5. Open decisions

| | Question | Recommendation |
|---|---|---|
| A | Hip seam design: (a) shared envelope, both parts reshaped, seam at the gluteal fold; (b) male-style, thigh covers and the pelvis hem tucks inside it; (c) pelvis covers and only the thigh tucks | (a): one continuous visible slope, smallest change to either part's approved silhouette |
| B | Knee: shared envelope with the seam at the back-of-knee crease | Yes |
| C | Order: pilot `pfh0` then roll out, or all bodies at once | Pilot first |
| D | Coordination with the skin rebuild (`docs/phenomorpher/skin-rebuild/plan.md`) | Geometry first, then bake the skin shading on the final geometry; publish both as 1.3.0 |
| E | Male knees: sharp but narrow crossings, not visible in the client | Audit only, no edit |

## 6. Risks

* A taper changes approved silhouettes near the joins. The windows stay bounded, and G1 compares sections
  and the client side by side.
* At hip flexion (sit, kneel, kicks) the seam slides, and a tuck that holds standing can open or poke
  through. The motion sweep decides, and the margins are tuned per body.
* The pelvis double wall or floor could surface after the hem moves. The clearance check covers this; if
  it fails, trimming the hidden floor becomes its own approved sub-step.
* The NeverBlender round trip must stay geometry-exact, and step 0 proves this before any edit.
