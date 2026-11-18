# Modern Exterior (`dgt04`) Shadowrun upfit — plan

Status: planning, 2026-11-18. Nothing in the packs has changed yet.

Source: `SR_NWN_Modern_Exterior_Upfit_Plan_Complete.zip` (revision 1.1, 2026-11-18), reviewed against this
repository. The package's art direction and its insistence on in-game proof stand. Its inventory, packaging and
schedule do not, for the reasons in "Corrections to the package". Where the two differ, this file is the plan.

## Decisions (user, 2026-11-18)

| Topic | Decision |
|---|---|
| Packaging | Replace in place in `srn_t_common`, `srn_t_dgt04`, `srn_door`. No override pack. Git history is the rollback. |
| Texture authoring | Hybrid. CC0 scanned material libraries for tiling surfaces (concrete, brick, asphalt, roofing, metal). Generated images only for facade atlases, windows, doors and signs that must follow the original UV layout. |
| Geometry | Release 1 is materials only on every original tile. Detail kit and remeshing are release 2, judged in game against the new materials. |
| Districts | Highrise 01–03 and 05–07 corporate and maintained; `Highrise_04` stays the collapsed ruin it already is; Slums 1–3 Barrens; Apartments mixed; Warehouses industrial. |
| New terrains | Two, copied from existing highrises: `Highrise_08` mid-tier residential from `Highrise_05`, `Highrise_09` derelict but standing from `Highrise_02`. |
| Prototypes | The earlier Highrise V2 and Slums V4 work is reference only. Nothing is imported from it. |
| Baked signs | Redrawn as generic 2070s signs with no brand names. Shadowrun brands stay on envkit buildings and placeables. |
| Doors and props | Tileset doors are restyled with the tiles. Modern Exterior placeables are a follow-up. |

## Verified baseline (this repository, 2026-11-18)

| Fact | Value |
|---|---|
| `dgt04.set` | 22 terrains, 14 crossers, 556 tiles (555 models), 68 groups |
| Original MDRNEE tiles | 433 ASCII models (428 original + 5 arcology `srt04_*`) |
| Envkit tiles (`ek_*`) | 122 compiled models with their own PBR materials; out of scope, and the look to match |
| Where the tile models are | 170 in `srn_t_dgt04`, 385 in `srn_t_common` |
| Textures the ASCII tiles name | 223 |
| … with both a TGA and a DDS copy | 202 (3 TGA only, 1 DDS only) |
| … also used by another tileset | 12 (all 12 by `fcx01`; 6 by `shp02`) |
| … held outside the two tile packs | 5 in `srn_door` (`glass`, `dgt04_chrome`, `lab_win1`, `manhole_tex2`, `arcology_win02`) |
| … in no pack here | 12: ten base-game (`tcn01_*`, `ttr01_*`), plus `obscuring` and `stone`, to confirm in Phase 0 |
| Source texture sizes | most 32–256 px; 18 at 512; 16 at 1024 |
| Existing materials on original tiles | none (all 57 `.mtr` files belong to envkit buildings) |
| Building terrains | each borders only Concrete. Highrise terrains are 6–10 tiles; Slums 30–44; Apartments 18; Warehouses 9–10; Police 8; Hospital 15; Lab 7 |

The most-used textures (`sidewalk10` 166 models, `concrete_10` 122, `concrete_08`, `pavement`, `roof_gravel1`,
`asphalt_road01`, `brick_tex19`) are used by `dgt04` alone, so the ground and wall foundation can be replaced
without touching any other tileset.

## Corrections to the package

1. **The inventory is of an older build.** It counts 429 tiles and 52 groups. The repository has 556 and 68: the
   five arcology groups (2026-11-10) and eleven envkit buildings were added since. Every "429 / 428 / 52" in the
   package's acceptance lists is replaced by the figures above, regenerated from the repository at each gate.
2. **"235 TXI" is wrong.** The package's reader appears to have mislabelled resource types: `srn_t_dgt04` holds
   31 DDS files and no TXI, matching its 31 "TXI", and its three "type 2022" files in `common` match the three
   TXI the original tiles have (`checks`, `walk`, `window_tex07`). The original tiles have almost no TXI,
   so there is little TXI behaviour to preserve, and a DDS copy of nearly every texture to replace.
3. **None of the 15 "missing" textures is missing.** Four are in `srn_door`, `chainlink_fence` is DDS-only in
   `srn_t_common` (the scan looked for TGA), ten are base-game. The Phase 0 "resolution audit" is done.
4. **A separate override HAK is the wrong shape here.** This repository is the source of both packs. An
   override pack that shipped only TGA would compete with the DDS copy of the same name below it, and same-name
   files in `srn_placeable` and `srn_door` already depend on pack order (`hakbuilder.json` lists them). In-place
   replacement of both copies avoids all of it.
5. **`SR_NWN/assets/tilesets/…` and new build scripts are not needed.** `hakbuilder.json`, `Test-Repository.ps1`,
   NWN Crunch, the MDRNEE test module, the envkit Toolset and client checks, and review by computer use already
   exist here. New code is one inventory/check tool and one material build tool under `tools/`.
6. **Licence is recorded, not open.** `NOTICE.md` and `PROVENANCE.md` hold the D20 Modern Haks 2.2 permission
   (open when the consuming project is open, credit requested). What is new is a PROVENANCE entry per CC0
   source and per generated texture.
