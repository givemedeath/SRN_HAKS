# Human male foot pair: offline validation

This record preserves the earlier offline proof. The newer user request
released client access for [material repair and validation](phenotype-body-texture-repair-validation.md)
on all current parts, including native foot/TBN inspection. The +3 mm foot pair
still has an extra underside toe-like lobe; anatomical acceptance is open.
Foot regeneration remains stopped. Material evidence does not finish the feet
or authorize another part. The default cadence remains offline collection
followed by bulk phenotype tests.

## Current shifted candidates and open anatomy gate

Paths are relative to `output/phenotypes/purposebuilt-foot-pilot-v1`.

| Role | Input | SHA256 |
| --- | --- | --- |
| Current left | `left-foot-forward3mm-v1/translated-local.glb` | `58831f36a8f29caf6fcd8ddc3727722f02d7a047ebb2710b35077e12e2aeb620` |
| Translation receipt | `left-foot-forward3mm-v1/translation.json` | `ef7a227082a6067a145f2ae1369cc568f11a1bbdad562528d4ea1f954b8fceca` |
| Current right | `right-foot-forward3mm-mirror-v1/mirrored-local.glb` | `079f04f9a7c043dfb13b1bb5b1a172c30c823bdb68108e8b7b068e366844ceb2` |
| Mirror receipt | `right-foot-forward3mm-mirror-v1/mirror.json` | `b0e5bccae8904d2b010b7f28f25fdb176346b317d0d9365bdb22ce4f6610e0a6` |
| Clean body manifest | `paired-feet-forward3mm-offline-collection-v1/body-resource-manifest.json` | `cce921837911d11d2cca8a2bb22765de0bcb1755726a94e3c473023516fa3c42` |
| Diagnostic HAK | `paired-feet-forward3mm-offline-collection-v1/offline-native-pending.hak` | `0b90ac59d370f69fe685aa3fd75d27f585ced1ea05a61cfe99b290a1cd7ce737` |

Both feet move +3 mm in their stock foot-local +Y frame. Actual serialized
position error is at most 6.08 nm; X/Z, N/T/UV, maps, height, scale and orientation
are preserved. Independent translation, mirror and finite contact proof are in
the `forward3mm-independent-*` directories. Parent full crossing proofs are
reused under isometry with the actual FLOAT32 limitation recorded; a targeted
389-face contact-region versus full-mesh check finds zero crossings.

`forward3mm-pair-offline-review-v1/comparison-audit-v3.json`, SHA256
`43e482fac22f3e5375c02faf3196ad03dd359bc5239360be5759f64cf0e384ab`,
binds 32 fresh standing/kneeling color/clay images. Root reviewed current idle
lateral and kneeling rear clay. Source-color renders do not represent the runtime
-8 PLT correction. Other pre-shift pose images below remain historical observations.

`forward3mm-package-independent-v1/audit.json` independently parses the actual
76-key HAK and separate clean 34-key body collection. All 68 accepted fixture
and 26 accepted body payloads, including corrected pelvis skin, remain exact.
Both new foot stages have zero source-to-ASCII P/N/UV error and exact original
2K map extraction. The -8 skin0 descendants have fresh calibration/stage pins,
zero clipped texels and unchanged source PNGs, MTR, normal maps and geometry.
No new native foot compile receipt, tested module or client evidence is present.

Correctly exposed source/selected sole views confirm five main toes plus an
extra toe-shaped underside lobe behind the fifth, already present in the master.
`toe-anatomy-review-v2/finding.json` SHA256 is
`bf6a448d90260dce9d46ab1a011ed11d1bf5e4868b85f02cdeaf7b2e2b1f2870`.
The consolidated independent diagnostic index is
`forward3mm-independent-diagnostic-index-v1/index.json`, SHA256
`a5775af3c1c38422f2ad6bee8986c666593a3c727593fc91be0984e8776ae838`.
It explicitly records anatomy hold while preserving valid transform/material/
package proofs. This underside defect is not resolved by any topology, mirror or
package pass. Inspect the source and intended five-toe references, identify the
actual lobe ownership and apply a separate bounded repair only if warranted.
Rebind stages, mirror and proofs after changing the donor. Do not promote this
current diagnostic candidate or carry it forward as anatomically accepted.

## Clean donor inputs before the final forward shift

All paths are relative to `output/phenotypes/purposebuilt-foot-pilot-v1`.

| Role | Input | SHA256 |
| --- | --- | --- |
| Untouched Comfy textured source | `comfy-v1/generated/textured_00001.glb` | `1757c79e20c7ee294082e33d4be980be7c260806a4cf32e7b6d7918d381a0323` |
| Selected left | `left-foot-contact-chart-v1/mapped-local.glb` | `c36c5f999b38a0c8767b7c6761b53856638c6b7273fdfc71c8cda8aa46ac9d21` |
| Left mapping receipt | `left-foot-contact-chart-v1/mapping.json` | `0d4ed7e8fcc6493565669e7839b849109eae090dd3e56af24b07b971f2c3d986` |
| Selected right | `right-foot-selected-mirror-v1/mirrored-local.glb` | `fb9321f669d512250b98ca74c64b65d07d2ff1ce476879ee0216285dab38a402` |
| Right mirror receipt | `right-foot-selected-mirror-v1/mirror.json` | `5db2aad71c9c45955652443b80bec1fc3d09b680a1a4af3c85732b1a38f66a91` |

