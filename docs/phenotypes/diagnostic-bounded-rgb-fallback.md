# Diagnostic bounded RGB fallback

`reference_color_bounded_fallback.py` and
`derive_reference_color_bounded_fallback.py` implement one explicit texture-only
operation: copy a frozen list of visible fallback texels from already accepted
skin donors in an immutable literal-reference RGB parent. This does not approve
skin/garment ownership or establish an accepted body candidate.

The parent region, original projection, target contract, source mesh, approved
reference artwork, contour proposal, source attributes and lineage are pinned by
hash. Cross-target, stale-source or stale-contract inputs are rejected. Execute
through the repository's verified shared-tool launcher using the discovered
bundled Python, current toolchain and current migration receipt.

## Required frozen evidence

The configuration has schema version 1, kind
`frozen-visible-skin-fallback-descendant`, `diagnosticOnly: true`, the target
contract pin, part, parent-region pin, contour-proposal pin, exact expected target
count and inner/shoulder scope counts. Limits are fixed at 2 fitted millimetres,
4 UV texels in Chebyshev distance, 5 degrees of original authored-normal
agreement, and minimum .15 geometric incidence in at least one of the eight
pinned visibility directions.

A target must be covered, unprotected and unambiguous, remain original fallback
in the parent, and have a proposed whole-skin source face. Target and donor must
both have canonical approved-reference skin labels. The donor must be a covered,
unprotected, already accepted literal skin sample from the exact parent; empty
chart padding cannot supply it. Their original faces must be identical or share
an original full edge with exactly two incident faces. Compatible accepted cloth
within the same UV/object/normal bounds vetoes propagation; the helper recomputes
this veto instead of trusting a stored false flag.

Only the already frozen target/donor pairs are used. No search for new targets,
recursive filling, new camera choice, cross-role blending, original UV changes or
geometry repairs occur. Every donor RGB is read from the untouched parent before
any result is written. All other RGB pixels, parent role maps, approved artwork,
original geometry, UVs, normals, tangents, signs, normal-map pixels and raw ORM
remain exact.

## Execution and verification

The CLI takes `--config <frozen-config.json> --output <fresh-output-directory>`.
It exports a separate derived RGB PNG, exact target/change masks, per-pixel
source-face/position/normal/UV donor lineage and the donor's original reference
camera, role and blend ancestry. Its receipt declares diagnostic status and
preservation limits. The source-frame preview input can be passed to
`blender_reference_color_preview.py` through the verified CPU Blender launcher.
Parent and descendant must use identical cameras, exposure, emission material,
UV conversion and source geometry.

Independently replay the entire atlas and every lineage row. Prove that all
pixels outside the frozen target set and all protected/mapped parent pixels are
identical; reject corrupted unrelated RGB, donor color, donor coordinates,
source positions and reference ancestry. Check all eight cardinal/diagonal
emission comparisons and preserve their exact package/camera hashes. An emission
preview proves color/filtering behavior only; native palette rows, normal and
roughness shading, neighboring parts, animation and actual client checks remain
separate gates.

## Current female example and limits

The unselected `chest-v4-bounded-fallback-v1` diagnostic copies exactly 555 frozen
visible targets: 377 inner-track and 178 shoulder texels. Every other pixel is
unchanged. Eight focused tests, independent RGB/lineage replay and five disposable
corruption cases passed. Eight matched emissions retain exact prior parent pixels
and camera matrices. The visual effect is small; thin inner tracks and doubled
shoulder paint persist. This result is not garment-cut or body acceptance.

The 14 known mixed skin/cloth faces remain withheld. Their maximum edges span
approximately 6–10.6 fitted millimetres, so majority face snaps would move the
approved boundary. An approved contour needs explicit boundary intersections or
bounded splits with original barycentric attribute lineage. Other selected-photo
cloth disagreement and unknown contours also remain open. Original physical
ridges and normal-map traces cannot be removed by RGB copying. No whole-atlas
fill, staging, selection or client acceptance is implied.

Related material work is described in
[diagnostic reference reprojection](diagnostic-reference-color-reprojection.md)
and [garment face ownership](../phenotype-garment-face-ownership.md). Final delivery
continues through the [female execution runbook](human-female-purposebuilt-runbook.md).
