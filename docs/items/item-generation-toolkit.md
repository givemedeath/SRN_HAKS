# Item toolkit: Cougar Fineblade pilot

For new runs, follow the [four-weapon lessons and faster finishing sequence](four-weapon-lessons.md).
Use the maintained `render-variants` worker for finish-only variants sharing one
scene; it reuses the eight verified clay views while rendering every finish's
lit/unlit views and icons. Separate geometry variants into separate batches.
The four completed weapons are approved; the SMG remains on hold.

The [early-check and recovery guide](early-checks-and-recovery.md) documents the
automatic pre-bake UV/donor checks, measured per-part silhouette shadows and
retained-bake recovery worker. Choose and review the projection plane; keep all
failed bake data and use fresh recovery outputs instead of repeating a completed bake.

Firearm sizing now uses the user-approved
`colt-l36-approved-firearm-grip-v1` reference in
`firearm-grip-standard-v1.json`: the thickness-based Colt fit enlarged uniformly
by 15%. Bind this reference for new firearms and measure their own grip landmarks;
preserve proportions and grip/barrel angle. Do not impose the Cougar melee usable
length or reuse the Colt source multiplier. Review native hand placement on both
shipped Human bodies. The Cougar standard remains applicable to melee weapons.
Firearm fitting rejects any other standard; replaying a pre-Colt firearm fit
requires `"historicalGripStandard": "cougar-approved-grip-v1"` in its fit config.

For new items, the user-selected authoring default is **smooth clay for geometry,
detailed color for saved-shape appearance** (2026-10-23). Use `clay-detail-v1` after
reviewing the pair. Remove shallow decorative grooves, serrations, stippling,
fine grip ribs, lettering, wear and tiny fasteners from clay; retain the silhouette,
proportions, major part boundaries, raised controls, structural members and open
spaces. The detailed original supplies surface appearance. The Ingram Smartgun X
clay v2 demonstrates the requested level of surface simplification; its alpha still
needs conditioning review. Keep all earlier references and accepted outputs.
Legacy CLI/intake defaults remain compatible and do not grant generation approval;
select the reviewed clay/detail route explicitly for new work. Head-specific
landmark alignment, skin/hair ownership and PLT processing do not apply.
When a separate raw clay source is retained, bind it as `inputs.clayReference`.
The geometry background review binds that source's hash and actual alpha route;
the detail review binds the original detailed reference independently. Without a
separate clay source, the existing reference binding remains the default. Both
generation stages consume the clay source when present, so changed source bytes
invalidate its review. This does not approve unreviewed masks or paired framing.
Untextured **renders of generated geometry** remain a review gate before appearance.

Use a separate ignored generation binding for calibration, geometry, appearance
and GPU export. Retain the Python/package, Comfy source, model, endpoint and ledger
bindings; omit Blender, the game client, Embree, UV libraries and fixture HAKs.
CPU processing keeps its separately verified binding. Do not merely filter an
input list after loading a broad binding: binding validation would still check
the unused tools. Generation orchestrators should use `consumed_pins()` to obtain
already verified file pins directly. The legacy `consumed_inputs()` path-list
interface remains compatible. Both reject conflicting pins before deduplication
and open a fresh verification pass for each call; dispatch and completion retain
their independent fresh byte and runtime checks.

Current implementation and pilot status: [Cougar checkpoint](cougar-fineblade-checkpoint.md).
Knife preparation and corrections: [workflow audit](cougar-workflow-audit.md).

Intake accepts `--id` and `--family shortsword|dagger|longsword`; omitted values preserve the
original Cougar shortsword defaults. New weapon fitting binds `inputs.gripStandard`
to the approved grip JSON. Dagger profiles use the measured installed dagger
contract, not copied shortsword donor dimensions. Optional family `resources`
supplies `texturePrefix`, `blueprint`, `hak`, `module` and `displayName`; collision
checks include both model/icon appearances and explicit texture/blueprint names.
Longsword profiles verify BaseItem1 / WSwLs / ModelType2 against the effective
stack, use separately measured native donors, and start at a recorded12K visible
budget. Private fixtures accept `inputs.comparisonBlueprint` and additional
numbered roles such as `comparisonBlueprint2`; each native UTI supplies its own
verified resref/tag. All comparisons are included in consumed-input verification,
collision checks and the player's inventory. Existing single-comparison defaults
remain compatible.
For post-bake changes, `resize-corners --arrays NPZ --matrix JSON --output FRESH
--bindings BINDINGS` runs through the verified Python launcher and retains exact
native normals, UVs, protected axes and shadow winding. Rebuild dependent package
and fixture outputs for every accepted geometry revision.

