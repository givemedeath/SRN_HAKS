# Human male pelvis skin continuity

The user reported that the pelvis skin looked different from the other new
parts in the assembled client. This follow-up changes only native skin shade
values. Accepted pelvis geometry, fit, UVs, authored normals, native tangents,
normal map, fixed underwear, rig and animation resources remain unchanged.
The completed shin pair is committed in `eafc4b4`; its frozen
[client validation](phenotype-shin-validation.md) remains separate evidence.

## Measured cause

Paths below are relative to `output/phenotypes/purposebuilt-shin-pilot-v1`.
`pelvis-skin-mismatch-diagnosis-v1/skin-luminance-report.json` samples the actual
packed PLT at native skin-node UVs, with four barycentric samples per triangle
weighted by geometric area. It excludes underwear geometry from skin statistics.
The installed `pal_skin01.tga` and every native input are hash-bound.

The exposed original lower pelvis skin averages shade 150.36, versus 96.33 at
the proximal thighs. The hidden new top cap averages 151.65. All use skin layer 0;
skin MTR parameters match, and only the briefs have a fixed diffuse texture.
The same installed palette therefore returns a visibly brighter, warmer color
for the pelvis before lighting. This is a shade calibration mismatch, not a
different character skin selection or misplaced top cap.

Original packed pelvis PLT SHA256:
`aef91e7b729305b24e3bdc4703beb1f0bc9b6543344f9785994fd2dfbee320b9`.
The diagnostic in-game image
`client-pair-v3-review-front-v1/client-evidence/pelvis-skin-close-before.jpg`
has SHA256
`ad2965154cc27ffe5f29e4e29346e6419d4bae15ab440bed1c95ec7e7780434d`.

## Correction and proof boundary

Prepare a fresh derivative with integer offset -54 on skin layer 0 shade bytes,
calibrated to the measured proximal thigh. Retain relative shade detail where
unclipped; record clipping for the whole atlas and for the actual sampled skin
surface separately. Preserve the PLT header, dimensions and every layer byte.
Other layers and all other resource bytes must remain identical.

Keep original native compilation receipts immutable. A runtime material-patch
receipt must bind the original compile lineage, source HAK and changed PLT;
it must not claim the compiler consumed the corrected map. Verify actual
packed resource keys and payloads, allowing exactly this one resource change.
Compare settled palette 3 and palette 8 front views in the real client before
selecting the derivative. Package audits and palette lookups do not alone
establish visual continuity.

## Reusable process improvement

Independent image-to-model jobs can produce plausible source RGB skin but
different luminance ranges. NWN's PLT skin lookup uses shade indices, so a
common palette index and common shader do not ensure assembled continuity.
Before packaging each new part, measure the visible skin UV regions against
accepted neighbouring parts and check at least two actual palettes in game.
Do not calibrate from a whole atlas average, which mixes unused pixels and
garments. Preserve anatomical contrast and authored normals. Derive each
correction from measured evidence; this pelvis offset is not a default for
other parts or races. Geometry and animation tests need not be replayed when
an actual packed-payload audit proves their bytes unchanged.

## Selected derivative and actual client checks

Selected PLT:
`pelvis-skin-shade-offset-minus54-v1/resources/pmh0_pelvis001.plt`, SHA256
`990aa66b5c642d6c45ab4f1c60ceffd732cd290b53207c9c5021698dc9181690`.
Its `material-correction.json` SHA256 is
`eba52550d9e025278ce306e40df38a2385ab84b8fb624d6dcf797f1989fe9d70`.
The executed config and helper are frozen beside it. The tracked
`adjust_pelvis_skin_plt.py --config <executed-config.json> --out <fresh-directory>`
performs the measured operation; never overwrite the selected derivative.

Visible original skin averages 96.357935 after correction versus 96.328557 at
the proximal thigh. Its standard deviation changes only 4.230541 to 4.230534.
The atlas has 694,621 clipped texels, but only 2 among 52,525 texels touched by
the frozen native skin samples; one of 12,892 visible samples is affected.
Do not substitute whole-atlas averages for this native-surface measurement.
Independent direct native-V sampling reproduces the result. All original
26 native resources and six body GLBs remain exact in their original locations.

