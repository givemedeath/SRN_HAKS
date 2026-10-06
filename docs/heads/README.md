# Head production pipeline

The current delivery is recorded in [delivery.md](delivery.md), with the
[seven-design catalog](pilot-catalog.json), [selected 200-entry roster](roster-selected.json),
[Human target](human-male-target.json), [Troll target](troll-male-target.json),
[protected Troll body resources](troll-body-resources.json), [slot audit](slot-catalog.json), and
[validation results](validation-summary.json). Review images are offline evidence.
Additional portable contracts cover [Elf](elf-male-target.json),
[Dwarf](dwarf-male-target.json) and [Orc](orc-male-target.json) males. Their
protected resource hashes are included in the pilot catalog.
Client testing and production acceptance remain pending under the user's revised scope.

The portable roster reserves 200 designs: 20 male and 20 female for Human, Elf,
Dwarf, Orc and Troll, phenotype 0. Troll uses NWN's `g` model family. The pilot
contains two Human males (natural and cyberware), one male each for Elf, Dwarf,
Orc and Troll, and an Elf female donor.
The merged `codex/derived-phenotypes` branch supplies male body contracts for all
five races. All six male candidates have passed native checks.
The Elf female donor stays pending until an approved female body contract exists.
The [gallery module](../../test-modules/srn_gallery/README.md) prestages all six
male candidates alongside its refreshable repository content catalog.

The pilot uses the Meshy plugin CLI at the user's request, superseding the
original MCP route. CLI 0.4.0's live command schemas were inspected before paid
dispatch. Authentication remains in Meshy's credential store. No credentials,
machine paths, generated source banks, tool binaries or built HAKs belong in Git.

## Preparation and resume

Use the bundled desktop Python and `tools/phenotypes/launch_shared_tool.py`.
Follow [shared tooling](../shared-tooling-and-workflow.md). Bind Python, Blender
and NWN to an ignored local toolchain. Run fresh Python and Blender import
smokes, then `tools/heads/finalize_head_migration.py`. Its evidence covers only
Python and Blender: it does not establish an Armory migration. Blender previews
use four threads and record elapsed times. Native compilation resolves the
explicit NWN binding separately and records its binary and consumed inputs.

Declare helpers and **all** consumed source, reference, palette, body, rig,
animation and material files with `--input` or `--input-manifest`. A manifest is
a JSON array of explicit `{ "path": "...", "sha256": "..." }` file pins. The
launcher freezes them before execution, snapshots helpers and verifies them
again afterward. Refresh migration evidence if launcher dependencies change.

Initialize an ignored session with `head_workflow.py init --roster
tools/heads/roster.json --output <session> --budget 300`. Keep a local binding
that explicitly identifies that session, the allocation, current contract,
selected source revisions and migration receipt. Resume those exact bindings;
never select the newest-looking file. Session events have consecutive names
and a SHA-256 parent chain. Historical requests, receipts and failed candidates
remain immutable. A held operation lock requires explicit reconciliation.

## References and geometry

1. Generate a coherent front/left/back/right isolated-head reference sheet with
   neutral expression and the design's racial features, hairstyle and accessories.
   The latest pilot direction requires the complete skull and intact mandible
   **without any projecting neck portion**. Preserve the rounded chin and lower
   jaw in both profiles; inspect whole silhouettes rather than cropping at the
   sheet midline. If alpha components cross quadrant boundaries, use the existing
   normalizer's `--layout-components` route to retain complete views.
   Retain the prompt, original raster, generation ancestry and review. Use the
   existing turnaround normalizer for shared-scale 1024-square panels. Review
   them before recording the `reference` gate.
2. Freeze a Meshy request with explicit `meshy-7`, `standard` multiview geometry,
   triangle topology, a 50,000-triangle master target, GLB output,
   `save_pre_remeshed_model: true`, `should_texture: false`, and no automatic
   sizing. Use `meshy_cli.py dispatch` through the launcher. The adapter reserves
   estimated credits before invoking the CLI and records the owning task ID.
3. Run one paid job at a time. Each pilot design permits at most two generation
   attempts. The original session cap was 300 credits; the user approved a
   descendant ceiling of 405 for the three additional male designs. Actual
   cumulative spend is 345, with no outstanding reservations. Timeouts and unknown charges retain
   their reservation. An uncertain create must be reconciled with the CLI's
   operation journal and task history before another create. An operation ID is
   a local journal key, not server-side idempotency.
