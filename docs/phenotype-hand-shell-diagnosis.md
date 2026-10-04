# Hand shell diagnosis: the remesh stage

2026-10-03. Read-only diagnosis for the complete muscular Human male goal.
Evidence lives in
`output/phenotypes/purposebuilt-forearm-pilot-v1/hand-shell-diagnosis-v1`.
No generated master, reference, material, rig or animation was changed. No GPU
job or client was started by this diagnostic workstream; source adoption,
compilation and actual client testing were completed by the coordinator.

## Finding

Current offline outcome: the recovered hand is freshly baked at 2K and fitted
as a mirrored pair to the stock wrist/held frames. Its final geometry keeps a
solid wrist and open grip. The practical moving-wrist audit passes all 4,374
stock-comparable rays across 243 poses. Nine compact faces have eight small
crossing pairs and one separate vertex pinch; the parent explicitly accepts
these under the latest user instruction to finish the hands without requiring
perfection. They remain recorded defects, not a crossing-free/manifold claim.
Source, fitted-pair and exact residual evidence are described below. Native
integration and complete-body/client evidence are parent-owned and complete in
[the final delivery](phenotype-human-male-delivery.md).

Stage-level pending statements below describe the chronological diagnosis and
recovery, not current completion gates. Fresh atlas baking, native checks,
cumulative offline review and the practical client pass are already complete;
do not replay those jobs or reopen cosmetic hand trials.

This diagnosis applies to the recorded Human donor and its recorded workflow
output. It does not predict defects in future hands. New hands begin with normal
generation, inspection and fitting; invoke fault tracing or recovery only when
their own results show a diagnosed defect. The repairs below are examples for
that condition, not mandatory steps or inherited parameters.

The v6 hand's thin paired walls are introduced by the installed UDF remesh
branch. They are not established as an upstream reference-generation failure.
The raw decoder's inconsistent winding makes its signed volume unreliable as
a solidness test. Earlier descriptions of a globally hollow raw hand must be
superseded by the direct depth-ray evidence below.

Five identical rays along source GLB Z, at X0 and Y0.1/0.2/0.3/0.35/0.4,
cross the untouched raw hand at two broad exterior depths. After UDF remesh,
each crosses four depths, in close pairs around those same exterior positions.
Compact decimation retains the four hits.

| Source stage | Wrist Y0.3 depth intersections | Volume / bounding box |
| --- | --- | --- |
| v6 raw decoder | −0.248787, +0.107846 | 0.020144; winding is inconsistent |
| v6 UDF remesh | −0.251425, −0.246149, +0.105167, +0.110526 | 0.036702 |
| v6 compact shape | −0.251408, −0.246014, +0.105097, +0.110090 | 0.036480 |
| Solid forearm raw | −0.111027, +0.105048 | −0.012395; winding is inconsistent |
| Solid forearm UDF remesh | −0.113679, +0.107731 | 0.500368 |
| Solid forearm compact | −0.113657, +0.107726 | 0.500521 |

These are unscaled generator coordinates. The forearm's raw signed volume is
negative despite its two broad exterior hits and accepted solid descendant.
Low or negative raw signed volume therefore cannot alone reject a donor.

The comparison samples fourteen rays per stage, retains exact source arrays,
and reports both 1e-7 and 1e-5 coincidence thresholds. It does not alter the
mesh. The wrist's two/four-hit distinction is stable under both thresholds.
Hands' independent closed-section measurements also show two concentric wrist
loops, with inner/outer area ratios 94.2–95.4%.

## Mechanism and limits

The installed `remesh_narrow_band_dc` UDF branch computes `sdf = udf - eps`.
Its own source comment states that a closed mesh produces a double surface.
At resolution 384 and band 1, the fixed cube scale is 387/384; epsilon is
0.00262451. Measured new hand pair separations around 0.0053 agree with roughly
two epsilon offsets. This is direct stage evidence plus an implementation
mechanism, rather than an inference from signed volume alone.

