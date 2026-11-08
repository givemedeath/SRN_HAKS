# SRN HAK Content Blueprint

## System Overview

SRN_HAKS is the public, curated source repository for Neverwinter Nights: Enhanced Edition HAK content shared by SR_NWN and SRN_NWN. SRN_CC may produce curated content for this repository, but is not a runtime consumer.

The layout deliberately follows SWLOR_Haks: every registered top-level `srn_*` directory is packed into a same-named `.hak`. Generated HAK and TLK files are written to `output/` and are not committed.

The repository incorporates automated pipelines and verification fixtures for character phenotypes, head models, robes, weapons, and 2DA/TLK data management.

### Purpose-built Phenotype Process

The [process package](docs/phenotype-process-package.md) documents individual-part generation, stock-rig fitting, material preservation and assembled client testing, with the accepted Human male as its reference case. Its 72 runtime resources are versioned in `srn_body`; build `output/srn_body.hak` with the normal HAK builder. Generation masters and local ComfyUI/game installations are separate dependencies.

The SRN inspection gallery was removed on 2026-10-14 pending a redesign. Its historical checkpoints remain under `docs/heads` and `docs/gallery`, and the validation records they cite remain in `test-modules/srn_gallery`; the code is in Git history.

### Pixal3D Head Toolkit

The [head runbook](docs/heads/head-generation-toolkit.md) provides a reusable single-image process and the retained multiview alternative for complex heads, with manifest-driven cleanup, textures, PLT review and native packaging.

### Quick Start

Requirements:
- Git
- PowerShell 7 (`pwsh`)
- Internet access on the first run to download the pinned neverwinter.nim tool archive

```powershell
pwsh ./tools/Bootstrap-Tools.ps1
pwsh ./tools/Test-Repository.ps1
pwsh ./tools/Build-Haks.ps1
```

Windows users may instead run `Verify.cmd`, `BuildTlk.cmd`, and `BuildHaks.cmd`.

### Adding a HAK

1. Choose a lowercase name beginning with `srn_` and no more than 16 characters total.
2. Create a top-level directory with that exact name and place only packable NWN resources directly inside it. Subdirectories are not supported.
3. Add the matching entry to `hakbuilder.json`.
4. Run `pwsh ./tools/Test-Repository.ps1 -AllPacks`.

Useful categories include `srn_2da`, `srn_ui`, `srn_shader`, `srn_palette`, `srn_sound`, `srn_music`, `srn_load`, `srn_portrait`, `srn_fx`, `srn_creature`, `srn_item`, `srn_weapon`, `srn_placeable`, `srn_door`, body-part packs such as `srn_pt_chest`, and tilesets named `srn_t_<short-name>`.

All `.2da` resources belong in the single `srn_2da` HAK. Existing EE rows are preserved; imported global rows may be relocated only through a reviewed, reproducible profile allocation recorded in `docs/imports/*-global-row-allocations.json`. The project intentionally does not impose an aggregate HAK size cap. Individual resources should remain at or below 15 MiB; reviewed exceptions must be recorded in `PROVENANCE.md` and must remain below GitHub's file-size limit.

### Shared TLK

`srn_tlk/srn.tlk.json` is the canonical talk table. Allocate entries with:

```powershell
pwsh ./tools/Allocate-StrRef.ps1 -Owner SR_NWN -Key combat.example -Text "Example text"
```

IDs are global, monotonically increasing, and never reused. A TLK entry ID `n` is referenced in game as `0x01000000 + n`.

Legacy talk tables use the quarantine-first importer. It takes an input TLK and an output path relative to `.quarantine/`, verifies a pinned profile and source hash, and deduplicates exact normalized entry payloads against the canonical TLK:

```powershell
pwsh ./tools/Import-Tlk.ps1 -Mode Analyze `
  -InputTlk D:\path\legacy.tlk `
  -OutputRelativePath legacy-tlk-review `
  -ProfilePath ./tools/import-profiles/legacy-tlk.json

pwsh ./tools/Import-Tlk.ps1 -Mode Apply `
  -InputTlk D:\path\legacy.tlk `
  -OutputRelativePath legacy-tlk-review `
  -ProfilePath ./tools/import-profiles/legacy-tlk.json
```

`Apply` is idempotent. An existing key must retain the same payload; an exact payload already owned by another active key is reused, the requested key is retained as a validated alias, and the result is recorded as deduplicated in the migration report. Primary keys and aliases both resolve in 2DA string-reference remaps without allocating a second TLK ID.

### Consumption and NWSync

SR_NWN and SRN_NWN consume this repository as a pinned Git submodule. Each consumer builds the HAKs and TLK, selects the required HAK order in its module, runs its own engine tests, and publishes its own NWSync repository from the final module/HAK/TLK stack. This repository publishes neither GitHub release artifacts nor a central NWSync repository.

### Validation Boundary

