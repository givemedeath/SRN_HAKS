# Purpose-built muscular Human male hands

Updated 2026-10-03. The completed full-body deliverable supersedes the older stop-after-feet
restriction and authorizes this hand workstream. The latest user direction
authorizes the coordinator's automated client tests after the complete body is
ready; the hand worker performs no client operations.
The coordinating worker owns scheduling, shared tools, native compilation and
cumulative packaging. This workstream owns `purposebuilt-hand-pilot-v1` and this
record; no worker purge or game-client operations are permitted.

## Current hand selection and completed handoff

**Both hands are selected offline, compiled by the coordinator and independently
verified in native format.** The latest user direction, "please wrap the hands
up soon, they don't need to be perfect," ends further cosmetic source trials.
Keep the current five-digit silhouette, curled grip and selected fitting.
The coordinator completed cumulative packaging, offline review and three actual
client runs with this pair. Both full-body animation sheets are complete.
See [the final delivery](phenotype-human-male-delivery.md). The hand worker itself
performed no client operations; no further hand trial is required.

All pilot paths in this record are beneath
`D:/srwt/codex/f0b3/SRN_HAKS/output/phenotypes/purposebuilt-hand-pilot-v1`.
The current pair is:

| Native replacement | Selected geometry | SHA256 |
| --- | --- | --- |
| `pmh0_handl001` | `left-uniform-stock-v1/placed-local.glb` | `a65969da012dc41661747f76e2585286e2e4f3cfad9fffcd852948694ea4fc0d` |
| `pmh0_handr001` | `right-uniform-stock-mirror-v1/mirrored-local.glb` | `58d803f87abaac491be54201aba9daced6b08096898af61aefade314327c5fc1` |

The immutable offline selection is `selected-offline-v1/selection.json`, SHA256
`10a51a41a8ec63689357c83d16fd311a50622639e465543719ae59dbec9951c2`.
It records the handoff state before native compilation; its old remaining-root
fields are historical. The additive `selected-offline-v1/native-handoff.json`,
SHA256 `661ee9089bc35c771385de3921219266d975ea6f8c8669cb0526ae5645ad18a9`,
pins the subsequent actual compile, material and independent native receipts
without rewriting that selection or changing either stage configuration.

Final clean texture job `3565bc47-42b7-4e91-a4ce-9c9e164058f3` completed once in
`human-male-complete-goal-v1/clean-hand-retexture-v2`. Its textured master SHA256
is `b5f12e349814fef7c70d87655c216eddf5138abd5b3476c205dbde5723018493`.
The fresh 49,990-face compact has 2K color/normal/ORM maps and a fresh AO bake.
Actual final history association, rather than the pending UV observation,
authorizes both fitted descendants. UV-master to textured-master positions,
faces and UVs are FLOAT32 exact. The UV-save contains no authored N/T; the
final welded normal reconstruction was measured rather than assuming absent
attributes were preserved literally.

Fitting uses one positive uniform scale `0.16561695430321036`, source wrist
anchor NWN Z `+0.39`, and a proper `19.326583956217448` degree rotation about
the measured stock weapon-shaft direction. An explicit source chirality
reflection precedes this proper fit; it reverses winding and tangent handedness.
The right hand is an exact detached mirror through the actual stock frames,
with independently checked asymmetric held-node offsets. No fitting mesh edit,
extra X/Y shrink, stock attachment edit, animation edit, height change or
equipment resizing was applied. Map/UV bytes and normal/tangent magnitudes
remain unchanged by fitting and mirroring.

Independent wrist proof compares the actual selected forearms and hands over
243 sampled stock poses and 4,374 comparable contact rays: zero new gaps,
zero exclusions and minimum occupied overlap 28.416955 mm. The interval checker
retains all occupied finger/wrist intervals and selects the actual wrist
segment; it does not bridge empty space or stretch an interval. Evidence:
`purposebuilt-forearm-pilot-v1/hand-shell-diagnosis-v1/final-hand-pair-wrist-local-intervals-v1.json`,
SHA256 `d53a941e9e75320477bfb54681295be7b82bad0b1641e1de6289ed61ffe9bf8d`.
Six bind clay views, four actual-texture wrist views, and representative actual
longsword/shield views at maximum sampled wrist and held-node rotations were
visually reviewed. The 32 captures for each extreme pose remain available;
only representative captures were spot-reviewed, not every view.

The coordinator's independent native audits are
`human-male-complete-goal-v1/handl-native-audit-v1/audit.json`, SHA256
`3b5337fdf1747cff10153a2c27b83b3d4354e2ce072bfa41c118e5718c5b0a60`, and
`handr-native-audit-v1/audit.json`, SHA256
`e908437c9305807246dd805ba31f87a655603b5aa29f263d94b81731fe61a582`.
Both compiled meshes have 49,990 triangles and 32,033 native vertices.
Positions, authored normals and UV corner arrays are FLOAT32 exact with no
UV rounding allowance. Native tangents are finite and unit within FLOAT32
precision; maximum absolute tangent/normal dot is `2.0410624e-6`, with valid
complementary mirrored handedness counts and zero degenerate UV triangles.
Compile-time material dependencies and declared final PLT/normal pixels are
exact. These transport proofs do not establish client visual acceptance.

Current materials are root-owned `hand-effective-materials-v1`: measured skin
offset -9 matches the actual selected forearm 20 mm wrist band (hand calibrated
mean107.5448, forearm107.4186). Fresh bounded AO uses strength0.35, maximum
darkening12/brightening3 shades and an explicit +Z wrist-plane 20 mm protection
band. Normal strength stays1; ORM green supplies native linear roughness.
The material-operation receipt SHA256 is
`56530d0c468c8f0049f2bda410a0b985f20427533b876be37abb065c10842132`.
Raw GLB preview colors/gloss are not the calibrated native material result.

