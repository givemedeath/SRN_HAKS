# Native body material preservation

Use this step after fitting/staging each purpose-built part and before adopting
its cumulative native package. The generator's GLB materials and the engine's
PLT/MTR material are different representations. Exporting just PLT and normal
can lose useful muscle shading and roughness. The selected Human male repair
is recorded in [the validation record](phenotype-body-texture-repair-validation.md).

## Freeze and inspect

Freeze the selected GLB, native MDL, effective runtime PLT/MTR/normal/fabric,
palette, UV samples and original compile receipts. An accepted runtime color
correction is the parent; do not rebuild it from the brighter source RGB.
Preserve original source maps and master geometry. Extract images through the
actual glTF texture bindings, including texture coordinate set, sampler,
occlusion strength and roughness factor. Filenames alone do not establish
channel ownership. Current helpers require embedded, untransformed TEXCOORD_0
and 2K atlases; other inputs need explicit support, not silent conversion.

`audit_body_material_inputs.py` extracts and hashes those inputs. Its triangle
area samples use actual staged skin UVs, but include hidden caps. They are
diagnostics, not visible-only color calibration. Assess visible skin and
connector regions separately in the client. Near-white source AO or nearly
constant roughness cannot recover detail absent from the source.

## Explicit material descendant

Use `bake_body_materials.py` with a frozen configuration and a fresh output.
For the current Human male, the selected operation uses the existing PLT shade
and actual installed skin palette rows 3 and 8. Decode palette RGB as sRGB,
apply linear AO factor `(1-strength)+strength*AO`, return to shade with a
bounded local inverse, then compensate measured mean shift subject to bounded
changes. The palette has local luminance reversals: a global monotone inverse
is invalid. All-white AO produces an identity operation. Within a mixed atlas,
mean compensation can brighten white-AO regions within the explicit limit.

The tested Human configuration uses strength 0.35, shade limits -12/+3, a
20 mm terminal-band influence transition and additional shoulder/neck
protection on the chest. Zero-influence regions and non-skin PLT bytes remain
exact, with a two-texel guard around classified protected connector polygons.
These values are a selected Human trial, not defaults for every part or race.
Protect actual visible joint bands, not just extrema of the whole mesh. For the
new upper arm, the shoulder pivot is Z0 while its closure extends roughly 83 mm
above it; the elbow pivot is about -302 mm while the end reaches -344 mm.
An automatic 20 mm band at the extrema misses both moving seams. Measure actual
skin UV cohorts against current adjoining native maps and declare seam protection
explicitly. Old foot/pelvis offsets are not arm calibration targets.
The baker accepts measured `connectorPlanes`: unit `outwardNormal` and
`offsetMetres` in native part coordinates. Influence fades over
`connectorBandMetres` toward the visible interior; the hidden extension beyond
each plane and its two-texel guard stay exact. Without these declarations the
historical extrema-based behavior remains unchanged. Freeze the actual plane
measurements and record them with each new operation.
The mask is conservative triangle-based atlas influence, not perfect semantic
segmentation. Compensation is bounded; it does not guarantee identical mean
shade after clipping the operation. Check actual joins before selection.

NWN's standard shader has no imported AO slot. Keep the controlled AO in PLT
shade; never bind AO as height, specularity or normal. Retain normal pixels and
strength 1, authored normals, UVs and native tangent arrays. AO is not height.

Extract ORM green times the declared roughness factor to a 2K grayscale RGB
TGA; bind its red channel as `texture3`. Set **explicit Roughness 0** so a
positive constant does not override the map. Keep Specularity 0.04 and
Metallicness 0.001 for the current skin; a specularity-map trial needs its own
operation and override policy. Skin MTR must omit `texture0` entirely, including
`texture0 null`, so the PLT remains the diffuse source. Fixed underwear retains
its original separate textures and MTR. Never bind packed ORM unchanged.

Map roughness is used by the installed shader's `SHADER_TYPE == 2` path;
compare High Quality with the user's ordinary quality setting. AO in PLT shade
survives the simpler lighting path. Record effective installed shaders, not
only old base-BIF hashes: patch KEY resolution can return newer include code.

