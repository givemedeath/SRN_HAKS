# Literal native material previews

The additive preparation and renderer provide target-bound offline captures for
the female Human `pfh0` stock-exact target and skin palette rows 3 and 8. They
preserve native positions, normals, bottom-origin UVs, triangle order, tangents
and handedness where present. They do not compile, convert, stage, select or
launch a client. Existing pilot entrypoints are unchanged.

Run `prepare_target_native_material_preview.py --config ABSOLUTE_CONFIG
--output FRESH_PREPARATION` with the verified shared Python launcher. Run
`render_target_native_material_preview.py --preparation ABSOLUTE_PREPARATION_JSON
--preparation-sha256 HASH --output FRESH_RENDER` with the verified factory,
background Blender launcher. Blender arguments follow its `--` delimiter.

The input configuration has schema 1, kind
`target-native-material-preview-inputs`, `diagnosticOnly: true`, and exactly
these controls:

- `targetContract`, `stockInventory` and `skinPalette` are absolute
  `{path, sha256}` pins. The installed bank and skin palette must be pinned by
  that target. `coordinateSpace` declares working or runtime; `paletteRows`
  is `[3, 8]`.
- `parts` declares any nonempty subset of the fourteen body owners and optional
  stock neck. Every entry has an exact target/rig/space `binding` and
  `nativeModel` pin. An `audited-candidate` body entry additionally pins
  `nativeAudit`; an `installed-stock-neck` entry pins `plt`.
- `poses` declares `{id: "stock-bind"}` or distinct `{id, clip, time}`
  rows. The latter sample the installed bank's frozen root/inherited animation
  chain. No custom frame, stature or mesh scale can enter.
- `render` contains integer `width` and `height` from 128 to 1536,
  nonempty `modes`, `views`, `focusParts` and `padding` from 1.01 to 2.
  Modes are `emission-only-color` and `neutral-native-material`. Camera IDs
  explicitly name world directions: `anterior-yplus`, `posterior-yminus`,
  `left-xplus`, `right-xminus`. All views of a pose use one measured
  orthographic magnification; framing never transforms the geometry.

Candidate entries require a completed, exact native-part audit, its stage and
all frozen source/material dependencies. Preparation decodes the binary again,
compares decoded layout/material ownership with that audit, and serializes every
literal native array with exact readback. Skin color uses actual PLT and the
installed palette; opaque cloth uses its independently audited fixed texture.
MTR dependencies must preserve the normal/texture3 roughness transport. Chest and
pelvis must have audited cloth ownership; unreviewed proposals are not inputs.

The stock-neck decoder is an additive bounded legacy path. It requires the
installed detached `pfh0_neck001` tree, native P/N/UV/indices and identity white
vertex colors. The current stock neck has 20 native vertices and 16 faces,
including split native normals. T/sign are absent and remain absent. The stock
material uses actual PLT, literal native normals, declared neutral roughness .8,
and no synthesized normal-map tangent basis. This does not assert that extracted
resources reproduce every installed stock shader default. Non-white packed
stock color semantics and other legacy stock model layouts remain unsupported.

Palette lookup happens separately for each categorical PLT texel before spatial
texture filtering. Palette PNG rows are top-origin while native UVs remain
bottom-origin directly in Blender. No glTF coordinate or tangent rebuild occurs.
Normal-map RG is interpreted through the existing literal native N/T/sign shader
bridge, with shader normalization explicit. Roughness uses the actual audited
texture3 map and a neutral offline Principled response.

The renderer also verifies actual Blender loop positions, UVs, corner order and
effective custom normals. Auto-smooth is enabled where supported. Its normalized,
packed loop-normal representation must stay within .0007 per direction
component; raw native N/T/sign shader attributes must be byte-exact. It fails if
geometric normals silently replace native normals. The isolated
`--self-test --output FRESH_DIRECTORY` verifies a deliberately nongeometric
authored normal and rejects an intentional geometric-normal substitution. It
uses no source asset.

Captures use CPU Cycles, four threads, seed 41, Standard view transform, no
denoising or adaptive sampling. Emission uses eight samples and exposure zero;
neutral material uses sixteen samples, exposure -.7, a .35 world and two
declared directional lights. Sampling noise may remain. The result kind is
`offline-native-material-preview`, never literal client evidence. Blender
interpolation, filtering, BRDF, color response and shadows differ from NWN;
engine mip behavior, ordinary/HQ paths and practical joint/garment acceptance
still require matched actual-client checks.

The first runnable real fixture is the frozen installed stock female neck at
`output/phenotypes/human-female-fit-purposebuilt-v1/stock-neck-native-material-controller-config-v2/configuration.json`.
It has sixteen captures, a correct per-texel stock palette measurement, and exact
Blender loop readback. Failed first import/closure attempts remain preserved.
Current replacement body assets and unresolved garments were not staged or
compiled for this proof.

For final skin calibration, freeze the final fourteen working geometry and
reviewed chest/pelvis ownership first. Keep the favored original-detail ankle
RGB recipe as its immutable reviewed compiler parent, independently replayed
from archived originals. Do not multiply an already treated PLT or feed a
calibrated child back as an untreated parent. Build all AO 0/.15/.35 comparisons
independently from the same declared parent and original AO. The current
`skinIntensityInputs` API supports only the recorded C1 skin-lighting replay;
the ankle recipe and general calibration need an explicitly replayable additive
interface before native staging. This controller consumes eventual audited
native results and does not bypass that dependency.