Repository verification proves resource naming, size policy, configuration consistency, TLK allocation, HAK construction, and archive inventory. Rendering, model behavior, texture appearance, walkmeshes, module loading, and live client/server behavior must be proven by the consuming project.

The portable MDRNEE smoke fixture is an aid for that consumer validation. Build its 18-area module and the 25 declared HAKs with:

```powershell
pwsh ./tools/Build-MdrneeTilesetTestModule.ps1
```

See `test-modules/mdrnee_tilesets/README.md` for installation and test scope.

### Licensing

Original repository material is available under the PolyForm Noncommercial License 1.0.0. Imported content retains its own license and attribution; see `NOTICE.md` and `PROVENANCE.md`.

### Analyzing Legacy HAKs

`tools/Import-Hak.ps1` provides a reusable quarantine-first import pipeline. All modes require an input HAK and an output path relative to the repository's predefined `.quarantine/` directory:

```powershell
pwsh ./tools/Import-Hak.ps1 -Mode Analyze `
  -InputHak D:\path\content.hak `
  -OutputRelativePath content-review
```

`Analyze` verifies and extracts the archive, then writes `raw/` and `analysis/` beneath the selected quarantine path. An optional `-ProfilePath` supplies archive-specific ownership and promotion rules; `-ExpectedSha256` pins the expected input. Supply `-NwnRoot` and `-NwnUserDirectory` when the report must compare resources against a base-game installation.

For item-system archives, `tools/Analyze-ItemHak.ps1` wraps the same parameterized extraction and adds palette-category, global-2DA, model-dependency, sound-linkage, and existing-pack collision reports. `tools/Analyze-ItemBlueprintErf.ps1` accepts a companion ERF and quarantine-relative output path, extracts it unchanged, and joins its UTI records to the item HAK's palette and base-item rows. An optional `-MatchTierPath` adds a validated Exact identity and Visual stand-in subset from a normalized catalog crosswalk. The current MDRNEE findings and all blueprints grouped by friendly category are documented in `docs/imports/mdrnee_item-analysis.md` and `docs/imports/mdrnee_item-blueprint-report.md`.

For a profiled archive whose SET count fields can be repaired without guessing, generate isolated repair candidates with:

```powershell
pwsh ./tools/Import-Hak.ps1 -Mode Repair `
  -InputHak D:\path\content.hak `
  -OutputRelativePath content-review `
  -ProfilePath ./tools/import-profiles/content.json
```

`Repair` requires the matching analysis manifest, leaves `raw/` untouched, rejects non-contiguous sections, writes candidates beneath `repaired/`, and records every changed line and hash in `analysis/repair-log.json`. Candidates are not copied into repository packs or registered.

After reviewing the generated manifest, apply a profiled import with:

```powershell
pwsh ./tools/Import-Hak.ps1 -Mode Apply `
  -InputHak D:\path\content.hak `
  -OutputRelativePath content-review `
  -ProfilePath ./tools/import-profiles/content.json `
  -NwnRoot D:\Games\NeverwinterNights `
  -NwnUserDirectory D:\NWNUser
```

`Apply` refuses a missing or mismatched manifest, an ambiguous landing, path traversal, or an attempt to overwrite a different resource. See `tools/import-profiles/README.md` for profile requirements.

### Model Compilation and Decompilation

The pinned legacy model tools are documented under `tools/vendor/nwnmdlcomp/`. For scripted work, use `tools/Invoke-NwnMdlComp.ps1`; it verifies the compiler hash and requires distinct explicit input and output paths.

### Texture Conversion

NWN Crunch 0.9 is vendored under `tools/vendor/nwn_crunch/` for BioWare/NWN DDS conversions. Use `tools/Invoke-NwnCrunch.ps1`; it verifies the executable hash and writes to an explicit, separate output path. `tools/Resolve-MdrneeTextureResolution.ps1` applies the documented higher-resolution selection rule to cross-HAK MDRNEE texture variants after import. `tools/Resolve-MdrneeEquivalentTextures.ps1` then applies the reviewed equal-resolution exception registry.

### Current Game-Ready Phenotypes

The [PhenoMorpher body release](docs/phenomorpher/README.md) publishes all twenty reviewed Fit/Large bodies in `srn_body`, with routing in `srn_2da`. Use its target contract for downstream body, head and clothing tasks.

Build `srn_body_tex` alongside `srn_body` and `srn_2da`, and use custom TLK `srn` for the release race names.

### Generated Head Production Selection

`srn_head` contains client-approved native NWN:EE character heads across Dwarf, Elf, Human, Orc, and Troll races (both male and female models, each capped at 20,000 triangles with 1024-square PLT recoloring). The models are fitted to stock stature and neck cuts (`mesh.neck.cut`).

For production workflows, pipelines, and manifests, see:
- [Head Generation Toolkit](docs/heads/head-generation-toolkit.md) (single-image runbook and multiview alternative)
- [Race Heads Runbook](docs/heads/race-heads-v1-runbook.md)
- [Troll Head Reindex Manifest](docs/heads/troll-head-reindex-v1.md)
- [Dwarf Male Pair Documentation](docs/heads/dwarf-male-pair-v1.md)

