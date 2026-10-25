# Female hip and knee joins: geometry fix plan (draft, 2026-10-25)

Status: **proposed, not approved.** No asset changes until the user approves this plan and its open
decisions. Baseline: contract 1.2.0 on `main` @ `769673e7`.

Evidence lives under `output/phenomorpher/skin-pilot/evidence/` (ignored):
* `legs-back/`: client captures under white, warm and flat light;
* `joins/join-sections.png`: side sections through the left leg in bind pose.

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