Practical limits retained under the user's current scope are eight tiny compact
crossing pairs (maximum about0.624 mm at the actual fitted scale), one QEM
pinched vertex link, and the selected forearm cap showing through the front
wrist crown in some extreme poses. Edge boundary/nonmanifold/winding and
degenerate counts are zero, but this is not an all-intersection/all-link clean
claim. The unchanged stock held-dummy rotation can sweep the shaft diagonally
through the left palm at the sampled73-degree extreme; the stock mitten also
penetrates. Bind gripping anatomy and both weapon alignments are acceptable
for complete-body/client review. Do not enlarge the whole fist to seek a
collision-free stock-animation result or alter the approved forearms.

## Reusable current method

Use stock attachment frames and real equipment first; generate coherent six
orthographic views with four curled fingers and one thumb. Freeze actual image
lineage and normalize with shared magnification. Inspect the new donor's anatomy,
geometry and maps, then proceed with ordinary fitting when sound. **Do not assume
future hands will repeat this round's defects.**

Only an observed defect warrants deeper raw/remesh tracing or a corrective
operation. This Human donor's SAT512 exterior recovery, two-cell leak patch,
sub-pitch fairing, authored-normal lowpass and special fresh-bake graph are
case-specific recovery history, not the default hand pipeline. Do not preselect
those operations or inherit their parameters for another donor. If a normal-only
correction is actually justified, prove its residual-corner identities rather
than comparing defect counts alone. Rejected outputs remain excluded from the
selected Human package, without predicting future generation outcomes.

Fit visible-hand and grip landmarks uniformly, then mirror detached arrays
through actual opposite stock frames. Preserve positions/normals/UVs/maps
through staging, calibrate only new material descendants against the current
neighbour, and verify actual native arrays after compile. Closed curled fingers
produce multiple ray intervals; retain every interval and identify the actual
wrist tissue instead of excluding most cases. Keep finite offline comparisons
separate from actual engine playback. No more image/model/source-polish jobs
are pending for this hand pair, and its GPU slot is released.

## Historical evidence and applied methodology

The following sections preserve chronological measurements, rejected attempts
and the sequence used to reach the selection above. Statements such as "pending"
or "no hand pair is selected yet" describe their recorded stage; they are not
current stop conditions or instructions to replay earlier jobs. The current
selection and additive native handoff above take precedence for continuation.

## Measured stock references

Actual input bank: `output/phenotypes/purposebuilt-stock-inputs-v1/stock/ascii`.
The root `pmh0.mdl` remains SHA256
`23fc893a8d18df461052ef978f33b7805da9188546833c0620b3a6014117d45a`,
stock `a_ba` chain, height 1.9339157 m and identity equipment scale.

`stock-measurement-v1/measurement.json` records actual triangle sections and
attachment matrices. Both hands have local extents 99.1481 × 119.5648 × 165.7961 mm.
Stock is a closed 16-triangle mitten proxy; detailed five-digit anatomy must be
independently inspected rather than inferred from that coarse resource.
The wrist-axis interval overlap with the stock forearm is 36.7484 mm; this is
an interval measurement, not a complete moving surface coverage test.

| Equipment child | Local translation from hand mesh attachment |
| --- | --- |
| `lhand` from `lhand_g` | -15.3355, -0.000201464, -94.5176 mm |
| `rhand` from `rhand_g` | +11.0681, 0, -96.1281 mm |

Both bind rotations are identity. These children are not perfectly symmetric:
the reflected left origin differs by 4.2674 mm X and 1.6105 mm Z from the actual
right origin. Preserve the exact rig and verify held-equipment alignment on
each side. Actual stock weapon and shield geometry, including animation-driven
child rotations, still need comparison; dummy axes alone do not prove a grip.

`held-animation-measurement-v1/measurement.json` independently evaluates 25 stock
clips at five phase samples for each side. Held-child translations stay fixed
to bind within 6e-13 mm, but their rotations differ by as much as 73.006 degrees
(`2wslashr`, left hand, phase .5). `xbowr` differs about 40.269 degrees. Wrist
rotation relative to its forearm reaches 141.727 degrees in this broader sample
set. Keep the measured grip center and inspect genuine item orientation through
these motions; a constant bind handle direction alone cannot cover all cases.
These are finite ASCII-controller observations, not engine playback evidence.

The actual installed normal longsword and small shield are now extracted by the
coordinator with empty overrides and pinned installation/tool evidence.
`equipment-measurement-v1/measurement.json` measures transformed model nodes:
the longsword's eight shaft vertices run along local **+Y**, with end centers
at Y -145.5538/+84.0765 mm and X/Z diamond diameters 39.5254/46.2448 mm.
The shaft center is X +0.422283/Z +0.168167 mm from the weapon root. A guessed
local Z handle would have been wrong. The shield has a transformed disk and
closed `Box07` strap; inspect its actual geometry rather than inventing a
cylindrical grip. Detailed posed coverage remains pending the generated hand.

## Image design and scheduled reconstruction

Nearly closed gripping fingers, one credible thumb, four fingers, neutral wrist,
ordinary closed short wrist end, no pointed taper and no held item in source.
Skin lighting keeps restrained crease definition without hard cast shadows.

The built-in image generation skill produced and retained several attempts.
`image-lineage-v1.json` records sources and prompts. Initial axial panels drifted
into oblique and duplicated side views; those attempts are rejected. A dedicated
two-view axial reference then corrected the six-view sheet. v3 axial apparent
magnification was excessive; v4 corrected it through image generation, not
independent normalization stretching.

