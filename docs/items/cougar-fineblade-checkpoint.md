# Cougar Fineblade implementation checkpoint — 2026-10-22

## Approved grip sizing reference (current v23)

The user's latest feedback was: "looks good, make sure future weapons are scaled
based on that grip size". The width20 candidate's grip is now the approved default
sizing reference for future weapons. See [weapon grip sizing](weapon-grip-sizing.md)
and the portable `weapon-grip-standard-v1.json` (SHA-256
`8d30d19ec7beb24ffc91946f1462148bce729becb391703815dcdc4b6a52f988`).
`AGENTS.md` and the item runbook require future fits to use the measured usable
length, face width and depth, with the reference hash in their fitting evidence.
The historical Cougar scale factors are not generic multipliers for new designs.

Current snapshot: `output/itemkit/cougar-fineblade-longblade/checkpoint-v23.json`,
SHA-256 `7f8db7f858dbfc36a76e18a43ed09c8cf0af290353d09b50ae92fc7aafc4f080`.
Its `grip-sizing-review-v1.json` records the exact user instruction and verification
of five transverse sections, usable grip landmarks and four source hashes.
Usable length is 0.1831918 native units; central width/depth are
0.048606638683900284 / 0.029581964161963813. Measurements exclude the extra hardware
length of the complete native grip part.

The current native delivery remains `width20-delivery-v1`; no mesh, map, package,
fixture or running client changed during this policy update. Grip sizing approval
does not establish the remaining client matrix or authorize production promotion.

## Additional visible-face width reduction (historical v22)

The user preferred the v21 slim candidate, then requested another 20% reduction
across the visible face of every part. Current checkpoint:
`output/itemkit/cougar-fineblade-longblade/checkpoint-v22.json`, SHA-256
`54a0ee00d41e3af74bd4efacf06845c22ceabcdd238d135c4602c9ff41de37b5`.
Current delivery: `width20-delivery-v1/delivery.json`, SHA-256
`df108af6a41ecfd4c55d2c0bfb663272c9750bd458fb03b60271a266e7d8fb06`.
Both paths are under the same asset root. Use its `README.md`,
`gallery/index.html` and `private-fixture.json`. The earlier slim candidate and
all previous checkpoints remain intact.

Selected geometry and renders: `width20-v1/result.json`, driven by
`width20-v1-config.json` and `output/itemkit/width20_blender_v1.py`.
The cumulative native `(X,Y,Z)` transform from the original is `(0.8,1,0.64)`
about the same grip origin. X is depth, Y is length, Z is visible-face width.
All three parts measure `(1,1,0.8)` relative to the preceding slim candidate.
Every current depth and length coordinate is exactly unchanged in the native
visible and shadow arrays. Corresponding donor geometry receives the same
transform. Native corner normals use the analytic inverse transpose; UVs,
diffuse pixels, topology, intentional openings and 4,956/488 budgets are unchanged.

Four-thread geometry/lit/unlit rendering took 81.391 seconds. Fresh native
compilation, string sanitation, attribute/shadow roundtrip, closed shadows and
exact HAK payload checks passed. Independent review validation confirms eight
matched poses, exact embedded 1K runtime pixels and unclipped inventory parts.
The original 4K donor-transfer maps remain retained; no appearance field was
resampled and no further generation attempt was consumed.

The new private fixture is separate from both earlier fixtures. No running
client was controlled or modified. Client validation and production approval
remain pending. When requested, launch only the exact new `userDirectory` bound
by `width20-delivery-v1/private-fixture.json`, and leave controls to the user.
The prior "looks better" feedback is recorded as a working preference, not
production acceptance. Runtime bindings remain the verified
`output/itemkit/runtime-slim20-v1/toolchain.json` and `migration.json`.

## All-parts transverse reduction (historical v21)

The user requested blade, guard and grip 20% narrower in both width and depth,
then explicitly included the pommel. Current checkpoint:
`output/itemkit/cougar-fineblade-longblade/checkpoint-v21.json`, SHA-256
`6d99dd705b81e5007c920dfd2f905b538977e0e705950eae9e755e2975c6b735`.
Current delivery: `slim20-delivery-v1/delivery.json` under the same asset root,
SHA-256 `3b9acde89c3673cb27b5863ce47d2060df5909d77f26c1952928a6524653be6d`.
Use its `README.md`, `gallery/index.html` and `private-fixture.json` for viewing
and client continuation. The previous delivery and production state remain intact.

Selected revision is `slim20-v4/result.json`, driven by
`slim20-v4-config.json` and `output/itemkit/slim20_blender_v4.py`.
Its deterministic post-bake transform is diagonal `(0.8, 1, 0.8)` about native
grip origin `(0.000394182, -0.0157349, 0.000168169)`. Native Y is the length axis;
every visible and shadow Y coordinate remains exactly unchanged. All three
native parts, their shadow proxies and retained fitted donor geometry received
the same transform. All visible widths/depths measure exactly 80% of baseline.
UVs, diffuse pixels, triangle counts and intentional openings are preserved.
Native corner normals use the analytic inverse transpose. Blender's custom
normal encoding is measured separately with cosine greater than 0.9998; it does
not replace the exact normals used by the native package. Preliminary revisions
v1-v3 failed display-normal checks and are not selected or packaged.

Fresh ASCII export, compilation, string sanitation, native attribute/shadow
roundtrip and exact HAK payload validation passed. The complete assembly remains
4,956 visible / 488 shadow triangles, with the original 4K donor-transfer maps
and exact 1K runtime diffuse. Twenty-four four-thread renders cover eight matched
geometry/lit/unlit angles; embedded runtime pixels and unclipped inventory parts
pass independent validation. Inspected front/rear, edge, oblique, grip and pommel
views retain the continuous assembly and open loop.

