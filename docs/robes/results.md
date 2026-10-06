# Meshy robe trial — results (interim, 2026-10-06, updated after client round 2)

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
| Native compile | CLI `compilemodel` rejects skinmeshes ("skinmeshes not yet initialized"). **In-client compile works**: with the robe actors in view, chat `## compileloadedasciimodels` writes binaries to `<userdir>/modelcompiler/`. Stock robes ship ASCII |
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
| corrected-v2 (row 17) | Adds belt-zone relabel after operator client observation | **Pass** | Belt zone carries no forearm/hand weight (0 vertices); worst stretch 19–27× (v1: 90–143×); bent-arms penetration 4.6 cm (v1: 14.2) | Full 99.5k model not run in client (equip stall, below) |
| v2 runtime 8k / 20k (rows 18 / 19) | Collapse decimation of v2 carrying weights, labels, outer mask, skin faces and UVs (`reduce_runtime.py`) | **Pass** / **Pass** | Silhouette kept; no cross-atlas UV stretch; standing 0.3 / 1.4 cm | Spawn ~4 s, re-equip ~7 s (stock-like). Operator: sleeve sinks at the left elbow (offline: 9 % of the elbow band 3.4 cm inside the arm), read as a belt piece on the elbow |
| corrected-v3 20k (row 35) | Clearance lattice and weight sampling in the Meshy A-pose (stock body, robe004 and cage posed in by inverse proxy transforms), converted to bind | **Pass** | Worst stretch 14×; bent arms 4.9 cm; no arm weight in hip/leg zone; but bind 10.9 cm (torso cloth inside the hanging stock arms), chest/armpit sink on conversion, sleeves clip the toolbelt (323 sleeve verts >1 cm inside garment torso vs 72 for v2) | Loads, animates; skin PLT tints by skin colour (model-named PLT). **Client-compiled binary** loads with the same timing as ASCII |
| corrected-v4 20k (row 36) | v3 plus a bind pass moving only torso/belt/leg cloth 12 mm clear of the stock arms | **Pass** | Bind 6.3 cm, walk 6.3 cm (v3 18.5), but idle 14.4, melee 11.5, kneel 10.2 cm; upper-chest sink larger than v3 | Not yet in client |
| v5–v8 (rows 37, 39–43) | Iterations toward v10: dual-quaternion conversion; clearance against visible parts only (v5 head clearance blew the collar out 27 cm; v6 open neck tube accumulated 26 cm pushes); v7 no clearance pass; v8 rigid gloves and the A-pose rest experiment | Pass (A-pose rest: bind rotation 4.9e-6 rad, Neverblender 5-decimal precision) | — | Row 40 experiment: **client skins against the robe's own rest frames** |
| **corrected-v10 20k, A-pose rest (row 46) — operator-selected** | Meshy A-pose mesh shipped unconverted on a robe skeleton at the outfit's A-pose joints; elbows on the straight shoulder–wrist line (estimated elbows had been 32–40° off-axis); no clearance pass (neck clips into the collar by design); gloves rigid past a 3 cm wrist band; shoulder top/front/back and outer-elbow blends narrowed, armpit and inner elbow keep full blends; A-pose weight sampling; 20k triangles | Pass except the known rest-rotation precision | Max stretch 26× (concentrated in narrowed seams) | Operator: "v10 looks better". **Client-compiled binary** (3.09 MB) loads, poses and tints correctly |

Inspection of the remeshed input: no floating fragments or duplicate faces; 171
non-manifold edges; closed shell (no neck, cuff or hem openings; capped collar sits
under the stock neck); ~16 % rest-pose-hidden faces kept (rest occlusion does not
prove faces stay hidden in motion). Automatic repairs: seam weld, decimation to
99,500 triangles. Exposed skin (bare forearms, fingertips) is a separate skin-layer
PLT node; colour-only detection also matched brown leather, so it is restricted to
forearm/hand segments.

### Client findings (round 2)

- **Equip stall = model size.** The 14 MB ASCII export of the 99.5k-triangle robe
  blocked the client ~2 min at spawn and ~104 s per re-equip (stock robes: ~7 s).
  The 8k (0.9 MB) and 20k (2.2 MB) runtime copies spawn in ~4 s and re-equip in
  ~7 s; the 20k client-compiled binary measured the same. First-cycle client-wide
  pauses (~50 s, stock actors included) did not repeat.
- **Missing heads were a fixture bug**: the actor template is a static appearance
  with no head; actors switched to appearance 6 now set `Appearance_Head`.
- **Skin PLT**: a PLT named `ww11s` on the skin nodes rendered flat grey (with or
  without its MTR, at 2048 or 512 px). The client tints it once the skin nodes use
  `bitmap pmh0_robeNNN` and the PLT is `pmh0_robeNNN.plt`, as stock robes do.
  Skin shades are remapped to the stock robe004 range (98–185).
- **Bind-pose proximity** (operator rule since 2026-10-06: weight and fit in A-/T-pose):
  in bind the hands hang on the toolbelt, which caused the original belt-to-hand
  weights and, in v2, the elbow sink. Moving the work to the A-pose (v3/v4) removes
  the weight leak but leaves sleeve/belt self-intersection and a chest/armpit sink
  from the shoulder conversion. Neither is resolved; operator visual review of v2
  vs v3 (and v4) in the client is pending.

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
- Runtime budget: keep the Meshy master (≤100k) for bakes and ship a reduced
  runtime copy; 20k triangles loads and equips like stock. Precompile in-client.
- Coat and robe classes: no evidence yet.
