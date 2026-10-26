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
* **v18 in the client (walk; front, side, rear; `evidence/client-v18-walk-front-rear-side.jpg`): fails.**
  * The front skirt reads as shorts. Its bottom hangs 3–4 cm below the brief and ends in a hard
    horizontal edge across the upper thigh: a bright step on the stance leg and a dark line on the
    swinging leg. This is a shelf. It is strong on pfh2 and fainter on pfh0.
  * On pfh2, skin shows through the brief cup.
  * Measured causes:
    * The curl drops steeply, and the 3 mm underlap leaves a step.
    * At extension the thigh front pulls back 15–35 mm under the pelvis rim, so the rim shows.
    * The hull envelope pushes pelvis skin out through the brief: about 55 new points per body (v16: 9–14).
* **v19 (user decision: skirt bottom at the brief leg line, a long taper with no edge, pelvis inside the brief):**
  * Brief leg line in the front-pass cylinder: −25 to 0 mm at the front-medial and +12 to +80 mm at the
    front-lateral (above the thigh top at +15 mm).
  * The pelvis spans −60 mm to the top. The shipped pelvis overhangs the thigh by more than 4 mm across
    the whole front.
  * The front pass (`briefSkirt`) changes:
    * **Skirt bottom:** set per column at the brief line, capped 10 mm under the thigh top, then
      smoothed around the leg.
    * **Pelvis below it:** crosses under the thigh within 4 mm, then sinks 20 mm inside the thigh's
      target over 30 mm. No curl, no underlap.
    * **Thigh:** carries the visible surface below the skirt bottom and is domed under the skirt above it.
    * **Brief clamp:** keeps both parts under the brief's profile.
    * **Sector:** −55° to +130°.
  * A finishing step (`briefpush.py`) pushes any vertex that the joins moved out through the brief back
    under it, with a two-ring falloff. The shipped belly fold over the waistband stays.
  * Walk results (8 frames):

    | | pfh2 v18 | pfh2 v19 | pfh0 v18 | pfh0 v19 |
    |---|---|---|---|---|
    | Pelvis rim outside the thigh (`walkpoke` rim cells) | 60/63, up to 35 mm | 0/0 | 46/47 | 0/0 |
    | Thigh top outside the pelvis | 36/46 | 76/53 | 16/24 | 57/49 |
    | New pelvis points outside the brief, front (`briefcheck`) | 54 | 3 | 56 | 5 |

    Thigh-top exposure in v19 is about v16's level, at the flexion extremes. Raising the skirt bottom
    without the 10 mm room let the swung thigh top show; more room (25–35 mm) or a deeper dome did not
    reduce it.
  * The front-lateral thigh now carries the shape the pelvis showed there: up to 23 mm radial growth at
    20–40° on pfh2.
  * Renders: `evidence/walk3-pfh2-v18-v19p.png`. The ledge under the brief is gone from the front, and
    the rear is unchanged.
  * Client (combo-v19; walk; `evidence/client-v18-v19-walk-front-side-rear.jpg`), awaiting user review:
    * **Front:** the shorts cuff and its hard edge are gone on both bodies. A faint soft line remains on
      the outer-front upper thigh just below the brief, where the pelvis now crosses under the thigh.
    * **Side:** the boxy lump below the brief is much smaller. A faint horizontal line about 1–2 cm
      below the brief remains on some frames.
    * **Rear:** unchanged from v16/v18, with the same soft fold line at the outer buttock.
    * Some brown marbling shows in the pfh2 brief at the rear. Unverified: it may be the brief's own
      PLT shading.
  * Tooling: `buildcombo.sh` (compile, audit, skin bake, stage, pack, install; reproduces combo-v18
    byte for byte), `briefcheck.py`, `briefpush.py`, `walkrender3.py`, and the walkpoke `rim`/`top`
    exposure counts.
