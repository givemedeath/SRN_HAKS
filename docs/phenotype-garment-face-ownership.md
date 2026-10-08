# Explicit per-face garment ownership and derived edge inputs

`target_garment_face_ownership.py` is an additive alternative for a fitted chest
or pelvis that has one shared skin/cloth atlas. The legacy
`target_garment_ownership.py` strict global-mask path is unchanged.

One global mask cannot supply different uniform labels to two shared-UV faces
whose filtered supports overlap. This helper separates explicit geometric face
decisions from measured source paint ambiguity, then proposes two independently
padded color/PLT inputs. It changes no original mesh, index, attribute, UV,
normal, tangent, color accessor, material or embedded map byte.

## Propose

Use the verified local shared launcher with the bundled Python, local shared
config and passed migration receipt. The command is:

```text
target_garment_face_ownership.py --mode propose --config CONFIG --output FRESH_DIR
```

The version-2 configuration uses `kind: "target-garment-face-proposal"` and
`diagnosticOnly: true`. Declare the target path/hash, chest or pelvis part,
working/runtime coordinate space, fitted source path/hash and current geometry
receipt path/hash. The exact installed target and its garment owners are
validated. Optional protected neighbor inputs use the existing path/hash map.

Declare:

- `faceDecisions: {path, sha256}`: a version-2
  `target-garment-face-decisions` document with the complete target/source/part
  binding, `sourceFaceIds: [0, 1, ...]` in original triangle order,
  `faceRoles: ["skin", "garment", "unknown", ...]`, and `accepted: false`.
  These explicit decisions are proposed by the caller; the helper does not infer
  ownership or approval from colors or dominant texel counts.
- `ownershipMask: {path, sha256}`: a diagnostic 2K categorical source color mask,
  0 skin / 127 unknown / 255 cloth. It measures paint uncertainty and filtering;
  it does not override the explicit face decisions. Raw GLTF V samples decoded
  image rows directly, as in the legacy helper.
- `padding: {radiusPixels: N}`: an explicit 0..16 pixel processing bound.
  Zero records uncorrected ambiguities. The implementation proposes copies of
  original same-role interior texels within this Euclidean radius; unresolved
  destinations remain measured and block reviewed staging. This is a tool's
  bounded edge operation, not a claim that any chosen radius looks acceptable.
- `knownSourceGarmentDefects: [...]`: the observed source defects, including an
  empty list when none was observed. Existing strap gaps or extra straps must
  remain listed. A face/material review cannot resolve them by relabeling them;
  a corrected source requires a new proposal.

Outputs include complete explicit face decisions, full bilinear and strict
interior center counts, physical ownership areas, conservative UV-to-position
padding distance estimates, independent skin/cloth color maps, AO0 skin PLT
intensity, original PNG bytes, texel-copy lineage and a pending review template.
All remain unaccepted. Geometry UV wrapping, degeneracy and unsupported material
adapters fail closed; mixed paint or unknown decisions are recorded for review.

For each role, changed destination texels are confined to that role's complete
filtered support. Copy seeds are original same-role diagnostic texels strictly
inside its declared triangles. Pixel distance, channel deltas, unresolved texels
and every source/destination pair are recorded. Original normal pixels and
ORM-green roughness transport are retained; AO0/.15/.35 can later derive from
this one reviewed color parent without cumulative changes.

## Review and staging interface

Create a separate `target-garment-face-review` from the pending template after
reviewing the actual part and its UV boundaries. It must bind the exact
proposal, target, source and original face inventory. An explicit ownership and
material review uses `accepted: true` and
`decision: "approved-face-ownership-and-material-inputs"`, a reviewer and notes,
complete face roles, `garmentDesignReviewed: true`, front/rear/side/UV-boundary
views, and explicit acknowledgment of the listed mixed/interior/filter face
ambiguities. This approves those inputs only; whole-body or client acceptance
is always separate.

Before reviewed staging, `paletteEdgeEvidence` must include direct garment-edge
views for both palettes 3 and 8, from `native-material-preview` or
`literal-client`, with image path/hash and the exact `proposalSha256`. An
unapproved diagnostic renderer may show the proposed sidecars and face roles
first; its own evidence must remain labeled diagnostic. The helper neither
renders those views nor creates their approval. It rejects stale evidence,
incomplete roles, unresolved padding and known source garment defects.

The exported interface is:

```python
reviewed_staging_inputs(proposal_path, review_path, target_path, target,
                        part, space, source, source_receipt, ao_strength=0)
```

It returns a partitioned document and original BIN, complete face/material
roles, original corner order, derived material rows and provenance. The document
only adds contiguous index-accessor slices and cloned original material
references. Original position/normal/UV/tangent/color accessors, winding,
indices and all map bytes remain exact. Effective color and PLT intensity are
explicit sidecars; they are not claimed to be unchanged source pixels. The
interface independently reconstructs all measured supports, padding pixels,
lineage, original map archives, PLT intensity and normal/ORM proofs before use.

`--mode verify-review --proposal PROPOSAL --review REVIEW --output FRESH_DIR`
records that verification without writing geometry, native resources or a
selection. It does not grant body/client acceptance.

`target_part_stage.py` now consumes the reviewed sidecars through an explicit
`garmentFaceInputs` control in its usual `target-part-stage` configuration:

```json
"garmentFaceInputs": {
  "proposal": {"path": "proposal.json", "sha256": "exact proposal hash"},
  "review": {"path": "review.json", "sha256": "exact review hash"}
}
```

Choose exactly one of `materialRoles` for original embedded maps or
`garmentFaceInputs` for reviewed per-face derived inputs. Unknown controls,
unreviewed/stale proposals, known source garment defects and missing direct
palette evidence fail before resources are written. The adapter calls
`reviewed_staging_inputs`, serializes the returned color/PLT rows with original
normal/roughness inputs, and records the derived proof and every pinned sidecar
alongside the original source.

The generated `pending-stage-interface.json` retains its distinct pending kind
and is deliberately rejected as a staging configuration. Convert it only after
the exact proposal/material review is complete. The ownership helper writes no
native package. The stage adapter has serialized PLT, fixed cloth, normal and
ASCII attribute integration tests; body/native/client acceptance is separate.

## Later skin lighting descendants

A derived lighting intensity map needs its own pinned operation and coverage
proof. It must bind the exact working geometry, lighting atlas and variant;
use literal skin coverage as copy seeds; exclude protected connector/garment
destinations; and expose every copied texel and bounded distance before fresh
preview/native/client review. The existing color-padding operation must not be
silently reused to fill a lighting seam. Normal/ORM pixels, original maps and
protected neighbors stay exact. No lighting padding is implemented here.

Actual source garment defects remain separate blockers. True garment cuts
through triangle interiors may require reviewed bounded subdivision or a
reviewed color correction that preserves the approved cut; this helper cannot
subdivide, remap UVs or waive geometry defects.
