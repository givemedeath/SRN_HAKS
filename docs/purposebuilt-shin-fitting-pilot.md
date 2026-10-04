# Purpose-built muscular Human male shin fitting

Started 2026-10-03 UTC after the completed thigh pair (`bd5ee99`). The latest
user authorizes one left shin/calf and its independently validated geometry
mirror. This record owns measurements, uniform placement and measured local
connector refinement methodology;
[the shin checkpoint](phenotype-shin-checkpoint.md) owns source selection,
live work and acceptance. The selected candidate is **Smooth shin connectors**,
`left-shin-connectors-v3-monotone`, and its exact stock-frame mirror. Independent
opposite-side, paired native and first-round actual client checks are now
complete. The root-owned validation record establishes finite acceptance;
this fitting record retains measurement and proof boundaries.
The [selected process](phenotype-purpose-built-shin-process.md) records the
reusable part-specific method and native lineage; root owns the final
[client validation](phenotype-shin-validation.md).

## Fixed inputs and ownership

The hash-verified stock bank is
`output/phenotypes/purposebuilt-stock-inputs-v1/stock`. Actual left resources
are `pmh0_shinl001` at `lshin_g` and `pmh0_footl001` at `lfoot_g`; right
resources are `pmh0_shinr001`/`rshin_g` and `pmh0_footr001`/`rfoot_g`.
These names come from the extracted ASCII and stock root, not kit aliases.
Stock front is +Y, up +Z, anatomical left -X. Left shin medial is +X and
lateral -X. The stock male rig, height 1.9339157 m, animations, feet and all
accepted neighbours remain unchanged.

Protected accepted GLB hashes:

| Part | SHA256 |
| --- | --- |
| Chest | `3ae78d023ba522d94c44d9914bac0b36f35b640c42b9532015575e5572161a50` |
| Pelvis | `db0bdf16099068da3bb685bcb61ae93ebed115e6ddbae90990c0b55e59b8d98a` |
| Left thigh, Hip crown taper v2-proof | `5420a77d5e9d51b7841f678d12710ce335bab16ed5ad417ae49b67f1e2950ab6` |
| Right reflected thigh | `3c002789b74bfb5e94392d7c557e3105924e078f0133c47d496b1c123764b980` |

The shin owns anterior tibial skin, posterior calf and closed shallow knee/
ankle overlap ends. The accepted thigh owns quadriceps/hamstrings; the stock
foot owns heel, instep and toes. References must contain no thigh, knee ball,
foot, clothing or armor. Natural muscular middle volume need not reproduce
stock flat skin, but attachment footprints and motion remain measured targets.

## Stock measurements and guide evidence

`prepare_shin_connector_guides.py` records actual source triangles, ownership
IDs, horizontal sections, bind frames and six actual male poses in
`output/phenotypes/purposebuilt-shin-pilot-v1/stock-connectors-v1`.
`measurements.json` binds every input/hash and command argument;
`source_triangle_sections.npz` retains triangle data and section segments.
Twelve equal-scale clay views show isolated left shin, stock context and
accepted-thigh context from front/rear/lateral/medial. Accepted thigh positions
come from their authoritative float64 archives. No source mesh is reexported.

- Overall left shin: 508.7992 mm tall, maximum 160.5141 mm width and 189.2346 mm
  depth; local Z -466.704 to +42.0952 mm.
- Knee to ankle pivot: `[20.427,-66.6266,-427.408]` mm, length 433.051919 mm.
  The right X offset is -20.430 mm.
- Upper band Z -9.745 to +42.095 mm: footprint 112.796 x 109.061 mm.
  Sections taper rapidly: Z +20 mm is 89.609 x 87.712 mm, +30 is
  76.950 x 62.163 mm, +40 is only 16.075 x 11.576 mm. A full-width top mesa
  would recreate the thigh pilot's exposed-crown problem.
- Calf section Z -175 mm: 159.260 x 164.271 mm, bbox centre
  `[-12.350,-60.775]` mm. The full calf projects posteriorly (-Y).
- Lower band Z -466.704 to -420.450 mm: footprint 86.297 x 96.946 mm.
  Sections Z -430/-450/-460 mm narrow to 73.498 x 93.502,
  33.449 x 46.963 and 13.424 x 18.848 mm respectively. The ankle closure
  should be shallow and rounded, not an ankle cuff or a generated foot.
