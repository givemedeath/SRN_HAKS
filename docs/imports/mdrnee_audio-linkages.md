# `mdrnee_audio.hak` linkage report

## Verified source and landing

- Source SHA-256: `012841691F5AB20EDAD8F2924DC63CC638C84CB8FD3D6A188F13388905E7742F`
- 158 resources are accounted for: 142 BMUs in `srn_music`, 15 WAVs in `srn_sound`, and
  `mdrnmod_barclub.wav` explicitly excluded
- Global tables are generated into `srn_2da` from the pinned NWN:EE 89.8193.37-17 (`r1284`) baseline
- The manifest records one differing base collision: `it_materialcloth.wav`

## Music registrations

Every BMU has an exact Resource match in the source `ambientmusic.2da`. The merge preserves the
legacy IDs because they do not collide with the EE baseline:

- rows 190–194: five DJohn tracks
- rows 201–337: 137 modern, science-fiction, ambient, and battle tracks

Rows 195–200 remain blank. Source row 338 is not promoted because `mus_theme_main.bmu` is absent
from `mdrnee_audio.hak`.

## Ambient-sound registrations

Five landed loops are relocated because source rows 201–203 collide with current EE wind
registrations. Existing EE rows 201–203 remain unchanged, and target row 206 remains blank for the
excluded bar/club loop.

| Source row | Merged row | Resource |
|---:|---:|---|
| 201 | 204 | `mdrnmod_cityday.wav` |
| 202 | 205 | `mdrnmod_office.wav` |
| 204 | 207 | `mdrnmod_bigwar.wav` |
| 205 | 208 | `mdrnmod_gangwar.wav` |
| 206 | 209 | `mdrnmod_comproom.wav` |

Their legacy custom string refs are migrated into the shared `srn.tlk` and the merged table now
uses SRN refs 16777216-16777220. Exact source refs, canonical keys, texts, and replacement counts
are recorded in `mdrnee_tlk-migration.json` and `mdrnee_tile-string-ref-remaps.json`.

The ten remaining WAVs are direct-use effects with no global ambient row:
`clankmachine`, `doorbell`, `dssawful`, `dssawhit`, `dssawidl`, `dssawup`,
`fishtank`, `fw_blaster`, `it_materialcloth`, and `phonering`.

`mdrnmod_barclub.wav` (source row 203, intended merged row 206) was dropped by operator decision.
It remains represented in the source manifest as `exclude`, but is absent from `srn_sound`.

## Tileset relationship

The SET files contain no authoritative `TILEnSOUNDj` sections that name or select these resources;
their stale nonzero `Sounds` counts are among the fields normalized by the repaired SET pipeline.
The audio is therefore shared modern-setting content, not a dependency unique to one friendly
tileset. The 24-HAK smoke module includes `srn_music`, `srn_sound`, and `srn_2da`, making the
registered tracks and loops available to areas from all 18 friendly tilesets.

Existing modules that used the monolithic source table must map ambient IDs 201→204, 202→205,
204→207, 205→208, and 206→209. Source ID 203 has no replacement because its WAV was excluded.
Music IDs remain unchanged. The decoded working and generated UDP2 test areas contain no ambient
sound or music selection fields, so neither references source ID 203.

## Remaining risk

The technical linkage is closed, but per-track redistribution rights are not documented in the
archive. Several display labels identify commercial game properties or soundtracks. Complete the
provenance/legal review before publicly distributing `srn_music.hak`.