4. `wait` uses the recorded resource and task ID. `collect` immediately downloads
   all outputs, including the pre-remesh source, and hashes every file. Meshy's
   [API retention](https://docs.meshy.ai/en/api/asset-retention) is short; the local
   source bank is required for reproducibility and recovery.
5. Inspect anatomy, axes, components, winding, UVs and topology with
   `inspect_head.py` and a four-thread `render_donor.py` turntable. Watertightness
   is a diagnostic; visible anatomy and usable surfaces require separate review.
   Preserve the original source. Prefer a Meshy remesh request with an explicit
   triangle budget. The API target is approximate; measure the returned geometry.
   The current runtime limit is 20,000 triangles,
   including accessories and caps, superseding the original 8,000 and later 10,000 limits.
   The neckless pilot's Meshy triangle and quad reductions had unsafe boundaries.
   `prepare_meshy_input.py` preserves a clean, bounded upload copy of the retained
   pre-remesh source. `prepare_runtime_lod.py` versions a local surface LOD,
   establishes selected UVs and bakes high-source normals before fitting review.
   This route produces the selected 19,000-triangle heads after hole caps.
   All service reductions and rejected local candidates remain historical.
   Reject visible damage, unsafe boundaries or unresolved budget failure.

## Body fitting and materials

`prepare_human_target.py` measures the published Human male body, preserved
`head_g` bind frame, stock neck, cranial envelope, palette files and animation
chain. Its output is an **unapproved proposal**. An approved contract must pin
the publication manifest and every protected resource, rig, neck and animation
dependency; `bodyRevision` must equal the manifest hash. Anatomical fit tolerances
and any envelope allowance require measured and visual justification.
`bind_target.py` resolves the portable approved contract through an ignored
`srn-head-target-bindings` JSON object containing `repository`, a `resources`
mapping from each logical `stock/...` key to its local file, and explicit `inputs`
pins. It verifies every binding and all published body resources before writing
a fresh local contract. Installed stock resources stay outside Git.

For a derived body, use `import_derived_body.py` to copy the complete fourteen-part
native compiler inventory and explicitly pinned rig/animation/palette dependencies
into an independent ignored bank. Never borrow another checkout's tools.
`prepare_derived_target.py` verifies the imported `head_g` against the derived
contract and emits an unapproved working-space proposal. Approve its racial
cranial envelope and corresponding anatomical landmarks separately. The Troll
uses a central scalp crown that excludes horn tips (`--central-crown`) and a
separate fixture visual scale of 10/7. Its source bodies and proportions are preserved.

The portable Troll target binds the exact retained operational `body.json` using
the logical `derived-bank/troll-male/body.json` key. Set the ignored binding's
`repository` to that independent body bank; map the logical rig, stock neck,
palettes and animation keys to their pinned copies. The portable resource list
records all 44 protected bytes without machine paths. Rebuilding a different body
bank requires a fresh target revision and fitting evidence, even if it looks similar.

`prepare_fixture_rig.py` orders geometry nodes parent-first while retaining every
original node block and transform. Native compile that copy and use
`audit_fixture_rig.py` to compare all decoded bind frames and parents. The fixture
requires this audit, the corresponding compiled root and every shared material
dependency; both head and body HAK payloads are verified. The body branch's rig
emitters now use the same parent-first serialization for future builds.

Annotate corresponding named anatomical landmarks in NWN head-local coordinates.
`fit_head.py` permits only positive uniform scale, a proper rotation and
translation. It rejects reflection, stretch, stale dependencies and excessive
residuals. Keep the donor's source orientation in its own source revision.
For the new neckless donors, use `cap_head_holes.py` only if actual boundary holes
exist. It appends caps in unused UV patches, retaining all original P/N/UV and
never trimming or tapering the jaw/skull. A closed donor is copied unchanged.
Reject an unsafe boundary or damaged anatomy; a cap is not permission to reshape
the head. The older trimmed/tapered Human experiments are historical and are held
after the operator identified chin involvement; they are not the selected route.

`correct_neck_rim.py` and taper audits remain readable historical helpers.
They are **not applied to the selected neckless donors**. Current exports declare
`geometryPolicy: neckless-cap-only`, which requires an exact closure/source match,
preserved original attributes and explicit false trim/taper flags.

`prepare_assembly.py` reads the actual published native body meshes and samples
the preserved animation chain. `render_assembly.py` shows standing assembly,
the measured maximum neck displacement and broader idle, talk, walk, run,
casting, combat, crouch, kneel and death samples. Offline sampling is not client
evidence. Both standing anatomy and measured motion must pass before expensive
maps. Do not raise numerical tolerances to conceal a visible connection defect.

Retexture only the selected local runtime geometry with original UVs enabled,
2K resolution and PBR maps. The CLI's local-file flags perform input transport;
the frozen recipe records the exact local sources. Download and hash the returned
geometry and maps. `verify_retexture.py` rejects changed positions, winding,
normals or UVs, allowing only triangle order and cyclic corner order changes.
If Meshy recenters and rebuilds the returned mesh, retain the selected source
geometry. `verify_texture_transfer.py` separately checks the atlas correspondence
under a proper positive uniform transform and exact matched UVs. The pilot uses
only the returned diffuse/roughness atlas, retaining the selected local high-source
normal bake with neutral normals on new caps. The audit supports an explicit
bounded microscopic omission allowance while retaining those source faces.
Changed UVs or actual
shape drift fail this route. Returned geometry and rebuilt normals are not selected.

Author and review a semantic mask: 0 skin, 1 hair, 2 fixed eyes/cyberware. Fixed
features require separate triangle groups. Source palette calibration samples
selected UV islands only; unused service atlas fill must not bias skin/hair rows.
Small hole caps inherit adjacent material ownership and use neutral normals.
`prepare_materials.py` exports
1024-square color, normal, roughness, palette shades and layers from reviewed
2K maps. It uses explicit skin/hair palette rows and explicit normal-green
transport. `head_export.py` is the dedicated rigid-head exporter; the body
adapter continues to reject heads and enforce skin-only body materials.
Palette groups use PLT layers 0/1; eyes and cyberware use fixed diffuse materials.
NormalTangents, normal strength 1 and Roughness0 preserve declared map transport.

## Slots, validation and publication

Audit the installed game and **all repository packs**, the consumer scope
selected by the user. `audit_slots.py` pins their inventories and reads installed
BIC `Appearance_Head` BYTE storage evidence. Slot 0 stays reserved; 1–255 is a
storage range, with actual selectability still requiring client validation.
Allocate the lowest collision-free contiguous block of 20 for each race/sex.
`docs/heads/roster-allocated.json` persists the allocation. Re-audits preserve
complete allocations and reject collisions or partial blocks; they do not
silently renumber designs. Naming is `p{sex}{family}0_headNNN`.

Compile Human exports with the installed NWN compiler in a separate staging
user directory. Decode actual native attributes, compare geometry/UVs/normals,
verify material and palette payloads, and recheck every protected body hash.
Build an isolated client fixture with its exact native resources, slot choices,
skin/hair selectors, light profiles, representative helmets and motion schedule.
Keep its candidate HAK and native resource bank ignored until acceptance.

The gates are independent: `reference`, `donor`, `fitting`, `assembly`, `native`,
`client`, `acceptance`. Each report pins its inputs, evidence and predecessor.
Native success does not imply client success. Client review must observe the
exact package across the palette, light, helmet and motion matrix. Acceptance
also requires redistribution evidence and unchanged body dependencies.

Use `publish_head_pack.py` after both client and acceptance reports pass; it calls
the guarded session publisher and registers `srn_head` in `hakbuilder.json` with
already compiled native resources. The low-level `head_workflow.py publish`
copies accepted resources only and does not register the HAK. Register the pack
when it has accepted content;
required production tables remain in `srn_2da`. Rebuild the HAK and verify its
entire payload against publication pins with `verify_head_hak.py`. Keep built
HAKs outside Git. Before PR readiness run head tests, full shared-tool and
phenotype helper tests, `Test-Repository.ps1` and `Test-ItemImportTools.ps1`.

The current user-authorized stopping point is **before client testing**.
Client and production acceptance must remain pending in pilot evidence and the
PR. Only the Elf female donor remains pending a body contract; all male heads
have fitting, assembly and native evidence.

Before retiring a disposable checkout, preserve verified source masters in a
durable bank outside it and run the read-only retirement audit. Provenance is
historical evidence; it is not a backup and does not authorize deletion.
