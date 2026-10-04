# Human male body material repair: validation and selection

Completed 2026-10-03 in `D:/srwt/codex/f0b3/SRN_HAKS`. The user authorized
material repair and actual game tests on every latest custom Human male part.
The selected runtime material descendant is **combined-v2**. It restores a
controlled portion of source AO to recolorable PLT shades and carries source
roughness into the native material. The visible improvement is restrained,
strongest on the torso; source maps on some other parts contain little detail.
It does not make flat ambient light equivalent to directional normal lighting.

Pilot paths below are relative to
`output/phenotypes/human-male-material-repair-v1`. Original source geometry,
normal maps/strength, rig, height and fixed underwear are unchanged.
The [reusable procedure](phenotype-body-material-process.md) and updated
[repair plan](phenotype-body-texture-repair-plan.md) own the method.

## Selected artifacts

| Artifact | SHA256 / scope |
| --- | --- |
| `materials-combined-v2/material-operation.json` | `5afdb150bdf29b4586dd062054378022f72a4bab863bc31a15fd1f390d981efc` |
| `selected-runtime-v1/selection.json` | `b002aa61517bd6441c8035ef96bd7c1ce5bcf524e82612e05341981ecde43f8d`; effective inventory and separate statuses |
| `selected-runtime-v1/human_male_current8_materials.hak` | `7f9c834a5d1c8499bf5dc4ed586544ddf428e860dfd9bd821dadc12b8003905f`; 42 body resources, including diagnostic feet |
| `selected-runtime-v1/human_male_accepted6_materials.hak` | `4f84d29f94796f0476d45f9f4486193172472e45fba167ce94ded4890b68e1d1`; 32 resources, exact six-part subset |
| Selected isolated client HAK | `bb6f835b0cee5e1803a5d2ef3f29bda1a9c6b5b37b420f89bcc4d787278bedb5`; 84 resources, includes private comparator/test assets |
| Front module | `0f2e45d0fa343f9c9fad2d8d47957c9ada94ebdd6aca73263d83d630efc95830` |

The body HAKs contain no appearance/phenotype tables, supermodels, animations,
resized equipment or comparator/test resources. They are replacement payloads,
not a finished multi-race phenotype deployment. The six-part HAK is an exact
subset of the eight-part assembly tested here, not a separately tested new
assembly. Current feet still have an extra underside lobe and remain
anatomically unaccepted. Regeneration is stopped. Arms, neck and head are stock.

`client-combined-front3-v1/userdir` is the isolated review installation,
loaded directly with `+TestNewModule srn_pheno_test`. Its camera is unlocked.
The final client was left on this selected material view; always reobserve its
ownership rather than replay a historical PID. Global user settings/override
were not used as the test installation.

## Operation and protected lineage

Every part uses explicit AO strength .35 with shade deltas bounded to -12/+3.
AO is linear data; the transfer operates on decoded sRGB palette colors and a
bounded local shade inverse for installed palette rows 3 and 8. Native palette
rows have local luminance reversals. All-white AO is an identity operation;
mean compensation in a mixed atlas can brighten some regions within bounds.
Terminal 20 mm bands and extra chest shoulder/neck masks reduce influence;
classified zero-influence polygons have a two-texel guard and remain exact.
The mask is conservative atlas influence, not perfect anatomical segmentation.

The operation starts from the effective native PLTs: pelvis -54 and current
foot -8 parents are retained. It does not reconstruct them from stale source
RGB. Output shade clipping count is zero. PLT layer ownership and all non-skin
pixels are exact. The fixed underwear MTR/TGA is exact. Left/right PLT and
roughness maps are byte-identical for each mirrored pair.

ORM green times the source roughness factor becomes a 2K grayscale RGB TGA.
MTR binds it as texture3 and **explicit Roughness 0**; retaining the former
positive .72 constant would override the map. Specularity .04, Metallicness
.001 and texture1 are retained. No texture0, height, AO-slot or illumination
override is introduced. Normals remain strength 1, not broadly reduced or
replaced by AO. The original adapter's loss of AO/roughness was real, but not
the sole cause of every flat-looking view.

All eight GLB hashes remain the ones in the current geometry/foot checkpoints.
The six accepted native MDLs are copied byte-for-byte from the accepted shin
donor. `baseline-native-v1` also made an actual complete eight-model compile;
its recompilation had differing non-raw bytes on old parts, so those binaries
were not substituted for the accepted six. Raw geometry matched. Original
compiler receipts/dependencies are immutable; `fixture.json` declares the
effective material overlay separately.

The feet were genuinely compiled in this task. `native-foot-arrays-audit-v1.json`
finds position/normal corner error 0 and UV error at most 2.9802322387695312e-8
(under .000062 texel at 2K, FLOAT32 rounding). Actual tangent lengths are
0.9999998212–1.0000001192, maximum absolute T·N 6.26e-7, valid +/-1 handedness.
This is native material transport evidence, not anatomical acceptance.

Area-weighted staged skin-UV shade statistics below include hidden caps and
are not visible-only calibration. The bounded operation does not guarantee
exact mean preservation.

| Part | Mean before → after | Standard deviation before → after |
| --- | --- | --- |
| Torso | 111.783 → 109.019 | 5.616 → 8.183 |
| Pelvis | 96.906 → 96.842 | 3.565 → 3.606 |
| Thigh pair | 96.583 → 96.958 | 2.263 → 2.813 |
| Shin pair | 105.588 → 105.419 | 5.881 → 6.099 |
| Diagnostic foot pair | 106.459 → 106.568 | 3.087 → 4.339 |