Inner/enclosed component filtering follows vertex connectivity. The filter
cannot remove an interior sheet connected to the exterior: inverted/enclosed
rejection is conditional on having multiple connected components, and the
largest is preserved. The hand's one connected remesh component has positive
net shell volume, so both enabled UDF filters leave it intact.

Why the hand forms these connections while the simple forearm's inner sheet
is removed has not been proved. Near-contact finger geometry and single-vertex
dual-contour cells are plausible contributing factors. Reference coherence and
anatomical quality remain separate gates; the comparison does not certify
every raw hand region or every raw topology defect.

The raw v6 mesh has 7,811,200 faces, 64,915 boundary edges, 61,328 nonmanifold
edges and 1,938,775 inconsistent manifold-edge windings. Those observations
make nearest-normal signed remeshing risky, but do not themselves show a thin
global raw geometry layer. Its raw-to-remesh ray comparison is the authority
for the stage at which the extra depth walls appeared.

## Singular-edge-only separation fails

Exact-coordinate diagnostic welding and face connectivity through only
exactly-two-face edges leave all 49,962 compact v6 faces in one component.
Excluding all 21 nonmanifold-edge adjacencies does not separate an interior
layer. Every singular edge remains internal to that ordinary-edge-connected
component.

The first hand donor similarly retains 49,862 faces together; only tiny 46-face
and 8-face fragments separate. The solid forearm control has 50,000 faces,
zero singular edges and one closed component. There is no justified
singular-edge-only interior component to discard in either hand attempt.
No face deletion, sheet adoption or global normal rewrite was performed.

## Same-raw SDF experiment: completed and rejected

The root submitted the prepared `same-raw-sdf-only-request.json` exactly once,
job `61d42751-47dd-45e8-aea1-40cbd56b49ef`. Its original prepared request remains
immutable; its `submitted=false` records this worker's preparation state, not
the later root execution. The success receipt and output are frozen under
`human-male-complete-goal-v1/same-raw-hand-sdf-trial-v1`. It uses five installed nodes:

`Load3DAdvanced → Get3DComponents → RemeshMesh → MeshToFile3D → Save3DAdvanced`.

Load3DAdvanced can read the original server GLB with the supported `[output]`
annotation. The server and local raw SHA256 are identical. The installed
Get3DComponents GLTF reader was independently invoked on CPU; it reproduces
the source positions, faces and available normals exactly, with no placement,
normalization or warnings. No reference upload or latent regeneration is needed.

The diagnostic changes the remesh sign-mode branch to SDF, explicitly retains
qef=false, sets the required SDF manifold widget=false, and keeps resolution 384,
band 1, project_back 0, fix_poles=false, smooth_iters 3, small-component fraction
0.01 and precluster cap 2,000,000. The raw source has 3,905,152 vertices, so
the original precluster policy remains consequential and unchanged. UDF-only
inner/enclosed widget keys are removed in accordance with the live SDF schema;
the node consequently uses its mode-specific defaults. This is a branch
diagnostic, not a promise that all internal code paths are identical.

The output has 1,615,578 faces, 246,389 boundary edges and 73,065 nonmanifold
edges. Its five wrist depth rays have two broad intersections, but that does
not make the globally porous mesh a closed exterior. Volume / bounding box is
0.019973 and is descriptive only. This is a failed sign reconstruction, not a
few residual dual-contour joins; a manifold-only rerun is not justified.
Output SHA256: `400deaad37c71c7ce13bf5b19fff31b67773ff613f32054191eb034642b23821`.
Actual gates are in `sdf-trial-topology-v1/topology-and-depth-sections.json` and
`sdf-fixed-depth-rays-v1.json`. Nothing has been adopted or fitted.

## Why source normals and latent occupancy do not provide a direct rescue

Both exact raw hand and accepted forearm raw masters have no authored NORMAL
attribute. `raw-authored-normal-proof-v1.json` confirms their immutable arrays.
There is no source-authored normal field to use as an independent outward oracle.