Pistol intake uses `--family firearm-sling --id EXPLICIT_DESIGN_ID`. It allocates
the complete pistol to bottom (9,992 visible / 500 shadow), with four-triangle,
zero-shadow inactive slots, within the complete 10,000 / 500 cap. Intake leaves
the generic native gate blocked and grants no fit or generation approval.
The maintained separate firearm adapter is exposed by `firearm-inputs`,
`firearm-prepare`, `firearm-native` and `firearm-fixture`. A preparation specification binds a source
profile with the verified effective stack, comparison HAKs, explicit resource
identity and each Color's final corner arrays, 1K diffuse and 32x64 RGBA icon.
The source profile supplies namespace/table evidence only, not a pistol grip fit.
Use `firearm-inputs --spec SPEC --bindings BINDINGS --output INPUTS` before the
verified launcher invokes `firearm-prepare --spec SPEC --output FRESH`.
For compilation, use `firearm-inputs --prepared PREPARED --bindings BINDINGS
--output INPUTS`, then launch `firearm-native --prepared PREPARED --output FRESH`.
Both mutating commands also require `--bindings BINDINGS`.
For the private fixture, enumerate `firearm-inputs --native NATIVE_JSON --manifest
ASSET --bindings BINDINGS --output INPUTS`, then launch `firearm-fixture --native
NATIVE_JSON --manifest ASSET --bindings BINDINGS --output FRESH`. The asset supplies
the pinned fixture template and Human donors; all fixture dependency HAKs stay in
the ignored local bindings. Stock KEY namespaces include UTI names as well as
models, icons and textures, so blueprint collisions cannot hide in stock indexes.

The adapter re-resolves allocation against the effective stack plus comparison
HAKs, checks each complete Color assembly, emits the private table override and
all six placeholder resources for two Colors, compiles fresh models, and audits
exact native corners, render/shadow flags, blueprint part bytes and HAK payload.
The fixture consumes those exact packaged UTIs, makes both variants accessible,
and adds ranged/reload, projectile/ammunition and variant/placeholder client
checks. This static/native tooling does not establish pistol grip placement,
visual acceptance or observed client behavior. Those gates remain required.

A firearm processing profile may enable fitting only after binding its own
reviewed Sling stack, `whole` model and `icon` donors, native frame and grip.
Record the effective `modelType` separately from `packagedModelType: 2`; the latter
declares the isolated override. Pistol `iconDimensions` contains only `b: [32,64]`.
Its exact assembly is the design in bottom and `hidden-placeholder` in middle/top.
Legacy melee model allocation remains unavailable for firearms.

The fit binds `workingSourceSha256`, measured `gripEndpoints`, `gripSurfaceFaces`
and a unit `nativeGripDepthAxis` perpendicular to the fitted grip axis. The surface
selection excludes the barrel/guard and is specific to that working mesh. Measure
all five standard sections after the uniform fit. A midpoint width/depth departure
over 5% retains a measurement report and requires an explicit `gripDeparture`
review tied to its `measurementDigest`; do not silently distort the design.
The same recorded transform applies to donor and working geometry. Fit imports each
distinct source once, measuring the working object before transformation.

Whole-firearm processing uses only its active slot, no `joinY` cuts, and no invented
cut caps. Atlas, bake, shadow and export operate on that mesh; budgets add the two
inactive four-triangle placeholders. `render.firearmViews` supplies exactly `left`,
`right`, `muzzle`, `rear`, `top`, `underside`, `grip` and `oblique`, each with finite
`direction`, `target`, nonparallel `up`, and positive relative `scale`. Clay, lit and
unlit renders share these cameras. `run --stage export` produces `variant.json`
with bound arrays, runtime texture and icon; combine reviewed Color variants through
the separate firearm package commands above. Generic melee `native` is blocked.
The final fixture extracts its own MOD and verifies every resource byte against the
staging payload before returning success.

