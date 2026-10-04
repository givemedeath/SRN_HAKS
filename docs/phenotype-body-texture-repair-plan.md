# Body-part texture repair plan and execution

Updated 2026-10-03. The original side-conversation investigation identified
lost source AO/roughness information. The later user request authorized the
repair and actual client tests on all latest Human male parts, superseding the
old client hold for that completed task. A later user request resumed foot
regeneration; [the foot checkpoint](phenotype-foot-checkpoint.md) owns its current
scope and offline bulk-validation cadence. These material-client tests belong
to their exact earlier geometry/package, not a newly generated foot.

The selected repair is **combined-v2**: controlled palette-aware AO into PLT
shade and extracted ORM-green roughness bound to texture3 with explicit
Roughness 0. Geometry, normal maps/strength, stock rig and fixed underwear are
unchanged. Torso, pelvis, thigh/shin pairs and diagnostic current feet have
material evidence in [the execution/validation record](phenotype-body-texture-repair-validation.md).
Use [the reusable material procedure](phenotype-body-material-process.md) and
[current runbook](phenotype-purpose-built-current-runbook.md) for continuation.
The accepted pelvis -54 correction is the input parent, not a correction to undo.

AO strength .35, shade delta limits -12/+3 and conservative connector masks
are selected for this Human baseline. A chest-only .50/-20 trial was compared
front/rear/ambient and rejected: it darkened the torso without useful added
definition in flat light. Source AO is nearly white on pelvis/shins, so their
improvement is small. Missing AO alone did not explain all apparent flatness;
shader quality, lighting and limited source maps also matter. This task does
not claim new anatomical acceptance of feet or whole-phenotype readiness.

The findings below retain the original research and implementation rationale;
the linked validation record owns actual completed tests and selected hashes.

## What the investigation established

The selected parts retain more material information in their GLBs than the
current native adapter exports. This is a concrete export limitation, not
evidence that the accepted geometry needs to be changed.

- `stage_stock_part.py` and the frozen executed shin-stage helper convert source
  RGB bytes to skin-layer-0 PLT shade bytes using
  `clip(RGB @ [0.2126, 0.7152, 0.0722], 0, 255).astype(uint8)`.
  This removes source hue/chromatic variation to allow palette recoloring.
  It does not explicitly blur or flatten brightness contrast, but the final
  appearance also depends on the selected palette's shade-to-color lookup.
- The adapter preserves selected normal-map RGB pixels and requires normal
  strength 1. It preserves authored corner normals and UVs. Current accepted
  part staging is not applying a broad normal-strength reduction. Historical
  whole-body experiments and their noise-reduction settings are not evidence
  about these individually generated selected parts.
- The native MTR binds `texture1` only and sets constant `Roughness 0.72`,
  `Specularity 0.04`, and `Metallicness 0.001`. Generated AO and spatial
  roughness information remain in the GLB but do not reach the native material.
- Actual selected chest, left-thigh and left-shin MTRs in the corrected shin
  package have those same constants. No fixed diffuse `texture0` override is
  present on skin.
- The accepted pelvis brightness correction changes only layer-0 shade
  indices by -54. Its visible-skin standard deviation remains 4.230541 before
  versus 4.230534 after; the documented native-UV sampling finds negligible
  clipping on the exposed region. Do not blame or revert that correction as
  a general contrast-flattening operation.

An exploratory source-only check sampled each triangle at barycentric weights
`(1/3,1/3,1/3)`, `(.6,.2,.2)`, `(.2,.6,.2)`, `(.2,.2,.6)`, using triangle-area
weights and nearest texels in glTF UV convention. It found source albedo shade
standard deviations of about 6.03/255 on the retained torso primitive,
2.50/255 on the thigh, and 5.91/255 on the shin. Mean AO-red values were about
0.55, 0.98 and 0.99 respectively. Normal scale was 1 on all inspected
materials. These are provisional whole-part samples, including hidden areas,
not visible-only statistics, a saved formal audit or an in-game lighting test.
They suggest that missing source AO matters especially for the torso, while
the thigh's weak painted shading needs separate attention. Inspect the maps
and visible anatomy before selecting any correction; do not multiply the
torso's full-strength AO into skin blindly.