First-trial references: `image-design-v4/source.png`, SHA256
`fd7e26b3ecfb22cfba3fee6d75ed399b1e44c7c60bd2d6d27880c8532801744a`.
`normalized-v4` preserves six full silhouettes at one isotropic scale and
centered framing. Side heights range 473–493 source pixels; front/back widths
348/378 and axial widths 325/342 remain an AI consistency limitation. These
are intended orthographic observations, not a calibrated scan.

`hand-generation-config-v1.json` and `model-job-request-v1.json` declare the
genuine orthographic six-view workflow, 50K triangles, 1024 shape resolution,
2048 maps and frozen camera dependencies. The coordinating worker copies the
references into the requested original `reference_images` directory. Actual
`reference-copy-audit-v1.json` verifies 19 current files byte-for-byte; its SHA256
is `ec8f51880d511bb8417d78aec49b2c53bcd6b274563f05b6084f221596e45e40`.
The coordinator submitted one hand job `71eb4493-b634-4ae2-b3a7-b78977bd9382`
in `comfy-v1`, preparation SHA256
`0c7b37478a19d4e7d791f3a52d476ded58da7fa882563af199f6e10451a5b726`.
Inspect that job's actual receipt/history before any recovery or retry. Its
four collected masters were inspected and have topology defects, as recorded
below. Remeshed/compact outputs have paired walls; raw signed volume alone does
not establish raw occupancy. A successful job does not establish hand adoption. The worker
never changes queue state or restarts the service.

Owned `place-hand-v1.py` prepares explicit source/job/stock-frame bound similarities
with ordered corner and original BIN/map proof. It permits an explicit,
anatomically evidenced source-chirality correction only if actual generated
hand sidedness contradicts labels, reversing winding/tangent sign. Sidedness is
still unconfirmed before reconstruction: source image labels cannot establish
it. A proper rotation must never be substituted for a required reflection.
`review-hand-cpu-v1.py` provides read-only orthographic clay views without local
GPU contention; it does not simulate authored texture/normal maps or native
palette shading and does not replace full geometry audits.
`measure-wrist-skin-v1.py` prepares read-only actual staged 2K native-UV band
calibration against the current effective new forearm material. Four bilinear
samples per triangle retain area weights and skin-layer checks. No old stock
hand/forearm shade offset is inherited; a selected offset needs fresh measured
evidence after both current donors are staged. Calibration includes hidden
surfaces and does not itself establish visible or client palette acceptance.

## Rejected first donor and current second trial

The first textured source is SHA256
`3427fcc382c498c078585e04fd79654bc8aa6a664bc0d2884910101e6a140fc9`.
Its four fingers and thumb are recognizable in twelve orthographic clay views,
but exact sections expose paired inner/outer walls through the wrist and palm.
The central gripping corridor is largely fused. All four saved levels have
topology defects; paired walls are established in the remeshed/compact source,
and raw winding makes its signed-volume interpretation unreliable:

| Master | Faces | Components | Boundary edges | Nonmanifold edges | Signed volume / AABB |
| --- | ---: | ---: | ---: | ---: | ---: |
| Raw | 5,696,638 | 412 | 45,780 | 43,732 | 2.317% |
| Remeshed | 1,543,742 | 1 | 5 | 237 | 3.267% |
| Shape | 49,916 | 1 | 5 | 46 | 3.259% |
| Textured | 49,916 | 1 | 5 | 46 | 3.259% |

`all-master-topology-v1/index.json` binds the actual generation outputs and
read-only reports. The raw source also has 1,402,525 inconsistent winding
edges. `source-full-audit-v1/audit.json` checks every textured triangle and
finds no positive-length/area crossing, but 318 faces have at least one
negative authored-normal corner. This does not authorize recomputing all normals.
`source-grip-measurement-v1` contains exact plane sections; the apparent dark
triangle speckles in the CPU clay view are not evidence of a duplicate mesh
instance. Source maps and geometry remain unchanged.

Conservative 256/384 exterior flood diagnostics pass analytic solid/shell
fixtures but leave 13,322 source faces unresolved at 384. No face selection,
repair or native promotion follows from those labels. The remeshed/compact
source is rejected; no thousands of unresolved exterior edits are adopted.
The untouched raw source remains available for a controlled meshing experiment;
raw signed volume is not proof of an already hollow master.

The v5 reference edit opened the C grip channel, but the user rejected its
bottom-right image because the duplicated finger/nail row looked wrong.
`model-job-request-v2.json` was never submitted. A targeted v6 axial correction
removed that row; alpha haze then caused original normalization to fail.
Built-in background extraction produced v7, followed by v8 uniform image
magnification correction of the distal panel. All sources and exact prompts
remain separate. Built-in edit invariants are requested, not byte-exact; every
result requires a fresh six-view review.

The v8 distal view still resembled an oblique dorsal view, with long finger
shafts and a dorsal hump. The user also identified only three non-thumb tips
in its top view. v9/v10 attempted compact distal domes with a thumb on the
wrong image side because the worker substituted a generic bottom-camera
convention for the actual adapter. These references and requests v2–v5 were
**never submitted**. Their incorrect camera claims remain historical receipts,
not current design inputs. v10 did establish four distinct top fingertip/nail
forms plus a separate thumb.

The concrete camera correction uses the frozen installed adapter and upstream
orbit formula, not a generic Blender camera. `polar-angle-evidence-v1/review.json`
records proper camera rotations and an explicit projection fixture: world
point [.2, .1, .3] becomes top [75, 45], bottom [75, 65] at resolution 110 and
span 1.1. **Both polar views project world X to image right; world Y reverses.**
The thumb therefore stays on the same image-X side. Actual adapter SHA256:
`b7a8605b71ae1cde49a7abf6ea8feec1ee6eeb1cb5055c4dae6c7bbeb248b3e1`.
The earlier `review-hand-cpu-v1.py` uses generic diagnostic cameras; its bottom
camera is not evidence for this actual workflow contract.

