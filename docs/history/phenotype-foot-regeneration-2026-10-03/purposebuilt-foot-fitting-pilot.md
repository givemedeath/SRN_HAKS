# Purpose-built Human male foot fitting

The current offline donor is the corrected toe-contact geometry with coherent
local patch charts, shifted +3 mm anterior in the stock foot-local frame and
mirrored between the actual stock ankle frames. Its original uniform scale,
height and orientation remain fixed. The newer material request released
client access and completed material-specific native/TBN/client checks in
[material validation](phenotype-body-texture-repair-validation.md).
An extra plantar-lateral toe-shaped lobe is now an open anatomical defect under
read-only review; previous topology/package proofs do not establish correct toe
anatomy. Foot regeneration remains stopped. This fitting record does not
authorize a next part or claim anatomical game acceptance.

## Stock dimensions and ownership

The actual resources are `pmh0_footl001` attached to `lfoot_g`, and
`pmh0_footr001` attached to `rfoot_g`. Stock native front is +Y, up +Z, and
anatomical left is -X. The left foot's medial/big-toe side is +X. Do not infer
source orientation from earlier generated limbs.

| Left foot quantity | Measured value |
| --- | ---: |
| Width X | 122.5966 mm |
| Heel-to-toe extent Y | 297.6431 mm |
| Sole-to-crown extent Z | 163.2612 mm |
| Sole datum below ankle pivot | 136.731 mm |
| Closed crown tip above ankle pivot | 26.1562 mm |
| Stock sole vertex spread | 2.424 mm |

The left heel extreme is `[-15.7723,-61.3921,-136.731]` mm. The longest
toe-side extreme is `[14.3075,236.251,-137.105]` mm. Those extremal points
describe the stock low-poly silhouette; they are not an authored foot skeleton.
The sole datum is the median of source vertices within 4 mm of its minimum.
It is a practical datum, not a perfectly coplanar contact plane for every pose.

| Foot-local section Z | Width | Depth | Centre X/Y |
| --- | ---: | ---: | --- |
| +20 mm | 23.75 mm | 17.82 mm | -7.36/-11.75 mm |
| +10 mm | 62.34 mm | 46.78 mm | -11.22/-11.00 mm |
| 0 mm | 96.47 mm | 74.54 mm | -17.31/-9.67 mm |
| -10 mm | 100.10 mm | 90.81 mm | -18.06/-2.59 mm |
| -20 mm | 101.87 mm | 107.09 mm | -17.88/+4.50 mm |

Generate one bare left foot with heel, Achilles insertion, ankle, instep,
medial arch, ball, toes and sole. The upper end is a shallow closed skin crown
buried in the accepted shin, without a calf shaft, clothing cuff or footwear.
The stock foot is only an attachment/proportion reference; its coarse wedge
surface is not an anatomical skin projection target.

## Fixed neighbours and measured motion

The accepted shin donor remains
`purposebuilt-shin-pilot-v1/left-shin-connectors-v3-monotone/refined-local.glb`,
SHA256 `bde4b16194010cd42ad40d282512e1189c7c992a5ab6df06d0d24c27c5123ee7`.
Its right mirror remains `right-shin-v3-mirror-v1/mirrored-local.glb`, SHA256
`7efe4b5a9e85bacd1b8d23958c96fe4518e186363f5c6c8b91aed5b17b3f4e24`.
The torso, pelvis and thigh pair are fixed, as is the accepted pelvis PLT
shade correction, SHA256
`990aa66b5c642d6c45ab4f1c60ceffd732cd290b53207c9c5021698dc9181690`.
Stock root/controllers/native height remain unchanged. Human equipment scale
remains identity.