The installed shape decoder emits seven channels: dual-vertex position offsets,
three unsigned edge-intersection flags and quad split weight. The mesh builder's
three axis quad tables use a fixed order with no inside/outside sign channel or
outward flip. The output node packages vertices and faces without authored
normals. Nearest geometric normals consequently cannot reliably sign the original
mesh. This is a code-supported limitation, not an instruction to globally rewrite
normals or geometry.

The original workflow's structure decoder supplies a 32-cube occupancy to seed
the sparse shape stage. It saves the four mesh stages, but no shape latent or
structure occupancy. A cached volatile tensor is not a frozen deliverable. That
coarse occupancy would require a separately frozen execution and explicit checks
before being used as a shape oracle; it cannot directly recover the detailed
gripping opening at the final mesh resolution.

## Winding-independent fill: measured feasibility and remaining leak

CPU diagnostic voxelization uses a conservative triangle / axis-aligned cube
intersection test with all thirteen separating axes. It marks only cubes actually
touching the original compact surface, then identifies empty cubes connected to a
padded exterior through six-neighbour connectivity. No dilation, closing,
blanket smoothing or source edit occurs. Diagnostic `filled = ~outside` includes
the surface and empty regions proven enclosed at the stated resolution.

| Resolution | Pitch in generator coordinates | Filled volume | Wrist result |
| --- | --- | --- | --- |
| 384 | 0.00260417 | 0.161327 | One solid interval at all five measured rays |
| 512 | 0.00195313 | 0.020197 | Main interior leaks to exterior; paired intervals remain |
| 512 with measured two-cell closure | 0.00195313 | 0.160143 | One solid interval at all five measured field rays |

The 384 result alone is insufficient: its conservative support closed a narrow
opening that 512 resolves. Do not silently choose the coarser grid as a valid
production repair. Cached grids and sections are retained in
`conservative-fill-diagnostic-384-v1` and `conservative-fill-diagnostic-512-v2`.
An independent workstream located the entry and prepared a two-cell min-cut,
indices `[298,78,148]` and `[298,79,149]`. It adds only two previously empty
surface cells. All original surface cells, grid origin, pitch and dimensions
remain exact. Independent recomputation of the entire six-connected flood agrees
byte-for-byte with the saved outside mask and confirms the main tissue cavity is
enclosed. All four protected core lines remain open and all 22 reference line
occupancy arrays are unchanged. The source-clear marginal line's original
conservative raster contact remains recorded below.

Current closure authority is
`purposebuilt-upperarm-pilot-v1/hand-leak-independent-v1/localized-512-mincut-v2`;
grid SHA256 `aef870130e31af29fe26c3254d2f034d09c3c0166c0e45ab7da0667810cf68ca`,
closure SHA256 `d19370c63c0232824cf2eb37c2f861dcab54601534331a7fae263c0f0532f984`.
Independent field receipt:
`localized-512-mincut-independent-recheck-v2/measurement.json`, SHA256
`66e4ec2a38c007b00ba473c5d6f194789154e96819959ba44354905e5665fe06`.
The earlier 25-cell closure is superseded diagnostic history and is not a selected
input. Neither a coarse filled surface nor sign-only SDF is an adopted hand.

The hands workstream supplied 22 wholly clear X-axis lines through the grip
pocket. Independent queries confirm all 22 are clear in both untouched raw and
compact source meshes. Both diagnostic grids keep 21 lines entirely clear; the
same marginal line at GLB `[0,-0.19,+0.08]` touches raster cells. Its compact
surface clearance is only 0.0001974 (raw 0.00124315), below either pitch, while
its central axis point remains exterior-connected. The protected core at
`[0,-0.175,+0.05]` has clearance 0.0268116 in compact and 0.0288228 in raw,
comfortably above either pitch. Full evidence: `grip-clearance-proof-v1.json`.