The Cougar uses a short-sword native contract and the user-approved calibrated grip
defined in [weapon grip sizing](weapon-grip-sizing.md). Future weapons must use that
measured usable length, width and depth as their default hand-fit reference, rather
than scaling from total weapon bounds or copying the Cougar's historical scale factors.
Its reverse has symmetric major construction and no
required text. Preserve blade bevels/channels, compact guard, usable grip, hardware
and the open pommel loop. Fine grip pattern and front branding belong to appearance.

## Source and runtime identity

The integration baseline is headkit commit
`e607a617c273828a37d8fc56dd43d7d8a0070844`; `tools/itemkit/source-lock.json` records
original source hashes and the supplied weapons-kit reference hashes. Headkit source
is local to this checkout. Its original request CLI delegates to the shared
`headkit.generation.prepare_request`, also used by itemkit. Do not execute helpers
or borrow binaries from another worktree.

Use bundled desktop Python and the durable shared tool bank. Runtime paths belong
in ignored local bindings, never the portable examples. Follow
[shared tooling](../shared-tooling-and-workflow.md) for fresh migration smokes.
The item bindings extend headkit's local binding format with `submissionLedger`,
`itemTrialId`, and, for fixtures, `fixtureHaks` (name to pin).
All required Python packages must resolve from the byte-bound `pythonPackages`
installation; configure its directory in `PYTHONPATH` before launching Python.

Install the pinned headkit Comfy adapter only after freezing the executing Comfy
source inventory and external implementation roots. A request requires the running
adapter's source/runtime identity, installed adapter bytes and model hashes to match.
Do not substitute a historical workflow when these checks fail. Items share headkit's
submission implementation, queue lock, 45-minute deadlines, reconciliation and
coordinated release; an uncertain job must never be resubmitted automatically.

For Comfy versions with conditional runtime settings, start the installed adapter's
`custom_nodes/srn_headkit/verified_startup.py` with the same arguments normally passed
to `main.py`, using Comfy's bound Python and working directory. Its audit hook compares
each managed module's complete code object with a fresh compilation of its frozen
source **before execution**, including when Python loads a cached `.pyc`. This proves
the actual conditional assignments and default factories without rerunning them.
The later verifier still checks retained function bytecode and unchanged source/runtime
files. Preloaded modules and ordinary `main.py` startup retain conservative static
state validation; unresolved predicates remain errors. Source scope matches the frozen
inventory: nested environment files have their own runtime inventory, while explicitly
declared implementation dependency roots remain covered by source verification.

The current user-approved limit is **five geometry generation attempts per model**
(2026-10-23), including attempts already used. Historical two-attempt ledgers remain
valid until explicitly upgraded. Initialize a new bound durable ledger
once with `init-trial --bindings BINDINGS --evidence AUTHORIZATION` through the shared
launcher. This command refuses to overwrite an existing ledger. All item jobs use
that ledger; input revisions and resumed runs never reset the allowance. Attempts
are reserved under its submission lock. Uncertain POSTs and server rejections count;
local preflight failures before POST do not. Appearance and export reuse a generated
shape and do not consume another geometry attempt. To upgrade the existing trial,
use `set-trial-limit --bindings BINDINGS --maximum 5 --evidence AUTHORIZATION_JSON
--output FRESH_DIRECTORY` through the verified launcher. The authorization declares
`scope: all-items`, `maximumGeometryAttempts: 5`, and the user's authorization text.
It is a consumed, hash-bound input. The command holds the shared submission lock,
rejects outstanding jobs, preserves all job history, and retains before/after
snapshots plus an authorization receipt. Never reset the ledger to gain attempts.
Stable model IDs and original
reference hashes associate history across revisions and accidental renaming. Headkit's
existing CLI and global safety ceiling remain compatible.

## Commands and snapshots

Read-only entrypoints are `python -m tools.itemkit --help`, `status`, and `preflight`.
`intake --reference IMAGE --output FRESH_DIRECTORY` copies the original byte-for-byte
and creates a portable manifest/profile pair. `inputs` writes the launcher input list.

Processing uses this pattern with absolute local binding paths:

