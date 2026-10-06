# Meshy outfit to NWN:EE robe trial

A bounded experiment measuring how far Meshy-generated outfits can be converted
automatically into skinmeshed NWN:EE robes for stock Human male phenotype 0. The
automatic first pass and every correction are kept as separate candidates.
Results and the recommendation are in [results.md](results.md).

Nothing here changes `srn_2da`, `hakbuilder.json`, the stock rig, the stock
animations or another session's assets. Sources, candidates, receipts, the trial
HAK and the module stay in ignored `output/robes/<run>/`.

## Tooling

All jobs run through `tools/phenotypes/launch_shared_tool.py` with a local
runtime binding and a robe-scoped migration receipt.

| Step | Helper | Notes |
|---|---|---|
| Migration | `run_robe_migration.py`, `finalize_robe_migration.py` | Python/Blender scope; stock robe extraction and Neverblender import smokes. Main's equipment finalizer needs an Armory tool that is not on main and is not used here. |
| Stock extraction | `extract_stock_robes.py` | Every installed `pmh0_robe*`, `parts_robe.2da`, the `pmh0` animation chain and the `*001` body parts, overrides disabled. |
| Inventory | `inventory_stock_robes.py` | Skin nodes, bones, influences, hide flags, hem coverage; donor proposals. |
| Control | `blender_roundtrip.py`, `compare_skin_models.py`, `freeze_tolerances.py` | Neverblender import → export → re-import of unchanged stock robes; tolerances frozen from measured loss. |
| Meshy | `prepare_reference.py`, `meshy_robe.py` | Pinned `meshy-cli@0.4.0`; credit cap, one open job, two generation attempts per outfit, recorded reference approval before any 3D job. |
| Inspection | `inspect_source.py` | Budget, islands, duplicates, boundaries, hidden faces, limb sections, skin estimate; defects classified. |
| Repair | `repair_source.py` | Seam weld, floating/duplicate removal, UV-preserving decimation to the 100k budget. |
| Fit | `fit_outfit.py`, `fit_math.py` | Landmark similarity, geodesic segmentation, proxy-rig pose conversion to the stock bind joints, lattice inflation to clearance over the naked stock body. |
| Weights | `transfer_weights.py` | Region-restricted nearest-face barycentric transfer from stock robe and body-part cage donors, smoothing, ≤4 influences, normalisation, validation. |
| Model | `build_robe_model.py` | Stock bind skeleton copied unchanged; region skin nodes; exposed skin in skin-PLT nodes. |
| Review | `deformation_review.py`, `render_review.py`, `contact_sheet.py` | Offline linear blend skinning over the motion matrix against the stock donor; matched renders; stretch/collapse/penetration flags. |
| Materials | `prepare_materials.py` | 2K fixed-colour TGA/MTR; skin-layer PLT with an MTR that omits `texture0`. |
| Package | `build_robe_fixture.py` | Trial HAK, `parts_robe` rows, robe items and the comparison module in an isolated userdir. |
| Client | `Launch-RobeTrialClient.ps1` | Refuses to start beside a running client; records package hashes. |

## Findings that shape the pipeline

- The EE `compilemodel` command rejects skinmeshes ("not yet initialized"), and
  every installed `pmh0_robe*` is ASCII, so robes ship as ASCII and native
  validation is the engine's own load in the client.
- Neverblender 4.1.0 writes 5-decimal positions, 4-decimal UVs and 3-decimal
  weights (renormalised, influences below 0.001 dropped), writes 0 in the
  per-face surface-material column, exports every vertex group as a bone and
  does not enforce bone limits. Region labels therefore never travel as vertex
  groups; the intended model is written by `build_robe_model.py`.
- `pmh0_robe001/002` are rigid cones; `003–006` are single skins over `pmh0`
  with at most 10 bones and no hand, foot or neck influence; `020/021` coats use
  `a_ba_coat` skirt chains; `030–033` and `038` are loincloths and an apron.
- The stock bind pose has the arms almost straight down (8.4° from vertical)
  and an exceptionally deep, broad naked body. Stock robes clear it by a median
  2–3 cm; a realistic Meshy outfit needs about 1.5× chest depth to enclose it.

## Gates

G1 reference approval before each paid 3D job; G2 offline deformation review of
standing and worst-case motion before packaging corrections; G3 client review of
the packaged candidates. None of these is production acceptance.
