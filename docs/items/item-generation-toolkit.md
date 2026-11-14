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
Each family's parts, native adapter, carrier and grip binding live in one record
in `tools/itemkit/routes.py`; a new family starts there. A design ID other than
the three Cougar IDs receives its own hashed `sr<8 hex>`
resources from intake, never a shipped Cougar identity. Shortsword, dagger,
longsword and greatsword fitting, and any `midpoint-depth-two-hand` fit, refuse an
unbound `inputs.gripStandard`. The fixture refuses a comparison HAK named like the
candidate and any bound HAK sharing a resource with it, because the candidate is
listed last and would lose that resource. A two-hand fit whose midpoint width departs
over 5% needs a `gripDeparture` review tied to its `measurementDigest`.
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
Both mutating commands also require `--bindings BINDINGS`. A skinned crossbow
needs the qualified offline compiler: pass `--compiler COMPILER_JSON` to both
`firearm-inputs --prepared` and `firearm-native`.
Shields use `shield-inputs --spec SPEC --bindings BINDINGS --output INPUTS`, then the
launcher runs `shield-prepare --spec SPEC --output FRESH`; repeat `shield-inputs` with
`--prepared PREPARED --compiler COMPILER_JSON` before `shield-native`. The spec holds
`profile`, `arrays`, `texture`, `icon`, `impacts` and optional `evidence`, `appearance`
and `alpha`. The 64x96 render is padded to the stock 64x128 canvas. Use
`preflight --scope generation` with split generation bindings.
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
cannot recover the submission contract. A lost connection during completion is not a verdict: the job stays `submitted`
and a repeat `collect` resumes from the retained history, even after a Comfy
restart. A restart may change only the session id and pid: the retained history must
name this job, and any other runtime difference stays a terminal failed-validation.
A folder that holds no intent for the token is refused without touching the job.
Preserve a failed-validation receipt and
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

## Long-weapon straightness

Long thin weapons (`shortsword`, `longsword`, `greatsword`, `staff`) need
`approval.referenceView` before a geometry request: an approved `oblique` pair, or
`side` with `sideViewWaiver: true` and review notes. After each collected clay run
`python -m tools.itemkit.straightness check MESH.glb --family F`; bend, twist and
guard-skew flags are advisory and go to the reviewer with the views. A bowed but
otherwise correct clay can be unbent with `straighten MESH.glb OUT_DIR [--family F]`
(the family picks the limits its result is assessed against, as in `check`). It
bridges wide sections such as a cross-guard; add `--whole` to straighten through
them when a hafted head is cocked on its haft (the saved map keeps that choice). Review
the straightened views like a generated attempt. Appearance and the source bake
stay in the generated frame, so re-apply the saved map with `--map` to the
textured donor and working shell before fitting. See the wave-1 section of
`four-weapon-lessons.md` for calibration and limits.