The final guide receipt is
`output/phenotypes/purposebuilt-foot-pilot-v1/stock-connectors-v2/measurements.json`,
SHA256 `dbd2ea5a15726b701138becdf97646c6b2a5685e031d35a9ff0a6559d812bdc4`.
Its section/pose archive is `source_triangle_sections.npz`, SHA256
`327769cbbc2515a80d28737a1225c9b4375ab9e98775fd8559b0e9cee490eadc`.
Eighteen front/rear/lateral/medial/top/sole guides show isolated stock left
foot, stock context, and accepted-shin context at recorded orthographic scales.
Inputs are rehashed unchanged after rendering.

Both sides are evaluated offline using actual `pause1`, `getlowlp`, `kneel`,
`walk`, `run` and `conjure2` controllers. Source triangles and real section
segments retain their parent IDs. Distal shin polygons are clipped at shin-local
Z <= -390 mm before posing into foot coordinates; using whole stock triangles
would incorrectly include most of the shin because those faces span its length.
Accepted distal-shin foot-local Z bounds vary approximately -40 to +59 mm
across these poses. This supports a buried ankle crown without increasing
the whole foot. Unsigned finite nearest-surface samples are not a containment,
complete seam or visual acceptance proof.

`stock-connectors-v1` is historical: its foot dimensions and guide images are
valid, but its stock distal-shin bounds selected whole spanning faces. Use v2
for connector ownership and motion bounds.

## Actual-source fitting

`tools/phenotypes/place_purposebuilt_foot.py inspect` requires the collected
successful generation receipt and selected source hash, stock root/guide receipt,
six accepted neighbour GLBs and accepted corrected pelvis PLT. It records actual
raw P/N/UV/optional attributes, embedded map hashes and source bounds without
mesh editing. Its template deliberately leaves the anatomical ankle anchor
unset and orientation unconfirmed. Raw glTF-to-native basis is `[X,-Z,Y]`.

Inspect toes, heel, sole and medial big toe in untouched source views first.
Measure an anatomical ankle anchor, sole-under-ankle datum and heel/toe points.
The helper's `landmark_similarity` fixes the ankle exactly and solves one
positive uniform scale/proper rotation against the other three landmarks,
with sole/heel/toe weights 4/1/1. It reports every residual rather than stretching
the foot to satisfy incompatible proportions. Alternatively record an explicit
proper rotation and uniform scale once measured anatomy justifies them. The
stock height ratio alone is an inspection proposal, not an accepted fit.

`place` produces a canonical identity-node detached GLB, original source BIN
prefix and unchanged UV/images/materials, plus authoritative float64 ordered
P/N/T corners. Normals/tangents rotate with proper R only; authored magnitudes
remain unchanged. Actual FLOAT32 serialization error and uniform triangle-edge
similarity are checked. The standard candidate/hash/archive receipt is suitable
for the existing staging adapter once later review allows staging. A synthetic
nontrivial proper rotation/scale/translation recovery and collinear-landmark
rejection passed. The actual first-fit receipt below now proves the executed
similarity and immutable source association separately from acceptance.

First offline assembled comparisons must keep all six accepted neighbours and
stock opposite foot fixed, with equal native scale/camera and real stock
controllers. Check sole/heel/toe proportions and ankle coverage in idle,
flexed kneel/crouch, walk/run and casting. After the donor is accepted offline,
mirror detached geometry through the measured `lfoot_g`/`rfoot_g` frames:
reverse winding and tangent handedness, preserve source UV/image sampling,
and independently inspect the opposite side. Never reflect or regenerate the
skeleton/controllers. No NWN client executable, CLI compiler, client process
query, UI operation, launch or client log access is permitted until the user
releases the hold.

## Current generator and first-fit evidence

The coherent four-view design is `image-design-v1/source.png`, SHA256
`51eea0acee5fd5c460348efe3e18a97e8ade7084ed56c158c4ede67a2e2fd4c4`.
`normalized-v1` uses one isotropic scale and top-aligned translation. Its
medial/lateral image widths differ by 6.42%, and normalized heights range
492–510 pixels; shared scaling does not prove four exact projections of one
3D shape. The actual mesh is the orientation authority.