The separate revised fixture retains both shipped Human bodies and the same
private namespace. No running client or original fixture was changed. Client
review and production acceptance remain pending. Two geometry generation attempts
remain used; this revision generated no new shape. Runtime migration evidence is
fresh at `output/itemkit/runtime-slim20-v1/migration.json` because bundled Python
changed; historical bindings were preserved. Reopen the revised fixture's exact
`userDirectory` only when requested, and do not control it if the user's standing
viewing preference remains in force.

## Delivered native candidate; client review deferred (historical v20)

Authoritative snapshot: `output/itemkit/cougar-fineblade-longblade/checkpoint-v20.json`,
SHA-256 `38249665b9b01a3a263ca9da59b2422c135f9742df8a691199026c131131ac1d`.
It binds the exact manifest `production-5k-v6.json`, family
`native-family-v2/family-5k-v3.json`, runtime `runtime-v4/local.fixture-v1.json`,
and completed live `production-run-v3/state.json`. All ten stages through fixture
and their reviews are complete. Historical receipts and checkpoints are unchanged.

Delivery: `output/itemkit/cougar-fineblade-longblade/delivery-v1/README.md`.
The delivery manifest is `delivery-v1/delivery.json`, SHA-256
`e6ef68cd13cce54f1f06a24ef2d65de8a73b1b8c8414d3a927e2498ae67c4598`.
Its 69 copied files match their bound sources. It contains the final 4,956-triangle
textured GLB, ASCII models, seven sanitized native resources, candidate HAK, item
blueprint, 4K/2K/1K/512 diffuse maps, inventory icons and eight-angle matched
geometry/lit/unlit gallery. The runtime diffuse is 1K; the donor transfer master
is 4K. Closed shadow proxies total 488 triangles. Two geometry attempts were used;
the two-attempt limit remains exhausted. Retained original shape/appearance,
199,504-triangle donor, working meshes, fitted scenes and correction proofs are
indexed by hashes without duplicating large masters.