7. **`Highrise_04` is not corporate.** It is a destroyed building (rubble, rebar, broken brick). It gets ruin
   materials, not glazing.
8. **Sixth World identity largely exists.** Stuffer Shack, Ares Depot, Pulse Tech and the other envkit groups
   are already in the palette. The restyle must sit beside them; the package's Phase 4 shrinks to generic signs.
9. **Night windows are separate glow textures** (`hrise_05_wall_g`, `window_tex08_g`, `win001_unbrknn`). Each
   new facade needs its lit-window layer redrawn to the same layout, or lit windows will not line up.
10. **Shared-texture risk is small and specific.** Twelve textures, all shared with `fcx01`. Each is either
    restyled for both sets after looking at `fcx01` in game, or forked to a new name for `dgt04`.
11. **The schedule is dropped.** 24 weeks and 500–900 hours describe one person painting by hand. Work here runs
    in reviewed batches with a gate each, like envkit sheets.
12. **"No new terrain types" no longer holds**, by decision: two are added, appended after tile 555 so no
    existing tile number moves.

## Constraints

- No walkmesh changes. Every original `.wok` and every `aabb` node hashes the same before and after.
- No existing tile number, terrain name, crosser name or group moves in `dgt04.set`. New tiles are appended.
- Release 1 edits no original model unless a texture must be forked to a new name; then only the `bitmap` line.
- A texture is replaced in every format and every pack that holds that name, or the difference is a recorded
  decision. No file over 15 MiB without a size exception in PROVENANCE.md.
- No shared tiling crack, stain or patch large enough to read as a repeat across four adjacent tiles.
- Tiles are placed in four rotations: ground and road materials must have no lighting direction baked in.
- Nothing is accepted from a preview render. Acceptance is the Toolset and the game client, day and night.

## Phases and gates

### 0 — Inventory tool and engine proofs

- A tool that writes, from the repository: texture → models → tiles → terrains, UV coverage per texture, formats
  and sizes, same-name copies in other packs, base-game names, and a walkmesh hash baseline.
- A review area for `dgt04` that holds every terrain, crosser and original group, with fixed camera positions.
  Baseline screenshots by day, night and overcast before anything changes.
- Proofs on three textures (`sidewalk10`, `brick_tex19`, `hrise_05_wall`), each in the client:
  - a `.mtr` named like the texture is applied to an ASCII tile that names only `bitmap`, with no model edit;
  - the normal map lights correctly on all four tile rotations and on mirrored UVs;
  - which of TGA and DDS the client shows when both are present;
  - the night glow layer still switches on over a material with a normal map.
- **Gate:** the four proofs pass, or the plan changes (for example, materials named in the models instead).

### 1 — Material standard and pilot block

- Resolution budget by measured coverage: 1024 for wide tiling surfaces, 512 for small ones, up to 2048 for
  facade atlases. Normal maps everywhere they show; roughness and specular only where the surface differs from
  the default (glass, wet asphalt, metal).
- About fifteen textures: sidewalk, two concretes, asphalt, pavement, roof gravel, one brick, Slums windows by
  day and night, one corporate facade with its glow layer, door trim, street lamp, metal fence.
- One block in the review area: a corporate highrise, a Slums building, a street with an intersection, a
  warehouse, next to a Stuffer Shack for comparison.
- **Gate (user):** the look, by day and night, beside the envkit building. This fixes the standard for the rest.

### 2 — Ground, streets and infrastructure

Roads, sidewalks, curbs, crossers (fences, walls, alleys, railings, docks), Freeway, Green_Bridge, Aqueduct,
Water edges, Cliff. Checked on a grid of straight, corner, T, four-way, ramp and transition tiles in all
rotations. **Gate:** no new seam at any tile join; road against sidewalk still reads at night.

### 3 — Building families, one batch each

Slums 1–3 (104 tiles) → Highrise 01–03, 05–07 → `Highrise_04` ruin → Apartments → Warehouses → Police, Hospital,
Lab → tileset doors and the five textures in `srn_door`. The twelve textures shared with `fcx01` are settled in
the batch that first meets them. **Gate per batch:** in-game review, walkmesh hashes unchanged, repository checks.

### 4 — `Highrise_08` and `Highrise_09`

Copies of the `Highrise_05` and `Highrise_02` tiles under new model names with their own textures; walkmeshes
copied unchanged; terrain entries, appended tiles, door records, roof-access group, palette entries, edge-table
rows and minimaps. **Gate:** both paint, border Concrete and place doors in the Toolset; existing areas unchanged.

### 5 — Cohesion and release

Wear and saturation evened out across families; frame rate and load time against the Phase 0 baseline on the
same area; pack sizes reported; `fcx01` and the other sixteen tilesets opened once to confirm nothing else
moved. One pull request per phase rather than one at the end.

### Release 2 (not planned in detail)

Detail kit and selective remeshing on the families that still look flat, Modern Exterior placeables, and any
branded signage the generic signs leave wanting.

## Open items

- Names for the two new terrains as builders will see them in the Toolset.
- Whether `fcx01` should take the new look for the twelve shared textures (decided on sight in Phase 3).
- Which CC0 libraries are acceptable sources, to be listed in PROVENANCE.md before the pilot.
- Other sessions append envkit groups to `dgt04.set`; Phase 4 must land as one short-lived change to that file.