The single job is `9b103b49-458d-4a54-825a-130b18b07923`, collected successfully
in `comfy-v1`. Textured source `generated/textured_00001.glb` SHA256:
`1757c79e20c7ee294082e33d4be980be7c260806a4cf32e7b6d7918d381a0323`.
All four raw/shape/remeshed/textured masters remain unchanged. The textured
source has 49,982 triangles, one component, zero boundary edges and 17
valence4 edges in toe-web/distal-forefoot contact regions. Actual source normals
also have a small localized negative-corner population. These are explicit
source defects, not a reason for global normal substitution or remeshing.

`source-attribute-inspection-v1` freezes actual raw attributes/maps. The
read-only `source-visual-inspection-v1/views` has camera +Y heel/rear and
camera -Y toes, with big toe on raw -X. Proper Z180 gives front +Y/big-toe
medial +X, confirming left anatomy without reflection. The shared read-only
inspection renderer's `front` filename means camera +Y, not anatomical front.
Its imported/computed-normal difference is not an authored-normal acceptance
test; independent raw audits own that result.

The height-first fit uses one scale `0.31872117420733903`, proper Z180 and an
inferred ankle anchor from the actual source-ring centroid minus the measured
stock section-to-pivot offset. The inference uses the 26.1562 mm hidden crown
allowance; it does not claim an authored generator joint. It preserves width
115.736 mm, length293.983 mm and height163.261 mm, without stretching or
refitting accepted neighbours. Bounds are X[-77.667,+38.069],
Y[-72.678,+221.305], Z[-137.105,+26.156] mm. Heel/forefoot lower-band mean
heights are -134.02/-136.14 mm versus stock sole datum -136.731 mm.

`left-foot-firstfit-v1/placed-local.glb` SHA256:
`a0dfa0c4723b249b819acbe18eeb338b89951b598a2171f71065f973e4a8a132`.
`placement.json` SHA256:
`ba31bc70f4738c2e7b866e74a164dba63c2000df785bcc3bd54552ed47c7668f`.
`native-corners.npz` SHA256:
`80de4cdd29412f4e408240022b64cb0e74a257807df6c952e6c192ec14d7ae49`.
This fit stays immutable while bounded descendants repair original contacts.

`left-foot-firstfit-review-v1` contains idle/kneel color+clay and running-color
comparisons: 15 full-body and 20 close images. `comparison-audit.json`, SHA256
`911fc6cddc07b46da0a241481e4d2ac8b7ba9297527b18e6af57ace5db0429a3`,
verifies six identical accepted neighbours, actual stock other parts, equal
stock joint matrices and native displayScale1. Only the left foot changes.
Close views alter cameras and display spacing only. Idle minimum world Z is
0.924 mm versus stock0.763 mm, a +0.160 mm difference. The kneel/run geometric
extrema differ +16.6/+17.8 mm from the wedge, which is not by itself a ground
contact defect for an elevated/rotated foot.

`firstfit-contact-shade-v1/inspection.json`, SHA256
`f5abae9b7602b3bc18197ee5eb92dd0b2c967568a1d731600501486d3a55d250`,
records 25 fixed ankle rays, all missing hits and source/stock comparable
sets. Gap-above1mm counts are 7/9 idle,8/10 kneel,10/10 run on paired rays.
These are finite axial tests; fewer counted gaps does not prove complete seam
coverage. Foot ankle Rec709 shade mean114.11 versus adjacent shin106.08
suggests a possible small native shade-index correction later. Source maps
remain unchanged; Blender color previews do not simulate palette/native
lighting. This fitting work changes no map pixels or material properties; any
separately authorized native PLT shade correction has its own runtime receipt.