* **v19 user review:** soften the remaining lines, above all the hard edges around the thigh top, and fix an
  odd texture or normals patch on the side of the pelvis. The user marked a lighter patch with a jagged,
  triangle-shaped outline on pfh2's left outer buttock, below the brief leg line.
  * **Cause of the patch (shipped, not from the joins):**
    * The pelvis skin is three meshes: p1, plus strips p2 and p3 around each leg opening. They share
      about 100 border vertices per side.
    * Shipped pfh2 normals disagree across that border: p50 about 10°, p95 up to 86°, max 137°.
      pfh0's p50 is about 2°.
    * The skin bake's `smoothed_normals` worked per mesh, so the normal map repeated the seam.
  * **Thigh-top line:** in the walk the two rigid parts keep crossing (the thigh pokes 4–13 mm through
    the pelvis at v16 level). Each crossing reads as a sawtooth line with a shading jump.
* **v21:**
  * `seamnormals.py` welds the part's skin meshes and blends the shared border and two rings to one
    smoothed geometric normal, orienting each mesh's winding as a whole. Mismatch is now at most 2°.
  * The bake smooths normals over all skin meshes of a part as one welded surface (garments apart).
    This also changes other multi-mesh parts' normal maps along their internal borders.
  * The normal blend runs all round except the groin (`groinGap` [−130, −50, 20]).
  * The hip passes add a 15 mm thigh-top tuck after a 4 mm hold (`tuckDepth`). Relaxation limits it to
    about 40 vertices.
  * Walk results: pelvis rim 0; thigh top 54–80 cells (v16 level). Brief: 3–5 new front pelvis points.
  * **Client (`evidence/client-v19-v21-walk-front-side-rear.jpg`), awaiting user review:**
    * The jagged patch on the hip side and rear is gone on both bodies.
    * Faint lines remain at the outer-front thigh below the brief and at the lower buttock fold.
  * **User decisions (2026-10-25, after v21):**
    * Accept the faint thigh-top line for now; no added geometry.
    * Speed up the bake before the next build.
    * Before pilot approval, run the full motion check: idle, walk, run, both kicks, sit and kneel, in
      front, side and rear views on both bodies.
    * After the pilot is complete, stop. No rollout to the other female bodies, no tool
      productionizing and no publication until the work being developed elsewhere is ready.
  * **Faster bake (`skin/bakepar.py`, used by `buildcombo.sh`):**
    * Each part is baked in its own worker, 3 at a time.
    * A part is reused from a content-addressed cache (`output/phenomorpher/skin-bake-cache`) when its
      model, PLT, source maps, bake code and PARAMS are unchanged.
    * Verified against combo-v21: a cold run took 411 s (against 1,190 s serial), a warm run 2 s. All 42
      outputs are byte-identical.
  * **v21 motion check (client; `evidence/client-v21-motion-check.jpg`), awaiting user decision:**
    * Hip ranges of the stock clips (thigh relative to pelvis):

      | Clip | Flexion |
      |---|---|
      | walk | −12° to +32° |
      | run | −31° to +48° |
      | kicks | up to 85°, with 59° abduction |
      | chair sit | 80° |
      | cross-legged sit | up to 123° |
      | crouch (`getlowlp`) | 122° to 149° |
      | kneel (`meditate`) | about 40° |

    * **Idle, walk and run:** acceptable. A faint crossing line at the Large hip side and at the Fit lower
      buttock in the run.
    * **Kicks:** a corner-like step where the thigh top meets the pelvis, at the front and side. The
      offline shipped-vs-v21 comparison (`evidence/pose-nwkickl-pfh2-ship-v21.png`) shows a regression
      at the front: the kicking thigh's top rim shows at the groin beside the brief, where shipped keeps
      it covered. This is a cost of the v19 brief-line skirt, where the thigh carries the front surface.
    * **Chair sit, crouch and kneel:** the thigh tops bulge below the buttocks with seam lines at the rear
      and side. Shipped also fails here, with a boxy pelvis rim and a dark gap line at the buttock fold
      (`evidence/pose-sit-pfh2-ship-v21.png`, `pose-getlowlp-pfh2-ship-v21.png`). v21 looks different,
      not clearly worse.
    * **Cross-legged sit:** Fit clean. On Large, a light thigh-top patch beside the brief at about 120°.
  * **Pose-suite evaluation (user request: fix all issues, evaluate first):**
    * **Tool:** `posesuite.py` renders 9 clips × 6 frames × 4 views per body with back-face culling. A
      visible back face is painted red; in the client that pixel is a hole into a part. Exposed open rims
      of the thigh and of the pelvis leg opening are counted too.
    * **Shipped:** 0 holes and 0 thigh rim in every clip. The pelvis rim shows only as a thin sliver at
      the brief's edges.
    * **v21:** 1.0k–5.9k hole pixels per clip, with thigh rims showing. Two causes:
      * **Seam cracks:** the v19 brief push moved each seam copy separately, splitting 85–103 pelvis
        seam groups by up to 5.7 mm and the thigh by up to 4.4 mm. Fixed by working on welded points.
        `cracks.py` is now a gate in every build.
      * **Cup inner layer:** below the hips the shipped pelvis is a closed cup. An inner layer of about
        950 vertices sits 3–10 mm inside the outer skin and faces into the cup, plus a floor and a lip.
        It is never visible standing or walking; it fills see-through gaps in deep poses (shipped with
        it removed: about 4.6k hole pixels, mostly crouch and sits). The joins moved the outer skin
        without it, pushing it out through the skin (84% / 70% of hole pixels on pfh2 / pfh0).
    * **Not a shadow mesh:** all pelvis meshes are rendered and shadow-casting. The layer is shipped
      geometry, so keeping it adds no cost against shipped.
  * **Fix (v34–v36), no new vertices:**
    * `innerclear.py`: each inner-layer vertex is rebuilt from its shipped outer partner (the nearest
      opposite-facing vertex) at its shipped wall thickness, at least 3 mm. Seam copies move together,
      and lip points shared with the leg-opening strips stay.
    * `holefix.py`: iterates the pose suite and pulls the hidden points behind any remaining hole
      2 mm toward the leg axis. Folds in skin not covered by the brief get one smoothing step.
    * Hole pixels over all 216 renders: pfh2 18.3k (v22) → 1.9k (v34) → 29 (v35); pfh0 26.7k → 1.8k → about
      0.5–0.8k. The remainder is millimetre specks deep in the crotch gap below the brief.
    * Thigh rim 0; pelvis rim at the shipped level; walk exposure unchanged from v22.
  * **v39** (chain: jointfix → briefpush → innerclear → holefix → briefpush → innerclear → briefpush →
    seamnormals → normblend; `chain.sh`):
    * `innerclear` only pairs back-to-back walls. Facing skins across the crotch had been taken for the
      inner layer and pushed through the brief.
    * Pose suite (all 216 renders per body):

      | Body | Holes | Thigh rim | Pelvis rim |
      |---|---|---|---|
      | pfh2 | 546 (v22 18.3k; shipped 0) | 0 | 114k (shipped 129k) |
      | pfh0 | 925 (v22 26.7k) | 0 | 337k (shipped 351k) |

    * Cracks 0. Brief: 5–6 new front and 3–4 new rear pelvis points (v22: 2–5). Walk exposure equals v22.
    * Built with the cached bake: 159 s for the whole build.
    * Offline poses (`evidence/pose-{walk,sit,getlowlp,nwkickl}-pfh2-ship-v21-v39.png`): the holes are
      gone. The deep-pose shapes are unchanged: a corner step where the kicking thigh meets the pelvis
      at the groin and the side, and rounded thigh tops under the buttocks in the chair sit. A
      millimetre skin speck shows through the brief at the rear centre.
    * No vertex rings were needed to close the holes.
    * Client capture was blocked: another session held the computer.
  * **Deep-pose reshape attempt (v40, pfh2 only, `deeptuck.py`; report-back point for extra rings):**
    * Method: thigh points that stay inside the pelvis through idle and walk, but poke out of it in
      run, kicks, sits, crouch or kneel, are pulled toward the thigh axis by their worst poke (capped at
      25 mm, relaxed against triangle flips).
    * Only 30 (left) and 14 (right) welded thigh points qualify; their deep-pose poke reaches 66–68 mm.
    * The tuck moved 29 + 12 points, up to 25 mm. Poking points fell from 15 to 5 (left) and 8 to 3 (right).
    * In the kick and chair-sit renders (`evidence/pose-{nwkickl,sit}-pfh2-v39-v40.png`) the corner and
      the bulges are unchanged.
    * Mesh resolution at the joint, edges within 12 cm of the hip pivot:

      | Part | Median | p90 |
      |---|---|---|
      | Thigh (pfh2 / pfh0) | 17 / 16 mm | 30 mm |
      | Pelvis main skin (pfh2 / pfh0) | 19 / 16 mm | 30 / 27 mm |

      The visible corner and bulge contours are single triangles.
    * Conclusion: reshaping the deep-pose contours needs finer geometry at the joint. That means
      subdividing the thigh's top band and the pelvis's lower band once or twice (about 8 mm edges, UVs
      interpolated). Awaiting the user's decision.
  * **v39 client motion check** (`evidence/client-v39-motion-check.jpg`: idle, walk, run, both kicks,
    chair sit, cross-legged sit, crouch, kneel; both bodies; front, side, rear):
    * No see-through holes or open edges in any capture.
    * Idle, walk and run are clean apart from faint fold lines at the lower buttock.
    * Remaining shape defects:
      * a rounded thigh-top bulge under the buttock in chair sit, crouch and the left kick (both bodies);
      * a crease or step at the buttock/thigh in kneel and in the run on Fit;
      * a dark crease at the brief's edge on Large in the left kick.
    * These are the subdivision question above.
