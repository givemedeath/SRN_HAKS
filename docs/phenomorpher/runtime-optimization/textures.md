# Runtime optimization: Phase 4 1K body textures

`phenomorpher downsample-textures` (run through `tools/phenomorpher/run.py`) halves every
published body palette and skin map above 1024 px. No packaged file has been replaced
yet; this creates no texture, client or production approval.

## Method

Integer 2:1 area reduction; names, formats, orientation, headers (except dimensions),
TGA footers, materials and the PLT file set are unchanged. Map roles come from the
material slot that names them (`texture1` normal, `texture3` roughness).

* **PLT:** per 2×2 block the layer covering most texels wins; ties go to skin 0, then cloth
  4/5, then the lowest other id. Intensity is the mean of the winning layer's texels.
* **Normal:** RG decoded to a unit vector with the shader's reconstructed Z, averaged,
  renormalized, Z ≥ 0.02, re-encoded with no green flip.
* **Roughness:** linear per-channel mean, no gamma, RGB kept (not converted to grey).
* Means round half to even; each unique payload is converted once and written to every
  resource name that carries it.

## Result

| | Resources | Unique payloads | Before | After |
|---|---:|---:|---:|---:|
| PLT (chests, pelvises) | 25 | 3 | | |
| Normal maps | 28 | 28 | | |
| Roughness maps | 28 | 25 | | |
| **Total** | 81 | 56 | 914,361,336 bytes | 228,592,632 bytes |

Receipt: `.tmp/runtime-optimization/phase4/textures-001/downsample-receipt.json`
(`2295facc0bb31de2f68f1185d6daf46b23dc5076ca9bf352a43075fb619d7c43`).

* Palettes use only layers 0 (skin), 4 and 5 (cloth). 1.8% of 1K texels come from mixed
  skin/cloth blocks; per-layer coverage changes by at most 2.5% and the mean intensity
  per layer by at most 1.4 of 255.
* Normal maps: the 1st-percentile length of averaged vectors is 0.94 before
  renormalization; encoded length error ≤ 0.007. The 2K sources already contain the same
  0.08% of grazing texels.
* Roughness channel means move by ≤ 0.05 of 255.

## Review

UV-space sheets (`.tmp/runtime-optimization/phase4/review-001/`) compare 2K and 1K for
`pfh0_chest001`, `pfh0_pelvis001`, `pfh2_pelvis001` and `pmh0_pelvis001` palettes
through stock skin row 3 / cloth row 13, their layer maps, and the lit normal and
roughness maps of `s20f_chest`, `s20m_chest`, `s20f_legl` and `s20m_pelvis`.
Layer boundaries carry over without skin/cloth contamination. As expected at half
resolution, 1–2 px highlight strips along some cloth edges become broken dashes and
fine normal detail softens. Matched 3D views (Phase 6) and the client session (Phase 7)
remain the acceptance gates.