Grid NPZ schema: `shape[3]`, `origin[3]`, scalar `pitch`, and packed boolean
`surfacePacked` / `outsidePacked` arrays. Unpack with big-endian bit order,
truncate to `prod(shape)` and reshape C-order. Cell i spans
`origin + i*pitch` through `origin + (i+1)*pitch`; its center is
`origin + (i+0.5)*pitch`. World-to-cell uses `floor((P-origin)/pitch)`.
These arrays are diagnostic evidence, not prepared game assets.

The root extracted the verified two-cell 512 field into
`human-male-complete-goal-v1/filled-exterior-512-mincut-v1/exterior-highpoly.glb`,
SHA256 `d955864c9184a210d0ad9997006576bcb3e6adcdc8b4ecfc46dce410e15c4c9b`.
It has 5,828,260 triangles and 2,914,088 vertices. Independent checks establish
one connected component, no boundary/nonmanifold/inconsistently wound edges and
a single cyclic link at every vertex: no pinched or unused vertices. Euler
characteristic −42 means 22 total topological handles; this count is retained
explicitly and does not by itself certify every small tunnel as anatomical.

Every candidate vertex was checked against the immutable compact source triangles
on CPU. Maximum distance is 0.003378137 and median 0.00140233 in source coordinates,
within the conservative 512 support bound. All four core grip lines remain wholly
clear: smallest clearance 0.0132859; principal core clearance 0.0250709. The same
marginal near-edge source line retains its explicit raster-derived contact, so
21 of 22 exact wholly clear source lines remain wholly clear on this descendant.

Five exact wrist rays have contact counts `[2,2,2,3,2]`; all ten explicit ±1e-6 X
companion rays have two intersections. Keep both exact and companion results.
Independent receipts are `exterior-512-mincut-{distance,rays,vertex-links}-v1`.
This high-poly exterior is a credible reconstruction input, not a finished game
hand. User-reviewed clay anatomy is approved as a direction. The next bounded
polish removes visible voxel ridges within one pitch, protecting the flat wrist;
its serialized result still needs fresh independent envelope/ray checks. Then
fresh decimation/UV/bakes, low-poly crossings, stock fitting, native proof and
whole-body evidence remain. Original generated masters are immutable.

The first three-pair fairing passed those independent geometry checks: maximum
source distance improved to 0.003179394, all five exact wrist rays became two-hit,
all four grip core clearances stayed exact, and 106,883 protected cap/core vertices
plus all face indices remained encoded-exact. Maximum actual movement was
0.000484562 (0.248 pitch), with no flips/degenerate faces and volume ratio
1.00000527. It remains unselected because normal-bake ridge inspection still
shows visible voxel steps. A separately serialized twelve-pair trial retains
the same one-pitch displacement bound and protection; it must pass fresh
independent checks before adoption. Three-pair source and receipts remain history.

The twelve-pair serialized candidate now passes those independent CPU gates.
Its SHA256 is `feb84aa43e2c7963bf099c3f5b9040f23f2695ae02400405b23bc6303e90a7d6`.
Every one of its 2,914,088 vertices was queried against immutable source
triangles: maximum source distance remains 0.003179394, with median 0.00143512.
All five exact wrist rays and ten explicit companion rays have two broad
intersections. All four grip core clearances remain exact; 21 of 22 original
clear lines remain clear, with the same recorded marginal raster contact.

Independent array transport confirms exact face indices, 106,883 protected
cap/core positions, 102,040 flat-cap-plus-one-pitch positions and unique vertex
positions throughout. It therefore preserves the previously proven single
manifold component and cyclic vertex links. Maximum movement is 0.001083380
(0.554691 pitch); all faces retain orientation, none degenerate, and volume
ratio is 1.00001847. The complete geometry evidence is in
`faired-exterior-512-{distance,rays,transport}-v2`; the transport receipt SHA256
is `da294928af0fa0c12bfbf21f11127a7894edf4e9081e7a8ccbd6d37b05152e72`.
This is a gated high-poly reconstruction input. Visual normal-bake approval,
fresh compact topology/crossings, UV/material bake, stock fit, native preparation
and assembled-body evidence are separate downstream gates. No game hand has
been selected by this read-only workstream.