Disposable true-axis renders of the rejected donor were used only as camera
and folded-finger angle evidence. `image-distal-design-v1` converts that end
projection to skin; no rejected model geometry or maps were adopted. The end
view has a coherent curved band of four foreshortened folded fingers and a
wrapping thumb, rather than disconnected domes. v11 composited this insert
into v10; alpha haze joined the silhouettes and failed strict normalization.
v12 background extraction restored separate silhouettes. v13 corrected the
remaining distal picture magnification through built-in image generation.
The intermediate `image-axial-design-v2` attempt failed into front-like views
and is unselected. Every source and exact prompt is retained separately.

The coordinating worker reviewed **v13** against the actual angle evidence and
accepted it for a reconstruction trial, not for hand adoption. Current request:
`model-job-request-v6.json`, SHA256
`0fd2fea7f5a18bda25963fe7be2c2c551874b6f1bd33795525d15b28cf5d04f3`.
Current sheet: `image-design-v13/source.png`, SHA256
`b1edc30c08e9f8650d3da39c6fe155833a6a8a1405e31808e0e4928ae13d79ab`.
`normalized-v13` passes six complete alpha-component and clipping gates using
one shared isotropic scale 1.792 and bounds-centred translation. Source side
heights are 478/500/480/494 pixels; front/back widths are 370/409 and top/bottom
430/392. Top is 5.13% wider and bottom 4.16% narrower than back; front/back
widths still differ 10.54%. These AI observations are not a calibrated scan.
Repeated edits also drifted fine skin appearance, so requested panel invariants
must not be reported as byte-exact preservation.

`image-lineage-v6.json`, SHA256
`278f6b079daa1fbcb0109f1d58619f38d148e5ed188433bd97d33a6ec89489c8`,
binds all edited parents, prompts, actual camera evidence and corrections.
The external-copy bundle also includes original ancestor images and existing
normalization receipts. Fresh `hand-generation-config-v6.json`, SHA256
`7d4e338d5507a9df6db066305c1a1aaec4c595df212b9b6b98cc4c636f922e5c`,
uses seeds 67/68/69 and retains the frozen six-view workflow, 50K budget and
2K maps. The coordinator alone copies external references and submits once;
`submitted:false` describes preparation and must not substitute for live queue
history or a generation receipt. Inspect collected anatomy and all four master
topologies before any fitting. No hand pair is selected yet.

The coordinator subsequently copied 87 current-reference and ancestry files
byte-for-byte to
`D:/source/repos/SRN_HAKS/.tools/reference_images/human-male-muscular-purposebuilt-hand-v6`.
`reference-copy-v6.json` reports a passing exact-copy audit. The second trial
was submitted exactly once as `d6d729af-2cd1-4fe7-b223-71d01fcbc7f3` in
`comfy-v6`; check its actual `generation.json` and service history before
recovery. No worker submitted or retried this job. Collection and donor adoption
remain separate gates.

The job completed and all four actual masters were collected. Textured SHA256:
`02d51a168c6cf40ad49c10066ed638c3bb2159d5f1c1e02630acc5e8b1b84b0d`.
`all-master-topology-v6/index.json` binds these untouched outputs:

| Master | Faces | Components | Boundary edges | Nonmanifold edges | Signed volume / AABB |
| --- | ---: | ---: | ---: | ---: | ---: |
| Raw | 7,811,200 | 602 | 64,915 | 61,328 | 2.014% |
| Remeshed | 2,109,528 | 1 | 0 | 256 | 3.670% |
| Shape | 49,962 | 1 | 0 | 21 | 3.648% |
| Textured | 49,962 | 1 | 0 | 21 | 3.648% |

The raw source also has 1,938,775 inconsistent-winding edges. Low signed volume
alone is not a reliable shell diagnosis. `source-grip-measurement-v6b` supplies
exact triangle-plane segments, plots and diagnostic loop areas: wrist Z
.1/.2/.3/.35/.4 contains two closed contours with inner/outer area ratios
94.2–95.4%, leaving only 4.6–5.8% annular material. The X=0 longitudinal
section also has a 94.23% inner/outer area ratio. This independently confirms
paired thin walls without relying on triangle winding or painter speckles.
The earlier empty `source-grip-measurement-v6` directory belongs to a failed
plot invocation; only v6b is complete.

Twelve CPU clay views and eight bounded EEVEE color views in
`source-clay-review-v6` / `source-color-review-v6` show recognizable four curled
fingers, one wrapping thumb and improved axial anatomy. Color materials have
strong wrinkled/pink detail; source-material refinement remains separate from
the geometry diagnosis. Color rendering uses display-only positive uniform
scale and translation, retaining imported source maps, with no model export.
No fit, source repair, reflected hand, native hand or final hand selection has
been produced. The coordinator withheld adoption and further image/job changes
pending actual meshing-cause diagnosis. Do not carry this source into the final
body merely because its reference images or visible exterior improved.

An independent raw-versus-remeshed ray diagnosis by the forearm worker now
finds two broad raw wrist hits, while UDF remeshing creates four closely paired
hits offset about .0026 source units. The current evidence identifies the UDF
two-offset meshing step as the shell cause; it does not establish that the
untouched raw hand has a thin shell. Exact manifold-only adjacency still leaves
the compact hand as one component, so dropping separate enclosed components
cannot resolve this connected shell. The coordinator is evaluating a controlled
same-raw SDF experiment. Preserve raw anatomy as potential input and defer
fitting until a sound remeshed/retextured candidate passes fresh gates. Historical
v6 configuration statements claiming all master levels were hollow overstate
the evidence and must not be copied into future current configurations.

