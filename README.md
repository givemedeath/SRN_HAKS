# SRN HAK Content

SRN_HAKS is the public, curated source repository for Neverwinter Nights: Enhanced Edition HAK
content shared by SR_NWN and SRN_NWN. SRN_CC may produce curated content for this repository, but
is not a runtime consumer.

The layout deliberately follows SWLOR_Haks: every registered top-level `srn_*` directory is packed
into a same-named `.hak`. Generated HAK and TLK files are written to `output/` and are not committed.

## Quick start

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

## Adding a HAK

1. Choose a lowercase name beginning with `srn_` and no more than 16 characters total.
2. Create a top-level directory with that exact name and place only packable NWN resources directly
   inside it. Subdirectories are not supported.
3. Add the matching entry to `hakbuilder.json`.
4. Run `pwsh ./tools/Test-Repository.ps1 -AllPacks`.

Useful categories include `srn_2da`, `srn_ui`, `srn_shader`, `srn_palette`, `srn_sound`,
`srn_music`, `srn_load`, `srn_portrait`, `srn_fx`, `srn_creature`, `srn_item`, `srn_weapon`,
`srn_placeable`, `srn_door`, body-part packs such as `srn_pt_chest`, and tilesets named
`srn_t_<short-name>`.

All `.2da` resources belong in the single `srn_2da` HAK. Existing EE rows are preserved; imported
global rows may be relocated only through a reviewed, reproducible profile allocation recorded in
`docs/imports/*-global-row-allocations.json`. The
project intentionally does not impose an aggregate HAK size cap. Individual resources should remain
at or below 15 MiB; reviewed
exceptions must be recorded in `PROVENANCE.md` and must remain below GitHub's file-size limit.

## Shared TLK

`srn_tlk/srn.tlk.json` is the canonical talk table. Allocate entries with:

```powershell
pwsh ./tools/Allocate-StrRef.ps1 -Owner SR_NWN -Key combat.example -Text "Example text"
```

IDs are global, monotonically increasing, and never reused. A TLK entry ID `n` is referenced in game
as `0x01000000 + n`.

Legacy talk tables use the quarantine-first importer. It takes an input TLK and an output path
relative to `.quarantine/`, verifies a pinned profile and source hash, and deduplicates exact
normalized entry payloads against the canonical TLK:

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

`Apply` is idempotent. An existing key must retain the same payload; an exact payload already owned
by another active key is reused, the requested key is retained as a validated alias, and the result
is recorded as deduplicated in the migration report. Primary keys and aliases both resolve in 2DA
string-reference remaps without allocating a second TLK ID.

## Consumption and NWSync

SR_NWN and SRN_NWN consume this repository as a pinned Git submodule. Each consumer builds the HAKs
and TLK, selects the required HAK order in its module, runs its own engine tests, and publishes its
own NWSync repository from the final module/HAK/TLK stack. This repository publishes neither GitHub
release artifacts nor a central NWSync repository.

## Validation boundary

Repository verification proves resource naming, size policy, configuration consistency, TLK
allocation, HAK construction, and archive inventory. Rendering, model behavior, texture appearance,
walkmeshes, module loading, and live client/server behavior must be proven by the consuming project.

The portable MDRNEE smoke fixture is an aid for that consumer validation. Build its 18-area module
and the 25 declared HAKs with:

```powershell
pwsh ./tools/Build-MdrneeTilesetTestModule.ps1
```

See `test-modules/mdrnee_tilesets/README.md` for installation and test scope.

## Licensing

Original repository material is available under the PolyForm Noncommercial License 1.0.0. Imported
content retains its own license and attribution; see `NOTICE.md` and `PROVENANCE.md`.
## Analyzing legacy HAKs

`tools/Import-Hak.ps1` provides a reusable quarantine-first import pipeline. All modes require an
input HAK and an output path relative to the repository's predefined `.quarantine/` directory:

```powershell
pwsh ./tools/Import-Hak.ps1 -Mode Analyze `
  -InputHak D:\path\content.hak `
  -OutputRelativePath content-review
```

`Analyze` verifies and extracts the archive, then writes `raw/` and `analysis/` beneath the selected
quarantine path. An optional `-ProfilePath` supplies archive-specific ownership and promotion rules;
`-ExpectedSha256` pins the expected input. Supply `-NwnRoot` and `-NwnUserDirectory` when the report
must compare resources against a base-game installation.

For a profiled archive whose SET count fields can be repaired without guessing, generate isolated
repair candidates with:

```powershell
pwsh ./tools/Import-Hak.ps1 -Mode Repair `
  -InputHak D:\path\content.hak `
  -OutputRelativePath content-review `
  -ProfilePath ./tools/import-profiles/content.json
```

`Repair` requires the matching analysis manifest, leaves `raw/` untouched, rejects non-contiguous
sections, writes candidates beneath `repaired/`, and records every changed line and hash in
`analysis/repair-log.json`. Candidates are not copied into repository packs or registered.

After reviewing the generated manifest, apply a profiled import with:

```powershell
pwsh ./tools/Import-Hak.ps1 -Mode Apply `
  -InputHak D:\path\content.hak `
  -OutputRelativePath content-review `
  -ProfilePath ./tools/import-profiles/content.json `
  -NwnRoot D:\Games\NeverwinterNights `
  -NwnUserDirectory D:\NWNUser
```

`Apply` refuses a missing or mismatched manifest, an ambiguous landing, path traversal, or an attempt
to overwrite a different resource. See `tools/import-profiles/README.md` for profile requirements.

## Model compilation and decompilation

The pinned legacy model tools are documented under `tools/vendor/nwnmdlcomp/`. For scripted work,
use `tools/Invoke-NwnMdlComp.ps1`; it verifies the compiler hash and requires distinct explicit
input and output paths.

## Texture conversion

NWN Crunch 0.9 is vendored under `tools/vendor/nwn_crunch/` for BioWare/NWN DDS conversions.
Use `tools/Invoke-NwnCrunch.ps1`; it verifies the executable hash and writes to an explicit,
separate output path. `tools/Resolve-MdrneeTextureResolution.ps1` applies the documented
higher-resolution selection rule to cross-HAK MDRNEE texture variants after import.
`tools/Resolve-MdrneeEquivalentTextures.ps1` then applies the reviewed equal-resolution
exception registry.