## NWN:EE inputs relevant to this repair

The standard normal-mapped shader supports the following inputs:

| Input | Native binding | Repair use |
| --- | --- | --- |
| Diffuse / PLT | Engine-resolved base texture | Recolorable skin with anatomical shade detail |
| Normal | `texture1` | Surface-lighting detail; preserve initially |
| Specularity | `texture2`, red channel | Restrained spatial reflection strength |
| Roughness | `texture3`, red channel | Spatial highlight width/softness |
| Height | `texture4`, red channel | Parallax and locally derived light occlusion |
| Self-illumination | `texture5` | Available, but inappropriate for this ordinary skin repair |

The default shaders have no dedicated imported AO map. Bake a controlled AO
contribution into diffuse/shade values if useful. A height map produces a
different, locally derived occlusion effect; AO is not a substitute height
map. Packed glTF ORM cannot be assigned unchanged to an arbitrary NWN slot.
Its green roughness channel can be extracted into a native roughness map;
its red AO needs separate treatment. Metalness is not automatically equivalent
to a suitable skin specularity map.

PLT skin remains the engine's diffuse source: omit the MTR `texture0` line
entirely, including `texture0 null`. Keep `renderhint NormalTangents` and valid
native tangent/handedness arrays. Use the existing stock attachment/rig setup.