The selected 68-resource HAK SHA256 is
`2ea5a2ffd5ee9b717e785b6aae08e88d39449395665ee18adb07c6513fcbb299`.
Only packed key `pmh0_pelvis001` type 6 changes; all other 67 payloads are
byte-identical to the completed shin HAK. The comparator, original native
compilation receipts and all geometry/normal/fabric resources remain exact.
No compiler was invoked. `material-patch.json` records effective runtime
dependencies separately from original compiler inputs.

| Actual comparison fixture | Result | Exact module SHA256 |
| --- | --- | --- |
| `client-pair-v3-pelvis-skin-minus54-front3-v1` | Exposed pelvis skin blends with proximal thighs; user viewed this version and said **Much better now**. Fixed dark briefs retained. | `477048e576b1bf0e42d8b88f213d6d239238c504b585a8e2acb143e92becd0f0` |
| `client-pair-v3-pelvis-skin-minus54-front8-v1` | Alternate palette recolors exposed pelvis consistently with thighs; no former bright band; briefs remain fixed. | `592cb51518890311c0351e955aa64ffe8464adf118f36553e6bd8b166e9dd990` |
| `client-pair-v3-pelvis-skin-minus54-rear3-v1` | Rear exposed skin also blends; accepted back geometry and underwear unchanged. | `91cb2fbfb3ed60c6f4c370a043fffd0fef59c757bec58af93f4821810929468f` |

All three actual MOD payloads are byte-identical to their original comparison
fixtures. Cameras remain unlocked. Settled screenshots and schema2 receipts
are in each fixture's `client-evidence` directory. The original manually
zoomed before frame and new front frame have different camera framing, so
they are visual comparisons rather than pixelwise lighting measurements.
These finite palette 3/8 and front/rear checks establish this correction;
they do not test every palette, lighting condition or animation frame.
The packed geometry bytes prove the prior shin motion tests remain applicable.

Independent package proof is
`pelvis-palette-independent-audit-v1/packages-front3-front8-rear3.json`, SHA256
`ad9315b36ec555e7f86c58c0d451f78d6017d71ad1f2d541ab02a1a77656b5ec`.
`pelvis-material-patch-helper-proof-v1/final-package-proof.json`, SHA256
`9181ecf1bcdf5fb96e3f94095b8e380823e4b10f9f52bcd813304d29e90cf9d1`,
freezes helpers, operation guards, three package audits and normal native
dependency checks. Root ran 9 focused tests successfully with bundled Python.
A real CLI build rejects the patched candidate without `--material-patch`;
ordinary native fixtures still reject stale dependencies. Earlier helper
snapshots remain historical execution evidence; final guards additionally
validate actual PLT header/layers and correction-record associations.

`pelvis-skin-minus54-client-evidence-index-v1/index.json`, SHA256
`c3ce9bf6bcd19e592a3852f76af2a7edda597b2babd0516ce13dd5d0c1a100d0`,
freezes two before and three after screenshots with actual package/launch
associations, plus six final log files from three exited sessions. Running
rear-client logs are excluded. `root-verification.json` confirms all 54 file
references, four actual fixture HAK/MOD pairs and five capture associations.
The original shin index remains byte-identical.

## Carry forward without reverting

Keep the selected pelvis GLB and native MDL as geometry authorities. For skin,
use the corrected PLT and its separate material-patch receipt. Copying the old
thigh donor or restaging the source RGB alone would restore the rejected
lighter map. The current diagnostic composer
`compose_pelvis_palette_patch.py` and `audit_pelvis_palette_patch.py` explicitly
bind the selected six-part, 68-resource shin baseline; do not silently reuse
that exact inventory for a larger future body package. Extend its declared
resource/preservation contract when adding the next part, retaining the
selected pelvis PLT and honest compiler/runtime dependency distinction.
No earlier pelvis mesh edit, image generation, rig fit or whole-body slicing
is part of this correction.
