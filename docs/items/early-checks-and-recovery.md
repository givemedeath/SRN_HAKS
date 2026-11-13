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

A reviewed `unorientedSourcePatch` fills the listed faces with colour only, from the nearest donor surface whichever
way it faces. It may reach the policy's `maximumUnorientedDistance` (default 2.1 mm, at most the 3 mm transfer
distance) and cover at most 0.01% of the mapped texels. A patch that quotes the user's own approval in `userApproval`
may reach 3.25 mm and 0.05% instead. The 1.90 m stun staff at its chosen 41 x 49 mm grip needed that: about 220
missed texels lay up to 3.203 mm from a generated donor that is inside-out in spots (user, 2026-11-12, "Raise the patch
cap", then "Allow 3.25 mm").
Neither form changes geometry, and both still need the lit and unlit visual review.

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

Thickness probes are measured on the whole assembly, but a shadow proxy measures
only its own part. On a multipart item add `"parts": ["t"]` to scope a probe; a
probe without `parts` applies to every proxied part.

`processing.constrainedReduction: true` reduces each part outside its seam band
before the worker validates the candidate, and repairs the
`Reduction changed a mating contour` failure inside the Runner.
`processing.uvCoordinateScale` (default 1) and `processing.materialPalettes` reach
the atlas and finish steps the same way.

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

### Quadric shadow proxy

A silhouette cannot serve a part whose section varies around its axis: a head
that is wider off-centre than along a thickness probe puts any projected outline
outside the probe (the 1.90 m stun staff measured 4.4 mm against the 2.5 mm
sample bound). Blender's plain collapse, the default shadow, has no probe
awareness and loses those samples at small budgets.

`{"method": "quadric"}` collapses the part's own closed surface to its shadow
budget with a topology- and normal-preserving quadric (bound pymeshlab, run by
the CPU runner like the silhouette builder). Faces within `probeRadius` (default
6 mm) of every thickness-probe end stay as they are, so probes measure the source
surface itself; they may use at most half the budget. Each `qualityThresholds`
value (default `[.3, .5, .1]`) is one bounded attempt; the first that stays
closed, within budget, within `maximumDistance` (default 6 mm, at most 20 mm) of
the source and passes every protected probe is installed. The staff head went from
13,790 triangles to 296 of its 300 with residuals of 0-0.6 mm and a 5.6 mm worst
distance. The vertices alone can stay close to the source while the large triangles between them cut across a
curve or bridge a recess. So the shadow surface, sampled at 28 points per triangle, has its own looser bound:
`maximumSurfaceDistance` defaults to 25 mm, with a 40 mm limit. The staff head measured 5.6-7.8 mm at its vertices and
15-20 mm across its triangles. The reverse gap, from the source to the shadow, is recorded as `maximumSourceGap` but
not gated. A large
gap points at a fin or spike that the collapse removed, so check those parts in the visual review of the shadow,
which is still required.

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

## Screening donor misses and measuring a colour patch

The driver repeats the bake preflight's donor test on CPU and prepares a reviewed patch, so a fit that cannot bake is
found before unwrap finishing and Cycles (`tools/itemkit/miss_patch.py`):

```text
python -m tools.itemkit.drive screen ID SUFFIX DONOR_GLB [--distance M --alignment A]
python -m tools.itemkit.drive patch-measure ID SUFFIX DONOR_GLB <preflight.json | donor-miss-diagnostic.json | --faces F,F,...>
python -m tools.itemkit.drive patch-add ID SUFFIX NEW_SUFFIX --faces F,F,... --distance M --notes "review" [--user-approval "user's words"] [--replace]
```

- **`screen`** joins the run's unwrap arrays (the final atlas, else the extract's `uv-source.npz`) in native part
  order. A run with several unwrap or fit attempts is refused until `--arrays` or `--fit` names the one to use; the
  commands never guess between attempts. It moves the textured donor through the fit's `rawToNativeMatrix` and fails every visible face whose
  centroid has no donor triangle within the distance that faces within the alignment, as `transfer_preflight` does.
  The bounds are the manifest's `maximumDistance` and `minimumNormalAlignment` unless the options override them. A
  reviewed patch in the manifest covers its faces as in the preflight (`coveredByPatch`), and only when its corner hash
  matches this target (`patchMatchesTarget`). It is the same centroid early warning, not a surface proof. On the stun
  staff's fit-v38 it found 1 of 21,976 faces in about 10 s, face 2364, which that manifest's reviewed patch covers.
- **`patch-measure`** takes the failed faces of a bake report, or `--faces` (for example `screen`'s `failedFaces`
  before any bake). It refuses a report whose `targetHash` belongs to another target. For each face it records the centroid and sampled maximum distance to the fitted donor (45 points), the
  nearest donor facing and the mapped texels. It also gives the total texel fraction, a suggested patch distance
  (the sampled maximum rounded up to 0.01 mm) and the target's corner hash.
- **`patch-add`** writes a new manifest with `processing.missCorrection.unorientedSourcePatch` for exactly those faces,
  bound to the run's corner hash. It needs the manifest's existing `nearest-finished-donor` policy and a review note.
  It raises `maximumUnorientedDistance` to the patch distance when that is above the policy's bound (2.1 mm by
  default), since the worker caps the patch there. The scope is 3 mm and 0.01% of the mapped texels, or 3.25 mm and
  0.05% with `--user-approval` quoting the user's own words. The patch is checked with `validate_texture_patch` before
  it is written, and the worker checks it again when it bakes. A manifest that already has a reviewed patch is refused
  unless `--replace` is given; list the earlier faces again, with a note that covers both reviews. Rebuilt from the staff's fit-v38 atlas, the command
  reproduces that manifest's reviewed policy exactly.

None of these approves a patch. The user reviews the measured faces, the note quotes that review, and the baked
colour still needs the lit and unlit review.

## Repairing a working shell

When a generated or donor-derived working shell is not one closed outward solid, these write a new GLB and refuse
(writing nothing) when the result fails the same `topology` check the pipeline uses (`tools/itemkit/shell_repair.py`):

```text
python -m tools.itemkit.drive shell-from-donor IN.glb OUT.glb [--voxel 0.001 --faces 200000 --dilate 1 --erode 0 --sigma 0.8 --taubin 5]
python -m tools.itemkit.drive drop-specks IN.glb OUT.glb [--fraction 1e-6]
python -m tools.itemkit.drive repair-shell IN.glb OUT.glb [--rings 2]
python -m tools.itemkit.drive remesh-shell IN.glb OUT.glb EDGE [--taubin N]
```

- **`shell-from-donor`** rasterises the donor surface into voxels. It dilates them, flood-fills the outside, smooths
  the solid, runs marching cubes, cleans the result, Taubin-smooths it and decimates to the face target. The shell
  sits about one dilation outside the donor, and holes narrower than the dilation close. It refuses grids over 50M
  voxels (about 1.2 GB of grid coordinates alone); use a larger voxel for a bigger donor.
- **`drop-specks`** removes components under the volume fraction of the largest one. It reports the closed state
  rather than requiring it.
- **`repair-shell`** cuts rings of faces around every vertex whose faces do not form one fan (the topology check's
  vertex links) and every edge used more than twice. It then closes the holes. A shell without such spots is returned
  unchanged.
- **`remesh-shell`** remeshes to an even edge length in native units. It must keep the shell closed and outward at
  the same genus, with no degenerate triangles.

Each reports topology before and after and the volume ratio. A repaired shell is a new working mesh, so pin it in a
new manifest and review it like any other; these commands do not change an existing manifest or run.

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