- Stock shin extends 39.296 mm below the ankle pivot. Stock foot's highest
  surface is 26.156 mm above its own pivot. Across the sampled idle/crouch/
  kneel/walk/run/cast poses, the foot reaches shin-local Z approximately
  -400 to -408 mm. This is explicit moving overlap evidence, not a claim
  that every frame is covered.

The world X=0 reflection conjugated between actual shin joints is local
diag(-1,1,1) with X translation -2.794 micrometres. Real reflected stock
left/right vertex sets differ by up to 1.160156 mm; do not claim exact stock
shape symmetry. Opposite-side coverage still needs independent review.
Nearest cap-to-neighbour distances are unsigned finite samples, not solid
containment or a complete seam proof.

## Uniform fitting helper and calibration

`place_purposebuilt_shin.py inspect|place` requires a successful collected
generation receipt that identifies the exact selected source path/hash. It
binds actual stock root/connectors and all four protected GLBs. Inspection
retains raw attributes/maps and emits an unconfirmed template. Anatomical
front/rear/medial/lateral evidence must approve the proper rotation before
placement; another part's rotation is not a default.

`centerline_proposal` begins with total-height calibration and measured hidden
end allowances. Real triangle-section centroids infer source knee/ankle
anchors, retaining the measured stock section-to-pivot offsets: knee Y
+13.540 mm and ankle X +17.413/Y -2.353 mm. A centroid-only fit would lose
these attachment offsets. The source has no authored skeleton; these remain
explicit geometric assumptions requiring actual source and posed review.

The fit permits one positive uniform scale, proper rotation and translation.
The finalized `detached_affine_bake` canonicalizes detached geometry and
preserves original BIN-prefix/accessor/map/UV evidence. Authored normals and
tangents rotate without magnitude substitution; native UV V flips once.
The authoritative native archive is float64 and rendered GLB FLOAT32 error
is measured separately. Uniform triangle-edge checks prohibit stretching.
No old mesh-edit operation, supermodel generation or neighbour fitting runs.

`fit-calibration-proof-v1/proof.json` proves actual stock identity fitting and
reconstruction of a known proper rotated/scaled/translated stock source to
1.11e-16 m. Both helpers compile. This calibration does not establish any
generated shin's topology, anatomy, fit, runtime or client acceptance.

Use bundled Python; never the Windows Store shim. Guide execution used Blender
`-b --python-exit-code 1 --python tools/phenotypes/prepare_shin_connector_guides.py`
with the stock bank, accepted left/right receipt paths and fresh output above.
The receipt and executed helper retain the exact arguments and source hashes.
Do not regenerate accepted neighbours, or reapply a completed uniform fit to
its own descendant. Subsequent local refinement requires fresh measured
evidence and a separate protected-attribute receipt.

## Actual collected source and first placement

All following directories are under
`output/phenotypes/purposebuilt-shin-pilot-v1`. The successful, collected job
is `comfy-v2-skin/generation.json`, prompt
`ce0d67fc-8bd3-4763-b772-4805a42647b7`. Its untouched
`generated/textured_00001.glb` SHA256 is
`5bc23bf23a0d86fca74650939e410cc479daa8f60fa42bc0f892d9fcbb5ce157`.
The selected sheet is `image-design-v3-skin/source.png`; the input views are
`normalized-v2-skin`. Earlier `comfy-v1` was prepared but never submitted.

`source-attribute-inspection-v1` and `source-visual-inspection-v1` retain
untouched inspection evidence. The camera at +Y sees the posterior calf;
the camera at -Y sees the anterior tibial surface. That actual source evidence
justifies a proper 180-degree Z orientation before axis calibration. Visual
medial/lateral asymmetry is weak; the design intends a left limb, but the
recipe alone does not prove its anatomical handedness. There is no reflection
in the left first fit. The independent source audit records 50,000 triangles,
one closed component, no nonmanifold/winding/degenerate defects or genuine
crossings, and healthy authored normals. Sampled two-hit rays support a solid
exterior with finite coverage; there is no source repair in this lineage.

