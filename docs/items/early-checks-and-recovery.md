# Early checks, measured shadows and retained-bake recovery

These are maintained itemkit paths for future work. The four approved weapon
packages remain unchanged. The SMG remains on hold. No generation or GPU work is
needed to use these CPU finishing operations.

## Early geometry and UV checks

`blender_worker.measure` now records Euler characteristic, total genus and a
shadow-method recommendation alongside the existing topology, budget, opening
and thickness checks. These measurements run during fitting and reduction, before
atlas/bake work. They reuse the topology traversal instead of scanning edges twice.
A genus above eight recommends a measured proxy; it does not authorize deleting
holes or certify that generic decimation will fail.

`bake` automatically performs a transfer preflight before invoking Cycles:

- Runtime UV coverage must reach 30%; no overlaps, degenerate UVs, out-of-atlas
  coordinates, missing charts or more than 0.1% unsampled visible surface.
- Two-pixel gutters remain mandatory. Hidden cap palette sharing is distinguished
  from overlap with visible surfaces; degenerate cap UVs are rejected.
- Every visible triangle centroid is checked against the fitted donor for bounded
  distance and compatible facing. The default bounds are 0.003 native units and
  0.5 normal alignment; an explicitly configured correction policy may tighten
  these. Existing exact-geometry reviewed patch exceptions remain bounded.

The report is saved as `preflight.json` before a failed gate stops the bake.
Centroid sampling is an early warning, not a continuous surface proof or a
replacement for actual visible-miss classification. The same check is available
as the Blender worker's `preflight-transfer` action for an independent diagnostic.

The maintained atlas now retains per-face `uvRegions`. Applying that atlas binds
the region labels to exact mesh corners and UVs in the saved Blender scene.
Changing geometry, UVs or labels invalidates this binding. Preflight uses verified
region lineage when present; otherwise it reconstructs conservative UV connectivity.
This matters for custom repacked atlases: the retained pistol's older atlas passes
its recorded region-based checks, but reconstructing connectivity divides several
of those regions and produces missing-chart/gutter warnings. That diagnostic does
not revoke its acceptance. Do not suppress warnings by inventing merged labels;
use the maintained atlas lineage or qualify a custom packer's region evidence.

## General projected shadow route

Set `processing.shadowProxies` by active native part, for example:

```json
{
  "b": {
    "method": "projected-silhouette",
    "basis": [[1,0,0],[0,1,0],[0,0,1]],
    "origin": [0,0,0],
    "resolution": 1024,
    "tolerances": [2,3,4,6,8],
    "closingPixels": 0
  }
}
```

The basis columns are depth and the two silhouette axes, in native coordinates.
They must be right-handed and orthonormal. Use the measured broad-face plane,
not an assumed source-image axis. The identity basis projects onto native Y/Z.
The part name is not restricted to pistol bottom or Cougar pommel geometry.

When configured, the reduction worker exports source arrays and the CPU runner
constructs candidates before expensive baking, retaining each bounded attempt in
`shadow-preflight/`. Construction uses bundled Python's verified SciPy installation;
Blender imports the candidate only after checking source corners, policy and array
hashes. It does not import a scientific package from an incompatible Python ABI.
The shadow stage installs this same candidate. Existing projected-loop and ordinary
decimation routes remain available when no silhouette policy is selected.

The builder simplifies a raster silhouette, preserves contour edges through
triangulation, extrudes a local measured depth envelope, and checks the declared
part budget, closed outward topology, opening probes and at least 95% silhouette
overlap. It keeps disconnected components rather than silently selecting only the
largest one. Zero-pixel closing is the default; one pixel is an explicit option.
`depthRadius` and `minimumThickness` may be specified in native units, within
bounded fractions of the measured extent. Attempts and tolerances are bounded.

This is a 2.5D candidate builder, not a universal replacement for 3D shadows.
Angled bores, overlapping structures and thin members still need probes and visual
review from multiple angles. Numeric success never grants visual approval. The
retained pistol test produced a separate 484-triangle candidate in about 0.5 s;
its approved 468-triangle shadow was not replaced.

## Recover a completed bake without repeating it

Whenever a bake has projection misses, before attempting correction it now writes:

- `bake-unpadded.exr`: original linear pixels;
- `bake-masks-original.npz`: original owners, hidden caps and visible misses;
- `recovery-scene.blend`: exact joined target and fitted textured donor;
- `bake-recovery.json`: hashes of those files, the source scene, external donor
  images, target/donor mesh-and-UV correspondence, family and processing settings.

These files remain even when correction fails. Recover into a fresh directory.
Using bundled Python, prepare the worker configuration and declared inputs:

```text
-B -m tools.itemkit.recovery --proof <bake-recovery.json> --policy <reviewed-policy.json> --output <fresh-recovery-preparation>
```

The policy contains the existing `nearest-finished-donor` method, maximum distance,
minimum normal alignment and, only when necessary, the independently reviewed
`unorientedSourcePatch`. No item-specific face IDs or enlarged bounds are supplied
by the recovery helper.

Dispatch the resulting `worker.json` through `launch_shared_tool.py` using the
current byte-bound Blender toolchain/migration bindings and generated `inputs.json`:

```text
--tool blender --input-manifest <inputs.json> --output <fresh-launch-directory>
-- --python tools/itemkit/blender_worker.py -- --config <worker.json>
```

Recovery permits only the miss-correction policy to differ. It verifies the source
scene, saved scene, external images, exact target/donor correspondence and original
pixel classifications. It corrects misses from the fitted textured donor without
sampling the original appearance field in transformed coordinates. A row-streamed
hash proves every successful texel unchanged, avoiding a second nearly full 4K
RGBA selection copy. Original masks and failed inputs remain immutable.

The result is fresh `bake-linear.npy`, zero-unresolved-miss masks, a scene, sampling
provenance and `result.json`. Feed those outputs to the existing `finish_bake` map
derivation and review the resulting 1K diffuse. Recovery does not overwrite a
failed runner receipt or mark a visual review approved. Bind the recovered result
explicitly in the continuation checkpoint before downstream work.

## Validation scope

New focused regressions cover invalid geometry, blocked openings, UV defects,
caps, small charts, stale region bindings, rotated shadow frames, budget failures,
changed recovery artifacts and unchanged successful pixels. A small four-thread
Blender test performs a real 64-pixel CPU bake, retained one-texel recovery,
linear-colour verification and rejection of a displaced donor before baking.
This small test is not a production 4K throughput benchmark.

Exact source pins, focused tests, smoke receipts, retained-pistol diagnostics and
protected-package hashes are under `output/itemkit/early-checks-recovery-v1/`.
The user explicitly prohibited the full regression suite; only affected itemkit
tests, a catalog check and bounded CPU smoke/diagnostics are used for this change.

Final validation: 162 tests across 17 affected modules passed in 45.397 seconds;
one catalog-equality test passed separately. Both CPU Blender integration smokes
passed on bound source. The approved weapon HAKs, Human HAK and combined module
were rehashed unchanged. Final evidence: `output/itemkit/early-checks-recovery-v1/result.json`.
No full regression suite, GPU work, client launch or SMG processing occurred.