```text
<bundled-python> -B tools/itemkit/run_itemkit.py inputs
  --manifest ASSET --bindings BINDINGS --run RUN --stage STAGE --output INPUTS

<bundled-python> -B tools/phenotypes/launch_shared_tool.py
  --toolchain TOOLCHAIN --migration-receipt MIGRATION
  --tool python --output FRESH_LAUNCH --input-path-list INPUTS
  -- tools/itemkit/run_itemkit.py COMMAND --manifest ASSET --bindings BINDINGS --run RUN
```

Commands are `init-trial`, `prepare`, `request`, `submit`, `collect`, `reconcile`, `release`,
`run`, `resume`, `review` and `status`; use help for stage-specific arguments.
Submission/collection commands use bindings and the shared ledger rather than a run.
Use the same `--output` job directory for `submit` and `collect`: collection reads
that directory's immutable `submission-intent.json`. A new collection directory
cannot recover the submission contract. Preserve a failed-validation receipt and
its terminal ledger state; never reset history to retry a collection.
Include immutable request or job-intent files with `inputs --extra` before dispatch
or collection. Mutable ledger/state files are operational outputs, not frozen assets.

Freeze a new manifest for each phase. Preparation preserves the detailed image.
Record original pixel landmarks, material regions and the frozen generation settings
in the manifest. Input-review approval requires at least four distinct in-frame
landmarks; the complete sampler graph remains byte-bound to the toolkit source.
`request --stage calibrate` inspects the actual image before compiling its Comfy
graph. A meaningful, unclipped existing alpha mask bypasses background removal;
an opaque/effectively full-canvas image uses the installed, hash-bound local BiRefNet
model. Empty/clipped alpha inputs fail. Both detector/crop branches use the same
foreground mask. Comfy retains the original-resolution mask and RGBA cutout plus
the normalized RGB images and normalized mask for review. RGB design pixels are
composited from the source; no clay reference or design redraw is involved.

Inspect the tip, thin edges, grip, hardware and intentional openings in the mask
and cutout before any geometry submission. Pin matching normalized images as
`inputs.geometry` and `inputs.detail`, the mask as `inputs.foregroundMask`, and the
reviewed FOV. `approval.background` must contain `decision: approved`, the selected
`route`, `imageSha256`, `maskSha256`, `referenceSha256` and review `notes`. Geometry
and appearance reject a missing/stale review, full-canvas/clipped masks or visible
background pixels outside that mask. Background calibration does not spend a
geometry attempt; an already submitted bad geometry job remains counted.

Run geometry with the frozen single-image preset (shape1536, shape CFG12, texture
CFG1, texture12 steps; other sampler values unchanged). Retain raw mesh and shape.
An optional `geometrySeedOffset` (integer 0..2147483647) adds the recorded offset
to the three frozen geometry noise seeds only. Omission/zero preserves historical
requests. Use a fresh manifest and distinct offset for a new noise trial; identical
conditioning and identical seeds are not a useful retry. Appearance keeps its
saved-shape binding and its original texture seed. Every submitted geometry job
still counts against the shared model allowance.
`run --stage inspect` renders the raw mesh in seven directions without texturing.
Record the generated-geometry decision with both exact raw-mesh and saved-shape
hashes before requesting appearance. The generation engine verifies redecode
correspondence during collection. Retain the deterministic source export as
`inputs.geometryDonor` and appearance transport as `inputs.field`. Saved fields
may contain XYZ or integer BXYZ coordinates; only a single explicit batch zero is
accepted. Raw data stays unchanged. The sampler still rejects duplicate/out-of-range
coordinates and unreviewed decoder overshoot.