Sources: [developer-authored standard material inputs](https://nwn.wiki/spaces/NWN1/pages/38175898/Standard%2Bmaterial%2Binputs),
[MTR and PLT requirements](https://nwn.wiki/spaces/NWN1/pages/12027232/MTR),
and [Beamdog's PBR lighting announcement](https://www.beamdog.com/news/patch-819315-neverwinter-nights-enhanced-edition/).
Installed shader code was also read directly from `data/base_shaders.bif` via
`data/nwn_base.key`; no game executable was invoked.

## Important shader precedence

In the installed `inc_material.shd`, `SetupSpecularity` uses a positive
`Specularity` uniform before consulting `texture2`. It likewise uses positive
`Roughness` before consulting `texture3`. Simply adding maps to our existing
MTR while retaining `0.04` and `0.72` can leave the maps unused.

For a map-driven trial, omit the corresponding positive constant override.
The checked source uses zero as the default/fallback discriminator. Preserve
the explicit low nonmetallic setting unless a measured trial justifies a
change. Verify the effective result rather than assuming bindings alone prove
the maps are consumed. Shader quality affects the resulting lighting.

These are the installed resource hashes, resource type 2069, read on
2026-10-03 from
`C:/Program Files (x86)/GOG Galaxy/Games/Neverwinter Nights Enhanced Edition/data/base_shaders.bif`:

| Resource | SHA256 |
| --- | --- |
| `fslit_nm` | `08c88af8a8fddf0a3bf687f324f9b57d3eb47ba9fa8586686f44c748927931b0` |
| `inc_common` | `3a6f965d2eec5411b2075919e5dc0316d2ddbc783958de6c53730e94c75bfcab` |
| `inc_material` | `cbb65ee4c20051ac2aeb6e4bbd368d049f3206d84e07d1ea5b3780dc872a5338` |
| `inc_lighting` | `249d4f9e2dfcdafb8918d0e6c33403fd1e9fbcbf25d83fd0b58f49e4e3266576` |

Useful source locations: `inc_common` lines 53-59 identify slots;
`inc_material` lines 122-214 implement constant/map precedence and metalness;
lines 246-292 implement height-derived occlusion. `fslit_nm` enables normal,
specular, roughness, height and illumination processing. Recheck resource hashes
after an installation update rather than assuming line numbers remain valid.

Execution recheck: `human-male-material-repair-v1/installed-shaders-v1` freezes
actual installed KEY-resolved resources with no override. `fslit_nm` matches
the base-BIF research hash above; the effective includes have these hashes:

| Resource | Effective KEY-resolved SHA256 |
| --- | --- |
| `inc_common` | `20ecd0437d31e26ee797c83422c83870d62c7f910ca3bffc2473553401575337` |
| `inc_material` | `e6b53caa87429237c32b37606b956f3b6fc20eeff69ddedd35a3128c0a3992ac` |
| `inc_lighting` | `8548ea59d662829521e0618edb1511fc2a88a3ecf7108ead86829b8f3d200bf8` |

The effective code reconfirms positive constant precedence and texture3 red
roughness under `SHADER_TYPE == 2`. The old base-BIF table is retained as
research provenance, not silently replaced. Hash differences alone are not
proof of which installation archive supplied the effective include or of GPU
input consumption; no GPU debug capture was made.

## Protected inputs and starting point

Use the main checkpoint's current accepted lineage at execution time. The
following selected geometry was fixed during this investigation, under
`output/phenotypes`; these masters must remain unchanged:

| Part | Relative selected GLB | SHA256 |
| --- | --- | --- |
| Chest | `purposebuilt-torso-pilot-v1/common-cap-atlas-v4-perimeter/common-atlas-local.glb` | `3ae78d023ba522d94c44d9914bac0b36f35b640c42b9532015575e5572161a50` |
| Pelvis | `purposebuilt-pelvis-pilot-v1/selected-d-original-polished-material-v1/postfit-local.glb` | `db0bdf16099068da3bb685bcb61ae93ebed115e6ddbae90990c0b55e59b8d98a` |
| Left thigh | `purposebuilt-thigh-pilot-v1/left-thigh-proximal-cap-v2-proof/refined-local.glb` | `5420a77d5e9d51b7841f678d12710ce335bab16ed5ad417ae49b67f1e2950ab6` |
| Right thigh | `purposebuilt-thigh-pilot-v1/right-thigh-v2-mirror-v1/mirrored-local.glb` | `3c002789b74bfb5e94392d7c557e3105924e078f0133c47d496b1c123764b980` |
| Left shin | `purposebuilt-shin-pilot-v1/left-shin-connectors-v3-monotone/refined-local.glb` | `bde4b16194010cd42ad40d282512e1189c7c992a5ab6df06d0d24c27c5123ee7` |
| Right shin | `purposebuilt-shin-pilot-v1/right-shin-v3-mirror-v1/mirrored-local.glb` | `7efe4b5a9e85bacd1b8d23958c96fe4518e186363f5c6c8b91aed5b17b3f4e24` |

The selected runtime pelvis PLT is
`purposebuilt-shin-pilot-v1/pelvis-skin-shade-offset-minus54-v1/resources/pmh0_pelvis001.plt`,
SHA256 `990aa66b5c642d6c45ab4f1c60ceffd732cd290b53207c9c5021698dc9181690`.
Its correction receipt SHA256 is
`eba52550d9e025278ce306e40df38a2385ab84b8fb624d6dcf797f1989fe9d70`.
Use that map as the pelvis color baseline, not the lighter source RGB or the
original compiler PLT. Do not apply -54 to other parts as a default.

The corrected six-part native donor inspected here is
`purposebuilt-shin-pilot-v1/client-pair-v3-pelvis-skin-minus54-front3-v1/human_male_fit/converted`.
Its HAK SHA256 is
`2ea5a2ffd5ee9b717e785b6aae08e88d39449395665ee18adb07c6513fcbb299`.
The complete HAK includes comparator/fixture resources; use its declared body
inventory, not a wholesale production copy. New feet/arms may be selected
later: consult their current checkpoints rather than reverting to this snapshot.

## Recommended repair sequence

This sequence was executed as separate control/AO/roughness/combined trials.
The explicit runtime overlay avoids changing source GLBs or old compiler
receipts. New parts must preserve the selected neighbour materials, apply
their own explicit material preparation, and repeat affected client checks.
Do not silently return to PLT/normal-only staging or apply the same AO twice.

1. Freeze the accepted runtime PLTs/MTRs/normal maps, source GLB materials and
   actual package inventory. Record source image dimensions, encodings, sampler
   behavior, factors, UV orientation and hashes. Extract original AO and ORM
   channels losslessly for inspection. The torso's `common-color.png`,
   `common-normal.png`, `common-ao.png` and `common-orm.png` provide explicit
   source maps. Verify channel assignments from the GLB; filenames alone are
   insufficient.
2. Start with torso material-only A/B trials, which have the strongest evidence
   of lost AO. Keep an unchanged control. Separate a moderated AO/shade trial
   from a roughness-map trial, then compare their combination. Use restrained,
   recorded AO strengths; treat trial values as experiments, not accepted
   defaults. Preserve muscle interiors, skin detail and connector colors.
3. For AO baking, distinguish sRGB color from linear data. A declared trial can
   decode source color to linear, multiply by
   `AO_factor = (1 - strength) + strength * AO`, then re-encode before the
   established PLT conversion. Record every step. Do not silently change the
   existing RGB-to-PLT convention or apply gamma conversion to data maps.
   For already corrected native PLTs, use an explicit shade-domain operation
   and actual palette lookup rather than reconstructing from stale source RGB.
4. Measure visible skin using actual native UVs and triangle-area weighting.
   Check broad muscle separations, local contrast, clipping and waist/hip/limb
   connector bands separately. Preserve the accepted neighbor shade match;
   compensate a measured mean shift without erasing anatomical contrast.
   Whole-atlas averages mix unused pixels, hidden caps and clothing and are
   unsuitable calibration targets.
5. Extract roughness from ORM green to a native single-value-per-texel map,
   retaining its data values. Inspect skin plausibility before use. Remove the
   positive constant roughness override for this trial. If a specularity map
   is separately authored, keep it restrained, omit its positive constant
   override, and preserve nonmetallic behavior. Do not blindly use a nearly
   black metalness map as skin specularity.
6. Preserve normal-map pixels and strength in the first trials. Inspect tangent
   conventions, authored normals and native TBN separately if lighting defects
   remain. Increasing normal noise is not a substitute for broad muscle shading.
   Height/parallax is a later optional experiment, not the initial repair.
7. Evaluate donor-side materials before sharing them with the mirrored limb.
   Verify that both sides retain correct UV sampling and normal handedness.
   Retain fixed underwear textures and material separation. Neck/head polish
   and stock equipment resizing are outside this material repair.

## Tooling and package requirements

The current helpers intentionally reject undeclared material changes:
`stage_stock_part.py`, `prepare_stock_limb_stage_config.py` and
`audit_limb_ascii_material.py` verify selected embedded maps or exact luminance
conversion; the existing pelvis patch contract is specifically a skin shade
offset, not a generic AO/roughness patch. Do not bypass those guards by replacing
a PNG, overwriting a selected GLB or editing an old execution receipt.

Implement any necessary support as a scoped, explicit material operation with
parent hashes, input maps, masks, color spaces, algorithm, parameters, output
hashes and a declared resource allowlist. If producing a material-only GLB
descendant, prove all geometry, UV, authored normal and tangent attributes and
node transforms unchanged; preserve the original GLB. Keep original native
compiler dependencies immutable and distinguish them from effective runtime
material descendants. Extend the actual current body inventory rather than
assuming the old six-part/68-resource fixture contract still applies.

Prefer new variant directories and a material-only package overlay that copies
accepted native MDLs exactly when suitable. Add roughness/specularity resources
only through explicit configuration and audits; keep names within the existing
resource limits. Future engine-dependent verification must respect the latest
user client direction. This repair has actual native/TBN and material client
evidence. Use bundled workspace Python exclusively.

## Validation and selection gates

Offline checks must verify map sizes/channels/orientation, operation masks,
fixed underwear, skin-layer preservation, finite normals, clipping, contrast,
neighbor shade continuity, exact rig/geometry retention and actual packed
resource ownership. Test rejection of stale parents, unexpected resource edits
and accidentally retained constant overrides. These checks establish operation
integrity, not visual acceptance.

When client access is authorized, compare
unchanged control and variants under identical camera, skin palette, pose and
lighting. Include front/rear/side, close/gameplay distances, diffuse ambient
lighting and stronger directional lighting, at least two skin palettes, moving
joint seams and representative stock equipment. Use engine material debug
views where practical to confirm roughness/specularity inputs are consumed.
Watch for dirt-like AO, excessive dark grooves, plastic shine, flat highlights,
palette clipping and newly visible connector bands. Tie screenshots and logs
to exact package and variant hashes. Select only a visible improvement and
retain rollback assets.

Finish by updating the main checkpoint/runbook with the selected material
lineage, actual results and remaining gates. Accepted geometry remains the
geometry authority; this texture pass should not replay obsolete slicing,
rig-fitting or whole-body generation recipes.
