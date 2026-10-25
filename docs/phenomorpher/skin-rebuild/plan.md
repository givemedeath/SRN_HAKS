# Human skin texture rebuild: plan (draft, 2026-10-25)

Status: **proposed, not approved.** No asset changes until the user approves this plan and its open decisions.
Baseline: contract 1.2.0 on `main` @ `769673e7`. Evidence from the review that prompted this plan:
`output/phenomorpher/human-texture-review/` (ignored; client close-ups, texture sheets, measurement scripts).

## Correction after the G1 pilot (2026-10-25), which supersedes D1, D2 and Decision A below

The pilot rasterised the mesh UVs and found the first diagnosis was partly wrong.
* **D1 and D2 were measured on the wrong pixels.** The "detail" texels lie outside the mesh UVs; they are
  bake gutter smear the game never samples. The "filler" is the texture actually used. Inside the used
  area every Human part, Fit and Large, is one flat tone (male 145±1, female 128±1). The skin has no
  painted shading at all, and there is no clipping.
* **The real defects inside the used area:**
  * no shading or variation, so the skin reads like a mannequin;
  * dark gutter rims up to 67–145 values darker, which bleed in at seams (for example the streaks on the
    back of the female calves);
  * patchy female chest and pelvis roughness.
* **Pilot method (`output/phenomorpher/skin-pilot/`):**
  * keep each part's approved base tone;
  * add ambient occlusion and cavity shading baked from the part's own skin meshes, with garment meshes
    excluded;
  * add 3D micro-variation and an even roughness field;
  * fade all of it to the base tone within 4 cm of each part join, so neighbouring parts meet at one tone;
  * pad 16 px.

  Pilot v4 removes the calf streaks and the rims. The male bodies are clean under white, warm and flat
  light.
* **Not texture:** the female buttock band and knee line come from join geometry. They are planned
  separately in `docs/phenomorpher/female-joins/plan.md`.
* **Client fixture caveat:** pilot sessions before the `nwn.ini` alias fix loaded the shipped HAKs, so
  conclusions drawn from them were void and have been withdrawn.

## 1. What is wrong (as first measured; see the correction above)

All findings are in the source assets. The Fit male chest PLT is byte-identical to its source
`pmh0_chest237.plt` (`pm25fulltonea.hak`). The female PLTs were only downsampled from 2048 px. None of the
source HAKs (`pm25*.hak`, `sr_pm17*.hak`) exist on any local drive.

| # | Defect | Evidence |
|---|---|---|
| D1 | **Fill patchwork.** 32–65 % of each Fit skin texture is constant filler: one PLT value, flat normal, roughness exactly 0.60. Filler is far brighter than the detail beside it: male ≈145 vs ≈107, female ≈128 vs ≈68–79. Islands are small and fragmented, so it reads as sharp-edged blotches. | `pltcmp.py`; flat-normal mask vs PLT; client close-up of `pfh0` under white directional light |
| D2 | **Clipped tonal range.** Skin values stop at ≈146 (male) and ≈129 (female). Stock Human PLTs reach p95 ≈ 171–195 and p99 ≈ 190–207. Female skin is also darker overall: mean ≈87 against stock ≈111–136. Highlights plateau, so lit skin looks flat and dull. | stock `p?h0_chest001/shinl001.plt` vs ours |
| D3 | **No island padding.** The female chest has value-0 (darkest palette column) texels directly against its islands, and the male chest has dark rims around islands. Mipmaps bleed them into seam lines at distance. | texture sheets |
| D4 | **Normal-map edge spikes.** Female Fit normal detail is concentrated on island borders, with flat interiors, so a single strong light draws bright and dark rims around every fragment. | normal-amplitude sheet |
| D5 | **Patchy roughness.** The roughness map follows the patchwork: constant 0.60 filler, and pure-white (1.0) patches next to 0.45 on the female parts. `Roughness 0` in the MTR is correct (the stock shader then reads `texture3.r`). | `inc_material` shader source |
| D6 | **Large has no surface detail.** Every Large MTR uses the 4×4 flat normal `p25lgflat_a` at roughness 0.85. The Large chest PLT is nearly uniform (male 126–146, gradient ≈0.35). | MTR scan, PLT stats |