Before `run --stage donor`, inspect the exported thin blade, channels and openings
again and record `approval.sourceDonor` with `decision: approved`,
`geometryDonorSha256`, `fieldSha256` and review `notes`. The pilot's explicit
`processing.sourceFieldPolicy` is `{minimum: -0.02, maximum: 1.032,
allowDecoderOvershoot: true}`; this legacy policy remains supported. Other reviewed
ranges must also supply `fieldSha256` matching the retained field. Bounds must be
finite numbers, include [0,1], and remain within [-0.25,1.25]; values outside the
declared range fail before baking. Raw voxel attributes stay unchanged and samples
are clamped only after interpolation. The donor stage unwraps through the verified
CPU xatlas library, verifies unchanged triangle geometry in the original glTF frame,
bakes the retained field at 4K, then embeds an ordinary diffuse PNG in a retained
GLB. The source atlas is qualified at its actual 4K sampling resolution, including
a clear two-pixel chart-domain gutter. A bounded UV-only repair can isolate fewer
than 3% of faces and surface area; healthy domains, triangle positions and winding
stay exact. It rejects remaining overlap, degeneracy, missing charts or at least
0.1% unsampled surface. Candidate atlases and repair provenance survive failures.
Derived source maps are diagnostics; the final runtime atlas retains its separate
1K gutter and coverage checks. Source sampling remains in the original glTF frame.
Fitted coordinates cannot pass this source-frame check. Review fallback counts,
maps and the actual textured donor; a vertex-color preview is diagnostic only.

Import the reviewed high-resolution textured donor into a fresh fitting manifest,
with its own hash-bound review and retained donor-stage evidence. Keep the prior
manifest/run immutable when recording the donor hash and measured fit.

CPU stages are `donor`, `fit`, `reduce`, `unwrap`, `finish`, `bake`, `shadow`, `render`, `export`,
`native`, `fixture`, `client`. Each numerical success needs a recorded review before
consumption. Rejected parents invalidate descendants, including cached results.
Two failures on one code/manifest snapshot stop repeated processing. Preserve failed
attempts and use corrected snapshots; never overwrite historical receipts.

An independently repaired `inputs.workingMesh` may accompany the retained high-resolution
`texturedDonor`. Review the exact working-mesh hash in `approval.workingMesh`; fitting
applies and verifies the same uniform transform on both. Only the closed working parts
become native geometry. A render-only donor is not a native geometry approval.

Final item UVs use a geometry-bound atlas with explicit 4K/2K/runtime/512 audits,
bounded UV-only repair and a clear two-pixel runtime filtering gutter. Subtexel
triangles must remain within sampled charts and below the recorded surface-area
allowance; 512 remains a diagnostic resolution. Hidden caps retain explicit materials.
Only triangles whose three corners lie on a measured join plane are classified as
hidden caps. They deliberately share a reserved dark swatch; that palette must not
overlap any visible UV. Visible UVs are checked at Blender's actual float precision.
Bounded local repairs may disconnect pieces of one original chart without moving
the healthy triangles. Those unchanged pieces retain their original continuous
colour domain for filtering checks; every relocated triangle gets an independent
domain. Keep both connected-component and domain gutter diagnostics, and retain
the original/final UV arrays and domain assignments as proof. Independent domains
must retain the full two-pixel runtime gutter.
The optional `finish` stage projects reviewed reference grip artwork onto the fitted
donor material without changing geometry. The subsequent bake transfers that donor
colour to final UVs at 4K; it never samples the appearance field at fitted coordinates.
Projection misses remain separate from empty atlas padding. An explicit
`processing.missCorrection` policy may correct them by sampling the fitted textured
donor's UVs, within a recorded distance and outward-normal bound. Retain per-texel
target/source faces, source positions/UVs, distances, normal alignment and colours.
The known reference-grip material is evaluated in linear colour with its same
front/reverse masks; verify raw image probes against the bound PNGs. Unsupported
material graphs fail. Do not sample the original generated appearance field.

The render-only donor may contain inward surfaces. A small explicit
`unorientedSourcePatch` is permitted only with exact target-corner hashing, reviewed
face IDs, less than 3% of faces and surface area, at most 2.1 mm source distance,
and at most 0.01% of mapped texels. It changes colour only; native geometry keeps
its closed, outward topology requirements. Record its distinct texel mask and
require actual lit/unlit review. Missing unapproved surfaces still fail.

