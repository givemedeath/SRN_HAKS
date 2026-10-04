# Purpose-built muscular Human male shin process

This is the selected shin method and its completed generation, fitting,
mirror and native proof lineage. First-round game-client acceptance is complete
in [the shin validation record](phenotype-shin-validation.md).
Read [the shin checkpoint](phenotype-shin-checkpoint.md) for current work and
[the fitting record](purposebuilt-shin-fitting-pilot.md) for measurements,
commands and finite evidence limits. Do not infer pair acceptance from a
successful compiler, package audit or offline image.

All pilot paths below are relative to
`output/phenotypes/purposebuilt-shin-pilot-v1`. The accepted torso, pelvis and
thigh pair are hash-verified context; their geometry and native resources are
copied unchanged. Actual stock `pmh0` root/controllers, Human height
1.9339157 m, head/neck/arms and feet remain fixed. Human equipment is identity
scaled. The only new native body resources are `pmh0_shinl001` at `lshin_g`
and `pmh0_shinr001` at `rshin_g`.

## Measure and generate one donor

`prepare_shin_connector_guides.py` measures actual stock shin/foot triangles,
joint frames, section centres and moving ownership against the accepted
thighs. `stock-connectors-v1/measurements.json` and its triangle archive retain
the input hashes and six stock poses. Stock shin extent is
160.514 x 189.235 x 508.799 mm; the left knee-to-ankle pivot vector is
[20.427, -66.6266, -427.408] mm. The upper end reaches 42.095 mm above the
knee and the lower end 39.296 mm below the ankle. These heights alone do not
define useful overlap: measure width, depth and centre at each end too.

Design an isolated bare LEFT shin/calf with smooth anterior tibia, natural
posterior calf mass and shallow closed skin ends. Exclude thigh, foot, toes,
garment and decorative cuff. Save the image prompt, parents and original.
Normalize the four complete alpha components with one shared isotropic scale;
record differing view widths instead of stretching individual panels.
Selected references/provenance are copied to the user's reference folder:
`D:/source/repos/SRN_HAKS/.tools/reference_images/normalized/purposebuilt-human-male-left-shin-v1`.
`reference-copy-audit-v1.json` verifies 16 copied files byte-exact.

The selected sheet is `image-design-v3-skin/source.png`; the four inputs are
`normalized-v2-skin`. `generate_purpose_built_part.py prepare` freezes the
actual live `SR_NWN_3d_pixal3d_multi_views` graph, schema, settings, references
and executed dependencies. An explicit part configuration is required.
The single submitted job is `ce0d67fc-8bd3-4763-b772-4805a42647b7`, recorded
in `comfy-v2-skin/generation.json`. It succeeded; four masters are retained
under `generated`. Collect existing jobs with their frozen status helper
before considering a retry. A 50K detail source and 2K maps describe this
asset; they do not establish runtime performance.

## Inspect and fit before changing the ends

Inspect untouched geometry and authored attributes, including winding,
actual intersections, normals, tangents, UVs and shell ownership. This source
passes its independent closed/manifold/outward/intersection checks, with no
paired-wall signature on the recorded finite rays. No source repair belongs
to this shin lineage. Blender computed normals are not a substitute for
authored corner normals.

The actual camera at +Y sees the posterior calf; the -Y camera sees the
anterior tibia. That evidence establishes the required proper Z180 orientation
to stock front +Y/up +Z. Anatomical left is the image-design intent;
medial/lateral identity is only weakly distinguished in the reconstruction
and is not proven by a generated skeleton. Do not copy another part's
orientation assumption.

`place_purposebuilt_shin.py` measures real length-weighted sections and retains
stock section-to-pivot offsets. Centroid-only placement would lose those
offsets. It aligns the inferred source knee/ankle axis using one positive
uniform scale, proper rotation and translation: scale 0.5428384362095527 and
a 4.858871-degree minimal axis correction after source orientation. Inferred
anchors are explicit geometric assumptions requiring assembled review.
`left-shin-firstfit-v1/placement.json` binds the job, source, config, neighbour
hashes and canonical detached output. Original map/UV/index evidence is
preserved; float64 authoritative corners and float32 rendered geometry have
separately measured precision. Never reapply this completed fit to a child.

## Shape only the measured connector regions