* **Sitting work, in progress (user: "hip joint still needs improvement for sitting"; paused for a reboot
  2026-10-25):**
  * `subdiv.py` (conforming midpoint subdivision; seam twins split together; UV, normal and tangent
    interpolated) splits the thigh faces within 12 cm of the hip pivot, once.
  * Result: pfh2 1,344 → 2,081 vertices and 1,750 → 3,050/3,044 faces per thigh; pfh0 → 2,187 vertices,
    3,236/3,234 faces. The surface is closed, the area unchanged and the shape identical.
  * Base: `joins-pilot/sub-ascii-{pfh0,pfh2}` (shipped files with only the thighs subdivided).
  * **v42** (`chain.sh` with `BASE=sub-ascii SIT_TUCK=1`; `sittuck.py`):
    * Method: thigh points hidden through idle and walk but exposed in sit, sitcross, crouch or kneel are
      limited to a cone above the walk-visible thigh surface (24 sectors, slope 0.6, 3 mm margin).
    * Coverage: 85–101 points per thigh qualify (versus 14–30 before subdividing). They need up to
      68–82 mm, but the flip guard limits the move to 17–23 mm.
    * Gates against v39:

      | Gate | Result |
      |---|---|
      | Cracks | 0 |
      | New brief violators | 0 |
      | Thigh rim | 0 |
      | Walk `rim` cells | 0–3 |
      | Pose-suite holes, pfh2 | 546 → 1,360 px (kicks 159 → 725, kneel 65 → 181) |
      | Pose-suite holes, pfh0 | 941 → 1,370 px |

    * Visual (`evidence/pose-{pfh2,pfh0}-sits-v39-v42.png`, `evidence/pose-pfh2-sit-zoom-v39-v42.png`):
      the chair-sit side and rear views are essentially unchanged. The visible defects are where the
      thigh crosses the buttock underside (a stepped silhouette in side view, lumpy shelves under the
      buttock in rear view), and that thigh surface is walk-visible. Tucking only walk-hidden points
      cannot reach it.
    * Verdict: v42 is not adopted (no visible gain, more holes). The installed client hak stays combo-v39.
  * **GPU pose suite:**
    * `posesuite.run_jobs` sends every render to `gpurender.py`, which runs in Blender 5.2 in background
      mode on the GPU (OpenGL, RTX 3060). Each part uploads once; the thighs pose by a matrix per render.
      `holefix.py` uses the same path. `GPU=0` falls back to the CPU rasterizer.
    * Parity on v39 pfh2 (9 clips × 6 frames × 4 views): identical hole counts per render and identical
      hole points (546, parts equal, ≤0.1 mm rounding). Pelvis rim differs by ≤7 px per clip, and 0.004%
      of pixels differ, all on triangle edges.
    * Time: about 8 s per body, versus about 10 min on 3 CPU workers.
  * **Hip fillet flaps** (user proposal, 2026-10-25): a closed flap on the back of each thigh top and under each
    buttock, buried inside the other part when standing, meeting in the middle when sitting. Kneeling (`kneel`,
    `meditate`) and praying (`worship`) must show no flap at the front.
    * Tool: `fillet.py` (scratchpad). Pelvis-frame voxel grid (3 mm). Per pose, the solid is pelvis walls (waist
      capped) plus both posed thighs. The crease is the closing (ball 90 mm) of that solid, minus the solid, behind the
      hip and clear of the brief.
    * Rule: a flap point must stay at least 5 mm inside in pause1, pause2, walk and run. In every other clip it must be
      hidden or lie in a back crease.
    * Cross-sections (`evidence/xsect-pfh2-l-v39.png`): in the chair sit, the thigh's slanted top becomes a
      near-vertical face about 1 cm behind the pivot. The pelvis underside is exposed between that face and the
      buttock.
    * Feasibility, pfh2 left. The chair-sit crease is 23.8k voxels (0.64 L); the share each clip rules out:

      | Clip | Thigh flap | Pelvis flap |
      |---|---|---|
      | worship (pray) | 91% | 31% |
      | getlowlp (crouch) | 94% | 39% |
      | sitcross | 98% | 39% |
      | kneel | 51% | 13% |
      | pause1 | 13% | 59% |
      | walk | 20% | 64% |
      | run | 37% | 69% |

    * Result: a thigh flap that fills the chair-sit crease shows in front of the hip when praying, crouching and
      sitting cross-legged. A pelvis flap that fills it shows behind the thigh when standing and walking.
    * Relaxed rule (any flap allowed behind the hip plane in the non-walking clips):
      * thigh flap: still 65% ruled out by praying, at the front;
      * pelvis flap: 23% of the crease remains buildable, near the pivot.
    * User chose the partial pelvis flap. **f1** (`ONLY=pelvis DEEPRULE=back RHO=90 fillet.py`):
      * Each flap is a closed blob over the feasible part of the sit, sitdown, meditate, kneel and worship creases.
        It is a surface net on a 9 mm lattice with Taubin smoothing, written as pelvis nodes p4 and p5.
      * UVs and tangents come from the facing buttock skin, in one UV island.
      * Triangles: pfh2 1,288 + 1,380; pfh0 828 + 856.
    * GPU pose suite (`posesuite.py` now counts visible flap pixels per view; `FLAPCOL` tints them):

      | Clip | Visible flap |
      |---|---|
      | pause1, pause2, walk, run | 0 px in every view, both bodies |
      | kneel, meditate | 0 px from the front |
      | worship | 20 / 318 px from the front (pfh2 / pfh0) |
      | getlowlp (crouch) | 16–18k px from the front |
      | sitcross | 1–3k px from the front |

      Holes are unchanged from v39.
    * Visual (`evidence/flap-review-{pfh2,pfh0}[-tinted].png`: front, side and rear; standing, sit, kneel, pray;
      v39 against f1): standing is identical. In sit, kneel and pray the flap shows under each buttock as a lumpy
      separate lobe. It does not read as a filled crease: it is a secondary shape, which the no-shelves rule forbids.
      Its edge is set by where the flap would show in walking, not by the crease, so smoothing would remove the lumps
      but not the lobe.
    * Verdict: f1 is not adopted, and nothing is built or installed (combo-v39 stays).
  * **Rounded domes and bulbs** (user: "work the flaps for the thigh and pelvis more, we can accept some minor
    protrusion in positions that aren't common … a rounded taper towards the axis of the thigh"). Tool: `domes.py`.
    * Both flaps are closed surfaces of revolution about the thigh's rest axis, with per-sector radii:
      * thigh dome (thigh node p1): from just under the thigh skin below its slanted top, the radius rounds in to the
        axis over H = 70 mm;
      * pelvis bulb (pelvis nodes p4 and p5): from just inside the buttock underside at the leg opening, the radius
        rounds in to the axis over D = 45 mm, deepest at the back and fading toward the front.
    * Every surface point is pulled toward the axis until it is at least 4 mm inside in the HIDE clips, then blurred
      and re-clamped.
    * Mesh: about 1,150 triangles per thigh dome and about 400 per bulb.
    * Variants:

      | Version | HIDE clips | Rounding |
      |---|---|---|
      | d1 | idle, walk, run | quarter ellipse |
      | d2 | idle, walk | quarter ellipse, wider bulb window |
      | d3 | idle, walk | superellipse P = 3, blunter |

    * d3 pose suite, pfh2 / pfh0. Holes are unchanged from v39.

      | Clip | Visible flap |
      |---|---|
      | idle | 0 px |
      | walk | 14 / 0 px |
      | run | 4.9k / 1.6k px over 6 frames, back and side |
      | kneel, pray | 0 px from the front |
      | crouch | about 10k px from the front |
      | sitcross | 4 / 843 px from the front |
      | kicks | about 300 px from the front |

    * Visual (`evidence/dome3-review-{pfh2,pfh0}[-tinted].png`: idle, run, sit, kneel, pray; front, side, rear):
      * The flaps fill under the buttocks in sit, kneel and pray, and the run's jagged under-buttock ledge becomes
        rounded.
      * The bulb still ends in a downward point. The walk clamp cuts its outline into a V.
      * The sit side view keeps the jagged thigh/hip intersection line, which is outside the flaps' reach.
    * User: the bulbs' outer edges do not line up with the thighs' outer edges (pray, side view).
    * **d4**: the bulb is full depth on the outer side as well as the back (outer depth 65 mm). Below the leg opening it
      never leaves the standing thigh's own outline (5 mm inside). The outer thigh sits near the flexion axis, so that
      line stays in place in sit, kneel and pray.
    * d4 pose suite: as d3 (idle 0 px, walk 14 / 0 px, kneel and pray 0 px from the front). Pray side views show
      5–6k px of flap.
    * Visual (`evidence/dome4-side-zoom-pfh2.png`: v39, d3, d4; sit and pray, side): the bulb's outer line now
      continues the thigh's line further. A separate rounded lobe and a dark notch between it and the thigh remain
      under the buttock.
    * User: replace the separate dome and bulb lobes with one rounded shape under the buttock that closes the notch.
    * **d5/d6** (`MERGE=sit`): one shape per thigh, owned by the thigh.
      * Construction: the dome plus the d4 bulb as it sits against the thigh in the chair sit, closed with the thigh
        (ball 15 mm) so the notch fills. It keeps only what idle and walk hide and is rooted at least 4 mm under the
        thigh skin.
      * Mesh: surface net on a 9 mm lattice, Taubin smoothing, about 1.9–2.5k triangles per thigh. The pelvis nodes
        are no longer added.
      * d6 also pulls toward the thigh axis any vertex that idle or walk would show. Within 12 mm of the skin it blends
        the pad's normals into the thigh's, which removes the dark meeting line seen in d5.
    * d6 pose suite, pfh2 / pfh0. Holes are unchanged from v39.

      | Clip | Visible flap |
      |---|---|
      | idle | 77 / 253 px, rear only, voxel-tolerance slivers |
      | walk | 0 / 131 px |
      | run | 4.6k / 3.3k px |
      | kneel | 0 px from the front |
      | pray | 160 / 99 px from the front |
      | crouch | about 14–16k px from the front |

    * Visual (`evidence/dome6-zoom-{pfh2,pfh0}.png`: sit, kneel and pray; side and rear; v39 then d6): one rounded pad
      under each buttock; in the sit side view the notch is filled. Some uneven shading remains on the left pad.
    * **d6 client build** (`combo-d6`, installed in profile-combo; compile and audit pass; the pfh0 legs re-baked
      with the pad present): in-game captures in `evidence/client-d6-motion-check.jpg` (chair sit, kneel, pray bowed
      and upright, crouch; Fit and Large; back, side and front). The sitcross, run and kick captures were cut short:
      window focus kept returning to Claude. The client was left running for the user's own review.
    * Not approved. Awaiting the user's in-game judgement.
    * User (after the d6 close-up): restart from the shipped models; extend the pelvis's thigh portion, round it to curve
      under, and let the thigh overlap. The fixed textures stay.
    * Reference (`evidence/ref-shipped-v39-male.png`, GPU): v39 has jagged lines in every pose and is worse than
      shipped. The male bodies have no band: the thigh is a rounded form that overlaps the pelvis.
    * **b3** (`ballsocket.py`, `PARTS=thigh`, from `sub-ascii`):
      * The thigh's full cross-section, taken just below its slanted top, is extruded up to hip-pivot height and rounded
        over to the axis (H 65 mm, P 2.5). Vertices only move outward.
      * Then `seamnormals.py` and `normblend.py` as before; the skin re-bake in the build keeps the fixed textures.
      * A pelvis roll-under (`PARTS=pelvis`) crumpled the cup's inner floor and is not used; the overlapping thigh
        already covers the pelvis edge.
      * The shins are shipped, so the v39 knee edits are not included.
    * Gates, both bodies: 0 holes and 0 cracks (as shipped), thigh rim 0, pelvis rim exposure below shipped. The brief
      check counts about 250 thigh points per side within 20 mm outside the brief; the front views show the brief
      intact.
    * Visual (`evidence/ref-b3*.png`): the rear band is gone in idle, walk, run and kneel, leaving a thin soft crease.
      A faint shading step remains on the outer thigh where the widened top starts.
    * Client (`combo-b3` installed; `evidence/client-b3-motion-check.jpg`: idle, walk, chair sit, kneel, pray,
      crouch; Fit and Large; back and side): no band, cut edges or lumps at capture distance. The client was left
      running for the user's review.
    * User: the thigh tops need more rounding.
      * `ballsocket.py` now takes `S0`, the height where rounding starts. The b3 dome was squat (about 100 mm wide,
        65 mm tall) and read as a flat end in sit and pray.
      * Variants: b4 (P 2, S0 −25, H 70), b5 (P 1.7, S0 −40, H 75), b6 (P 2, S0 −10, H 95) and **b7 (P 2, S0 0,
        H 110: a near-hemispherical top)**.
      * Starting the rounding below the pivot (b4, b5) brings back a jagged crossing line when standing.
    * b7 (`evidence/ref-b367.png`, `evidence/ref-b7-front.png`): in sit, pray and crouch the thigh tops under the
      buttocks are smooth round forms; idle and walk are as in b3.
    * b7 gates: holes 2 / 10 px (pfh2 / pfh0, across 9 clips), thigh rim 0, cracks 0. Built and installed as
      combo-b7; the client was relaunched for the user.
    * Open (also in shipped and b3): in front view, one outer hip still shows the pelvis's lower edge as a horizontal
      step over the thigh, where the pelvis is wider than the thigh.
    * User: fix the outer-hip step, then add the knee fix from v39.
      * Knee: `jointfix.py` can now run knee-only (`cfg-knee.json`), so the v39 knee edit is re-applied to the new
        thighs.
      * Step, attempt 1, b8: pulling the hem inside the idle thigh (`hipstep.py`) aimed at the leg-opening edges. The
        step is a fold, not an open edge, so it moved the waistband region instead and opened holes.
      * Step, attempts 2 and 3, b9–b10 (`COVER`): widening the thigh top over the outer hip removed the step.
      * b11, covering the front as well, made the thighs balloon across the crotch.
    * User: undo that thigh change and round the front of the pelvis's bottom edge instead; then "needs more gentle
      rounding".
      * **b13**: b7 thighs plus the knee fix, then `hipstep.py ROUND=20 ROUNDH=70`. Per 10-degree sector, the pelvis
        hem curls in on an elliptic profile, 20 mm deep over 70 mm of height, in the front half, fading by the
        side-back. The inner layer follows.
      * `holefix.py` now puts back the best pass when a pass makes it worse; previously it kept the worse state.
    * b13 gates: holes 16 / 28 px (pfh2 / pfh0, across 9 clips × 6 frames × 4 views), cracks 0, audit passed. Built
      and installed as combo-b13; the client was relaunched.
    * `evidence/ref-b13-front.png`: the front step is now a soft, rounded curve on both bodies. A faint line
      remains in the side views.
    * In-game animation tour of b13 for the user: walk, run, sit, kneel, pray, crouch, cross-legged sit, kick; back,
      side and front; 4 s each. User, 2026-10-25: "Looks good".
    * Pilot visual result: b13 (combo-b13) is the user-reviewed hip and knee shape for pfh0 and pfh2. Per the earlier
      decision, work stops here: no rollout to other bodies, no productionizing or publication until the user's next
      piece of work is ready.
    * Torso polish on top of b13 (user, 2026-10-25): the pelvis top-back and the torso sides where the shoulders cap
      need gentler rounding; then also the bottom of the Large torso, at least the front sides.
      * New GPU torso review: `gpubody.py` (Blender) and `bodyrender.py` pose pelvis, chest, neck, biceps and thighs by
        their nodes' animated rotations, re-rooted on the body's rig and held in the torso's bind frame. A visible back
        face is red; the brief counts as two-sided cloth. `bodyslice.py` draws plane sections of the bind pose.
      * Found:
        * pfh0: the pelvis top stands up to 37 mm outside the chest at the back. That makes a crest across the
          lower back, with the chest's hem above it.
        * Both bodies: the chest's upper-lateral corners form square pads above and outside the bicep cap. This is
          most visible on pfh0.
        * pfh2: the chest is closed at the bottom, so it has a floor. At the front sides its lower wall stands 1–2 cm
          outside the pelvis and meets the floor at a sharp corner. That corner is the ledge.
      * `ringroll.py`: a part's top or bottom rolls in toward a vertical axis through `torso_g`. Every vertex scales by
        amt/r_out, so layers keep their order, and seam copies stay welded. With `OTHER`, the depth per sector comes
        from how far the edge stands outside the neighbour part. `TUCK=hold` holds that depth up the band, then eases
        it out. `TUCK=roll` gives one convex elliptic roll.
        * The hold tuck on the pelvis top exposed the chest's hem as a new ledge, with a 40 px hole at the side, so it
          was rejected.
        * The convex roll keeps the pelvis inside the chest only near its top edge.
      * `cornerround.py`: about a front–back axis through each bicep pivot moved `IN` medially and `DOWN` down, each
        coronal slice's upper-lateral contour is pulled onto the superellipse through its own lateral and top extents
        (`P=2`, an ellipse). It only moves inward, by a vertex scale, and fades over `SPAN` at both ends.
      * **c6** (from b13 and the shipped chest):
        * pelvis, both bodies: `ringroll OTHER=chest TUCK=roll BAND=10 MARGIN=2 TAPER=70 DEPTH=12 HEIGHT=50`, with
          `W=0:0.3,60:0.6,95:1,180:1` (back and sides). Then `seamnormals`.
        * pfh2 chest bottom: `ringroll DEPTH=40 HEIGHT=70 W=0:0.6,25:1,80:1,115:0` (front sides).
        * chest corners: pfh0 `IN=50 DOWN=55 SPAN=25`; pfh2 `IN=55 DOWN=60`.
        * Largest moves, in mm (pfh0 / pfh2): pelvis 30 / 12, chest 36 / 40.
      * c6 gates:
        * Hip pose suite (pelvis, brief and thighs; 9 clips × 6 frames × 4 views): hip-region holes unchanged at
          28 / 16. The suite has no chest, so it now also shows about 7,300 px of the rolled pelvis top, all
          22–41 mm above `torso_g`.
        * With the chest drawn (`bodyrender`, 13 clips × 4 views): the pelvis shows no holes. The bicep holes are the
          open elbow ends, as in b13 (no forearms drawn). pfh0 has 9 px on the crop top's armhole edge in arms-up
          poses, a sliver with skin directly behind it.
        * Cracks 0. Pelvis and chest seam groups: none split. Brief check: 0 new points outside. Chest normal seams
          as shipped.
        * Compile audit 12/12. The re-bake covered pfh0 chest, pfh2 chest and pfh0 pelvis. Installed as combo-c6.
      * Evidence:
        * `evidence/ref-c6-pfh0.png` and `ref-c6-pfh2.png`: b13 against c6, standing, five views.
        * `torso-c6-*-motion.png` and `torso-c6-*-armsup.png`: motion.
        * Variant studies: `torso-c3-pfh2-belly.png`, `torso-c4-pfh0-backtint.png`, `torso-c5*-shoulder.png`.
      * c6 awaits the user's in-game review.
  * Tools snapshot (scratchpad copy): `joins-pilot/scratchpad-snapshot-2026-10-25/` (`joins/`, `skin/`,
    `stock-anim/`). Installed client hak: combo-v39.
  * Build time: 1,255 s, of which the bake is 1,190 s. Only the female pelvis, legs and shins change
    between join iterations (about 300 s of bake). An incremental, 3-way parallel bake would cut an
    iteration to about 6 min.

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