The final high-poly bake input adds a bounded normal-only refinement on that
new reconstruction, keeping its encoded positions and triangle indices exact.
`clean-exterior-512-normal-polish-v2/normal-polished-highpoly.glb` has SHA256
`57a01f46487c94a5a03f8bcfc255dcd706e4796c8ab724bbbe8cac694963f494`.
Independent full-array checks confirm finite unit normals, exact normals at all
102,040 flat-cap-band vertices and a maximum change of 35.00000235 degrees
(the recorded FLOAT32 rounding of the 35-degree limit). All prior geometry,
source-distance and grip checks apply through exact encoded P/F transport.

Noncap adjacent-normal RMS falls from 16.12358 to 4.17106 degrees across
16,870,030 edge samples. This metric includes real curvature, not just noise.
All 17,484,780 face corners were checked: no face has all three normals inward.
Two residual concave corners retain their exact original normals and are a
subset of the source's three negative corners. The first N-only trial had one
new grazing corner on a 4.36e-7-source-unit-squared triangle; the fresh final
trial restores only that vertex's original normal. Its geometry never changed.
An overly strict identical-corner-set diagnostic failed and is retained as
history; exact geometry and zero wholly inward faces were already established.
Current authority is `normal-only-transport-v2/measurement.json`, SHA256
`dffd996afadf3e63577a186cda5f06e44a9857db740207c174a1f8f6822bd8e5`,
and `normal-only-concave-corners-v3/measurement.json`, SHA256
`abaf0a2b39c88b4a1a00391a343334a8e939f8d99fccf9067b8b38a39f1a1f4f`.
This is authored-N polish on a newly created untextured source; it changes no
existing texture normal atlas or normal strength. Fresh compact/bake gates
remain required. The latest user direction prioritizes finishing the hands
without further cosmetic refinement loops.

Exact grid-aligned rays can contact a coplanar marching-tetrahedra transition:
the unselected 384 surface's X0/Y0.2 ray has three contact depths, while explicit
X companions at ±1e-8, ±1e-6 and ±1e-4 have two crossings. Keep exact and companion
results separate; do not silently jitter a model or discard an odd ray count.

Successful untextured geometry would still need fresh decimation, UV/material
transfer and native preparation from verified sources. Existing textured UVs
cannot be assumed to match a newly remeshed surface. Preserve source maps and
freeze the later bake reference explicitly.

## Final compact bake and practical wrist evidence

Actual job `3565bc47-42b7-4e91-a4ce-9c9e164058f3` completed once. Its frozen
collection is `human-male-complete-goal-v1/clean-hand-retexture-v2`.
The UV mesh SHA256 is `4c3813d5d609a9bb1f160e36fb861aa48e5b34be260d36f1bbd80d6ce677bef7`;
the textured mesh is `b5f12e349814fef7c70d87655c216eddf5138abd5b3476c205dbde5723018493`.
Actual final collection agrees with the earlier observed UV save. Their
position/index arrays and ordered 49,990-triangle geometry are exact. Fresh
textured UVs match the installed bake/attach association formula exactly.
All 32,018 normals and tangents are finite/unit; tangent W is exactly ±1,
and an independent CPU UV-derivative check has zero W-sign mismatches and
maximum tangent-angle difference 0.00048463 degrees. Receipts:
`textured-compact-transport-v1/measurement.json` and
`textured-compact-basis-v1/measurement.json`.

The compact mesh has one component, no boundary/nonmanifold/inconsistently
wound edges and no degenerate triangles. All five measured wrist depth rays
and their ten companions have two hits; all four grip core lines remain open.
The same marginal line retains its previously recorded raster contact.
All-face conservative triangle tests find eight crossing pairs on nine faces
in two small concave regions. Exact vertex-link testing also finds one pinch
at raw GLTF `[-0.23209392,-0.12641059,-0.01290094]`; these compact defects were
introduced after the separately verified high-poly manifold stage. They are
explicitly accepted for this goal's current scope and are not hidden by
weakening a shared diagnostic or rewriting source geometry.

