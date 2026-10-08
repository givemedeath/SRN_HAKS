# Original-source ankle detail compiler inputs

`replay_stage_skin_detail.staging_inputs` replays the exact user-favored ankle recipe for working-space skin compiler inputs. `target_part_stage.py` dispatches this explicit mode, and `audit_target_native_part.py` independently replays its source, recipe and effective material rows. Existing original-map, C1 lighting and garment paths remain unchanged.

```json
{
  "materialRoles": {"0": "skin"},
  "skinIntensityInputs": {
    "mode": "original-source-uv-detail-v1",
    "receipt": {"path": "<original-detail materials.json>", "sha256": "<hash>"},
    "sourceManifest": {"path": "<four-part source-binding.json>", "sha256": "<hash>"}
  }
}
```

Controls have exactly these keys. No arbitrary PNG, strength, gain, donor, geometry or approval flag is accepted. Initial sources are the exact favored `shinl`, `footl` and their actual-frame `shinr`, `footr` mirrors. They require original material0 skin, the installed female Human stock-exact target, stature0 and working-space geometry. Runtime conversion and garment combinations are unsupported by this mode.

The source manifest binds exact working geometry, literal PNUT fingerprints/corner archives, original-fit candidates, map archives, UV-location atlas and favored appearance. Current source receipts remain immutable; the helper checks their actual data/helper closure and canonical GLB. Right-side reflection is recalculated from the unique pinned mirror configuration and installed opposite frames; serialized winding, positions, normals, UVs, tangents, signs, material definitions and original BIN prefix must match the independently baked reflection. Texture-U and normal-map channels stay unchanged.

The recipe rebuilds both original2K UV-location atlases from literal original-fit geometry, including inequivalent overlaps and their guard. Original four-barycentric sample statistics determine the common-tone pigment/gain correction. The helper reconstructs that phase directly from original RGB and compares its archived output. It then reconstructs the shin's original24–40mm body detail using exact physical+UV full-edge charts, protected chart-normalized Gaussian filtering and bounded periodic nearest donor lookup in the35mm cylindrical metric. Every donor ID/UV/chart, source height, mask, support, lookup error, highpass, padding lineage and output RGB/intensity pixel is replayed. PNGs and the independent audit receipt are comparisons/evidence, never treatment parents or replay waivers.

The approved recipe's two RGB quantizations are retained: common-tone nearest-integer RGB, then shin detail nearest-integer RGB. Each phase starts from the same original lineage; the final PLT intensity truncates once after luma and optional original AO:

`floor(clip(dot(replayedRGB,[0.2126,0.7152,0.0722]) * (1-AO*(1-originalOcclusionRed/255)),0,255))`

AO strengths0,0.15,0.35 independently reuse this same original recipe. No pre-AO intensity or staged/treatment source can be an input parent. AO0 must equal the exact favored intensity sidecar. Original normal pixels remain exact. Roughness retains original ORM-green times authored roughness factor, rounded to byte, with the existing texture3/Roughness0 policy. Original embedded maps and current source PNUT are unchanged; the proof explicitly records derived RGB and intensity as edited.

For a no-stage replay, call:

```text
launch_shared_tool.py --tool python --output <fresh launch directory> --
  tools/phenotypes/replay_stage_skin_detail.py
  --config <target-original-source-detail-replay-diagnostic-inputs JSON>
  --output <fresh replay directory>
```

Use the verified bundled Python/toolchain/migration receipt specified in AGENTS.md. The diagnostic config has the ordinary target/source/source-receipt/part/roles/AO fields and the new controls, with `diagnosticOnly:true`. Its kind is `target-original-source-detail-replay-diagnostic-inputs`, never `target-part-stage`. The result records exact effective pixel-array fingerprints and replay proof; it stages, compiles and converts nothing.

Fresh native palette3/8, stock female neck continuity, ordinary/HQ shader, affected motion, equipment and actual-client validation remain required. This mathematical replay does not prove engine mip/filter behavior, repair or accept disclosed original shin/foot normal/topology defects, or approve whole-body garment inputs.
For diagnostic staging, use the existing kind `target-part-stage` with the exact controls above. Staging writes PLT from replayed intensity and transports original normal and roughness pixels; native auditing compares actual material dependencies with freshly replayed rows. Neither operation implies appearance acceptance. Existing source receipts and old executed evidence retain their historical helpers; the current 14-part source bank has no live stage/audit helper pins requiring source migration.

Focused dispatch tests substitute the expensive replay worker with asymmetric synthetic effective rows, while exercising real ASCII/PLT/TGA/MTR serialization and material-resource auditing. Separate helper tests and pinned real2K diagnostic replay verify the source-chart recipe itself. AO siblings always start from the same original source recipe. Forged proof/basis/parent, malformed modes and rehashed serialized material corruption reject.
