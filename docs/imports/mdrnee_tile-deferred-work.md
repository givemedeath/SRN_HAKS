# MDRNEE deferred-content and edge-review map

This document turns the current 1,462-resource quarantine and the source archive's 48 missing
edge-model identities into decision-sized work. Counts come from `mdrnee_tile-manifest.json`.

## Recommended order

| Priority | Work | Why |
|---|---|---|
| 1 | Validate the five incomplete edge tables | Known localized visual/walkmesh risk |
| 2 | Resolve four intentionally excluded texture overrides | Confirm whether split-stack rendering actually needs them |
| 3 | Locate companions for placeable PWKs and unused tile WOKs | Walkmeshes alone are not usable content |
| 4 | Classify orphan models and texture families | Most have no proven consumer |
| 5 | Review audio provenance | Several music labels identify third-party game soundtracks |

## Quarantine categories

| Category | Count | Contents | Recommendation |
|---|---:|---|---|
| Deliberately excluded texture overrides | 4 | `black.dds/.tga` (shared by tjsb0, vac01, vmp01) and `tin01_bed02.dds/.tga` (shp02) | Keep quarantined unless visual comparison proves the source override is required |
| Unproven textures | 1,382 | 727 TGA, 652 DDS, 3 TXI; large families include minimap-like `mi*` assets, ships, windows, concrete, hospital, sidewalk, and arcology | Keep by family; promote only with a model, palette, placeable, or visual consumer |
| Placeable walkmeshes | 56 | `cq*.pwk` only | Find matching placeable MDL/templates first; then create `srn_placeable` |
| Unproven models | 9 | six curtain models, two ship ceilings, and `c_decap_npc` | Split into placeable/tile and character investigations |
| Unused tile walkmeshes | 8 | `dgw01_34_01`, `tid01_d0[8-10]`, `enginec`, and three `mod01_o01*` WOKs | Pair with matching MDLs and a SET/group reference before promotion |
| Effects | 2 | `asteriods.mdl`, `fx_flame01.mdl` | Future `srn_fx` after a consumer is identified |
| Source global table | 1 | legacy `doortypes.2da` | The source table remains quarantined; the generated EE-baseline merge is active in `srn_2da` |

The rows total exactly 1,462 quarantined resources. Skyboxes, all door assets, 142 BMUs, 15 WAVs,
and their approved baseline-preserving registrations are now promoted; `mdrnmod_barclub.wav` is
separately recorded as excluded in the audio manifest.

## Cross-tileset dependency audit

Cross-tileset reuse is extensive and intentional. The manifest assigns 936 resources to more than
one tileset: 915 are in `srn_t_common`, 17 door-related resources are in `srn_door`, two are in
`srn_skybox`, and only `black.dds` plus `black.tga` remain quarantined. The owner combinations are:

| Tileset owners | Shared resources |
|---|---:|
| D20 Modern Exterior (`dgt04`) + D20 Shadowrun Exterior (`srt04`) | 861 |
| D20 Futuristic City SW (`fcx01`) + D20 Starship Interior SW (`shp02`) | 39 |
| D20 Suburbs UDP (`udp1`) + D20 Office Interiors UDP (`udp2`) | 16 |
| `fcx01` + `shp02` + `srt04` | 6 |
| `dgt04` + `fcx01` + `srt04` | 5 |
| `dgt04` + `fcx01` + `shp02` + `srt04` | 3 |
| `fcx01` + `srt04` | 2 |
| `shp02` + D20 Space (`vac01`) | 2 |
| D20 Secret Base (`tjsb0`) + `vac01` + D20 Planetscape (`vmp01`) | 2 |

UDP1 and UDP2 share 16 textures: 13 are in `srn_t_common` and three door textures are in `srn_door`:
`az-msc-drtdr.dds`, `gg_black.dds`, `gg-conc.dds`,
`gg2-bark.dds`, `gg2-h2-3.dds`, `gg2-wd-pl.dds/.tga`, `udp1-blck-gr.dds`,
`udp1-blck-gr2.dds`, `udp1-mtl-alum.dds`, `udp1-mtl-chrm.dds`, `udp1-mtl-grid.dds`,
`udp1-mtl-gry.dds`, `udp1-mtl-gry2.dds`, `udp1-pnt-wh1.dds`, and
`udp1-wd-grd1.dds`. Nine of those shared identities use an `udp1` prefix. UDP2 also references
two UDP1-named textures not used by UDP1 itself, `udp1_d_sldgl.dds` and
`udp1-hydr1a.dds`; both are packaged in `srn_t_udp2`. All 11 UDP1-branded UDP2 dependencies
are present.

## Missing edge-model inspection

The source has 48 missing identities across five `*_edge.2da` tables. They are not placed tile models:
the table chooses a helper model for a terrain/crosser edge signature. A successful tile-0 smoke test
therefore does not exercise them. In the Toolset, paint the named terrain/crosser boundary, rotate it,
undo/redo it, reopen the area, and then test the resulting edge in the client. Record whether the
failure is Toolset-only (preview/painting), persisted geometry, or walkmesh behavior.

### D20 Modern Exterior — dgt04

Six missing models across eight rows:

- `dgw02_z01_01`: Concrete / Wall02 / Concrete at height 0 and raised height 1. Inspect palette
  group **Wall02_Tunnel**, especially tiles 232–237 and 262.