Assembled idle and flexed views showed a good calf with withdrawn knee/ankle
silhouettes. Matched peripheral rays quantify that withdrawal relative to
stock on identical lines; they do not prove a whole-joint void or universal
solid containment. Small global scale/pitch alternatives move the inferred
ankle without correcting the end-to-middle ratio. The adopted correction is
therefore a local connector field, not whole-calf enlargement.

`refine_shin_connectors.py` uses dense actual 2 mm triangle sections to derive
a smooth absolute width/depth envelope and centre path. Shape-preserving
cubic Hermite interpolation supplies analytic derivatives, without forcing
zero slope at every dense knot. End-only radial factors widen the required
footprints; the complete middle at shin-local Z[-250,-80] mm remains exact.
The lower transition extends above the too-thin source lower shaft. Source
closed tip heights, topology, ordered faces, UVs, maps and neighbours stay
unchanged. Maximum movement is 30.841 mm.

Normal directions use the local inverse-transpose Jacobian while retaining
authored magnitudes. Tangents use the forward Jacobian and normal
orthogonalization, retaining magnitude and handedness. Identity regions keep
P/N/T exact. `left-shin-connectors-config-v3.json` and its executed receipt
freeze this field; `monotone-connector-envelope-v1/design.json` binds the
measured targets. Actual discrete 1 mm sections record tiny departures from
the ideal monotone envelope, rather than claiming every facet is monotone.

Independent proof checks the serialized triangles, not just positive
Jacobian. `connector-v3-independent-index-v1/index.json` verifies one closed
component, zero boundary/nonmanifold/winding/degenerate defects or genuine
crossings, zero negative authored-normal corners, and 69,703 protected P/N/T
corners exact in both archive and GLB. Original UV/map/material/BIN and fit
lineage checks pass. Rendered contours remain a separate gate: a geometrically
valid field can still create visible rings. Sparse factor knots were rejected
for that reason and are not an operational recipe.

## Mirror through actual stock frames

Root's initial native donor join check authorized the exact selected v3
mirror. `mirror_stock_limb_part.py` conjugates world-X-zero reflection between
actual `lshin_g` and `rshin_g` frames. It reflects detached geometry, uses
corner order [0,2,1], reflects authored N/T directions and flips tangent W.
The atlas, UV/accessor/image bytes and rig remain unchanged. The right derives
from the selected canonical left GLB's declared float32 serialization; do not
claim it is a byte-exact reflection of the left float64 fitting archive.

`right-shin-v3-mirror-v1/mirror.json` binds the source receipt, frame matrix,
helper, config and archive. Real stock left/right geometry is slightly
asymmetric; mirror the perfected donor, then validate the opposite attachment
and actual asymmetric animation phases independently.
`selected-v3-pair-independent-index-v1/index.json` verifies frame-derived
P/N/T/TBN, winding/handedness, source UV/maps and a clean actual 50,000-face
right mesh. Finite opposite-side contact samples retain their coverage limits.

`paired-shin-v3-review-v1` contains 36 full-body and 24 close images of six
poses in color/clay, against stock shins with the same four accepted
neighbours and stock feet. `paired-shin-v3-review-death-top-v1` adds six prone
views because the normal front view hides the shins. Their command and
comparison audits rehash actual inputs/images and verify equal stock joint
matrices and native display scale 1. Camera-only close labels must track actual
display translation; only corrected close outputs are used. Offline untextured
stock parts cannot establish palette blending or native shader acceptance.

## Compile, compose and prove the real payload

`prepare_stock_limb_stage_config.py` binds the reviewed descendant receipt,
actual part/attachment, unchanged embedded 2K maps and fixed stock baseline.
`stage_stock_part.py` stages one declared shin with authored corner normals,
native UV V flipped once, skin layer0 and frozen material dependencies.
Compile each new shin independently with `native_compile.py`, its own compiler
userdir and the exact staged MTR/PLT/normal-TGA dependencies present. A model
compiled without those dependencies can lack required tangents despite valid
source normals. Keep compiler processes separate from interactive test clients.

The selected left and right native staging directories are
`left-shin-native-stage-v3-monotone-v1` and
`right-shin-native-stage-v3-mirror-v1`. Their `human_male_fit/converted`
directories contain separate native receipts. The corresponding
`left-v3-monotone-native-shading-audit-v1` and
`right-v3-mirror-native-shading-audit-v1` decode the actual binaries: ordered
corner P/N/UV match source float32 values exactly, with valid native tangent
and sign arrays. Source GLTF tangents and compiler-derived native tangents
have separate proof roles; do not substitute one claim for the other.