`source-full-audit-v6/audit.json` checks the entire current UDF compact source:
21 nonmanifold edges, five positive-length/area triangle intersections, and
442 negative authored-normal corners across 363 faces (nine all-negative).
Authored normal lengths remain unit within approximately 4.3e-8. This is a
rejected compact-source baseline; a replacement remesh and texture must receive
its own fresh audit. These observations do not authorize global normal changes.

The same-raw SDF diagnostic was submitted by the coordinator exactly once as
`61d42751-47dd-45e8-aea1-40cbd56b49ef`. Its untextured master is
`human-male-complete-goal-v1/same-raw-hand-sdf-trial-v1/generated/sdf-remeshed-master_00001.glb`,
SHA256 `400deaad37c71c7ce13bf5b19fff31b67773ff613f32054191eb034642b23821`.
Independent `same-raw-sdf-frame-review-v1` finds the envelope and five-digit
anatomy generally retained but heavily speckled geometric-face views. The
master has 1,615,578 faces and no authored normals. The independent topology
gate finds 246,389 boundary edges and 73,065 nonmanifold edges; it is unselected.
Raw hand and solid-control raw forearm also lack authored normals, so an
authored-normal-guided winding correction is not available. The coordinator and
forearm worker are evaluating winding-independent surface voxelization and an
exterior flood. See [the meshing diagnosis](phenotype-hand-shell-diagnosis.md)
for actual raw/processed stage evidence and current recovery experiment.

`grip-pocket-rays-v1/measurement.json` provides 169 exact winding-independent
X-line intersections around the observed C opening. Twenty-two complete axial
lines are clear in the compact source, including source NWN [0, -.05, -.175],
equivalently raw glTF [0, -.175, +.05]. Nearby clear lines and tissue controls
are retained for independent opening preservation checks. The first visually
estimated deeper pocket at NWN Y+.02/Z-.20 was partly blocked axially by finger
surfaces; the corrected datum comes from actual intersection measurements.
These finite rays do not by themselves prove full volumetric occupancy, a
particular handle clearance or native equipment acceptance.

Read-only `texture-graph-discovery-v1` freezes actual installed node schemas and
the original v6 bake graph. A supported retexture path must keep the original
multi-view/shape/texture latent ancestors because texture decoding requires the
shape subdivisions; those hidden latents were not saved. Final geometry can
instead come from an exact loader of a separately gated clean high-poly mesh.
Use fresh decimation, smoothing, UV unwrap and color/ORM voxel bakes, with fresh
normal/AO bakes against that clean high-poly. The old UDF tangent-normal atlas
must not be attached blindly to new UVs. No dispatchable retexture request was
prepared on the failed SDF master. Freeze a concrete clean-source ancestry and
supported graph before the coordinator submits a later texture job.

The parameterized recovery graph is now frozen in
`clean-retexture-template-v2` and is **not dispatchable**. Its builder is
`prepare-clean-hand-retexture-v1.py`; current template preparation checked
41 nodes and 68 links against the live installed schemas without changing
the queue. The first template is retained unsubmitted history.
The original six image inputs, conditioning, samplers and neural texture
subdivision ancestors remain exact. Node 241 now denotes an exact
`Load3DAdvanced` → `Get3DComponents` clean exterior, and no `RemeshMesh` or
historical raw/shape save survives the final output closure. Direct map links
replace unnecessary preview pass-throughs. New decimation, smooth authored
normals and UV unwrap feed 2K base color/metallic/roughness, a fresh 2K normal
bake and a fresh 1K AO bake. Both normal and AO use the same gated high-poly
source; normal strength remains 1. Save outputs are `textured` and `uv-master`.
The latter retains the actual new UV/normal geometry before material assembly.
Final export comes directly from `ApplyTextureToMesh`, which supplies the
normal and tangent basis used by the bake. The current graph omits redundant
post-bake node 260. This is a new-hand method simplification, **not a measured
defect in the existing accepted arms**. Original smoothing reproduced their
shape normals exactly. Unwrap does discard the incoming normal attribute,
but the installed fallback computes position-welded normals across UV charts;
it does not introduce the initially suspected chart-local shading basis.

`original-master-basis-audit-v1/measurement.json` measures the actual hand v6,
upperarm v1 and forearm v1 masters without changing them. All three have exact
oriented geometry associations and FLOAT32-exact shape/textured corner
normals: respectively 149,886, 149,982 and 150,000 corners. Shape masters have
no UV or tangent attribute, so literal shape/textured tangent equality cannot
be claimed. An independent FP32 reconstruction of the supported welded bake
fallback differs from actual final normals by less than 0.00001 degrees;
reconstructed tangents differ by less than 0.000081 degrees for the hand and
0.000013 degrees for either arm, with no handedness differences. GPU scatter
order is not claimed bit-exact. Actual tangent/normal dot products are bounded
by 1.11e-6 for the hand and 2.1e-7 for the arms. No substantive basis mismatch
was found, and this investigation does not justify altering accepted arms or
neighbour resources. Future graphs should preserve the bake basis explicitly
and measure any suspected recomputation before describing it as a defect.

Instantiation requires a fresh output directory and an explicit
`source-contract.json` matching the template contract. It pins byte-identical
local and server geometry, the original raw ancestry, reviewed topology,
single-exterior, grip-opening, anatomy and frame gates, and at least three
actual hashed receipts. Known raw/UDF/failed-SDF masters are refused as final
geometry. The annotated Comfy path must resolve to the pinned server file;
installed implementations and six references are checked again. The builder
does not submit. Root can prepare with the bundled Python:

