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

All `.2da` resources belong in the single `srn_2da` HAK. Existing 2DA rows may not be renumbered or
reused; a row allocator will be designed only when independent allocation is actually needed. The
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

## Consumption and NWSync

SR_NWN and SRN_NWN consume this repository as a pinned Git submodule. Each consumer builds the HAKs
and TLK, selects the required HAK order in its module, runs its own engine tests, and publishes its
own NWSync repository from the final module/HAK/TLK stack. This repository publishes neither GitHub
release artifacts nor a central NWSync repository.

## Validation boundary

Repository verification proves resource naming, size policy, configuration consistency, TLK
allocation, HAK construction, and archive inventory. Rendering, model behavior, texture appearance,
walkmeshes, module loading, and live client/server behavior must be proven by the consuming project.

## Licensing

Original repository material is available under the PolyForm Noncommercial License 1.0.0. Imported
content retains its own license and attribution; see `NOTICE.md` and `PROVENANCE.md`.
