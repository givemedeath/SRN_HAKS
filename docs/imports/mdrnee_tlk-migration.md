# MDRNEE TLK migration

The merged MDRNEE 2DAs now reference the repository's shared `srn.tlk`, not offsets in the
legacy `mdrnee_tlk.tlk`. The source TLK SHA-256 is
`18620A3D984410024C79BDA7647A100A0F23A1D14713B602CE37DEFC95361D0F`.

## Landed entries

| SRN ID | Game strref | Text | Consumer |
|---:|---:|---|---|
| 0 | 16777216 | Modern City Day | `ambientsound.2da` |
| 1 | 16777217 | Modern Office | `ambientsound.2da` |
| 2 | 16777218 | Modern Computer Room | `ambientsound.2da` |
| 3 | 16777219 | Modern War | `ambientsound.2da` |
| 4 | 16777220 | Modern Gang War | `ambientsound.2da` |
| 5 | 16777221 | Bay Door/GarageDoor | `genericdoors.2da` |
| 6 | 16777222 | Sliding Glass Doors | `genericdoors.2da` |
| 7 | 16777223 | Elevator Doors | `genericdoors.2da` |
| 8 | 16777224 | Wood Glass Reflect | `genericdoors.2da` |
| 9 | 16777225 | Manhole | `genericdoors.2da` |
| 10 | 16777226 | Glass Window | `doortypes.2da`, D20 Shadowrun Exterior (`srt04`) |

The first ten texts are exact source-TLK migrations. Source `doortypes.2da` row 117 used
`1678190`, which is below the custom-TLK range and beyond the installed EE base talk table.
Its `GlassWindow` label and `t_door12` model provide the evidence for the synthesized
Glass Window repair.

## Coverage and deduplication

All 16 staged 2DAs were scanned after regeneration. The three consuming tables contain 33
custom-range cell occurrences, all resolving to active IDs 0-10; no legacy custom refs or
suspicious seven-digit substitutes remain. `ambientmusic.2da` uses literal display strings,
`skyboxes.2da` does not add custom refs, and the edge tables contain no string-ref columns.
Imported `doortypes.2da` values other than row 117 resolve to the EE base talk table.

`tools/Import-Tlk.ps1` deduplicates the complete normalized TLK payload. If another import
requests a new key for an existing payload, it records that key as a validated alias on the
canonical allocation instead of creating another ID. Both primary keys and aliases resolve during
2DA rewriting. Existing-key payload or owner conflicts are rejected.

Machine-readable source-to-target mappings are in `mdrnee_tlk-migration.json`; exact table,
replacement-count, and canonical-key evidence is in `mdrnee_tile-string-ref-remaps.json`.