`left-shin-firstfit-v1/placement.json` binds its actual job, source, inferred
anchors, proper rotation, scale, protected neighbours and executed helper.
The positive uniform scale is 0.5428384362095527, with a 4.858871-degree minimal
axis correction after source orientation. The source knee anchor is
[0.0008921445, -0.0633985388, 0.3956406638] m and maps to shin-local zero;
the inferred ankle maps to the exact measured stock knee-to-ankle vector.
The canonical candidate SHA256 is
`6ffa99dbf09602a70378839e6a707b3f9c23c24cdbeb7b8de8ff8cf9d2c4b3ba`.
Rendered dimensions are 171.182 x 178.997 x 512.133 mm. Original UV/map/index
bytes and authored P/N/T lineage remain associated; float32 render precision
is reported separately from the authoritative float64 corner archive.

The firstfit images in `left-shin-firstfit-review-v1` compare actual stock
shins against the single fitted left shin, with the same accepted four
neighbours, stock feet and male controllers. The calf physique is useful;
the source knee and ankle silhouettes withdraw too far from neighbouring
parts. Actual sections and independent matched-ray evidence, rather than
nearest-point distances alone, motivate connector refinement. The numeric
rigid alternatives in `monotone-connector-geometry-probe-v1/rigid-alternatives.json`
show why a global scale/rotation cannot fill those local footprints while
retaining the calf and both inferred attachment anchors. They are measured
diagnostics, not alternate rendered or adopted fits.

## Current local connector field

`refine_shin_connectors.py` applies a separately recorded local field to the
canonical completed first fit. It does not repeat uniform placement or change
the rig, feet, accepted thighs, pelvis or torso. The first sparse-factor trial,
`left-shin-connectors-v2-proof`, protects Z[-320,-80] mm and passes geometric
audits, but its knee flange and ankle cuff were rejected in rendered review.
The earlier v1 execution is preserved with superseded wording; no frozen
receipt was rewritten. These variants are historical diagnostics.

The selected **v3-monotone** uses actual triangle sections spaced every 2 mm
to derive radial factors from a smooth, monotone absolute width/depth envelope.
The lower blend extends above the original too-thin lower shaft; the revised
protected middle is explicitly **Z[-250,-80] mm**. Nothing in that interval
changes. There is no assertion that the rejected v2 protection interval still
applies. The upper blend starts at -80 mm. Source closed tip heights, ordered
faces, UVs, maps and materials remain unchanged; maximum local movement is
30.841 mm. No stock-facet projection or whole-calf contraction is used.

The field uses shape-preserving cubic Hermite interpolation with weighted
harmonic secant slopes and bounded endpoint slopes. It does not force a zero
slope at every dense sample. Exact analytic derivatives transport authored
normals by inverse-transpose Jacobian, retaining their original magnitudes.
Tangents use the forward Jacobian and normal orthogonalization, retaining
original magnitudes and handedness. Protected/outside identity portions remain
exact. The helper has no extra scientific-package runtime dependency.

`monotone-connector-envelope-v1/design.json` binds the dense actual source
measurements and chosen smooth targets. The actual triangulated section probe
at 1 mm spacing records minor reverse changes: up to 0.211 mm upper width,
0.138 mm upper depth and 0.033 mm lower depth. Thus a monotone design envelope
is not a claim that every discrete source facet is perfectly monotone.
Its finite-difference Jacobian check agrees within 4.76e-10.

The authoritative current recipe is `left-shin-connectors-config-v3.json`;
the executed receipt is `left-shin-connectors-v3-monotone/refinement.json`.
Candidate SHA256:
`bde4b16194010cd42ad40d282512e1189c7c992a5ab6df06d0d24c27c5123ee7`.
The directory freezes its executed helper/config and authoritative archive.
Positive Jacobian alone is not a winding, intersection, shading or seam proof;
independent checks must inspect the actual serialized triangles and attributes.
No broad normal substitution is authorized by this field.

`connector-v3-independent-index-v1/index.json` binds the exact selected v3
candidate, executed helper, archive and independent checks. Actual quantized
geometry has no boundary/nonmanifold/winding/degenerate defects or genuine
crossings, and no negative authored-normal corner dots. The minimum corner
dot is 0.442919. Independent polynomial evaluation reproduces the field and
P/N/T transport; 69,703 protected middle corners are exact in the archive and
serialized GLB. The two microscopic normal disagreements in rejected v2 are
absent in v3. UV/map/material/index/BIN and completed-fit lineage checks pass.
Matched peripheral contact rays improve the recorded stock-relative edge
withdrawal but do not establish universal animated seam coverage.

