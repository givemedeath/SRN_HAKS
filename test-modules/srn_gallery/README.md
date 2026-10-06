# SRN custom content gallery

`output/srn_gallery.mod` is the inspection module. Its editable source is
[gallery.json](gallery.json), [the builder](../../tools/gallery/build_gallery.py),
and [the control scripts](../../tools/gallery/scripts). Rebuild after changing
content; generated modules, HAKs, bindings, catalogs and receipts stay in ignored
`output/`.

The completed native build is recorded in [validation.json](validation.json):
75 areas, 29,019 inventoried resources and six male head candidates prestaged.
All 26 repository HAK payloads, the inspection overlay and saved module copies
passed byte verification. Interactive client inspection remains pending.

The starting area has labeled category and page controls. The first page appears
on entry. Search and stage individual appearances with chat commands:

```text
.gallery find chair
.gallery stage placeables:<model-resref>
.gallery category doors
.gallery page 2
.gallery home
```

Staged objects remain in the starting area while browsing other pages. Add their
catalog IDs to `prestaged` in `gallery.json` to place them on every fresh session.
There are 24 display slots and 24 staging slots. The module is intended for one
inspection session; browsing changes the shared display for everyone present.

The catalog refreshes from every registered pack in `hakbuilder.json` and the
production tables. It lists every model in the configured placeable and door packs, existing item
and creature blueprints, music, sounds, skyboxes and tilesets. Each custom tile
ID is placed in a display area, with each page selectable in the browser;
`catalog.json` maps tiles to areas. Use
`.gallery area <area-resref>` or the Toolset area chooser to inspect subsequent
tile pages. These are sample layouts for inspecting individual tiles, not proofs
of terrain transitions or walkmesh compatibility.

Textures, palettes, materials and body parts are included in the complete hashed
resource inventory and loaded through their consuming models. Assets without a
production placeable/door row receive an explicitly labeled test appearance in
the inspection overlay. Production tables stay unchanged. Other assets without a
blueprint need an `additions` entry describing their
consumer. For example, a creature blueprint already supplied by a registered HAK:

```json
{"id":"creatures:review_guard","category":"creatures","kind":"creature",
 "name":"Review guard","resref":"review_guard"}
```

Remove stale prestaged IDs when content is removed; rebuilds reject them. Optional
verified head fixtures are merged into an isolated test HAK, and their head actors
are prestaged. They remain labeled test candidates with client validation pending.

## Rebuild

For later updates, rebuild everything from an existing local binding template:

```powershell
./tools/Refresh-Gallery.ps1 -Toolchain $localToolchain `
  -MigrationReceipt $freshMigrationReceipt -BindingTemplate $previousLocalBinding `
  -OutputDirectory output/gallery/refresh-003
```

This rebuilds all registered HAKs and the TLK, creates fresh pins, and saves
`output/srn_gallery.mod` plus `output/srn_gallery_test.hak`. Use a fresh output
directory every time; previous receipts remain available. Changes to the
portable `prestaged` and `additions` lists take effect on the next rebuild.

Opening the finished module in NWN does not run this build pipeline or hash the
repository. A refresh verifies the bytes of its consumed inputs before and after
execution. The builder reuses the launcher's verified snapshot for catalog and
dependency bookkeeping, while independently checking actual HAK payloads. It
does not reread all source files just to record the same hashes again. Direct
builder calls retain their own before/after checks. Refresh migration evidence
when launch helpers change; an older migration receipt is intentionally rejected.

Build the repository HAKs/TLK first with `tools/Build-Haks.ps1`. Prepare the stock
inputs `ttr01.set`, `ttr01_edge.2da`, and typed `nw_humanmerc001.utc.json` using
the installed game and pinned resource/GFF tools, as for the head fixture. Create
a fresh ignored binding:

```powershell
./tools/Bind-Gallery.ps1 -Stock $stockInputs -GameRoot $installedGame `
  -Fixture $verifiedHeadFixtureReceipts -Output output/gallery/local/binding-002.json
./tools/Build-Gallery.ps1 -Toolchain $localToolchain `
  -MigrationReceipt $freshMigrationReceipt `
  -Binding output/gallery/local/binding-002.json `
  -OutputDirectory output/gallery/run-002
```

Use the bundled workspace Python recorded in the local toolchain and fresh
migration evidence described in [shared tooling](../../docs/shared-tooling-and-workflow.md).
The launcher freezes every consumed source/resource before dispatch and verifies
the bytes afterward. The builder compiles all control scripts, independently
decodes the module startup GFF and verifies the complete packed resource payload.
It writes a refreshed `catalog.json` and `build.json` with pins and counts.

The generated `build/user` directory contains the module, test overlay, declared
repository HAKs and custom TLK for later client inspection. Copy those files to
the matching NWN user directories when ready. No interactive client validation is
claimed by the build checks.