The first contact-repair descendant `left-foot-contact-repair-v1`, SHA256
`f400c12f20bf1f680d6967a2b8988a8b6b0789039f5d711c784399aa09513efe`,
is **rejected diagnostic evidence**: independent full tests found 14 tiny
crossings despite closed/manifold edge/link metrics, and four added triangles
cross unrelated UV charts. Its `left-foot-contact-repair-review-v1` renders
remain historical; they cannot authorize donor selection, staging or mirroring.
That rejected repair has been superseded by the verified descendant below.
Keep the first uniform scale/placement fixed unless a new measured/user
direction explicitly changes it.

## Historical clean donor and pre-shift mirror

The initial root-selected parent was `left-foot-contact-chart-v1/mapped-local.glb`, SHA256
`c36c5f999b38a0c8767b7c6761b53856638c6b7273fdfc71c8cda8aa46ac9d21`.
Its `mapping.json` SHA256 is
`0d4ed7e8fcc6493565669e7839b849109eae090dd3e56af24b07b971f2c3d986`.
It inherits the corrected `left-foot-contact-repair-v2` geometry, SHA256
`e59ff6b7144589336cf230832de0a25c1fb3faf41e678b083ccb50a490d7963c`.
The five new patch triangles use one coherent original chart with derived
tangents; all surviving attributes and original map pixels remain unchanged.
The independent index `independent-foot-audit-index-v2/index.json` binds the
generation, uniform placement, repair and chart proofs. Actual serialized
geometry has 49,974 faces, no boundaries, nonmanifold edges, winding errors,
degeneracies, bad vertex links or genuine crossings. The source's tiny population
of 141 negative authored-normal corners remains explicit; no broad normal
substitution occurred. Nine finite chart-seam midpoint samples differ at most
5.4/255 in an RGB channel; this is not exhaustive texture continuity proof.

`right-foot-selected-mirror-v1/mirrored-local.glb` SHA256:
`fb9321f669d512250b98ca74c64b65d07d2ff1ce476879ee0216285dab38a402`.
Its `mirror.json` SHA256:
`5db2aad71c9c45955652443b80bec1fc3d09b680a1a4af3c85732b1a38f66a91`.
The transform is `inverse(rfoot_g world) * reflection(world X=0) * lfoot_g world`,
which in the measured local frames is X reflection plus +0.206 micrometres X
and +0.100 micrometres Y. This mirrors detached geometry, not joints/controllers.
Triangle corner order changes 0,2,1; normals and tangent XYZ reflect orthogonally,
their authored lengths remain, tangent W changes sign, and UV/maps remain exact.
The original generated left big-toe/arch asymmetry therefore becomes the proper
right anatomy. The stock left/right source meshes themselves are not asserted
to be exact mirror copies.

The exact command/config are recorded by `run_selected_pair_v1.py` and
`right-foot-selected-mirror-config-v1.json` under this pilot. The reusable command
uses the bundled workspace Python:

```powershell
& 'C:\Users\benco\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' tools/phenotypes/mirror_stock_limb_part.py --config output/phenotypes/purposebuilt-foot-pilot-v1/right-foot-selected-mirror-config-v1.json --output output/phenotypes/purposebuilt-foot-pilot-v1/right-foot-selected-mirror-v1
```

This records the completed execution; the output must be fresh if replayed.
The fixed six neighbour sources, stock other parts and native male height stay
unchanged. Pair review inputs are `selected-pair-stock-map-v1/stock-replacement.json`
and `stock-foot-control-v1/stock-replacement.json`; the latter substitutes no feet.
`selected-pair-offline-review-v1` contains actual stock idle, kneel, walk and
casting views, with color/clay idle and kneel. Its frozen commands, equal-camera
close images and `comparison-audit-v3.json` bind native displayScale1, identical
actual joint matrices, six identical neighbours and source hashes. These are
offline geometry/source-map comparisons, not native palette, shader or game
motion validation. The corrected pelvis runtime PLT is protected but Blender
does not simulate its palette result.