The uniform stock fit is 0.16561695430321036 metres per source unit. Maximum
crossing-segment length is 0.623673 mm; maximum vertex excursion through the
opposite triangle plane is 0.783379 mm. These are separate measurements, not
a claim of exact penetration depth. Exact source face IDs, raw locations,
actual fitted locations on both hands and the separately located pinch are
frozen in `compact-residuals-{actual-scale,fitted-locations,fitted-pinch}-v1.json`.
Their scope acceptance records the latest user instruction to wrap up hands
without requiring perfection. No further cosmetic repair is scheduled.

The first whole-part wrist checker required exactly two axial hits per part.
Closed gripping fingers legitimately make those rays nonconvex: 941 of 4,374
stock-comparable rays satisfied that old assumption, with no gaps; 3,433 were
honestly recorded as uncomparable. The fresh practical wrist interpretation
keeps every contact and uses even-parity occupied intervals nearest the
actual stock wrist joint, with a declared 50 mm neighbourhood limit. It
never stretches or bridges intervals. All 4,374 rays are now comparable,
with zero exclusions, zero gaps and minimum actual wrist overlap 28.416955 mm
over 243 exact stock animation cases. The original result is immutable.
Current contact receipt: `final-hand-pair-wrist-local-intervals-v1.json`, SHA256
`d53a941e9e75320477bfb54681295be7b82bad0b1641e1de6289ed61ffe9bf8d`.
This is practical sampled contact proof, not continuous engine-motion or
exhaustive cap-visibility proof. The exact tested pair is left SHA256
`a65969da012dc41661747f76e2585286e2e4f3cfad9fffcd852948694ea4fc0d`
and right `58d803f87abaac491be54201aba9daced6b08096898af61aefade314327c5fc1`.

The intermediate UV-save mesh has no authored NORMAL attribute. A legacy
normal-required audit stopped on that missing field. Geometry-only checks
therefore use a fresh read-only helper that records the absence and never
fabricates source normals; the actual final textured N/T/W check above is
separate. This distinction prevents a UV-stage attribute omission from
becoming an invented geometry repair or a false final material pass.

## Frozen authority

| Evidence | SHA256 |
| --- | --- |
| Raw v6 hand | `9392865b50dd48400a415e1bd2f7e7255cf17b47bc292a005fe858042610037d` |
| Remeshed v6 hand | `449390eab7a81816817a4b15d60cc439e21ddb39c134819fb0858abca2dcad62` |
| Compact v6 hand | `8dab9ee5a3a6a1596b0577693e3321f23634976f04fc255a1e1c8204a21d9559` |
| Painted v6 hand | `02d51a168c6cf40ad49c10066ed638c3bb2159d5f1c1e02630acc5e8b1b84b0d` |
| Installed remesh implementation | `7c67190df434abd6a32de6fe5c987ef7755387f552311e0a088b9c674fcff3c7` |
| Installed postprocess nodes | `215ed682a2a4554de99d6d676236723e9cfc7e037b0cde77747ca802f8ddd005` |
| Prepared same-raw SDF request | `1296a6c588e0b2802b914268570624182bb4530b9d18ad9b4e55ea7267c7a1b5` |

The leaf directory retains `stage-ray-comparison.json`,
`compact-singular-adjacency.json`, installed code snapshots, live schemas and
workflow, loader proof and proposed API graph. Original v6 job:
`d6d729af-2cd1-4fe7-b223-71d01fcbc7f3`.

## Process improvement

Separate raw decoding, remesh, compact geometry and material stages in every
receipt. Retain the exact pre-remesh mesh. Compare the same physical section
rays before and after remeshing; distinguish paired walls from legitimate
grip openings. Use reliable closed-manifold signed volume only with its topology
and orientation evidence. Component-filter success on a simple limb does not
prove a connected hand shell is solid. Prefer the same-raw remesh experiment
over another unrelated image/model regeneration when stage evidence identifies
the remesh branch as the defect source.