Example exact local-refinement command (fresh output required):

```powershell
$py = 'C:\Users\benco\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $py tools/phenotypes/refine_shin_connectors.py `
  --parent-receipt output/phenotypes/purposebuilt-shin-pilot-v1/left-shin-firstfit-v1/placement.json `
  --config output/phenotypes/purposebuilt-shin-pilot-v1/left-shin-connectors-config-v3.json `
  --output output/phenotypes/purposebuilt-shin-pilot-v1/left-shin-connectors-v3-monotone
```

This records the already executed operation; do not rerun into its existing
directory. Offline views in `left-shin-connectors-review-v3-monotone` compare
stock, rejected sparse v2, and smooth v3 with identical accepted neighbours.
The motion review is `left-shin-connectors-review-v3-motion`. Exact commands
are frozen beside each review. Use only the `close-correct-labels` subfolders
for disposable close views: the earlier `close` images reversed labels in the
camera-only renderer and are rejected evidence. The corrected camera receipt
records display translation, labels and hidden right/upper-body parts; no
model geometry is edited. Standard full-body `pose_preview.py` labels were
correct throughout. Native/client review remains owned by the live checkpoint.

## Selected donor mirror and paired comparison

After root's actual left-client join check, `right-shin-v3-mirror-config-v1.json`
pins the selected v3 GLB and refinement receipt, actual `pmh0.mdl`, stock
`lshin_g` and `rshin_g`, and the world-X-zero reflection plane. The existing
`mirror_stock_limb_part.py` conjugates that body reflection between actual
joint frames. It does not reflect controllers or fit neighbours.

`right-shin-v3-mirror-v1/mirror.json` binds the executed helper, config,
source/frame hashes, matrix and output archive. Right candidate SHA256:
`7efe4b5a9e85bacd1b8d23958c96fe4518e186363f5c6c8b91aed5b17b3f4e24`.
The canonical right uses corner order [0,2,1], reflects authored N/T directions,
preserves their original lengths, and flips tangent W. UV/accessor/image bytes
are retained; the atlas itself is not mirrored or repainted. Its source is the
selected canonical left GLB, with that file's declared float32 serialization;
do not claim a byte-exact reflection of the left float64 fit archive.

`paired-shin-v3-stock-map-v1/stock-replacement.json` replaces only shinl/shinr
in addition to the same accepted chest/pelvis/thigh pair. The control has those
same four accepted neighbours and actual stock shins. Feet, other body parts,
male controller matrices and native height remain stock. The paired review
uses PAUSE1 .4, GETLOWLP .2, KNEEL 1, RUN .4, CONJURE2 1 and DEADFNT .02,
in color and clay, with the exact argv captured in
`paired-shin-v3-review-v1/executed-commands.json`. Offline snapshots are finite
pose evidence; live walking/running, opposite-side shading and equipment
ownership remain the root's native/client validation stages.

The paired review is complete: 36 full-body views and 24 close paired-leg
views, plus six supplementary prone top/rear-top/side views in
`paired-shin-v3-review-death-top-v1`. A normal front camera occludes the shins
in DEADFNT, so that view alone is insufficient prone seam evidence. Each
review's `comparison-audit.json` rehashes every actual input and image and
verifies equal stock joint matrices, display scale 1, the four identical
accepted neighbours and stock feet. The control replaces exactly four parts;
the paired candidate replaces those four plus shinl/shinr. Close views hide
only upper-body display objects; both legs and feet remain visible. Their
labels use actual display translation, retaining the earlier camera fix.

Independent `selected-v3-pair-independent-index-v1/index.json` binds the exact
left and right sources. The right has 50,000 actual closed/manifold triangles,
no winding/degenerate/crossing defects and no negative authored-normal corners.
Direct frame-derived P/N/T and full TBN reflection, [0,2,1] winding order,
tangent-W flip and UV/map/BIN retention checks pass. Opposite-side contact
samples use actual asymmetric stock phases, not an assumed mirrored animation.

Image review shows a coherent paired physique and no new mirror-specific gap
in the inspected standing, running, kneeling and prone views. Small selected
thigh end protrusions in kneeling also occur in the stock-shin control; they
are unchanged neighbour context, not a shin or mirror edit. Offline stock
parts appear untextured, so palette blending and tangent shader behavior still
require the packaged game client. No native/client outcome is inferred solely
from these comparisons.