The [process record](phenotype-purpose-built-foot-process.md) explains image
design, source orientation, exact similarity fitting, rejected contact repair,
successful bounded correction and coherent local UV mapping. Source masters,
six accepted neighbours and actual stock male rig/controllers remain exact.
Fifteen normalized image/prompt/configuration/provenance files are byte-exact
in the original `reference_images/normalized/purposebuilt-human-male-left-foot-v1`.

The pre-shift pair below is immutable ancestry. The current +3 mm translation,
mirror and collection are recorded above; the new underside anatomy gate is
still open. Shape, size, local Z and source material sampling remain unchanged
by that placement operation.

## Historical parent geometry, attributes and attachment evidence

Each pre-shift foot has 49,974 triangles and 24,981 unique rendered positions.
Independent actual FLOAT32 all-face audits find zero positive-length/area
crossings, boundary/nonmanifold/winding/degenerate defects and bad vertex links.
The left geometry proof is `contact-repair-v2-full-audit-v1/audit.json`, SHA256
`569612cdb929f1e7a2628bf90de7f87a93e4e5433cf37570cea71809342c8feb`.
Its mapped child preserves all P/N/indices exactly; `contact-chart-independent-audit-v1`
independently verifies this and original maps/materials. The right full proof is
`mirror-full-audit-v1/audit.json`, SHA256
`825716bf66f8d36759a42d14a215bf992cceaddd9d3e68f6837603263ae10121`.
Shared contacts/tangencies within tolerance are excluded explicitly.

Proper Z180 and uniform scale0.3187211742 preserve original anatomy. Local
repair moves89 identified corners by at most50 micrometres, with three selected
fans using inward10-micrometre geometric offsets. Only13 source faces are
replaced by5 rim triangles. Source maps, retained N/UV/T and unaffected P remain
exact. New patch UVs use one measured existing chart; independently derived
new T agrees with actual serialized UV directions above0.9999999998.

The exact left-to-right attachment-frame reflection is local diag[-1,1,1]
with X0.206/Y0.100 micrometre translations. Right winding reverses0/2/1,
normal/tangent XYZ reflect properly and tangent W flips. UV/map sampling is
preserved. Actual right position serialization error is at most4.31 nm;
quantized vertex correspondence remains bijective. The rig is not mirrored.

Idle minimum world height differs from stock by0.16 mm. Both soles/crown
extrema reflect exactly. Finite central ankle rays show overlap in idle,
kneel, walk, run and cast. One left crouch ray measures9.12 mm withdrawal,
versus20.15 mm with stock foot on that line. Right crouch has7/9 applicable
central hits, as does stock; all7 overlap. Peripheral rays and missing hits
are retained in `pair-independent-contact-v1`; this is sampled coverage,
not proof of every seam throughout animation transitions.

## Historical pre-shift visual and material scope

Root reviewed the selected donor's front/rear/medial close views and original
uniform-fit idle/kneel/run comparisons. The right is independently mirrored and
assembled pair views retain exact native scale, stock poses, stock neck/head/arms
and six fixed accepted neighbours. Final pair image/camera receipts identify
usable images: `selected-pair-offline-review-v1/comparison-audit-v3.json`, SHA256
`5e14a0012bee1d07cc29af88e1e98f8e5f0c3b24c0f44d99071f4b9c7b8ebb6d`,
binds18 full-body and30 `foot-close-pair-v3` images. The final renderer checks
that both specimens' foot bounds are separated and in frame. Root additionally
reviewed pair front/lateral idle, medial kneel and lateral walk views. Older
close-view overlap/crop diagnostics are not selected.
Blender source-color/clay renders are offline previews, never client screenshots.

Area-weighted actual UV-used ankle side bands measure the foot about 6.5–8.4
skin shade indices above the accepted shin. Explicit -8 skin0 PLT descendants
preserve all geometry, UV, normals, tangent data, original source PNG bytes,
MTR and normal TGA. The selected corrected palette is SHA256
`1c3ddf531e6e8f6d512dac7fe5f0009aa49ee23d5af5add46fe498990114afad`.
The left declared operation receipt is SHA256
`4d470d66167afee4cfa4b3dc1ed85652075c35d394336c5462019faf48aa7143`.
All 4,194,304 skin0 texels shift by 8 with no clipping; layer/header bytes stay
exact. This is a calibrated offline trial awaiting palette/shader review in
the bulk client pass, not source-map intensity exactness or user acceptance.

Finite limitations remain: genus4 toe-gap handles,141 inherited negative-normal
corners across109 tiny faces (3 all-negative), sampled cap/color/contact tests
and initial detail-source budget. No broad smoothing was applied to conceal
these. There is no actual native-foot TBN or practical performance evidence yet.

## Deferred bulk client gates

After the user releases NWN access, compile the declared feet with the exact
selected material dependencies, independently decode native P/N/UV/T and signs,
then assemble the whole phenotype into clean isolated fixtures. Preserve all
accepted native bytes and explicit runtime palette descendants. Keep camera
controls unlocked. Verify at close/gameplay distances and in transitions:

- Idle, walk, run, casting, combat, crouch/kneel, death and resurrection.
- Both skin palettes previously used for continuity checks and additional
  relevant phenotype palettes; compare foot/shin and complete-body transitions.
- Bare feet, stock boots and representative armor, including part hiding and
  stock fallback resources. Human equipment remains identity-scaled.
- Standing/locomotion ground contact, cap exposure, resource ownership and
  practical performance with representative actor counts.

Capture package-hash-bound screenshots/logs. Do not call offline test/pack
success whole-phenotype completion. The current client hold and stop-after-feet
instruction remain in force until newer user directions.