Minor, separate: the published `pfh0_chest001.mdl` carries a stray client-compiler string (`NoAoOWithPotion`).
It is harmless, but it is the kind of residue `armor-publish` now zeroes.

## 2. Scope facts that shape the plan

* **One skin set for every race.** `srn_body` holds 318 PLTs but only 34 distinct ones. Each Human part PLT is
  shared byte-for-byte by the same part on Dwarf, Elf, Orc and Troll, Fit and Large. Fit non-Human MTRs
  (`pm25?_*.mtr`) point at the same `s20?_*n/r` maps. **Fixing the Human textures changes the skin of all
  20 bodies.** That is intended, and validation must cover all 20.
* **Large limbs and pelvis reuse the Fit UVs.** Per part they have the same topology and identical UV sets,
  scaled 0.93–1.36×, and the same PLT. Only their MTRs differ (flat normal, roughness 0.85). So the rebuilt
  Fit normal and roughness maps can drive Large limbs and pelvis directly.
* **The Large chest is separate.** Male and female Large chests have their own mesh, UVs and PLT
  (`pm25torsobm.hak`; 0 % UV overlap with Fit, about 1.0–1.25× size). This one part needs a 3D transfer bake.
* **Garments live in PLT dye layers.** The female chest bra uses layer 4 (cloth1). The plan only rewrites
  layer-0 (skin) values. Layer indices and garment texels stay byte-identical.
* **Unchanged:** geometry, UVs, rigs, node and material names in the models, PLT sizes (1024 cap), heads
  (out of scope), and every historical receipt.

## 3. Method

Each step reads only the contract's pinned resources and writes to a fresh staged folder with a receipt. The
steps are new `phenomorpher` commands launched through `launch_shared_tool.py` with declared inputs. Reuse
`audit_target_native_part.decode` (mesh UV/positions), `uv_atlas_raster.raster`, `lean_common.dilate_values` and
the existing PLT/TGA helpers; do not add parallel parsers.

**Step 0: Baseline and metrics** (`skin-audit`, read-only)
* Classify each texel per part as filler, detail, garment or empty.
* Build the 3D seam graph from the mesh: edges whose vertices share a position but not a UV.
* Record these metrics: filler fraction, seam-step p50/p95 (PLT value difference across 3D-adjacent texels),
  skin percentiles vs stock, empty texels within 16 px of an island, normal-amplitude spikes within 3 px of
  borders, and roughness range.
* These numbers become the acceptance thresholds in step 6.

**Step 1: Remove the filler patchwork** (PLT layer 0)
* Replace each filler island's constant with a seam-continuous field, solved in surface space (Poisson fill
  over the mesh, using 3D-adjacent texels across UV seams) from the surrounding detail regions. The filler
  then matches its neighbours instead of jumping by 35–60 values.
* Follow with a gradient-domain seam levelling pass, so detail islands that disagree at shared 3D edges also
  meet without a step.
* Decision A (below) selects what goes inside the former filler areas.

**Step 2: Tonal range** (PLT layer 0)
* Map each part's skin values by percentile so p1–p99 match the stock Human part of the same gender:
  highlights reach ≈190–205 and shadows keep their depth.
* Within a part this is monotonic and per-gender, so detail ordering is preserved.
* Check it against several skin palette rows (light, medium and dark) in the previews, not just row 3.

**Step 3: Padding**
* Dilate every island 16 texels, which survives mip level 6 at 1024 px.
* Fill the rest of the background with push-pull values, so no value-0 skin remains next to geometry.
* Apply the same mask to the PLT (value and layer), the normal map and the roughness map.

**Step 4: Fit normal and roughness maps** (the `s20m_*` and `s20f_*` maps)
* Normals: keep the real detail. Within 3 px of island borders, replace spike texels by interior-continuous
  values. Fade detail amplitude across filler boundaries so no hard edge remains. Filler stays flat, which
  is valid because the geometry still shades.
* Renormalise and keep z ≥ 0.02 in the compiler's tangent basis, as `lean_normal_maps.py` does.
* Roughness: one seam-continuous skin field, around the detail-region median (≈0.55, kept within
  0.45–0.70), with the filler and the 1.0 patches resolved.