## Subdirectories & System Boundaries

- [Tools & Infrastructure](./tools/README.md): Shared development tools, CI test impact analysis, build scripts, toolchain verification, and pipeline launchers.
  - [Headbatch](./tools/headbatch/README.md): Multi-head batch orchestration, GPU inference pipeline, stage progression, submission budgeting, and client trial module builder.
  - [Headkit](./tools/headkit/README.md): Character head creation, fitting, UV unwrapping, texturing, quality gate verification, and NWN native model compilation toolkit.
  - [Heads Pipeline](./tools/heads/README.md): Head production pipeline, landmark fitting, neck closure/taper auditing, and PBR/PLT material generation across a 200-head roster and 7 acceptance gates.
  - [Itemkit](./tools/itemkit/README.md): Single-image 3D generation, fitting, UV atlasing, texture baking, shadow proxy generation, inspection fixtures, and native equipment packaging for Neverwinter Nights: Enhanced Edition.
  - [PhenoMorpher](./tools/phenomorpher/README.md): Numerical morphology fitting, continuous mesh morphing, animation library extraction, and static armor retargeting.
  - [Phenotypes Toolchain](./tools/phenotypes/README.md): Architectural toolchain for purpose-built and derived NWN character phenotypes, ComfyUI generation, RBF deformation, and multi-gate client testing.
  - [Robes Pipeline](./tools/robes/README.md): Automated pipeline for generating, inspecting, fitting, skinning, and packaging custom NWN robes and garments for Human male phenotype 0 (pmh0) via Meshy AI, Blender, and NWN toolchain fixtures.
  - [Import Profiles](./tools/import-profiles/README.md): JSON import specifications for MDRNEE audio, item, placeable, tile, and talk table assets.
- `srn_2da`: Core 2DA game data tables defining phenotypes, appearances, equipment slots, base items, and talk table linkages.
- `srn_body`: Native compiled trimeshes (`.mdl`) and models for 20 published Fit and Large character phenotypes across all playable races.
- `srn_body_tex`: High-resolution PLT, TGA, and DDS texture maps supporting the character body catalog.
- `srn_head`: Native compiled character head models and PLT textures for playable races.
- `srn_weapon`: Native weapon models, ammunition packages, firearm FX, and sound-linked visual props.
- `srn_armor`: Fitted armor variants, robe donor models, and accessory attachments.
- `srn_placeable`, `srn_door`, `srn_sound`, `srn_music`, `srn_skybox`: Game environment audio, architectural props, and ambient resources.
- `srn_t_*`: Tileset packs (e.g. `srn_t_common`, `srn_t_dgt04`, `srn_t_fcx01`, `srn_t_fifi`, `srn_t_nac01`, `srn_t_shp02`, etc.) implementing dungeon, urban, and wilderness environments.
- `srn_tlk`: Canonical talk table (`srn.tlk.json`) managing global, monotonically increasing string references (`0x01000000 + n`).
- `test-modules`: Standalone test modules (`.mod`) and demo areas for in-engine validation and inspection.

## Global Invariants

- `[AGENTS.md:Connector Taper Rule]`: No shelves when tapering connector joints: a connector taper must form a continuous sloped transition between measured starting and ending contours without introducing flat shelves, rolled lips, cuff ledges, or secondary shoulders.
- `[AGENTS.md:Toolchain Binding]`: Installed Python, Blender, and NWN executable paths must reside strictly in ignored, byte-bound local runtime bindings (`toolchain.lock.json`); machine-specific absolute paths are forbidden in committed repository files.
- `[AGENTS.md:Validation Authority]`: Numerical connector success, tool receipts, and intermediate exports never automatically authorize anatomy or production acceptance; acceptance requires native and client validation gates.
- `[Repository Layout]`: Top-level pack directories must match `^srn_[a-z0-9_]{1,12}$` and have corresponding entries in `hakbuilder.json`.
- `[Talk Table]`: String reference IDs in `srn_tlk/srn.tlk.json` are immutable and monotonically increasing.
- `[Item & Head Budgeting]`: Generation trials permit at most 5 geometry submissions per model; trial ledgers and submission records are immutable.

## Global Side Effects

- Compilation and build commands (`Build-Haks.ps1`, `Build-Tlk.ps1`) write binary `.hak` and `.tlk` archives to `output/`.
- Pipeline tools launch external processes including the NWN model compiler (`nwnmdlcomp`), texture cruncher (`nwn_crunch`), headless Blender, and the NWN game client (`nwmain.exe`).
- Generative workflows dispatch external API calls via Meshy CLI or local ComfyUI GPU servers on `127.0.0.1:8188`.

## System Verification

- Run: `Verify.cmd` (or `pwsh ./tools/Test-Repository.ps1`)