```powershell
& 'C:/Users/benco/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' `
  output/phenotypes/purposebuilt-hand-pilot-v1/prepare-clean-hand-retexture-v1.py instantiate `
  --source-contract output/phenotypes/purposebuilt-hand-pilot-v1/source-contract.json `
  --output output/phenotypes/purposebuilt-hand-pilot-v1/clean-retexture-prepared-v1
```

The source contract records reviewed evidence; it does not substitute boolean
claims for the attached measurements. Unsaved neural latents may recompute
when cache is unavailable, so resulting colors must be reviewed. The loaded
clean exterior remains geometry authority regardless of neural replay. After
the job, audit the actual decimated/UV-serialized output rather than assuming
that a sound input guarantees a sound compact result. Native tangents and
skin/AO integration remain separate root gates.

## New reconstructed exterior and bounded ridge fairing

Root's selected recovery candidate is the original-coordinate SAT512 exterior
with two measured microleak cells added before flood extraction, retained in
`human-male-complete-goal-v1/filled-exterior-512-mincut-v1`. Its immutable
marching-tetrahedra high-poly is SHA256
`d955864c9184a210d0ad9997006576bcb3e6adcdc8b4ecfc46dce410e15c4c9b`:
2,914,088 vertices and 5,828,260 faces, zero boundaries/nonmanifold edges/
inconsistent winding. New area-weighted normals accompany the untextured
identity-node GLB. No raw, historic painted master or accepted body resource
was edited. Independent forearm evidence finds all vertex links single cycles,
all four core grip lines open, 21/22 whole-clear lines with the explicit
marginal quantization exception, and maximum raw-envelope distance .003378137
source units. Root retains that independent evidence with the recovery chain.

`clean-exterior-512-anatomy-v2` contains eight authored-normal clay views using
the actual polar camera convention. The first light setup was clipped and
remains exposure-rejected v1 history. The user said these new clay hands
"look much better"; preserve their macro anatomy, four curled fingers, thumb,
C grip opening and ordinary cap. That visual feedback does not accept final
maps, stock fitting, equipment or client behavior. The high-poly still showed
voxel contour ridges, which must not be blindly encoded into the normal atlas.

The coordinating worker authorized bounded fairing of this **new unselected
reconstruction**, not any authored accepted part. `fair-reconstructed-hand-v1.py`
retains exact face indices, freezes the cap plane and its one-pitch band, and
freezes all triangle vertices within two pitches of each core line's exact
nearest surface. Each Taubin step is clamped to no more than one 512 pitch
(.001953125 source units) from the original MT position. Fresh area-weighted
normals are computed after fairing; no UV/maps exist yet. Reject any source
change, protected-vertex displacement, core-clearance change, face flip,
degenerate face or unacceptable volume drift, then independently repeat the
source-envelope and tissue-ray gates.

The first three-pair candidate `clean-exterior-512-fairing-v1` moved at most
.000484562 units (0.248 pitch), retained all cap/grip guards exactly, had zero
flips/degenerates and volume ratio 1.000005271. Independent forearm proof
improved its maximum raw-envelope distance to .003179394 and found all five
principal and ten companion wrist rays with exactly two hits. Its four
`clean-exterior-512-faired-anatomy-v1` clay views still show visible contour
lines, so it remains unselected. The fresh 12-pair candidate from the **same
immutable MT input**, `clean-exterior-512-fairing-v2`, uses identical
λ=.5/μ=-.53 parameters, global one-pitch bound and guards. Its SHA256 is
`feb84aa43e2c7963bf099c3f5b9040f23f2695ae02400405b23bc6303e90a7d6`.
Maximum displacement is .0010833803 units (0.555 pitch), with zero flips or
degenerates, fixed faces, exact protected cap/grip vertices and volume ratio
1.00001847. Independent every-vertex envelope and ray proof passed: maximum
raw-envelope distance .0031793944, five principal and ten companion wrist
rays with two hits, all four core grip clearances exact, and the same explicit
21/22 marginal-line exception. The independent transport receipt is
`purposebuilt-forearm-pilot-v1/hand-shell-diagnosis-v1/faired-exterior-512-transport-v2/measurement.json`,
SHA256 `da294928af0fa0c12bfbf21f11127a7894edf4e9081e7a8ccbd6d37b05152e72`.
Its four moderate clay views preserve the approved macro anatomy but still show
fine voxel contour lines. Do not chain displacement bounds from v1 or weaken
normal-map strength to hide source noise.

The coordinator therefore authorized a **normal-field-only** trial on v2.
`smooth-reconstructed-hand-normals-v1.py` uses actual manifold-edge adjacency,
half self plus half neighbour mean, unit renormalization and a spherical
35-degree clamp from the original v2 normals at each step. P/F remain
byte-exact; all 102,040 flat cap-band normals remain exact. Twelve steps reduce
noncap adjacent-normal RMS from 16.123585 to 4.170979 degrees. Median/p95
change is 12.27152/29.00490 degrees; maximum serialized change is 35.00000235
degrees, within the explicit FLOAT32 angle tolerance. One tiny concave
triangle initially acquired three inward corner normals. Its three vertex
normals were restored to the original field before serialization. Final
geometry has zero wholly inward-normal faces; no source geometry was edited.
The later independent corner-identity check found that equal negative-corner
counts did not imply the same negative corners. That stronger check is now
required; never infer an unchanged set from a matching count.

The resulting high-poly `clean-exterior-512-normal-polish-v1/normal-polished-highpoly.glb`
has SHA256 `39b4b3b3a040f5c35cfd465a84631b894fccfc363060c25864b6f2459d5912af`.
`normal-polish.json` records field changes, cap guards, corner orientation and
all metrics. Independent transport receipt
`purposebuilt-forearm-pilot-v1/hand-shell-diagnosis-v1/normal-only-transport-v1/measurement.json`,
SHA256 `235f8b32e0778a5b567f091c4f536a63f6b5218bca7aa2630f2521ed38bb32bd`,
confirms exact P/F, unit N, cap N, bound and orientation. Its four moderate
`clean-exterior-512-normal-clay-v1` views visibly soften the contours while
preserving the five-digit silhouette; some fine contour lines remain at this
enlarged viewing distance. This meets the trial's measured RMS target; it is
not a claim that the final normal atlas, compact geometry or client is clean.
No texture or normal-strength adjustment has been applied. The installed
normal baker consumes authored high-poly normals, so fresh baking must use
this actual gated field and never the old UDF normal atlas.

The final fresh field `clean-exterior-512-normal-polish-v2/normal-polished-highpoly.glb`
has SHA256 `57a01f46487c94a5a03f8bcfc255dcd706e4796c8ab724bbbe8cac694963f494`.
`guard-negative-hand-normal-corners-v1.py` restores exactly one additional
vertex normal (vertex2654360) to v2's original field. It was on a tiny
4.35798643e-7-area triangle and had become grazing-negative (dot -0.002568806).
The final negative corner IDs [3111636,3111637] are a strict subset of the
original [3111636,3111637,5031865], with no wholly inward-normal faces. RMS is
4.171064 degrees. P/F, cap N, all unrelated field values and the 35-degree
bound remain unchanged. v1 sources, copy and instantiated graph remain
**unsubmitted history**. A fresh v2 source contract, server hash path,
preparation and output prefix are required; never modify the old preparations.
The retained v1 clay captures differ only at the one listed restored vertex;
the coordinator reviewed them as sufficient for the fresh compact/bake trial.
Fresh compact topology, bakes, fit and client evidence remain mandatory.
Independent final field transport and corner-subset receipts are
`purposebuilt-forearm-pilot-v1/hand-shell-diagnosis-v1/normal-only-transport-v2/measurement.json`
(SHA256 `dffd996afadf3e63577a186cda5f06e44a9857db740207c174a1f8f6822bd8e5`)
and `normal-only-concave-corners-v3/measurement.json`
(SHA256 `abaf0a2b39c88b4a1a00391a343334a8e939f8d99fccf9067b8b38a39f1a1f4f`).
Check actual paths from their receipts when composing the final package.

The user's latest direction is to **wrap the hands up soon; they do not need
to be perfect**. This supersedes further fine cosmetic source iterations.
Preserve final N-v2, complete the fresh compact/texture trial and stock fit,
then check obvious anatomy, solidness, both wrists and actual held items.
Do not let speculative micro-defects delay whole-body assembly and client
testing. Invalid geometry still requires correction. Root submitted the
fresh 2K/50K retexture exactly once, job
`3565bc47-42b7-4e91-a4ce-9c9e164058f3`, in
`human-male-complete-goal-v1/clean-hand-retexture-v2` with hand pilot preparation
`clean-retexture-prepared-v2`; prior preparations remain unsubmitted history.

## Actual bitmap ownership and denser moving frames

Stock hand model001 references bitmap003. The real installation's two
`pmh0_hand[l/r]003.plt` files are identical, SHA256
`559ea21a2c3cb444b065483cbc33926762b68784f6cac5a5b16a81d7d83d8db5`.
`stock-texture-ownership-v1` uses those actual 64×64 texels and native UV faces
in diagnostic grayscale. Left palm creases are on +X and dorsal tendon art on
−X; the thumb side is +Y in the stock front convention. The first generated
hand has palm −Y, thumb −X and distal −Z. The signed triple-product chirality
differs from the stock left interpretation: a proper rotation alone cannot
correct it. Any canonical left fit must explicitly record a necessary source
reflection, winding reversal and tangent handedness, followed by proper
rotation. Determine this again on the new donor rather than inheriting labels.

`wrist-motion-dense-v2/measurement.json`, SHA256
`3571898a938b6b98880e1eb136386290e09765d472060f7242981ba5994a98c4`,
contains 27 clips × nine phases (243 cases), both actual forearm, hand and
equipment world matrices and `forearmToHandLocal = inverse(hand) * forearm`.
The maximum 141.727-degree wrist angle occurs at right `1hslashl`, phase 0.75.
The forearm worker uses this shared archive for serialized moving wrist checks.
These remain finite controller samples, not engine playback or continuous proof.

`stock-grip-envelope-v1/measurement.json`, SHA256
`09646516d00eec10097dcd0dd2597b00db561c60054a56f742cd6828f45d534c`,
measures actual longsword-shaft centerline intersections with both stock hand
meshes in all 486 side/pose samples. No intersection parity was ambiguous.
The centerline lies within 108.47–130.91 mm of the solid stock mitten; stock
intentionally lacks detailed finger/channel geometry. This observed penetration
is a comparison baseline, not a requirement to reproduce filled geometry or a
promise of collision-free equipment. Detailed new fingers must visibly wrap
the actual held item; independently inspect both sides and moving dummy angles.

The selected new forearm's actual wrist section is 62.762 × 59.245 mm, centred
at −35.184/+21.922 mm in its left forearm frame. Its raw native wrist shade
is 96.361; the accepted torso family is approximately 105.738–106.951.
Root's selected +11 forearm baseline makes the true wrist bands 106.681–108.015.
Use these current bands for fresh hand calibration. Historical dark stock
shades are not targets for the new hand. Selected forearm left/right geometry
is `left-proximal-taper-moderate-v1/tapered-local.glb` /
`right-proximal-taper-moderate-mirror-v1/mirrored-local.glb`; only the elbow was
edited, so the measured wrist geometry is unchanged. Root owns final material
integration and the current exact material receipt.

`selected-wrist-targets-v1/measurement.json`, SHA256
`441c2bf744111a958bd41307b7caf42bd5d0cffe72eb93b71d575a686fac321c`,
independently transforms the actual selected forearms into each exact hand bind
frame and measures seven wrist planes from -25 to +25 mm. At hand Z=0, the left
section centre is [-2.09407, -0.97204] mm and its diameters 62.76218 × 59.24485 mm;
right is [+2.09357, -0.97215] mm and 62.76236 × 59.24512 mm. Exact held-root
transforms remain independently recorded. These are concrete neighbour targets,
not a fit or a requirement to squeeze the detailed hand into the stock mitten.
A sound donor's measured wrist and grip anchors will define a positive uniform
similarity. Proper rotation about the held shaft can align the wrist-to-grip
vector while retaining the true shaft direction. Stock joints/controllers stay
untouched; no extra X/Y scale is inherited. Inspect hidden crown overlap and
actual item contact before considering bounded cap edits.

## Applied adoption sequence (retained methodology)

This is the earlier design/recovery checklist, now executed through the selected
offline pair and actual native proofs recorded above. Cumulative body packaging
and actual client validation remain the coordinator's gates; do not repeat
completed source generation, fitting or cosmetic refinement from this checklist.

The next anatomy review compares the actual clean exterior to the raw source
and accepted v13 sheet from palm, dorsal, thumb side, little-finger side and
both measured longitudinal-axis cameras. Require four coherent curled fingers,
one thumb, no extra underside digits, preserved knuckles and a usable C opening.
Compare wrist section extents and channel rays independently of winding or
signed volume. Audit all 22 measured clear source lines and require the four
central witnesses to remain open. The independent raw/compact proof measures
core clearance 0.0288228/0.0268116 source units. Both voxel resolutions retain
21 whole-clear lines; the remaining line has only 0.0001974 source-unit
compact clearance and intersects conservative surface cells while its axis
point remains exterior. Record that bounded quantization result explicitly;
it is different from filling the central grip opening. A new filling receipt must expose
any altered voxel locations and source-envelope distance; do not silently
apply closing, smoothing, inflation or component deletion. Root's 384 exterior
diagnostic remains unselected history; the 512 microleak recovery and explicit
bounded ridge fairing above are the current path. No second SDF remesh is
assumed necessary.

After the fresh compact passes its own gates, measure its wrist closure centre,
visible crown section and geometric grip-channel axis in the unchanged source
frame. Fit a positive uniform similarity from those actual landmarks to the
selected forearm wrist and actual held-root shaft; no inherited X/Y shrink is
allowed. Do not use total donor AABB length as the scale authority: the source
has a long hidden wrist crown. Existing diagnostic outer sections at source
Z+.35 and Z+.40 are about .417×.374 and .410×.382 units, while the crown extends
to +.455. Re-measure the actual clean serialized donor, choose visible-hand
and grip landmarks, and compare its collar against the 62.762×59.245 mm
forearm. An oversized hidden crown is a separate measured taper decision,
not a reason to shrink the entire hand. Source v6 palm −Y, thumb −X and distal −Z imply an explicit reflection
for the stock left palm +X, thumb +Y convention, then proper rotation. Recheck
these signs on the clean textured compact. Rotation about the held shaft can
align the wrist-to-grip vector; the source crown must remain hidden inside
the selected forearm through the dense 243-case moving archive. Compare final
digit wrapping against actual longsword diamond and shield strap meshes,
using the stock mitten's measured intentional penetration as a comparator.

Only after the left donor is geometry-selected, mirror its detached corner
arrays through the exact right frame, reverse winding/tangent handedness and
preserve embedded maps/UVs. Independently measure right held-node offsets;
the stock held roots are not perfectly mirrored. Review at least bind,
right `1hslashl` phase 0.75 (maximum measured wrist rotation) and left
`2wslashr` phase 0.5 (maximum measured held-node rotation), then all 243 cases
for serialized wrist overlap. Shared forearm checks use the actual selected
hands, replacing the earlier stock-hand comparator. Root calibrates the
new wrist skin to effective forearm bands 106.681–108.015 and verifies native
P/N/UV/tangent/sign transport before cumulative assembly and client playback.

Inspect untouched anatomy, five digits, inner palm/channel and ordinary wrist
cap before fitting. Use actual stock attachment frames and exhaust proper
rotation, positive uniform scaling and translation. Coordinate wrist sections
with the forearm donor. Bounded connector or topology repairs require measured
scope, ancestry and unaffected P/N/UV/tangent/map proof.

Mirror the perfected detached hand, reverse winding and tangent handedness,
then independently inspect the right side. Review actual stock weapon/shield
geometry through representative held poses. Calibrate new-hand palette shades
against current effective forearm maps and prepare controlled AO/roughness
without changing accepted neighbours. Actual native arrays passed as recorded
above. Cumulative offline assembly, package proof and actual client palette,
lighting, continuous motion, representative equipment, stability and sampled
performance checks are complete. The selected hand pair was present in all
three actual full-body runs. See [the final delivery](phenotype-human-male-delivery.md)
and [client validation](phenotype-full-body-client-validation.md) for exact
evidence and practical limits. No further cosmetic hand iteration remains.