A handle too short for the hand at the chosen size can be lengthened alone with
`stretch MESH.glb OUT_DIR --span LO HI --factor K`: the span (fractions of the
length from the principal frame's low end; the report names `longAxis` and the `lowEndVertex` it counts from) grows by K,
the end below it stays and everything above moves along the axis unchanged.
Re-apply its `stretch-map.npz` with `--map` to the textured donor, review the
views, then fit at the natural size (wave-4 Sai). `narrow MESH.glb OUT_DIR --span
LO HI --band INNER OUTER --factor K` pulls side parts such as sai prongs towards
the centreline: across the width band (distances from the centreline as fractions
of the length) the extent shrinks to K, and everything beyond moves in unchanged.
It refuses a span that would cut through the side parts.

The same check flags a slab guard (`guardSectionRatio`) and an over-thick blade
(`bladeDepthToWidth`). `thin MESH.glb OUT_DIR` halves the blade depth by default
(`--factor` or `--ratio` to choose); it runs after straightening and its map carries
to the donor and shell the same way. `tools/itemkit/autofit.py` measures the fit
inputs from a straight shell: landmarks, a grip span sized to the stock carrier
length, vertex-free part cuts and a 40,000-triangle working shell. These measure
and never approve; hand-fit review on both Human bodies is unchanged.

Straightening also squares flat end caps that are tilted off the long axis (0.5 to
30 degrees), such as a club's pommel and head; the correction is stored in the
map's `ends` and carries to the donor and shell with the rest. A blade point or a
rounded butt is not a flat cap and is left alone.

A one-hand weapon with a round grip can keep its section round: set
`fit.sizingAuthority` to `usable-length-round`. The fit then applies one transverse
scale so the grip's midpoint diameter equals the approved face width, instead of
scaling depth and width separately. The depth departs from the standard by
construction, so the fit always stops until `fit.gripDeparture` carries an approved
review with the digest from the worker's retained `grip-measurement.json`. See the
Club continuation in `four-weapon-lessons.md`.

## Chained stages

Consecutive processing stages can run in one verified launch:

    python tools/itemkit/run_itemkit.py inputs --manifest M --bindings B --run RUN --stages fit reduce ... native --output LIST
    python tools/phenotypes/launch_shared_tool.py ... --input-path-list LIST -- tools/itemkit/run_itemkit.py chain         --manifest M --bindings B --run RUN --stages fit reduce ... native --notes "..."

`chain` runs each stage as `run` would and approves every stage but the last with the given notes, which must say what
the approval rests on (the numerical gates). The last stage is left unreviewed for a person. It refuses a plan with a
missing parent, a repeated stage or the `client` stage before running anything, and a failed stage stops the chain.
Each stage still takes its own fresh verification passes and writes its own attempt and receipt; only the launcher's
input freeze, the input listing and the per-stage review launches are paid once instead of per stage.

Measured on the wave-1 Club (2026-11-11, fit through native, same inputs): about 37 minutes stage by stage, about 13
minutes chained. Triangle counts were identical and the baked texture differed from a stage-by-stage run by at most
one colour level, the same as two stage-by-stage runs differ from each other. Roughly half of the chained time is
still verification inside the stages. End a chain at `render` when the look has not been reviewed yet.

## Unattended client capture

A built fixture can be photographed without anyone driving the client:

    python -m tools.itemkit.client_capture FIXTURE_DIR CAPTURES --nwn-root GAME_INSTALL

`FIXTURE_DIR` holds the fixture stage's `fixture.json`. The fixture's entry script carries a dormant shot sequence
(`fixture.SHOTS`): the driver switches it on with a 2DA in the fixture's own override folder, so the module bytes are
the same for an interactive look and a capture run. It then starts the client through `tools/armorkit/client.py`,
which refuses to start while any client is running and stops only the one it started. The player is hidden; the
camera is attached to each Human actor at stated moments of the existing motion sequence (four sides, hand close-up,
shadow, unequipped and re-equipped, walk, run, two attack frames, shield, off-hand, armour and gloves). Three window
captures are saved after each `ITEMKIT_SHOT` line. A shot that finds the camera in use is taken on the next cycle,
so a run lasts five to nine minutes. A burst that may show another shot's view is kept on disk but marked `rejected`
in `capture.json` and left out of the evidence draft and the contact sheets: a shot already followed by the next
one in the same log read is not captured at all ('next shot began'), and a burst that ended after the shot's hold
is 'burst overran the shot hold'. Its check is then listed as missing.

The greatsword carrier rests on the shoulder, so its fixture uses `fixture.SHOULDER_SHOTS`: the same moments framed
higher and a metre further off, with the close-ups aimed at the chest where the hand is. The framing follows the
route's `carry` (`fixture.carry_for`): the greataxe, halberd and scythe carriers are also shouldered. Other carries
(staff, bow) still use the hip framing until their own is measured.

`capture.json` records the shots and equip lines. `evidence-draft.json` groups the pictures by body and required
check with `result: "unreviewed"` and lists any check without a picture. It is material for the client evidence, not
the evidence: a person still looks, judges and writes the review. The fixture area keeps only the two review actors;
the template's idle lineup is left out. The driver also writes one contact sheet per body (`sheet-<body>.jpg`, the
middle frame of every shot).

## Item workspace and driver