Fresh native compilation, string-only sanitation, attribute/shadow roundtrip and
exact HAK payload checks passed. The isolated test module and both shipped Human
bodies (PhenoMorpher 1.1.0 / PR #49) are retained at the precise paths bound in
`delivery-v1/private-fixture.json`. This allocation is verified for the private
stock + shipped Human stack; it does not approve a production-world namespace.
The final frozen code passed 62 itemkit tests and 18 test-impact tests.

The user's latest instruction is **"Keep client review pending"**. No in-game
acceptance observations were recorded. The task-owned NWN process was verified
exited. Client validation and production acceptance remain false. Wait for the
user to resume client review; then reverify the bound fixture and client, launch
the exact isolated `userDirectory`, and visually observe both Human matrices.
Scripted heartbeat observations do not establish visual acceptance. Production
promotion still requires explicit user approval.

## Compiled native candidate (historical v19)

Authoritative snapshot: `output/itemkit/cougar-fineblade-longblade/checkpoint-v19.json`,
SHA-256 `da56fcd9b1219a81ec2efb693fdff88a6a36183c6e850eb793cb141c8fa08132`.
Keep the v18 manifest/family/binding and live `production-run-v3/state.json`.
The active phase remains `production-phase3-v1-config.json` (session 97988).

Fresh native compilation, string-only sanitation, geometry/normal/UV/shadow
roundtrip and exact seven-resource HAK payload checks have passed for all three
parts. Candidate HAK SHA-256:
`8705e50470a6115c1bf10c5255a59560a81ae02d67f947a95da02ec3672ce3f1`.
Its precise retained path is in the native receipt/checkpoint. The isolated Human
fixture is the next phase output. Wait for its actual receipt; then launch that
exact `userDirectory` with the bound client and observe both Human matrices.
Client validation and production promotion remain unapproved.

## Native packaging and client continuation (historical v18)

Authoritative snapshot: `output/itemkit/cougar-fineblade-longblade/checkpoint-v18.json`,
SHA-256 `cd2ecbde1192fdb155e89d8923c29befd262b04cdb7b6d64979532bc77fc472c`.
Continue with the explicit live state `production-run-v3/state.json`, manifest
`production-5k-v6.json`, family `native-family-v2/family-5k-v3.json`, and
`runtime-v4/local.fixture-v1.json`. `production-phase3-v1-config.json` is the active
native export/compile/sanitize/package/fixture phase. No additional shape attempts
are authorized or needed.

The fresh maintained fit, reduction, atlas, donor finishing, linear 4K bake, shadow
and render stages passed. The final complete GLB contains exactly 4,956 triangles
and embeds the exact 1024-square runtime PNG pixels. All eight camera poses match
across clay, lit and unlit views; all three inventory parts are visible, aligned
and unclipped. The full target views and inventory composite were inspected.
The closed shadow assembly is 488 triangles. Source colour probes pass; the only
range normalization is floating-point rounding (maximum 1.00000036). No generated
field was sampled after fitting. Retain its separate correction provenance.

Current review gallery: `production-review-v1/index.html`. The portable textured
GLB and fitted textured scene are bound by the render receipt. Generated source
bevel/hardware faceting remains in this working candidate. The full source donor,
working masters, maps and failed diagnostics remain separately retained.

Native compilation and both Human private-client observations remain pending.
Production promotion is unapproved. The fixture is limited to its verified private
stock + shipped Human stack; this is not production-world resource allocation approval.

## Fresh production snapshot after visual corrections (historical v17)

Authoritative snapshot: `output/itemkit/cougar-fineblade-longblade/checkpoint-v17.json`.
Use `production-5k-v6.json`, `native-family-v2/family-5k-v3.json`, and
`runtime-v4/local.fixture-v1.json`. The current maintained state is explicitly
`production-run-v3/state.json`; `production-phase1-v1-config.json` runs fresh
fit/reduce/unwrap/finish and stops before baking for material review.

The v16 visual prototype was rejected. A controlled known-colour Blender test
proved that its legacy sRGB-tagged EXR changed linear .18/.04/.6 to
.46135/.22092/.79774 on reload; Non-Color EXR retains the exact linear values.
The original 200K/4K donor and in-memory bake were unaffected. Do not consume
`projection-textures-v2` as final colour. The new run uses Non-Color float bake
images, continuous dark reverse weave, gentler review lighting, explicit camera
up vectors and correctly aligned vertical inventory icons. The actual 1K maps,
lit/unlit renders and package still need fresh review.

Visible geometry remains exactly 4,956 triangles, now checked against its reviewed
corner hash before expensive maps. The shadow prototype remains valid at 488
closed, outward triangles with the measured loop clear. The focused suite passes
62 tests. Both geometry attempts remain exhausted. Native/client validation and
production acceptance remain pending; all earlier checkpoints are historical.

## Final donor transfer and shadows (historical v16)

Authoritative snapshot: `output/itemkit/cougar-fineblade-longblade/checkpoint-v16.json`.
It supersedes v14/v15 for continuation. Use `production-5k-v5.json`, the same
`native-family-v2/family-5k-v3.json`, and `runtime-v4/local.fixture-v1.json`.
Both geometry attempts remain exhausted. The earlier maintained `production-run-v2`
is historical and stale after the necessary processing fixes; do not adopt its
reviews as current-code receipts.

The native visible geometry remains 4,956 closed, outward triangles. The final UV
prototype passes 4K/2K/1K overlap and runtime domain-gutter checks. Its 4K donor
projection had 27,833 misses; an explicit source-UV transfer corrected them within
2.5 mm, with per-texel provenance. Of these, 367 texels on 26 exact hash-bound
target faces use the reviewed inward-source colour exception within 2.1 mm and
below 0.01% of mapped texels. Source PNG colour probes pass. The raw donor field
was never sampled after fitting. Retain the unpadded projection and correction
proof separately. Derived 4K/2K/1K/512 maps are in `projection-textures-v2`.

Ordinary shadow decimation filled the pommel loop and was rejected. A closed,
variable-thickness silhouette with a measured opening now supplies its proxy.
The complete shadow assembly passes at 488 triangles (96/96/296), with all three
opening rays clear and protected blade thickness retained. See `prototype-shadow-v2`.

`prototype-render-v1` is the current matched clay/lit/unlit, 1K diffuse review job
(four threads), with aligned multipart icons and a retained textured scene/GLB.
Inspect its actual results before freezing the fresh maintained production run.
Native compilation, package and both Human private-client checks remain pending;
production promotion still requires explicit final user approval. The focused
itemkit suite passes 60 tests. All historical artifacts and checkpoints remain intact.

## Final 5K donor-transfer production path (historical v14)

The user authorized finishing the Cougar at 5K using the intended donor transfer.
Authoritative snapshot: `output/itemkit/cougar-fineblade-longblade/checkpoint-v14.json`,
SHA-256 `b6d56161e76db9cf300712ac1e2c7375da8b6074afece5f023c9b2bd7f26fdfc`.
Use `production-5k-v2.json`, `native-family-v2/family-5k-v3.json`, and operational
state `production-run-v2/state.json`; the checkpoint's state copy is historical.
Both geometry attempts remain exhausted. The preliminary whole-item targets are
now melee 5K–15K and firearms 10K–25K triangles; shadow budgets remain separate.

The retained 200K/4K textured donor and independently repaired working mesh share
the exact native fit. The final natural parts total **4,956 triangles**, including
hidden caps: pommel 1,174, grip 1,360, blade/guard 2,422. Each is closed and wound;
native usable grip length is 0.1831918. Matched clay geometry was inspected before
maps. The ordinary unwrap overlapped and was rejected. A geometry-bound audited
atlas and explicit donor-reference finishing stage are now in the maintained runner.
The next gates are final UV qualification, clean front Cougar grip branding/plain
reverse, actual selected-to-active donor colour transfer at 4K, runtime maps,
500-triangle closed shadow proxies, native packaging and both Human client checks.

The 200K source is render-only; its non-manifold geometry does not become native
geometry. The repaired outer shell supplies the native working mesh. Private
fixture and production acceptance remain pending. Production promotion still
requires explicit final user approval.

## 5K UDF with 1K diffuse review (historical)

Authoritative resume snapshot: `output/itemkit/cougar-fineblade-longblade/checkpoint-v13.json`,
SHA-256 `3243e0a9815734d3ae9cd8c361112ed1538685956f1666be2453c1296a5c08c4`.
Both geometry attempts remain exhausted. The new guarded export uses only the
retained 199,504-triangle UDF source and the same Comfy QEM midpoint reducer as
the earlier 2K comparison. Its 5,000-triangle target produced **4,962 triangles**.
No remeshing or shape sampling occurred.

The requested gallery is
`output/itemkit/cougar-fineblade-longblade/udf5k-review-v1/index.html`.
It contains nine exact matched camera angles, each lit and unlit, using an actual
1024-square embedded diffuse derived from a 4096-square appearance bake. Retained
raw reduction, diagnostic UV mesh, maps, 1K/4K textured models, scene, sheets,
launcher timings and receipts are bound by the checkpoint. Verification confirms
unchanged reduction corners/winding, actual embedded PNG content/dimensions,
matched cameras, 18 full-size renders, local gallery links and the two-attempt
ledger. The diagnostic atlas has zero raster overlaps at 4K/2K/1K, but its measured
1K radius-one chart-neighborhood test reports 29 pixels; it is not a production
UV approval. Original topology/native gates remain unchanged.

This review does not change the original runtime budget of 2,000 visible plus
500 shadow triangles or approve a source, native package, client matrix or
production promotion. Earlier geometry and texture reviews remain retained.

## Matched geometry and 200K diffuse reviews (historical)

Authoritative resume snapshot: `output/itemkit/cougar-fineblade-longblade/checkpoint-v12.json`,
SHA-256 `b511bf551fb4109e4b99ae401ad58b3319fa27dd885f9a14b755782df559c3b4`.
Both geometry attempts remain exhausted. All work below reuses retained geometry
and appearance; no new shape sampling occurred.

Nine matched neutral views compare the untouched 1,682,816-triangle generation,
199,504-triangle UDF export and 1,988-triangle reduction. The geometry-only gallery
is `output/itemkit/cougar-fineblade-longblade/stage-comparison-neutral-v1/index.html`.
Original surface speckling/striping is visible. The 200K export smooths and rounds
details; the 2K reduction loses blade channel/bevel definition and makes fastener
recesses and the pommel angular. Original-to-200K includes remeshing and reduction,
so these views do not isolate those two operations. A complete raw topology audit
has not been performed.

The user's all-stage textured comparison is deferred. The subsequent authorized
review shows **only the 200K UDF mesh**, with actual 1024 and 2048 square diffuse
textures derived from a 4096 square bake, using the same nine cameras and lighting:

- `output/itemkit/cougar-fineblade-longblade/udf200k-diffuse-review-v1/index.html`
- `output/itemkit/cougar-fineblade-longblade/udf200k-2k-review-v1/index.html`

Both include lit and unlit views. The diagnostic UV atlas preserves every original
triangle corner and isolates 141 problematic UV faces (0.0290 percent of surface
area). Raster overlap checks pass at 4K, 2K and 1K; measured 1K adjacent-chart
collisions at radius one are zero. Embedded PNG dimensions/content and identical
1K/2K geometry, UV arrays, cameras and lights were independently verified in
`udf200k-texture-resolution-verification-v1.json`. Four-thread render timings and
fresh launcher receipts are retained. The first sparse UV layout remains failed.

The repaired 152,674-triangle outer source passed its independent physical and
internal visual review, but its production source unwrap failed with 86 bad faces.
That failure is retained separately from the diagnostic 200K atlas. No native
donor, fitted assembly, runtime package, client matrix or production acceptance is
claimed. The current private family/fixture remains v2 with the accepted Human
1.1.0 bank. Review requests do not approve an asset or resume the historical donor
manifest automatically; select and bind the next exact source before processing.

## Bounded UDF repair and private fixture (historical)

Authoritative resume snapshot: `output/itemkit/cougar-fineblade-longblade/checkpoint-v11.json`,
SHA-256 `adf8d3749dd59c8cd9508d89d9ba21a5770e649fb246d016005c4e01e929fd42`.
Both geometry attempts remain exhausted. No third geometry sampler.

The SDF manifold export was collected successfully but rejected: 151,821 boundary
edges, 41 non-manifold edges and 149,822 invalid vertex links. Its failed first
request encoding and corrected second request/collection are retained separately.
Do not treat the SDF output as a native candidate.

The qualified `udf-outer-repair-v1/repair.json` separates pinched UDF shell fans,
subdivides 21 residual parallel edges (82 faces), and retains the enclosed inward
shells separately. Maximum local surface-offset bound is 0.000003 source units
(0.004608 source voxels). The outer mesh has 152,674 triangles, no boundary,
non-manifold or inconsistent edges, positive volume, and genus 11. It still needs
the independent vertex-link and actual visual checks. Its exact GLB hash is
`ec58e49e87697e591041fbff11dc182d837f06546048b16ec07bfd90b9153b6c`.
Running intake/render: `runtime-v4/udf-outer-intake-v1-launch/` and
`runtime-v4/udf-outer-colour-preview-v1-launch/`, session 82705. Forty-three focused
tests passed after adding the physical source gate, including vertex-only contacts.

If the repair is unusable after physical, visual or reduction checks, the user's
latest instruction is to show matched textured UDF and SDF **2,000-triangle**
exports from multiple angles. Produce that comparison before further repair loops.

The current qualified private family is `native-family-v2/family.json` (slot 071),
with the accepted Human 1.1.0 bank and private floor template in its effective
stack. The template and exact Human HAK are in
`output/itemkit/private-fixture-template-v2/fixture-template.json`.
Use `output/itemkit/runtime-v4/local.fixture-v1.json` for the final native/fixture
chain; source-only work retains `local.native-v1.json`. The source donor still
needs a real 4K UV bake and visual approval before fitting. No native asset,
client validation or production acceptance is claimed.

## Source topology correction (historical)

Current hash-bound resume snapshot: `output/itemkit/cougar-fineblade-longblade/checkpoint-v10.json`,
SHA-256 `8a788a23afb6c3d8198c0590ccf98beb621ed525c3c5cee9ea0277f91f9e551f`.
Both geometry attempts are exhausted. Background routing and the second geometry
and appearance jobs succeeded; never submit another geometry sampler.

The deterministic UDF source export is rejected for native processing: 378 edges
have four incident faces and 662 vertex links are invalid. It has no boundary
edges, winding conflicts, duplicate faces or zero-area faces, but is not manifold.
Its retained visual previews do not establish physical validity. Blender and xatlas
UV retries failed; preserve those artifacts and do not relax overlap gates.
The next qualified operation is the fresh mesh-only SDF manifold export at
`source-export-sdf-v1-input/asset.json`; inspect physical topology before UV work
and review the thin blade and pommel aperture again. No new shape sampling.

The current CPU binding is `output/itemkit/runtime-v4/local.native-v1.json`.
The verified xatlas library uses compact per-patch uploads; headkit's default
local group limit remains 17, while the item source-donor policy explicitly permits
128 disconnected repair patches. Zero overlap and bounded affected area remain
required. The full helper suite passed 2,032 tests with two skips before the new
bounded export-setting extension; three extension tests pass and its full suite
is pending.

The historical PR42 Human namespace/family is superseded by the accepted shipped
PhenoMorpher 1.1.0 contract, SHA-256
`582c25d1908854477fdff7a6b89655f6d6bef5a76c607875f0a909a681e1672a`.
Qualified `output/itemkit/current-human-bank-v1/selection.json` retains 147 published
resources (241,182,864 bytes), plus the unchanged shipped appearance table. Both
Human sexes use appearance 15100; the female shared animation library is included.
The current complete native-family/fixture binding is pending. No body assets
have been changed and no native/client/production acceptance is claimed.

## Conditional background correction (historical)

Current hash-bound resume snapshot: `output/itemkit/cougar-fineblade-longblade/checkpoint-v8.json`,
SHA-256 `754f7aacd38e0c36f2e57a17bff860c478a28dba2e0d7cecdb068d1cf5937f56`.
Appearance token `9feb6a708d0a49929ca218b926e93e0c`, prompt
`d5699f58-2c5f-44f6-983c-c3f3ed521bea` completed in 42.98 seconds. Its decoded
GLB is byte-identical to geometry attempt 2. The qualified collection launch is
`runtime-v3/appearance-1-collect-launch/launch.json`; retained portable input is
`appearance-1-retained-v1/asset.json`. Raw field SHA-256:
`4d6afca94b8bd0480f69bd2d09d39d830db6d79d10686e07353474639d279a13`.
All 822,848 six-channel voxels are finite; raw range is -0.01953125 to 1.03125.
Only interpolated samples are clamped for preview; raw appearance remains retained.

Pending source export: `source-export-1-request.json` via
`runtime-v3/source-export-1-request-launch/`. Use the configured 768-resolution UDF
and 200K high-resolution donor output, inspecting thin blade and pommel aperture
again. Export does not run another shape sampler. Current appearance preview work
is `runtime-v3/appearance-preview-v1-source-launch/` then `appearance-preview-v1-launch/`.
It samples colors at **original untransformed GLB positions** and attaches linear
vertex colors for diagnosis. It is not yet a UV-textured donor or a finished bake.
Do not sample the original field at fitted coordinates.

Native intake is now `native-contract-intake-v1/` via the qualified
`runtime-v3/native-contract-intake-v1-launch/`: eight stock resources from four
bound archives (391 MB total), with isolated empty override/HAK directories.
Native measurements are `native-measurements-v1/measurements.json`. The stock
short-sword grip belongs to part b (part m is the stock guard); the Cougar's
matching assembly may assign its own natural boundaries consistently. The stock
usable handle spans native Y -0.1073308 to 0.0758610, length 0.1831918.
The complete stock name index is `native-inventory-v3/inventory.json`, 113,538
resources read from two KEY files totaling 2.5 MB. The successful parser launch
is `runtime-v3/native-inventory-parse-v3-launch/`; prior inventory launches retain
format/isolation failures. Short-sword indices 1..6 are occupied; 7..25 are free
in stock. This is not yet the complete private-fixture stack/allocation contract;
the family remains pending-contract until its stock index and shipped Human
resource layer are bound. No gameplay tables, native package or client approval.

### Geometry review before appearance (historical)

Earlier hash-bound resume snapshot: `output/itemkit/cougar-fineblade-longblade/checkpoint-v7.json`,
SHA-256 `c5f396f6d0cf21fbdfc468da20fae6bd614c057e8002cb1cf1bf976ed59aa60b`.
Both permitted geometry attempts are used. Attempt 2 completed and was collected
as token `63c7144f2a45404ea7708f77b4c342b7`, prompt
`4fdb5263-f867-4a32-87b4-51d84bf1ca69`. **Never submit another geometry job.**
Its qualified collection launch is `runtime-v3/geometry-2-collect-v2-launch/launch.json`.
The original `geometry-2-collect-launch/` is an unused folder from a failed local
launch and is not a collection receipt.

The successful portable retained snapshot is `geometry-2-retained-v2/`;
`geometry-2-retained-v1/` is a retained failed helper attempt whose absolute asset
paths were rejected. Its raw bytes are unchanged but its manifest is not usable.
Raw GLB SHA-256: `85c6176cd6f12de305ac31c7ef30fca0eee7cf92e6562b4904115d8a142a51cc`;
saved-shape SHA-256: `ac66c046c46065256d705479bbe51c5ba97c69e826304ab52d269dd8980b8ed9`.

Seven global-axis views and six brighter matched broad-face/detail views passed
the visual geometry gate: the background sheet is absent, the continuous thin
blade/channel and usable grip remain, and the pommel aperture is visibly open
from both faces. The generated surface retains faceting and fine dark pinpricks;
keep these explicit cleanup/review items and retain the unchanged donor.
The qualified four-thread render launches are `runtime-v3/geometry-2-inspection-v1-launch/`
and `runtime-v3/geometry-2-details-v1-launch/`. Raw axes are not native weapon axes:
the `clay-tip` / `clay-pommel-underside` views show its broad faces.

Current generation input is `appearance-input-v1/asset.json`, with the exact raw
mesh, shape and all visual-review evidence bound in its manifest. Its decision
is `appearance-input-v1/geometry-review.json`. Appearance preparation is
`runtime-v3/appearance-1-request-launch/`; intended request is `appearance-1-request.json`.
Verify preparation and submit/collect that appearance token once. This approves
only appearance on the saved shape; native fitting, package, client and production
acceptance remain pending. The same runtime bindings and durable ledger apply.

### Background qualification before attempt 2 (historical)

Earlier hash-bound resume snapshot: `output/itemkit/cougar-fineblade-longblade/checkpoint-v6.json`,
SHA-256 `b65d81df113f9d0a952d5b0c24386b21388975f3fb18b19f5486304d9457fa95`.
Its explicit current conditioning is `normalized-background-v2/asset.json` in that
asset directory, reviewed through `runtime-v3/background-review-v2-launch/launch.json`.
Original RGB is byte-identical (maximum difference zero); the original-resolution
mask retains a 1,325-pixel internal pommel aperture. The normalized mask has 100
one-pixel resampling-fringe pixels, explicitly separated from empty background.
Its FOV is 58.56971487162531 degrees. `normalized-background-v1/` is a retained failed
review snapshot with no approved manifest; never select it by filename recency.

Final validation is 2,009 helper tests, two skipped: all 381 tools tests passed in
`runtime-v3/background-tools-v2-tests.log`; heads 60, phenomorpher 170, phenotypes
1,332 (two skipped), robes 66 passed in `runtime-v2/background-full-helper-tests.log`.
That older full log's two tools failures are superseded by the final tools run;
they caught the subsequently fixed background-decision/staging-variable collision.
The final alpha path preserves source RGB until Comfy applies its mask once.

The qualified second request is `geometry-2-request.json`. Its current submission
launch is `runtime-v3/geometry-2-submit-launch/`, collection directory `geometry-2-job/`.
Read the durable ledger before resuming; this is the **last allowed geometry attempt**.
Once submitted, collect/reconcile its original token rather than making any further
geometry request. This snapshot does not approve a generated mesh or appearance.

The user identified background removal as the first geometry failure and required
input-dependent routing. Geometry attempt 1 is complete and **rejected**, with its
unmodified outputs copied to `output/itemkit/cougar-fineblade-longblade/geometry-1-retained-v1/`.
The decision is `geometry-1-review.json` in that asset directory. A large background
sheet blocks appearance. The first inspection images are diagnostic only because
their launcher omitted itemkit helper declarations. No appearance was requested.

Current runtime bindings are `output/itemkit/runtime-v3/local.background-v1.json`;
installation and process receipts are `install-background-v1-launch/launch.json`
and `background-v1-process.json` in that runtime directory. The prior optimized-v2
service was stopped with an empty queue; its stop receipt remains in runtime-v2.
The same durable ledger is retained, with **one geometry attempt used and one left**.

New calibration input: `output/itemkit/cougar-fineblade-longblade/background-calibration-input-v1/asset.json`.
The original image is opaque, so the compiled Comfy graph selects local background
removal. Valid existing transparency skips that model; empty/clipped alpha fails.
The installed `birefnet.safetensors` is now frozen at SHA-256
`9ab37426bf4de0567af6b5d21b16151357149139362e6e8992021b8ce356a154`.
Its Comfy-resolved path and bytes use the same hash-keyed loader gate as other
checkpoints. The original six generation checkpoints/sampler settings are unchanged.

The graph retains full-resolution foreground mask/RGBA cutout, normalized mask,
matching normalized RGB images and camera evidence. Review thin blade/tip and the
pommel opening before updating `inputs.foregroundMask` and `approval.background`.
Geometry/appearance now require the exact source/image/mask hashes and a background
review, and reject full-canvas/clipped masks or visible pixels outside the mask.
The old normalized-v1 snapshot cannot pass this new gate. No clay reference is used.

Background calibration preparation is `runtime-v3/background-calibration-request-launch/`;
inspect its receipt/logs and `background-calibration-request.json` before dispatch.
Calibration does not consume the remaining geometry attempt. The 38 focused routing,
loader, graph and item-contract tests passed; full helper validation of this change
is running in `runtime-v2/background-full-helper-tests.log`. The prior optimizer
validation below remains historical. No second geometry job is authorized by a
numerical mask check alone: inspect the actual cutout first.

## Optimized runtime and first generation (historical)

Current hash-bound resume snapshot:
`output/itemkit/cougar-fineblade-longblade/checkpoint-v5.json`, SHA-256
`5e22c61a743de9a425ed51b450291959cc9fff4485efe40ded5c55bd9a7e6d6a`.
It binds the acknowledged first geometry job and approved conditioning. Its ledger
copy is historical; read the durable ledger bound by its current runtime bindings
for live reconciliation/collection state. Earlier checkpoints remain immutable.

This section supersedes the conditional-runtime and historical stops below. Current
bindings are `output/itemkit/runtime-v2/local.optimized-v2.json`; process receipt is
`optimized-v2-process.json` in that directory. Installation receipt:
`install-optimized-v2-launch/launch.json` (exit zero, unchanged inputs). The earlier
optimized-v1 installation changed the deployment files it had declared as inputs;
its result is retained as invalid. The subsequent v2 launch verified the installed
bytes against their new frozen snapshot before the service started.

Runtime inventory now excludes inactive base-interpreter site-packages and
nonexecution documentation/sample assets. Fresh membership and byte checks cover
18,530 runtime files / 3,408,261,141 bytes. Loaded module origins are included even
with an unusual extension. No timestamp cache replaces a byte check. Source-code
hash memoization uses actual source bytes and still checks retained live objects.
Duplicate file pins are hashed once per verification call. The server owns runtime
verification at preparation and under the submission lock, avoiding duplicate reads
by the client/launcher. Calibration scopes only MoGe, eliminating 14,429,428,691 bytes
of unrelated checkpoint inputs. Other stages scope their selected checkpoints.

Adapter startup fell from 418 to 125.2 seconds. Verified calibration preparation
completed in 127.329 seconds without extending the request timeout. Measurements:
`runtime-v2/optimization-scope-v1.json` and `optimization-live-metrics-v1.json`.
Full helper coverage on frozen code is 2,000 tests, two skipped: the 272 affected
headkit tests in `optimized-helper-tests.log`, plus all remaining catalogued modules
in `optimized-full-helper-remainder.log`; matching timing JSON files are retained.

Calibration completed successfully (6.71 seconds in Comfy). Both image/camera
passes agree: normalized SHA-256
`0bafc6e1083911adeb5db71d841a5bfdb023d39e529456f2417f431345738bab`,
camera FOV 51.26134744335198 degrees. Visual review retained the complete blade tip,
channels, guard, grip and open pommel loop. No clay reference was created. Current
geometry input manifest and review are
`output/itemkit/cougar-fineblade-longblade/normalized-v1/{asset,input-review}.json`.
The original reference is retained separately. Calibration job/collection:
`output/itemkit/cougar-fineblade-longblade/optimized-calibration-job/`.

Geometry attempt 1 uses `geometry-1-request.json` and `geometry-1-job/` in the same
asset directory. Token: `d63ed72ea144468fa309d7a890ee0f55`. At this checkpoint the
ledger acknowledged submission (prompt `5ea919dc-5a2a-4175-8317-db81a254a539`),
using **one of two** geometry attempts. Collection is running under the original
45-minute deadline, measured from the saved intent's `started` timestamp. Read the bound durable
ledger and `submission.json` before continuation; reconcile an uncertain intent by
its original token. Never resubmit it or initialize another ledger. Preparation,
submission and collection launches are explicitly named `runtime-v2/geometry-1-*`.
The two-attempt cap remains enforced. Appearance requires visual acceptance of the
actual generated mesh and its saved-shape binding. Native/client/production gates
remain pending; the family profile is still pending its effective native contract.

## Conditional-runtime continuation (supersedes the historical runtime stop below)

The user authorized fixing conditional-setting verification and continuing generation
with the same two-attempt trial limit. Current runtime bindings are
`output/itemkit/runtime-v2/local.conditional-v6.json`; the sequentially started service
is recorded in `conditional-v6b-process.json`, with `conditional-v6b.stderr.log` in
the same directory. Do not return to the historical `local.trial-v1.json` adapter.

The installed `verified_startup.py` checks complete module bodies against freshly
compiled frozen source before execution, including cached bytecode. Retained code
objects remain checked; modules loaded before the bootstrap retain conservative
static state checks. Conditional settings are accepted through verified execution
or safely resolved branches, not by accepting arbitrary branch values. Source,
runtime-file, checkpoint, queue and saved-shape checks remain enabled.

The final focused verifier suite passed 116 tests; runtime inventory tests passed
five tests. The final tools group passed 368 tests (`runtime-v2/final-tools-tests.log`
and `final-tools-timings.json`). The other full-helper groups passed: heads 60,
phenomorpher 170, phenotypes 1,332 (two skipped), robes 66. The initial full-suite
tools run correctly rejected a source edit during testing; the frozen rerun above
supersedes that group, retaining both logs.

Startup reached the server after 418 seconds in the adapter. Runtime inventory
includes approximately 62,500 existing Python environment files (5 GiB), separately
from the 1,221-file frozen source inventory; these are not Cougar outputs. The live
request check must still pass before dispatch.

The current original-image calibration snapshot is
`output/itemkit/cougar-fineblade-longblade/calibration-input-v1/asset.json`.
Its reference review authorizes calibration only: normalized framing and inferred
camera remain pending. Calibration preparation is recorded under
`output/itemkit/runtime-v2/calibration-request-v1-launch`. Consult its receipt and
stderr before resuming; never assume a prepared request or a submitted job exists.
The durable ledger remains the one bound by the current bindings. At this update,
no calibration or geometry job had been submitted and both geometry attempts remained.

## Historical implementation checkpoint

This is an **implementation and reference-intake checkpoint**, not a generated item
or production acceptance. Use the user's single detailed image for both geometry
and appearance. No clay reference image is required. Inspect untextured generated
geometry before requesting appearance on its saved shape.

## Authoritative local bindings

These paths are relative to this checkout and intentionally ignored:

| Role | Binding |
|---|---|
| Original intake | `output/itemkit/cougar-fineblade-longblade/intake/reference-original.png` |
| Current asset/profile snapshot | `output/itemkit/cougar-fineblade-longblade/reference-reviewed-v1/asset.json` |
| Current stage state | `output/itemkit/cougar-fineblade-longblade/run-v4/state.json` |
| Final hash-bound resume checkpoint | `output/itemkit/cougar-fineblade-longblade/checkpoint-v4.json` |
| Current local runtime bindings | `output/itemkit/runtime-v1/local.trial-v1.json` |
| Authorized trial initialization | `output/itemkit/runtime-v1/trial-init-launch/launch.json` |
| Python/Blender migration | `output/itemkit/runtime-v1/migration-v2.json` |
| Actual reference preparation launch | `output/itemkit/runtime-v1/trial-v4-prepare-launch/launch.json` |
| Original-preservation review | `output/itemkit/runtime-v1/trial-v4-review-launch/launch.json` |
| Durable original-copy binding | `output/itemkit/runtime-v1/durable-reference.json` |
| Live preflight | `output/itemkit/runtime-v1/trial-preflight.json` |
| Task-started Comfy process | `output/itemkit/runtime-v1/comfy-diagnostic-process.json` |
| Task-started service cleanup | `output/itemkit/runtime-v1/comfy-diagnostic-stop.json` |

The original image SHA-256 is
`d17b9478d822d534955c88f2e07c35828213debc3a1dd1ccfa80c9fa3e75549b`.
A byte-identical copy lives under the primary checkout's ignored shared tools bank,
`itemkit-assets/cougar-fineblade-longblade/intake-v1`; consult the durable binding
above for the actual path. The temporary attachment is not the sole retained copy.
Reference landmarks are initial visual pixel readings, not approved normalized
conditioning overlays. Reference-design review does not grant camera, generated
geometry, native, client or production approval.

## Generation remains blocked

All six installed checkpoint files matched the frozen headkit checkpoint hashes.
The pinned adapter was installed into a new `custom_nodes/srn_headkit` directory.
The task-started service reached an empty queue on loopback, but
`/headkit/runtime-identity` returned **HTTP 409**. Its current executing source/runtime
has therefore **not qualified**. Do not bypass verification, submit a legacy graph,
or claim that a generation succeeded. The adapter's source snapshot and service
logs are retained under the runtime bindings above.
After confirming the queue remained empty, the task-owned service was stopped.
The installed adapter was retained; no unrelated service or queue was stopped.

A diagnostic-only logging change now preserves the actual startup exception without
changing verification decisions. `comfy-diagnostic.stderr.log` identifies
`loaded_source_code` → `_source_constructor_literals` → `_unique_source_value`:
**Ambiguous source literal assignments cannot be safely matched**. A deterministic
scan of the frozen source inventory reproduces constructor-analysis rejection in
67 Python files (`constructor-source-diagnostics.json`). This scan is not a claim
that all 67 files executed. One concrete example is `comfy/clip_vision.py`, whose
constructor assigns `return_all_hidden_states` true or false according to model
type. The frozen verifier rejects such conditional assignments. Do not skip those
checks or treat a live endpoint/loaded checkpoints as runtime qualification.
The new diagnostic startup again returned HTTP 409 with an empty queue; its owned
service was stopped. Resolving this needs a qualified conditional-state verifier
or a compatible frozen runtime, preserving the existing stale-code/state tests.

The user subsequently confirmed that no shared ledger exists and authorized two
attempts per model for this trial. A fresh durable ledger is now explicitly bound
by `local.trial-v1.json` and initialized by `trial-init-launch/launch.json`, with zero
submitted jobs. That direction supersedes the earlier ledger clarification stop.
The shared submit lock enforces two geometry attempts per stable model across input
changes and resumed runs. Uncertain POSTs count; preflight failures before POST do
not. Appearance/export reuse the saved shape. Never initialize a replacement to
reset this trial. Earlier binding snapshots and receipts remain historical.

The current run is freshly prepared against the trial bindings and current helpers.
Its preparation review covers byte-preserved original intake only; it does not
approve normalized conditioning or generated geometry. The first run and checkpoint
remain immutable history and must not be resumed with changed dependencies.

Native packaging remains `pending-contract`. Installed stock short-sword parts,
icons, `baseitems.2da` and `nwscript.nss` were extracted read-only into
`output/itemkit/native-intake-v1`; that donor subset is **not** a complete effective
content-stack inventory. Resolve the actual private-fixture stack and review its
native grip/frame/dimensions and collision inventory before enabling packaging.
Camera calibration and normalized-image review also remain pending.

## Verification evidence

After the user's trial clarification, the full helper suite executed **1,984 cases**
across five import-root groups (`trial-policy-suite.log` and its timings JSON).
Its one real failure was the isolated startup-helper fixture omitting the newly
introduced diagnostic logger. The fixture now supplies and verifies that logger;
the corrected case, all itemkit cases and all trial-policy integration cases passed
in a **41-test focused rerun** (`trial-policy-corrected-tests.log`). The full-run
failure remains recorded. Nested intentionally failing test-runner fixtures are not
implementation failures. The dependency catalog is current and `git diff --check`
passed. No pack inputs changed and no packs were rebuilt.

Trial tests cover independent models, changed references, accidental renaming,
uncertain submission/reconciliation, preflight failures, saved-shape appearance and
export, ledger replacement rejection and item output collection. Item collection
now verifies its `itemkit` output prefix, while legacy headkit receipts keep their
original default prefix.

Test subprocesses created 102 bytecode cache files in the pinned Python package
bank. Those files are preserved in `runtime-v1/test-bytecode-archive`; the original
package membership was restored before the final verified preparation/review run.
The v3 preparation launch correctly rejected the extra membership before processing
and remains retained. Future suite launches should inherit `PYTHONDONTWRITEBYTECODE=1`
as well as use `-B`, including subprocesses.

The initial item/headkit contract run passed 280 tests. The final focused contract
and shared-tool fixture run passed 49 tests, including the item output namespace,
frozen settings, measured-landmark gate and stale review/dependency tests.
Logs: `output/itemkit/contract-tests.log` and
`output/itemkit/final-contract-tests.log`.

The full helper run executed 1,974 cases across its five import-root groups, including
the repository's import regressions. Its first run had failures from temporary
repositories located inside this linked worktree, and from item schema edits made
after that long-lived test process imported the earlier module. All 11 affected test
files were rerun with stable final sources and an external temporary directory:
**167 tests passed** (`corrected-suite.log`, `corrected-suite-timings.json`). The final
headkit and test/CI-selection run passed **184 tests** (`final-headkit-tests.log`).
The initial full-run failures are retained rather than relabelled as a clean pass.
No pack inputs changed, so no HAK pack rebuild was required.

Real Blender and NWN checks used **synthetic cuboid geometry**, not the Cougar:

- `runtime-v1/item-blender-smoke-v5/smoke.json`: exact-position seam welding,
  natural cuts and caps, uniform fitting, reduction, 4K/2K/1K/512 UV audits, 4K bake,
  closed/wound shadows and corner-array export. Zero visible bake misses; all
  3,685,994 visible mapped texels retained the constant synthetic donor colour.
- `runtime-v1/synthetic-native-v1/smoke.json`: padding and texture derivation,
  installed NWN compilation, fixed-string sanitization, geometry/normal/UV/shadow
  roundtrip and exact HAK payload hashes. Processing took 16.5 seconds.
- `runtime-v1/synthetic-render-v1/result.json`: 16 matched views plus three icons,
  four CPU threads, actual 1K runtime diffuse; 56.6 seconds. The textured oblique
  view was inspected. Synthetic render success is not Cougar visual acceptance.
- `runtime-v1/synthetic-bake-miss-v1/negative-test.json`: a target deliberately
  displaced from its donor was rejected with 2,717,224 visible misses, rather than
  silently extending padding over failed surface pixels.
- `runtime-v1/synthetic-fixture-v3/smoke.json`: real GFF/archive/NWScript tools
  produced the blueprint, compiled entry script and module. The compiler uses an
  isolated empty resource root and the pinned `nwscript.nss`, with game keys and
  overrides disabled. This minimal synthetic module is not a playable fixture or
  evidence of Human client validation.

All paths in this list are beneath `output/itemkit`. Failed earlier attempts remain
retained. The stock sword's cleanmodels `OTHER` classification failed Neverblender's
enum; the separate runtime import smoke succeeded with an unchanged stock head.
That migration qualifies only shared Python/Blender launching, not the sword's
native contract or any equipment asset.

## Continue

Follow [the itemkit runbook](item-generation-toolkit.md). First resolve the live
runtime identity failure; the authoritative trial ledger is now bound. Freeze a new binding snapshot
and input declaration after any dependency change. Then calibrate and review the
single detailed image, generate and inspect geometry, and bind both geometry and
saved-shape hashes to the appearance request. Preserve raw and fitted donors.
Complete the measured native contract before fitting and packaging. The actual
Cougar mesh, maps, models, blueprint, HAK, private module and Human client review
have **not yet been produced**. Production promotion still requires explicit user
approval.
