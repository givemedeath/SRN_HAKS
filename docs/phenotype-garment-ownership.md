# Reviewed garment face ownership

`tools/phenotypes/target_garment_ownership.py` partitions an existing fitted
chest/pelvis candidate into recolorable skin and fixed opaque cloth. It does not
fit, repaint, resample, weld, subdivide, or accept a body candidate.

Use the local verified shared launcher with an ignored local toolchain binding
(created by `tools/phenotypes/bind_shared_runtimes.py`; the tracked
`tools/phenotypes/configurations/shared-tools.json` is a portable historical lock)
and the passed migration receipt. Invoke the helper with `--mode propose --config <configuration.json>
--output <fresh-directory>`, then separately `--mode apply` with an explicit
review receipt. All paths and hashes bind the exact source and target.

The proposal configuration has `schemaVersion: 2`,
`kind: "target-garment-mask-proposal"`, `diagnosticOnly: true`, `part`,
`coordinateSpace`, `targetContract`, `targetContractSha256`, `source`,
`sourceSha256`, `sourceReceipt`, and `sourceReceiptSha256`. The source receipt
must be a current `target-part-geometry` receipt in the declared working/runtime
space. Only declared chest/pelvis garment owners are supported.

Specify either `ownershipMask: {path, sha256}` or an explicitly diagnostic
`diagnosticColorRule: {garmentMaxChannel, skinMinChannel}`. A mask is a 2048 by
2048 categorical PNG in L or equal-channel RGB: 0 is skin, 127 is unknown, and
255 is garment. UV v0 corresponds to the decoded original image's row0.
`filterRadiusPixels` is 1. The measurement covers entire triangles, partial
texels and a conservative bilinear footprint; vertex or centroid samples cannot
silently hide a garment boundary. Threshold diagnostics may mistake painted
muscle shadows for cloth and always require independent review.

A proposal writes the mask, full face roles, per-face footprint counts, boundary
measurements, executed helper snapshots, and `pending-review-template.json`.
It remains `accepted: false`. Copy that template to a fresh selection receipt
only after reviewing the actual candidate from front/rear/side and its UV mask.
Record the reviewer's identity, notes, those `reviewedViews`, and byte-pinned
`reviewEvidence`. Explicit approval is `accepted: true` and
`decision: "approved-face-ownership"`. The faceRoles list must own every face
and agree with the independently remeasured mask.

The apply configuration uses `kind: "target-garment-mask-apply"`, the same frozen
source/target fields, `proposalReceipt`/`proposalReceiptSha256`, and
`selectionReceipt`/`selectionReceiptSha256`. `maxOutputPrimitives` supplies a
bounded budget. Optional `protectedInputs` preserve selected neighbor bytes.

Application rejects mixed/unknown footprints, missing roles, stale inputs,
cross-target reviews, wrapping/degenerate UVs and unsupported material adapters.
It has no subdivision or ambiguity waiver. Refine a diagnostic mask or create a
separately reviewed geometry descendant and repeat proposal/review. Conservative
filter footprints can expose atlas-edge crossings beyond the triangle interior;
those remain explicit blockers for this helper.

The descendant duplicates the original material dictionaries and assigns them
through contiguous slices of the original index accessor. The complete source
BIN, original accessors, attributes, winding, global triangle order, texture
bindings and embedded PNG bytes remain exact. Its authoritative native-corner
archive preserves the parent positions/normals/UVs and topology lineage while
updating primitive ownership. No UV repair, cloth recoloring or map padding is
performed. `geometry.json` uses the existing `target-part-geometry` contract;
pass its `materialRoles` into ordinary staging. Runtime conversion still occurs
exactly once. Native material/palette behavior, garment cut and client review
remain separate gates.