**Step 5: Large detail and normals**
* **Large limbs and pelvis:** point their 130 Large MTRs (13 parts × 10 Large bodies) at the rebuilt Fit maps,
  with `texture1` and `texture3` naming the `s20?_*` maps and `Roughness 0`. They share UVs and PLTs with Fit,
  so this needs no new textures. The 10 Large neck MTRs stay as they are, because Fit necks have no maps
  either.
* **Large chest (male and female):** bake the rebuilt Fit chest PLT values, normals and roughness onto the
  Large chest UVs by 3D transfer.
  * The transfer aligns the Fit and Large chests in the shared rig frame, then takes the closest point along
    the normal within a distance limit, with Poisson fill for any misses.
  * Normals are re-encoded in the Large compiled tangent basis.
  * New maps per gender: `s20m_chest2n/r`, `s20f_chest2n/r`. The 10 Large chest MTRs then point at them.
  * The female bra layer comes from the Large chest's own garment layer, not from the Fit chest.

**Step 6: Validate before anything is published** (all gates below)
* Automated checks against the step-0 baseline:
  * filler fraction 0 %;
  * seam-step p95 at or below the detail-region p95;
  * skin p1–p99 within ±10 of the stock values;
  * no empty texel within 16 px of an island;
  * a mip-64 bleed check;
  * normals unit length with z > 0;
  * roughness within 0.45–0.70;
  * garment texels and layers byte-identical.
* Offline previews in Blender (4 threads): Fit and Large, M and F; front, side and rear; one directional
  "sun" light; three skin rows; before vs after.
* Client fixture, reusing `client-1.2.0-root-rebase` with a new bright-daylight preset (strong white sun,
  low ambient): all 20 bodies, three skin colours, idle, walk and run, close-ups. Compare against 1.2.0
  side by side.
* Also check the skin seam against `srn_armor` clothing parts, which carry their own skin texels, and adjust
  them only if a visible mismatch appears. That would be separate work and needs approval first.

**Step 7: Publish**
* Contract 1.3.0:
  * updated `selected-palette` and `selected-map` rows with lineage (`rebuiltFrom` the 1.2.0 hashes plus the
    rebuild receipt);
  * the Large MTR changes;
  * the four new chest maps.
* Then `verify-runtime`, the HAK rebuild, a PR, and the client gate. The 1.2.0 commit stays the rollback
  anchor.

## 4. Gates (user approvals)

1. **G1 – Method pilot:** male and female chest and shin, Fit and Large, offline previews plus one client
   session. Nothing broader runs until it is approved.
2. **G2 – Full set:** every Human part, with offline previews of the 20 bodies.
3. **G3 – Client:** bright-daylight fixture, all 20 bodies and three skin colours.
4. **G4 – Publication:** contract 1.3.0 PR.

Numerical checks never approve appearance (AGENTS.md); each gate needs visual review.

## 5. Open decisions

| | Question | Recommendation |
|---|---|---|
| A | What fills the former filler areas? (a) smooth seam-continuous field only; (b) (a) plus band-limited micro-detail synthesised from the part's own detail regions; (c) (a) plus low-gain detail projected from the stock Human PLTs (256 px, painted for a different mesh) | (b): no foreign shading baked for another shape; texture variety without new blotches |
| B | Tonal target: match the stock Human distribution per part, or only remove the clipping (stretch to ≈200 and keep the current means) | Match stock. The female mean rises from ≈87 toward ≈111–136, which also fixes the female/male brightness gap |
| C | Can you supply the original PM25 / SR_PM17 HAKs? Other tone variants or the 2048 px female originals might have less filler. | If they are available, run step 0 on them first, before rebuilding |
| D | Rename the Large chest maps as proposed (`s20?_chest2n/r`), or use a new prefix | As proposed |

## 6. Risks

* All races change at once, which is intended. A regression shows up on every body, so G1 and G3 include
  non-Human rows.
* Poisson fill and percentile mapping can flatten real anatomy shading. Step 0 records the detail-region
  gradient energy, and G1 compares it before and after.
* A Large chest transfer bake may smear where the Fit and Large shapes diverge (male Large chest is 0.92×
  wide by 1.25× deep). Misses are bounded by the distance limit and Poisson-filled; G1 reviews the result.
* Size: four new 1024² TGAs (about 12 MB), with PLT sizes unchanged.