`tools/itemkit/drive.py` runs every wave step as one command; it replaces the per-wave driver scripts that lived
outside the repository (wave-1's `wave.py`, `auto_fit.py`, `condition_oblique.py`, `views.py`). Machine paths live in
an ignored item workspace, found from `--workspace`, then `$SRN_ITEM_WORKSPACE`, then `output/itemkit/workspace.json`.
Start from `tools/itemkit/workspace.example.json`; relative paths resolve against the workspace file. `bindings` is
the processing binding and `generationBindings` the generation one, both inside `runtime`.

    python -m tools.itemkit.drive gen ID geometry --manifest calibrated-v2          # one GPU job through the ledger
    python -m tools.itemkit.drive fit ID SRC DST WORKING.glb DONOR.glb --overrides O.json --donor-review "user's words"
    python -m tools.itemkit.drive batch ID:SUFFIX ID:SUFFIX --stages fit,reduce,unwrap,finish,bake,shadow,render --jobs 2
    python -m tools.itemkit.drive refixture ID SUFFIX NAME --capture
    python -m tools.itemkit.drive contract greataxe ID --wave NAME

Every processing command goes through `run_itemkit.py inputs` and the verified shared-tool launcher, exactly as a
hand-typed run. Nothing in the driver approves a design: approvals it writes quote words passed in `--notes` or
`--donor-review`, and `batch` and `chain` approve intermediate stages only as numerical passes.
`python -m tools.itemkit.drive --help` lists every command.

`drive condition DESIGN ID` keys and measures an angled colour/clay pair and stops: keying fills enclosed holes and
drops secondary components, so whether openings and thin members survived needs a person's look at the keyed
images. Running it again with `--notes "user's words" --keyed DETAIL_SHA,CLAY_SHA` (the hashes the first call
printed) conditions the pair and writes the approvals with those words.

### Measure-only fit and fit preview

    run_itemkit.py measure-fit --manifest M --bindings B --run RUN --output RUN/measure-N

runs the fit worker's grip measurement without spending a fit attempt (`kind: fit-measurement`, `stageAttempt:
false`) and writes `measurement.json`: the departure flag, the worker's own `measurementDigest`, the fit matrix,
native length, fitted bounds and two x-ray previews (`fit-preview-broad-face.png`, `fit-preview-edge.png`) of the
fitted item over the stock carrier's part boxes, the standard grip cylinder at the grip origin and a 10 cm bar. The
digest is the one the fit stage checks, so a departure review can bind it before the first fit attempt. `drive fit`
does this automatically: when the measured fit departs and no digest is given, it writes `<DST>-measure` and runs the
preview. It writes `<DST>` with the digest bound only when `--authority` carries the user's words approving the
departure; without them it stops after the preview with `departureNeedsAuthority`, and the re-run with `--authority`
reuses that candidate and its newest measurement (it refuses if the working shell, donor or overrides differ). `drive preview ID SUFFIX`
runs only the measure. Measured on the Club: about 2 minutes, the same digest as the wave-1 fit.

### Rebuilding a fixture

    run_itemkit.py refixture --manifest M --bindings B --run RUN --fixture-inputs DOC --output RUN/refixture-N

builds only a fresh fixture from the run's existing native result after fixture code changes, instead of rerunning
the chain. It verifies the native chain at the code version it was recorded with (the receipts' `codeVersion`; their
own source-file pins are not rechecked against today's files) and takes the fixture's own inputs from a `kind: fixture-inputs` document beside
the manifests (`drive fixture-inputs` writes one, with its pinned files in its own `fixture-inputs/<ID>.<NAME>/` folder
so a later document never rewrites them; it also carries the fixture HAK pins, so the processing bindings every
native receipt pins are never edited). The receipt is `kind: fixture-rebuild`, never a pipeline stage and
never client-stage eligible: a release still needs the full chain at the current code. About 2 minutes against
15 for a chain.

### Parallel processing

`drive batch` runs one chain per item, at most three at once (the per-part run concurrency rule), each Blender
rendering on four threads. Items are independent: a failed item is recorded with its error and the rest continue.
Two Club fits ran side by side in about 2 minutes on 2026-11-11.

### Texture outliers

The bake stage adds an advisory `textureOutliers` block (`texture_check.check_bake`): per UV island, a
31-pixel median background, a smoothed residual and connected blobs above a contrast floor are flagged with a
heatmap. It found the Club's grip squiggle (3 blobs) and nothing on plain grain. It never fails the stage (an error in
the check is recorded in the block instead); a person
looks at the heatmap. `python -m tools.itemkit.texture_check BAKE_ATTEMPT` runs it on an existing bake.

### Clubs, axes and polearms

The composite melee routes add `club` (28), `handaxe` (38), `battleaxe` (2), `spear` (58), and the two-handed,
shouldered `greataxe` (18), `halberd` (10) and `scythe` (55), all on their installed carriers with the Cougar grip
standard. They are `shape: hafted`: the fit finds the head as the widest end (turned to +Y), scales uniformly to the
stock carrier's length or a chosen `targetLength`, and places the hand at the carrier's measured grip origin. One-hand
hafted fits use `usable-length-round` and always stop for a digest-bound departure review; two-hand fits use the
uniform two-hand rule.

The fit frame's long axis is measured, but which way its width axis points is arbitrary. A head that has a blade on
one side and a spike on the other (the tomahawk) can come out facing backwards in the hand. Look at it in the
client, then refit with `"turnAboutAxis": true` in the overrides. This turns the fit half a turn about the long
axis (native Y), so the edge and back swap sides. The landmarks, scale and grip measurements stay the same, but
earlier bake patches name faces by their corners and must be measured again.

A staff is one long shaft, not a hilt. The per-axis hilt calibration sizes a hilt's depth and face width separately
to the Cougar section (30 x 50 mm). On the 1.90 m stun staff, whose shaft is 1.2:1, it scaled one cross axis by 0.40
and the other by 0.56, so the staff looked flattened from the side (user, 2026-11-12). The `staff` route therefore has
`section='uniform'` (`midpoint-depth-uniform`, `grip.transverse_uniform`): a single cross-section scale brings the
grip's midpoint depth to the standard, and the shaft keeps its own proportions. The face width then departs from the
standard by construction, so it needs a review bound to the measurement digest, like the round one-hand rule. For a
thicker shaft, `"sectionBasis": "visibleFaceWidth"` in the overrides makes the face width meet the standard instead,
still with one scale (the user chose a 41 x 49 mm stun staff grip over 30 x 35 mm). Fitting
refuses the per-axis calibration on any route that isn't grip-bound if it would flatten the section by more than 10%.

`drive contract FAMILY ID --wave NAME` (`family_contract.py`) builds a native contract for a design on any of these
carriers from the measured wave-1 contract: it extracts the stock `_011` parts and icons into a new stack layer
(in a per-carrier `stack-<class>.json`, so the wave's `stack.json` and earlier contracts keep their pinned bytes),
measures the stock grip origin and span (`carrier.py`, from the binary models' triangle sections), sets the icon size
from `baseitems.2da`, allocates the visible budget from `budget-policy.json` by stock length (7,500 at 0.5 m to 22,500
at 1.6 m and over) and reserves resources, skipping slots the wave's other contracts on the same carrier pinned. The grip origin is measured, not reviewed in a hand: the first design on a
new carrier carries the both-body hand-fit review that confirms it.

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
| Melee weapons | 7,500–22,500 | Length and overall size |
| Firearms | 15,000–37,500 | Size and type: pistol, SMG, rifle |

The user raised every visible budget by 50% on 2026-11-11 (the ranges were 5,000–15,000
and 10,000–25,000). Shadow budgets did not change. Items already processed keep their
counts; one takes the larger budget only when it is reprocessed under a fresh profile.

These ranges are adjustable starting targets. Choose an exact cap and per-part
allocation in each fresh family profile; the range maximum is not an automatic
target for every model. The portable Cougar starting profile is 7,500 visible
triangles in the previous part proportions. Its shadow budgets remain unchanged:

| Part | Preliminary visible cap | Shadow triangles |
|---|---:|---:|
| Blade/guard (`t`) | 4,688 | 300 |
| Grip (`m`) | 1,687 | 100 |
| Pommel (`b`) | 1,125 | 100 |
| Complete assembly | 7,500 | 500 |

These are portable starting allocations. The shipped, measured Cougar production family
reallocates the same 5K whole-item cap to pommel 1,200, grip 1,375 and blade/guard
2,425, fitting the actual natural boundaries. Its visible result is 1,174/1,360/2,422.
The selected closed shadow result is 96/96/296. Its explicit `shadowPommel`
projected-loop method retains the measured opening with a variable-thickness,
96-triangle closed silhouette; it does not change visible geometry.

The firearm and shield routes cap the whole item at 15,000 visible / 500 shadow
(`contracts.FIXED_ROUTE_BUDGET`; 10,000 before 2026-11-11), including active hidden
placeholders. Shipped profiles under the cap stay valid. SMG/rifle slot reservations exist; no subtype size
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