The final comparison audit SHA256 is
`5e14a0012bee1d07cc29af88e1e98f8e5f0c3b24c0f44d99071f4b9c7b8ebb6d`:
18 full-body images plus 30 `foot-close-pair-v3` front/rear/lateral/medial/top
images. Each close camera explicitly checks that both feet are inside its bounds
and specimen foot projections are separated. Dynamic display spacing avoids
overlapping the wide posed feet. Shins can extend beyond the close frame because
the framing covers feet and ankle joins, not whole shins. Earlier `foot-close-v2`
pair images and `comparison-audit.json` remain historical camera evidence:
inherited donor framing/spacing could overlap specimens or crop paired feet.
Use the v3 close images for review. The shared full-body images are unchanged.

Read-only inspection of final idle front, kneeling medial/clay and walking side
shows coherent five-toed paired anatomy and the selected unchanged ankle fit.
Kneeling rotates each foot through its own actual stock controller; their posed
silhouettes need not remain mirrors in an asymmetric animation. Independent
frame/attribute/full-geometry and finite contact receipts are recorded separately
by the audit agent. Sampled coverage and offline appearance do not prove every
animation, native lighting or palette result. Native/client gates remain deferred;
no client action or next-part work occurred in this fitting stage.

## Current +3 mm anterior correction

The latest user requested a tiny forward shift. The exact operation is
`[0,+0.003,0]` metres in each actual stock foot-local frame. It changes neither
foot size, local Z, orientation nor any joint/controller. Preserve the original
generator masters, first fit, corrected contact/chart parent and pre-shift pair
as historical evidence; use the following translated selection operationally.

Current left `left-foot-forward3mm-v1/translated-local.glb` SHA256:
`58831f36a8f29caf6fcd8ddc3727722f02d7a047ebb2710b35077e12e2aeb620`.
Its `translation.json` SHA256:
`ef7a227082a6067a145f2ae1369cc568f11a1bbdad562528d4ea1f954b8fceca`.
Current right `right-foot-forward3mm-mirror-v1/mirrored-local.glb` SHA256:
`079f04f9a7c043dfb13b1bb5b1a172c30c823bdb68108e8b7b068e366844ceb2`.
Its `mirror.json` SHA256:
`b0e5bccae8904d2b010b7f28f25fdb176346b317d0d9365bdb22ce4f6610e0a6`.
Both receipts associate the correct parent candidate/archive and actual stock
frames; six neighbours are hash-protected. Right mirroring occurs once after
the left translation. The anterior shift is unchanged by X reflection.

`translate_stock_foot.py` derives the child from actual rendered parent GLB
positions plus the declared translation. The maximum final FLOAT32 coordinate
error relative to that result is 6.080 nm. The prior authoritative float64 parent
archive differed from its rendered GLB by at most 7.450 nm; the translation proof
reports this separately and does not claim the old double positions were used.
Actual rendered X/Z, N/T/UVs, original BIN prefix, maps, material definitions,
triangle order and indices remain unchanged. The child retains identity node
transforms. No cumulative scale or rotation was reapplied.

Reproducible commands (each output must be fresh):

```powershell
& 'C:\Users\benco\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' tools/phenotypes/translate_stock_foot.py --config output/phenotypes/purposebuilt-foot-pilot-v1/left-foot-forward3mm-config-v1.json --output output/phenotypes/purposebuilt-foot-pilot-v1/left-foot-forward3mm-v1
& 'C:\Users\benco\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' tools/phenotypes/mirror_stock_limb_part.py --config output/phenotypes/purposebuilt-foot-pilot-v1/right-foot-forward3mm-mirror-config-v1.json --output output/phenotypes/purposebuilt-foot-pilot-v1/right-foot-forward3mm-mirror-v1
& 'C:\Users\benco\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' tools/phenotypes/test_translate_stock_foot.py
```

Two focused test methods pass: actual GLB coordinate translation/attribute,
material and index preservation, plus five rejection cases for sideways/vertical,
negative or oversized shifts and unbound source hashes. Tests are offline only.
The helper's executed copy and config are frozen in the translation directory.