Colour export permits only a recorded `1e-5` floating-point range normalization;
larger excursions and nonfinite values fail. Keep raw values and clipping counts.
Padding preserves normalized mapped colours exactly. Never claim byte-exact raw
colour preservation when range normalization changed a mapped value.
Float bake images and diagnostic EXRs use **Non-Color**. Blender's sRGB-tagged
float EXR save/reload converts linear pixels to encoded values; re-encoding those
values would wash out the diffuse. Keep a known-linear-colour conformance receipt.
The CPU PNG writer performs the sole linear-to-sRGB conversion. Ordinary diffuse
materials consume those PNG/TGA maps as sRGB textures.
Review matched clay, lit diffuse and unlit diffuse views using the actual runtime
texture. Keep all renders at four threads and retain elapsed times.
Render inventory parts with one assembly camera, matching stock multipart icons.
Use the native length axis as camera up for icons, and check each alpha footprint
and the assembled icon; a numerical render success cannot detect a cropped part.
Keep a textured fitted scene and a final visible GLB alongside the native files.

## Native and geometry contracts

The supplied profile remains `pending-contract` until the actual effective content
stack is measured. `native.stack` points to a pinned JSON inventory with `complete:
true`, `order: low-to-high`, and ordered `layers`, each containing `resources` entries
of `{resource, file: {path, sha256}}`. Resource paths are relative to the stack file.
Inventory the actual selected stack, including all appearance and texture collisions;
an extracted donor subset is not a complete stack. Later layers override earlier ones.

A layer may instead combine selected resource bytes with `nameInventory`, avoiding
bulk extraction of unrelated payloads. `nwn-key-namespace-v1` binds copied/live KEY
indexes, current KEY membership, the selected BIF source archives, and a qualified
extraction proof/launch. The reader independently enumerates model, texture and
table names from the KEY tables; unextracted names still block allocations.
Selected resource hashes must match the extraction, and changed source bytes,
new KEY files or incomplete proofs reject the contract. Runtime paths remain in
ignored evidence/bindings; the portable family points to relative evidence files.
`published-human-namespace-v1` binds both approved shipped Human manifests for
the historical PR42 body namespace. For the current accepted PhenoMorpher 1.1.0
publication, bind the complete selected Human resource closure as explicit layer
resources, including shared animation/material dependencies and the unchanged
shipped appearance table. Both Human fixtures use appearance 15100. Actual body
payload hashes are checked when building the HAK; a namespace check does not
validate body geometry or motion.

Record `baseItem`, effective `baseitemsSha256`, lowercase `itemClass`, `modelType`,
all `b/m/t` donor resource names, native rotation `frame`, `gripOrigin`, measured
`gripLength`, and donor `iconDimensions` for `b/m/t`. Set `reviewed` only after inspecting
the donors. The first pilot requires composite ModelType2. Names are allocated without
collisions in the supported model1..25 range, with `model*10+colour <=255`; UTI fields
use that encoded byte. No gameplay table changes or mixed assemblies are generated.

Fit inputs are a reviewed positive uniform matrix bound to the textured donor hash,
plus measured grip endpoints in NWN/Blender basis (glTF conversion is `(x,-z,y)`).
Apply the same transform to donor and low mesh. Configure two natural `joinY` cuts,
opening probes and sampled thickness probes. Cuts get explicit hidden caps; arbitrary
holes are not filled. Nonclosed/inconsistently wound parts fail. Reduction must retain
mating contours, opening probes and measured thin features; failures require a bounded
geometry correction, never blanket wrapping or automatic gate relaxation.

The current **preliminary** target policy is recorded in
`tools/itemkit/budget-policy.json`. Counts mean triangles for the complete visible
assembly, including all parts, hardware and caps:

| Item category | Preliminary visible target | Selection |
|---|---:|---|
| Melee weapons | 5,000–15,000 | Length and overall size |
| Firearms | 10,000–25,000 | Size and type: pistol, SMG, rifle |

These ranges are adjustable starting targets. Choose an exact cap and per-part
allocation in each fresh family profile; the range maximum is not an automatic
target for every model. The Cougar profile starts at 5,000 visible triangles,
preserving the previous part proportions. Its shadow budgets remain unchanged:

| Part | Preliminary visible cap | Shadow triangles |
|---|---:|---:|
| Blade/guard (`t`) | 3,125 | 300 |
| Grip (`m`) | 1,125 | 100 |
| Pommel (`b`) | 750 | 100 |
| Complete assembly | 5,000 | 500 |