Source AO means are roughly .568 torso, .995 pelvis, .979 thigh, .992 shin and
.960 foot. Preserve those limitations. Recovering the source maps cannot
invent broad painted detail where they are nearly white or constant.

## Actual game comparisons

Client v89.8193.37-17 [26c6e573], executable SHA256
`3b7cb1252e0edb2ce22d7971f333aade027039ae30a45b4bc64732c3e6bec73a`.
Isolated windowed test settings use 1600x1000. Performance and High Quality
were compared; global settings were untouched. Native skin still recolors in
palette rows 3 and 8; the underwear stays fixed. Existing stock/custom shade
differences are not claimed fully eliminated by this pass.

| Case | Evidence / observed result |
| --- | --- |
| Control/AO-only/roughness-only/combined, Performance | Matching front camera/module/palette; cleared highlight. AO adds modest shade definition, roughness-only is subtle in this path. |
| Control/combined, High Quality | Matching front camera. Combined selected for additional restrained definition and retained source material information. |
| Stable rear idle | `client-combined-rear3-v1/client-evidence/rear-close-highquality.png`; muscle shading retained without dirt-like black AO grooves. |
| Side idle/rear crouch | Reviewed sequence screenshots; no new material bands. Existing permitted crouch geometry is outside this repair. |
| Held front and rear casting | Stable `client-combined-cast-{front,rear}3-v1` views show the torso and moving joints without phase-label ambiguity. |
| Moving kneel, conjure, death transitions/dead-back | Observed motion-loop captures; no new obvious material discontinuity. Commands alone are not screenshots. |
| Sustained walk/run | `client-combined-{walk,run}3-v1`, 24 m repeated routes; actual moving stride views plus sampled position/action logs. No new dark moving connector bands observed. |
| Palette 8 | `client-combined-front8-v1`; custom skin recolors, fabric remains fixed, no new obvious clipping. |
| Ambient-only light | Normal relief largely disappears; diffuse AO benefit remains modest. Not a promise of full anatomical relief without directional light. |
| Stronger directional light | Normals/geometry respond and material remains restrained. Lighting has a large effect on perceived definition. |
| Representative full stock armor | `client-combined-armor3-v1`; actual item `sr_pt_full` worn, stock sizing/fallback, no leakage. It hides custom parts and is coverage evidence, not bare material proof. |

Still views are captured at 3–4.2 m; the initial fixture settling view and moving
assembly provide gameplay context. Screenshots show roughly 60 FPS on this
machine during several settled views. No controlled hardware benchmark, GPU
memory measurement, complete combat suite or video acceptance is claimed.
Eight added 2K RGB roughness TGAs increase disk resource cost; compression and
whole-phenotype performance budgets remain production gates.
Their added payload is 100,663,648 bytes (about 96 MiB). No game crash or
material/resource-load error was observed in these tests. Logs do contain the
same startup OpenAL, undefined-alias, GOG authentication and empty IFO-label
messages seen in the unchanged control, plus master-server availability
messages. They are retained; this record does not call the logs warning-free.

The effective installed shader includes were re-extracted through actual KEY
resolution with no override in `installed-shaders-v1`. Their hashes differ from
the original base-BIF research include hashes, preserved in the plan. The
effective code reconfirms positive constant precedence and texture3 red-channel
roughness in the `SHADER_TYPE == 2` path. `fslit_nm` still matches. This is code
and binding evidence; no GPU debug input view was captured.

## Alternatives, evidence quality and checks

`materials-combined-torso-v3` changed only torso strength to .50 and its shade
limit to -20. Other seven parts were exact v2 bytes. Matching front/rear and
ambient client views showed a darker torso without useful extra definition
in flat light; it is unselected. Its prepared palette8 fixture was not run.
Failed v1 bake directories are also unselected (invalid monotone inverse
assumption). Original control and every source remain rollback evidence.

`evidence-summary-v1/index.json` pins 29 capture receipts, 24 launches and 48
log snapshots; all capture settings hashes have a preserved matching settings
snapshot. Three captures are excluded: highlighted first control, timed
`auto-rear-idle` that actually shows side idle, and an older cached crouch
snapshot (use `auto-rear-crouch`). Receipt timestamps are save times; observed
pose comes from pixels, not an assumed timer label. The front comparison
montage uses cleared High Quality captures and labels the rejected trial.
Evidence index SHA256:
`ad673aaae0852a753e1d9de1e76f72db1c2d406de71cd5b25d0ab1ecbafe96e4`.

Seven focused regression tests pass. `independent-material-audit-v1.json`
(SHA256 `05de00e0462901fb0b36c056a31b74d743d2a54bf2beeaf7c25d2ea3d40c3d0a`)
independently checks frozen inputs, output limits/pixels, normal/model hashes,
roughness channel/binding, mirrored maps, actual HAK inventories and empty
override. Rejected stale parents and illegal height/slot operations have tests.
The stronger trial has its own successful audit but remains visually unselected.
The final independent audit additionally pins the executed configuration and
body-only archive container hash:
`independent-material-final-audit-v1.json`, SHA256
`50600aaea9ea4a35e42726ddb289b3a02361930c5def2c8cfd199fb955041850`.

Future parts must follow the material process and preserve the effective map
inventory in `selected-runtime-v1/selection.json`. Do not drop back to old
compile-time materials or bake AO twice. This finishes the current material
repair/testing task; it does not restart the stopped foot regeneration or finish
all Human, Troll, head, armor-profile or phenotype table production gates.