- `dgt04_z12_01`: Water-to-empty outer boundary.
- `dgt04_z14_01`: Water / Green_Bridge / Water and raised Concrete / Green_Bridge / Concrete.
  Paint the **Green_Bridge** crosser at ground and raised elevations.
- `rdt02_a14_01`: Green_Bridge outer boundary.
- `dgt04_z00_03`: raised Concrete-to-Concrete edge. Inspect **Street_Raise**, **Freeway_Ramp**,
  **Green_Bridge_Ramp**, and **Stairway** rather than trying every matching concrete tile.
- `dgt04_z00_04`: raised Concrete-to-Water edge. Inspect **ConcreteToDocks**, especially tiles
  420 and 421.

### D20 Suburbs UDP — udp1

Three missing models, isolated to the otherwise undeclared **Forest_Clearing** terrain:

- `udp1_z01_33`: Forest_Clearing / empty / Forest_Clearing.
- `udp1_z01_34`: Forest_Clearing / empty / Forest.
- `udp1_z01_35`: Forest_Clearing outer boundary.

Inspect tiles 137–157 while painting Forest_Clearing into Forest and against the area boundary.
No named palette group owns these tiles.

### D20 Office Interiors UDP — udp2 (workflow confirmed)

Comparison with SWLOR's working decomposed `sw_t_office` establishes that its `udp2.set`,
`udp2_edge.2da`, WOK files, and TGA files match the original `mdrnee_tile` resources. Its palette
decodes to the same logical GFF content; the byte difference is serialization only. Its 251
matching MDLs are compiled binaries while the source MDLs are ASCII. SWLOR contains four extra
placeable resources (`udp2-p-45.mdl`, `udp2-p-45.pwk`, `udp2-p-99.mdl`, and
`udp2-p-100.mdl`), but neither the SET nor the tileset palette references them.

The Toolset workflow is Wall-first. UDP2 declares `Default=Wall` and `Floor=Office_Vinyl`.
Start with a filled Wall area, paint `Office_Vinyl`, `Office_Wood`, `Office_Alum`, or another
floor terrain over the Wall, and only then use that terrain's associated features and groups.
The prior fixture used tile 12, a `Service_Entry` group tile, so enlarging it did not establish the
required Wall canvas. The UDP2 fixture now uses tile 13, the uniform blank Wall filler used by a
Toolset-created area.

All 17 unique source `gi_z*` models are absent and cover rows 0–24. An experimental
`udp2_z*`/`Office_Alum` remap did not fix the placement failure and is no longer active. The
failure also reproduced in a separately enlarged split-stack area, while a module using the
monolithic source HAK worked. The current controlled test preserves the raw source edge table and
uses the count-normalized SET. The earlier repair failure was isolated to the precreated area and
its incorrect seed tile:

- **Foyer_L** and **Foyer_U** boundaries and the Entry, Win, WinCrnr, Firepl, Stair, Stair2, and
  Grandstair groups.
- **Hallway1** and **Hallway2**, especially groups `Hallway1_Entry 2x1` and
  `Hallway2_Entry 2x1`.
- **Service**, **Tiled**, **Office_Vinyl**, and **Office_Wood** interiors: each terrain's Entry,
  Win, WinCrnr, Firepl, Stair, and Stair2 groups.
- Wall-to-empty outer boundaries.

For future regression testing, paint each floor terrain over Wall before checking **Service**,
**Tiled**, **Office Vinyl**, **Office Wood**, **Office Alum**, both foyers, both hallways, stairs,
fireplaces, windows, entries, elevators, stairwells, restrooms, and the break room. Save/reopen the
area and walk representative boundaries in the client.

### D20 Alien Ruins — vmr01

All 15 unique edge models are absent. Exercise every terrain/crosser family:

- Floor, Wall, Chasm, and Plaza boundaries.
- **Fence** using `InteriorFenceDoor` and `ExteriorFenceDoor`.
- **Bridge** using `BridgeDoor01`.
- **Corridor** using the InteriorHallDoor and InteriorStairs groups.
- **Doorway** using `Door_Trans` and `Door_Trans_Exterior`.
- **Alley** using `BigDoorAlley` and ExteriorStairsUp/Down.
- Plaza transitions using Exterior Platform, Walkway, RuinedTower, Fountain, Garden, Pool,
  Exit, and Mosaic groups.

This table should be treated as a full-table replacement/repair task, not 15 unrelated fixes.

### D20 SciFi Base CQ — zsf01

Seven missing models cover nine rows:

- `zsf01_z07_01`: floor-to-floor and floor outer boundary.
- `zsf01_z06_01`: Floor2-to-Floor2 and Floor2 outer boundary.
- `zsf01_z03_01` / `zsf01_z04_01`: wall-to-floor and wall-to-Floor2.
- `zsf01_z02_01`: wall / Corridor / wall; inspect **StairsUP** and **StairsDOWN**.
- `zsf01_z08_01`: wall / Doorway / wall; inspect **Transiton** (source spelling),
  **2x1Room**, **Bedroom**, **Cell**, and **Room**.
- `zsf01_z09_01`: wall-to-2x2 boundary, tiles 58–66.

## Decision rule

If painting, saving/reopening, and client walking all behave correctly, record the missing identity as
a stale edge-helper reference and replace or remove it only when a tested table variant is available.
If the Toolset shows a missing preview or refuses to paint, repair the edge table. If saved geometry or
walkmesh is wrong, inspect the selected tile MDL/WOK and SET adjacency in addition to the helper row;
do not assume supplying a same-named model will repair the underlying tile.