`forward3mm-pair-stock-map-v1/stock-replacement.json` is the active eight-part
comparison input. `forward3mm-pair-offline-review-v1` refreshes standing and
deeply flexed kneeling, color and clay, against actual stock feet with all six
accepted neighbours identical. Its `comparison-audit-v3.json` SHA256
`43e482fac22f3e5375c02faf3196ad03dd359bc5239360be5759f64cf0e384ab`
binds four comparisons and 32 images: 12 full-body and 20 close views. Its
commands and close framing record exact unchanged stock joint transforms/native
height; both foot projections remain separated and in frame. Reviewed current
idle lateral/color and kneeling rear/clay confirm the small forward placement
with the accepted shape and local overlap unchanged. Prior walk,
cast and other pre-shift views are historical; a 3 mm geometry-only translation
does not substitute those screenshots for new current-pair observations. Finite
ankle contact and sole parity are independently refreshed by the audit agent;
they are not exhaustive animation or native shading tests. All game work stays
held for the later bulk phenotype validation. Finish feet and stop.

## Open underside anatomy finding

The user's subsequent report prompted a read-only sole inspection of the actual
current +3 mm left donor, untouched generator master and five-toe reference.
`toe-anatomy-review-v2` compares the master under the recorded temporary display
fit and current source with equal cameras, clay and original maps. Its
`toe-sole-clay.png` and `toe-front-under-color.png` show five distal toe pads plus
an additional toe-shaped lobe behind the little toe. `toe-top-color.png` still
shows five dorsal toes. This supports a generated extra plantar-lateral lobe,
without asserting a sixth independent anatomical digit/branch. The geometry is
present in the untouched master and was not introduced by contact repair,
mirroring or the 3 mm translation. The v1 diagnostic images were overlit and
are silhouette-only history; use the correctly exposed v2 views for shape review.

The independent `underside-anatomy-independent-v2/lobe-ownership.json` records
599 localization faces with actual original source IDs. Bounds in stock
`lfoot_g` local metres are X[-0.07490,-0.05796], Y[0.15682,0.18230],
Z[-0.13601,-0.11913]. This overlaps 42 original nonmanifold one-ring faces and
the five tiny repaired chart faces, but its extent predates those ≤0.05 mm
position repairs. The source tunnel/fold ownership is anatomy evidence, not
a deletion mask. My broader contextual 1,458-face ROI is also not an edit scope.
`toe-anatomy-review-v2/finding.json` SHA256 is
`bf6a448d90260dce9d46ab1a011ed11d1bf5e4868b85f02cdeaf7b2e2b1f2870`.

The minimal proposed correction is limited to rolling down or removing this
proximal plantar-lateral lobe into a smooth forefoot/sole transition, with a
measured boundary and protected five actual distal toe tips. Keep the little
toe tip around X−61/Y187 mm, ankle, heel, arch, sole datum and entire fit intact.
No correction is executed by this record. Any new child needs explicit local
geometry/normal/tangent and UV/material lineage, full serialized crossings/link
checks and five-toe underside/dorsal review. Successful manifold/HAK membership
tests cannot substitute for the anatomical silhouette check.

## Completed guide command

```powershell
& 'E:\Program Files\Blender Foundation\Blender 4.0\blender.exe' -b --python-exit-code 1 --python tools/phenotypes/prepare_foot_connector_guides.py -- --stock output/phenotypes/purposebuilt-stock-inputs-v1/stock --left-shin-receipt output/phenotypes/purposebuilt-shin-pilot-v1/left-shin-connectors-v3-monotone/refinement.json --right-shin-receipt output/phenotypes/purposebuilt-shin-pilot-v1/right-shin-v3-mirror-v1/mirror.json --output output/phenotypes/purposebuilt-foot-pilot-v1/stock-connectors-v2
```

This command records the completed execution; an output directory must be fresh.
Use bundled workspace Python for fitting/inspection, not the Windows Store shim.