`compose_stock_limb_native.py` accepts the two verified new native parts and
copies the accepted chest/pelvis/thigh resources unchanged. Audit the actual
allowlisted HAK/MOD payloads with `audit_thigh_package.py`, including their
resource types, exact six replacement models, preserved neighbour resources,
private comparator, male actors, Human appearance/rig/height and empty override.
The compositor and auditor now share the current limb contract; shin staging
uses `shinl/lshin_g` and `shinr/rshin_g`, not image-kit aliases. Use complete
real fixture orchestration as well as focused negative guards.

`v3-monotone-native-package-proof-v1/proof.json` records the actual left compile,
shading, composition, module build and package audit commands. The paired
fixtures and commands are indexed in `paired-v3-validation-fixture-batch-v1`.
The gameplay fixture package audit verifies the exact preserved resources,
stock rig/comparator/appearance and skin palette; it explicitly leaves client
acceptance false. Test-only comparator/fixture resources are not a production
asset directory to copy wholesale.

## Selected artifact identity and final gate

| Artifact | Pilot-relative path | SHA256 |
| --- | --- | --- |
| Reference sheet | `image-design-v3-skin/source.png` | `fd0faefc7a8b65f2ff12cf5922944408e8a29a62bacd1b5764e3805382eaa0d5` |
| Generated master | `comfy-v2-skin/generated/textured_00001.glb` | `5bc23bf23a0d86fca74650939e410cc479daa8f60fa42bc0f892d9fcbb5ce157` |
| First uniform fit | `left-shin-firstfit-v1/placed-local.glb` | `6ffa99dbf09602a70378839e6a707b3f9c23c24cdbeb7b8de8ff8cf9d2c4b3ba` |
| Selected left | `left-shin-connectors-v3-monotone/refined-local.glb` | `bde4b16194010cd42ad40d282512e1189c7c992a5ab6df06d0d24c27c5123ee7` |
| Left recipe receipt | `left-shin-connectors-v3-monotone/refinement.json` | `eeb791069a46f22920361d83dc3c22bce850e944c9a5986129ef5c5a4d1509da` |
| Selected right | `right-shin-v3-mirror-v1/mirrored-local.glb` | `7efe4b5a9e85bacd1b8d23958c96fe4518e186363f5c6c8b91aed5b17b3f4e24` |
| Right recipe receipt | `right-shin-v3-mirror-v1/mirror.json` | `9289083aec5bfa217f02ff7f654eb81b0da53a3a6c7c19407adbaeb0ca9c3274` |
| Native left MDL | `left-shin-native-stage-v3-monotone-v1/human_male_fit/converted/resources/pmh0_shinl001.mdl` | `3d4eb3c94fb8ce73114c5293e70a5edf9bf7647b32a46357e9abd9fb99e4ff63` |
| Native right MDL | `right-shin-native-stage-v3-mirror-v1/human_male_fit/converted/resources/pmh0_shinr001.mdl` | `282e55060fb333789ad8b6670d5fe83d9153df67be5756829d9b07195eb278a9` |
| Pair independent proof | `selected-v3-pair-independent-index-v1/index.json` | `0c9662c50f3cb2a5de0365efd6b981596daa7ddff9c942be14f7d5d6cfeb729b` |

Final client evidence must cover both sides at close/gameplay distances,
front/rear/side, idle/walk/run, casting/combat, crouch/kneel, death and
transitions, representative stock boots/armor, skin palette and practical
performance. Clothing that selects another stock shin hides custom shin001;
equipment ownership must be recorded before judging absence as a body defect.
Keep camera controls unlocked, isolate the userdir and reobserve exact owned
PID/argv before control. Save actual HAK/module hashes, logs and screenshot
metadata without inventing capture times. The [validation record](phenotype-shin-validation.md)
is the root-owned final gate. Its frozen client index
`selected-v3-client-evidence-index-v1/index.json` SHA256
`bcb274a710d67e29903ffc973f64d76c7a691d108f38e581d454e73926eeb376`
records completed finite checks and their limits. The user's subsequent pelvis
skin-color report is a separate material-only follow-up, not a shin refit or
authorization to start another part.
