# Meshy robe trial — results (interim, 2026-10-06)

Status: **workwear pilot in progress; long open coat and layered long robe not
started** (awaiting their reference files and credit cap). No candidate is yet
claimed usable: none has passed client review. Run root:
`output/robes/meshy-robe-trial-v1/` (ignored).

## Stock control

| Check | Result |
|---|---|
| Neverblender round trip, `pmh0_robe004` (1 skin) and `pmh0_robe020` (5 skins + dangly) | Structure, supermodel, parents and bind frames preserved |
| Measured loss | positions ≤ 1.03e-5 m, UV ≤ 5e-5, smoothing edges 0, weights ≤ 1e-3, weight sums ≤ 1e-3, sampled LBS ≤ 1.37 mm |
| Frozen tolerances (`control/tolerances.json`) | position 2.1e-5, UV 1e-4, weight 2e-3, sum 2e-3, deformation 2.74 mm, smoothing 0, ≤ 4 influences, ≤ 17 bones per skin node |
| Native compile | **Not possible for skinmeshes**: EE `compilemodel` reports "skinmeshes not yet initialized". Stock robes are ASCII; native validation = engine load in the client |
| Client, control robe (row 10) beside stock robe 004 | Loads and animates in the isolated client; side-by-side visual review pending |

Informational export differences: the per-face surface-material column becomes 0,
classification case is normalised and identical UVs are merged.

## Workwear pilot

Meshy: one textured 4K PBR A-pose generation (1,873,900 triangles, 30 credits)
and one triangle remesh (103,196 triangles, 5 credits). Spend 35 of the 120-credit
pilot cap. Both outputs preserved unchanged; the 1.87M master is kept for bakes.

| Candidate | What changed | Export vs frozen tolerances | Offline deformation (worst sample) | Client |
|---|---|---|---|---|
| auto-v1 (row 11) | Automatic pipeline only | **Pass** | Standing: 0.8 % outer verts inside body (stock robe 10.6 %). Raised arms/cast/melee: webbing sheets, up to ~20k edges stretched >1.5× | Loads, animates, weapons attach. **Fails**: left tool pouch/strap follows the left hand (5,011 belt-zone vertices carry forearm/hand weights, from a geodesic segmentation leak) |
| corrected-v1 (row 12) | Radial relabel of the left-arm leak (2,147 vertices), per-segment bone masks, torso arm-share cap 0.35, softer hanging-item blend | **Pass** | Flagged edges down 20–45 % in every family; webbing sheets gone in renders; standing deepest penetration 2.7 cm | 252 left belt vertices still carry arm weight. Re-equip stall (below) |
| corrected-v2 (row 17) | Adds belt-zone relabel after operator client observation | pending | pending | pending |

Inspection of the remeshed input: no floating fragments or duplicate faces; 171
non-manifold edges; closed shell (no neck, cuff or hem openings; capped collar sits
under the stock neck); ~16 % rest-pose-hidden faces kept (rest occlusion does not
prove faces stay hidden in motion). Automatic repairs: seam weld, decimation to
99,500 triangles. Exposed skin (bare forearms, fingertips) is a separate skin-layer
PLT node; colour-only detection also matched brown leather, so it is restricted to
forearm/hand segments.

### Client stall

In the isolated client, after the actors' scripted unequip step, the **re-equip**
of the ~15 MB ASCII candidate robes hung the client (log stops at the first
candidate re-equip; no engine error). Initial load also blocked the client for
~40 s. Isolation fixtures (stock-only, single workwear actor) are built; results
pending. Until resolved, no workwear candidate passes the client equip/unequip gate.

## Processing time (workwear, automatic path)

| Step | Seconds |
|---|---|
| Meshy generate (server) / remesh (server) | 205 / 226 |
| Inspection / repair | 19 / 17 |
| Fit (pose conversion + lattice inflation) | 586 |
| Weights / model / export round trip / export compare | 22 / 5 / 25 / 34 |
| Offline deformation review (76 samples) | 750 |
| Materials / fixture build | 4 / 12 |

Method caveat: the fitting method was developed on this outfit (fit v1–v10 are
recorded method iterations, not per-outfit interventions). auto-v1's quality is
therefore optimistic for the workwear; the coat and robe test generalisation.

## Recommendation (provisional)

- Fitted garments: automatic conversion reaches an engine-loadable, animating
  robe with acceptable locomotion, but not unattended quality. Fused accessories
  (pouches, straps touching sleeves) break limb segmentation, and arm-raising
  motions need a correction pass. Classify as **needs correction pass**.
- Runtime budget: 100k-triangle ASCII skin robes stall the client on re-equip in
  this trial; a reduced runtime LOD is likely required regardless of conversion
  quality.
- Coat and robe classes: no evidence yet.