These are portable starting allocations. The measured Cougar production family
reallocates the same 5K whole-item cap to pommel 1,200, grip 1,375 and blade/guard
2,425, fitting the actual natural boundaries. Its visible result is 1,174/1,360/2,422.
The selected closed shadow result is 96/96/296. Its explicit `shadowPommel`
projected-loop method retains the measured opening with a variable-thickness,
96-triangle closed silhouette; it does not change visible geometry.

The current pistol trial uses a 10,000 visible / 500 shadow whole-item cap, including
its active hidden placeholders. SMG/rifle slot reservations exist; no subtype size
thresholds or shadow budget increases have been established. Preserve historical profiles and receipts;
derive a fresh profile/manifest for future processing. New targets confer no geometry,
native, client or production approval.

The optional 768/200K source export is an explicit donor trial, not a runtime
budget or evidence that narrow openings survive. Retain the raw source regardless.
`sourceExport` requires `remeshResolution` and `targetFaceCount`; optional `signMode`
selects `udf` or `sdf`, and boolean `manifold` requires explicit `sdf`. Omitted
options preserve the frozen headkit export recipe. Conditional Comfy options must
use its scalar selector and flattened sub-widget keys. A source with non-manifold
edges or invalid vertex links is rejected before further UV/bake work, even when
its renders look acceptable. The Cougar UDF trial failed that physical gate.

Unwrap after fitting/splitting/reduction. Bake the **fitted textured donor** onto the
final atlas at4K, with profile-controlled cage/ray distances. Inspect unpadded masks:
visible misses fail, geometrically identified internal cut caps use an explicit colour,
and only empty atlas padding is extended. Derive2K/1K/512; initial runtime diffuse is1K.
No original appearance-field sampling at transformed coordinates is permitted.

Rendering uses four CPU threads, matched clay/textured views and measured native icon
dimensions. The exporter writes separate visible and closed outward shadow meshes.
Native compilation uses the maintained isolated compiler and fixed-string sanitizer;
decoded corners, normals, UVs and shadow geometry must roundtrip. HAK hashes must
exactly match packaged resources.

## Private client fixture and acceptance

Runtime verification inventories active interpreter/import roots and hashes executable
sources, native libraries, configuration, kernel/compiler inputs and loaded module
origins. Inactive base-interpreter site-packages, documentation, sample images and
distribution RECORD listings are excluded. Fresh membership and byte hashes remain
required; no timestamp cache substitutes for a byte check. Comfy source membership,
complete startup execution proof and retained live code checks remain separate gates.
Compiled expected-code hashes may be reused only for identical source bytes.

Generation requests retain the server runtime attestation. Its bytes are verified
inside Comfy at preparation and again under the shared submission lock; the client
and launcher do not consume a duplicate copy of that inventory. Client assets,
selected checkpoint pins and source inputs retain before/after checks. Use
`itemkit inputs --stage calibrate|geometry|appearance|export` to freeze only checkpoints
selected by that stage. The trial ledger and 45-minute job deadline still apply.

Pin `fixtureTemplate` (an isolated Human test module), `maleCreature` and `femaleCreature`
(Human UTC donors), and `nwscript` in the processing manifest before starting the CPU
chain. Bind each dependency HAK explicitly in `fixtureHaks`. The fixture clones these
inputs into its own user directory, adds the candidate item/HAK, and creates both actors.
Its entry script requests equipment; script execution alone is not a fit/attack pass.

Inspect both Human bodies in front/rear/side views, idle, walk, run, equip/unequip,
actual attacks, shadows, gloves/armor and supported shield/off-hand combinations.
Record specific responding-client observations, screenshot pins and log pins for
every matrix row. Use `run --stage client --evidence EVIDENCE` with the unchanged
processing manifest; include the evidence and nested files via `inputs --extra`.
The evidence must match the exact module, candidate HAK and all fixture HAKs.
`clientValidated` and `productionAccepted` are distinct; no command grants production
acceptance. Publication/promotion requires the user's explicit approval.

Unqualified firearm/Sling profiles remain blocked. The separate pistol adapter
supports the explicit multipart/Color contract above; synthetic native qualification
does not validate a generated pistol or observed ammunition/animation behavior.
Shields, multiview qualification, tinting and other player appearances remain deferred.