Primary references: [standard material inputs](https://nwn.wiki/spaces/NWN1/pages/38175898/Standard%2Bmaterial%2Binputs)
and [MTR/PLT rules](https://nwn.wiki/spaces/NWN1/pages/12027232/MTR).

## Transport and validation

`validate_body_material_repair.py` independently checks output pixels, channel
transport, limits, zero-influence regions, mirrored maps, native model/normal
hashes and actual HAK payloads. Original compiler receipts remain immutable.
A material overlay records effective runtime dependencies separately; it never
claims the new maps were inputs of an old compile. Copy accepted MDL bytes
exactly. Compile a new part with complete normal material dependencies and
decode native arrays to verify real tangents/handedness. Small FLOAT32 UV
rounding must be measured and reported rather than called exact.

`pack_body_material_fixture.py` verifies the frozen input hashes, declared
material changes/additions, native fixture and empty override. It keeps
comparator/test payloads separate from the body-only HAK. A reused HAK requires
its pin and equality of every actual resource payload, not just its filename.
`launch_material_fixture.ps1` loads the module directly with an absolute
isolated user directory; it replaces only the previously observed owned
client and archives its logs. Keep camera controls unlocked and respect the
latest user direction on client access.

Compare control, AO-only, roughness-only and combined with matching camera,
palette, pose, lighting and quality. Clear actor highlighting first. Check
front/rear/side, close/gameplay views, ambient/directional light, two palettes,
moving joints and stock equipment. Full armor can hide custom parts; it proves
fallback/coverage, not bare-skin quality. Use stable held poses for screenshots.
A timed phase name does not prove what the capture depicts; record observed
pose and exclude captures that crossed phases. Tie screenshots, settings,
launches and logs to exact package hashes. Shader bindings and code establish
the transport path; do not claim GPU debug confirmation without capturing it.

Adopt a selected-material receipt separately from anatomical acceptance. Earlier
material-tested feet had an open underside anatomy defect; that evidence does
not validate the regenerated v5 pair. Preserve rollback/configuration snapshots. Carry
the selected effective material bytes, not the older bare PLT/normal adapter
output, into every subsequent cumulative assembly. Do not bake the same AO
into an already repaired PLT again. A repeated parameter trial starts from the
frozen untreated runtime parent; adding a part preserves existing selected
bytes and applies an explicit operation only to the new part. Extend the
declared runtime inventory/overlay contract when that inventory grows; never
bypass an older helper's guard to make a new cumulative package pass.

## Current reproducible commands

Use the bundled Python and the current workspace. These commands inspect the
existing selected trial; fresh bakes/packages require a new output directory.

```powershell
$taskPython = 'C:/Users/benco/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
$materialPilot = 'output/phenotypes/human-male-material-repair-v1'
& $taskPython tools/phenotypes/test_body_material_repair.py
& $taskPython tools/phenotypes/validate_body_material_repair.py --operation "$materialPilot/materials-combined-v2/material-operation.json" --fixture "$materialPilot/client-combined-front3-v1/fixture.json" --output "$materialPilot/independent-material-audit-recheck.json"
# A fresh operation, only when a new trial is intended:
# & $taskPython tools/phenotypes/bake_body_materials.py --config "$materialPilot/configs/combined-v1.json" --output "$materialPilot/materials-combined-v3"
```

For a new part, update its explicit inventory/GLB/map hashes, UV samples and
material settings. Audit before baking, then freeze the executed config/helper.
Do not copy old Human shade offsets, masks or eight-part lists into a new target.

## Adding the regenerated v5 feet

`purposebuilt-foot-orthographic-v5/selected-offline-v1/selection.json` is the new
offline pair authority. Measure current-shin UV-used skin bands before any
correction: untreated new feet were 18.61–19.36 shades brighter, so an explicit
-19 correction precedes the new-foot-only material operation. Do not inherit
the old -8/-28 foot or -54 pelvis corrections.

The explicit new-foot inventory receives AO strength .35, bounded -12/+3 shade
compensation, protected 20 mm connectors and ORM-green roughness. Final four
ankle bands differ from current shins by -0.199 to +0.472 mean shades. Normal
strength stays 1 and source normal pixels remain exact. Left/right palette,
roughness and normal maps are byte-identical; original anatomy GLBs are unchanged
by this runtime material operation.

`contact-material-independent-v2.json` verifies actual PLT layers/protected
pixels and actual roughness channels/bindings. `final-offline-audit-v1/audit.json`
checks the HAK's exact 32 accepted resource bytes plus 10 new foot resources.
The collection mixes accepted native neighbours and ASCII feet and is historical
offline evidence. The complete native fourteen-part package now has actual
palette, lighting, boot coverage and runtime observations in
[the full-body client validation](phenotype-full-body-client-validation.md).

The subsequent full-body goal has now compiled both selected v5 feet and decoded
their native P/N/UV/T/sign arrays. Fresh compile units preserve final frozen
material dependencies and original stage/operation receipts; see the current
[goal checkpoint](phenotype-goal-checkpoint.md). Source/ASCII attributes are exact;
native P/N are FLOAT32 exact and six UV values per foot differ by one FLOAT32 ULP.
`audit_native_limb_shading.py --native-uv-max-ulps 1` is an explicit measured parser
tolerance; default 0 stays strict. This does not allow position/normal drift.

Compose current native assets with `compose_effective_native_body.py`. Its
`effective-material-inventory.json` separates original compiler dependencies from
current AO/roughness resources, verifies all 32 accepted-six bytes, and rejects
undeclared models, rigs, tables, materials and partial pair ownership. The native
fixture builder's explicit `--effective-materials` verifies this contract and
retained compile-time normal/diffuse bindings. Accepted neighbours are not
recompiled and their AO is not baked again. Client checks remain a separate gate.

## Current arm calibration and implementation preservation

`prepare_limb_material_collection.py` collects only declared new mirrored limb
pairs, verifies source stages/fit ancestry, and proves both positive and negative
integer shade clipping while preserving all material layers. It cannot collect
the accepted chest/pelvis/thigh/shin resources. Actual current shoulder and elbow
UV cohorts yielded upperarm -10 and forearm +11, rather than historical offsets.
These are current Human donor measurements, not defaults for future races.

The selected arm operation is `human-male-complete-goal-v1/arm-effective-materials-v2`.
It protects measured shoulder/elbow/wrist planes and the entire hidden extension,
keeps original normal maps at strength1, and binds actual ORM-green roughness.
Independent bilateral pixel differences must be measured rather than inferred
from matching mean shades or identical source atlases.
The independent current-arm audit reproduces each side's own calibration and
measured connector-mask bake exactly. The upperarm palettes differ at only two
of 4,194,304 texels by one shade: mirrored FLOAT32 rasterization produces mask
values138 versus139 there, moving the pre-round shade across107.5. Neither texel
is protected or zero-influence. Layers, authored normals and roughness remain
byte-exact; forearm palettes are identical. Preserve exact per-side reproduction
and report measured bilateral differences; never force palette identity by
silently editing a selected map. Receipt:
`purposebuilt-upperarm-pilot-v1/arm-material-independent-audit-v1/audit.json`.

New material operations archive their executed Python inputs under `frozen-tools`
and record `executedToolOrigins`. Future tool improvements must not invalidate
the historical implementation that made a selected map. Actual source geometry,
maps and receipts remain pinned at their origins; editing those still fails the
contract. The frozen executed bake/config remain separate from reusable helpers.

## Completed gripping hands and cumulative client pass

The selected hands use a fresh atlas from the accepted closed exterior, rather
than textures transported from the rejected double-wall remesh. Actual wrist UV
cohorts measured untreated hand shade 116.544772 against forearm 107.418602.
The explicit -9 correction precedes the new-hand-only AO operation; it is a
measured donor adjustment, not a default. AO strength remains .35 with -12/+3
limits, a protected 20 mm wrist plane, original normal strength 1 and ORM-green
roughness. Native P/N/UV and tangent signs were independently decoded and checked.

Both hands' normal/roughness maps and palette layer bytes match. Twenty-five of
4,194,304 palette texels differ by one shade because opposite-side connector-mask
rasterization differs. The independent audit reproduces each side exactly; do
not force their palette bytes to match by changing accepted outputs. Current
authorities are `human-male-complete-goal-v1/hand-effective-materials-v1` and
`purposebuilt-upperarm-pilot-v1/hand-material-independent-audit-v1`.

The complete fourteen-part HAK preserves all 32 accepted-six resource payloads
exactly. Actual client runs checked skin rows 3 and 8 in original and directional
lighting, moving joints and representative stock armor/weapon/shield coverage.
Anatomical definition remained visible and fixed dark underwear retained its
own material. This is a practical pass, not coverage of every palette or quality
setting. See [the delivery](phenotype-human-male-delivery.md) for exact packages,
captures and limits.

Hover highlighting can make the body blue/purple and flatten its apparent
definition. Move the cursor off actors or disable highlighting in the isolated
test settings before evaluating materials. Activate the actual client and allow
its viewport to refresh before capturing; a phase log or cached screenshot alone
does not prove the current rendered pose. Keep literal source captures unchanged
and caption what was visibly observed. These checks prevent lighting or capture
artifacts from becoming unnecessary asset corrections.
