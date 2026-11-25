# Unified Shadowrun interior tileset: Office + Modern Interior + Facility + Service Ducts

Revision 1 (2026-11-24): the review of the draft production plan v2.1 and the corrected plan, approved by the user
with the defaults under "Decisions for the user".

## Context

The draft (`F:\Dev\SRN_Concept_Art\SRX_Interior_Consolidated_Production_Plan_v2_1_EnvKit_Reused.zip`) plans one
interior tileset from four sets (Office Interiors `udp2`, Modern Interior `tfb01`, Modern Facility `tbx78`, Service
Ducts `nac01`), with 40 room floorplans as 80 unfurnished/furnished groups. It was written from uploaded HAKs and a
GitHub view of the catalog, without the repository. So it plans work that is already done here, and it misses the
tools and rules the exterior consolidation (`srx01`, `docs/tilesets/srx01-plan.md`) produced.

Its goals stand: one set, U/F room groups, every furnishing also a placeable, reuse before Meshy. This plan keeps
those and replaces the method with the srx01 method.

## What the draft gets wrong (checked on this checkout, main 9ccffe29a)

| Draft says | Actual |
|---|---|
| Build `hak_import`, `set_merge`, `itp_builder`, `hak_pack`, `qa_offline` and six more modules | They exist: `tilekit merge` (set, palette, edge table, lock, `--check`), `inventory`, `count`, `walkmesh`, `review`, `family-review`, `openings`, `compile`, `unique`, `repair`, `terrain`, `detail`, `apply`, `perf`; `envkit blueprints`; `hakbuilder.json`; `Test-Repository.ps1`. `merge.py` has no set-specific code. |
| One merged HAK holding every model (`dist/srx_interior.hak`) | srx01 pattern: the new pack holds the set, palette and new tiles only; models stay in the four source packs. |
| Register through `tilesets.2da` | NWN1 has no `tilesets.2da`. The Toolset lists every `.set` in the hak stack. |
| Integrate 117 UDP placeables and 10 UDP doors (P2-04, P2-05) | Done: 117 `udp2-p-*` models in `srn_placeable` with `placeables.2da` rows; `t_door82`–`91` in `srn_door`. |
| 149 envkit placeables, rows 22740–22888, in `srn_placeable` | 178, rows 22740–22917, all in `srn_envprop` (moved 2026-11-24). |
| 24 furnishing families have no standalone model; 26 have no envkit match (bed, bunk, sofa, wardrobe, chair, bath, kitchen…) | `placeables.2da` has 6,219 labelled rows, ~790 `[mdrn]`. Label hits: bed 43, bunk 6, sofa/couch 20, locker 4, wardrobe/closet 8, toilet/sink/shower 16, chair 75, desk 44, table 66, fridge/kitchen 17, medical 6, safe 4, computer/terminal 54. The real gap is far smaller than 74 work orders. |
| Canonical asset → `master.blend` → placeable **and** tile | Reverse it: the shipped placeable is the master. A furnished tile is built from placeables, so "every furnishing has a placeable" holds by construction. |
| Build a "furnished tile compositor" | `tilekit detail` already bakes pieces into tiles from a placement spec (`{piece, at, turn, scale}`), merges them to one node per material, cuts `obstacle` footprints out of the walkmesh as NonWalk, and hashes the walkmesh. |
| 3 missing models, 24 missing WOKs to triage | `tall_*` and `tin01_o20_01` are base-game models. The rest are recorded in `docs/imports/mdrnee_tile-analysis.md` and `mdrnee_tile-repair-log.json`. Stage 0 walkmesh baselines settle what is left. |
| TFB01 elevation risk | No tile in any of the four sets has a raised corner (`HasHeightTransition=1` in tfb01 is unused). Stairs are in-tile geometry. |
| Six family pairs × eight connector classes of adapter tiles | All four sets are Wall-first (`Border=Wall`, `Default=Wall`); every floor terrain touches only Wall. Families meet through Wall with no join tile. Only **crossers** need joining (see stage 3). |
| Nested palette tree `00 Construction … 90 Legacy` | Tile palettes are three flat lists (Features, Groups, Terrain). Categories are a name prefix; hiding is `palette: false` in `names.json`. |
| Resref `srx_interior`, new props `sxi_*` | Follow the convention: set `srx02`; new props are envkit props (`ek_<sheet>_<name>`). |
| Meshy budget 588–5,875 credits | The envkit Meshy cap (2,790) is fully committed. Any generation needs the user to raise it. |
| P0 legal gates, D538 "no export" | The four packs and the Meshy paid plan are already recorded in `PROVENANCE.md`; each release adds an entry as before. D538 is in SR_NWN and was not read for this review. |

**Missing from the draft altogether:** tile numbers never move after release; door types are keyed to a set (srx01
needed rows 266–268); a group is found by its first tile's model, so U and F need models of their own names; tile
packs ship compiled with ASCII in `sources/`; client rules (fog clip 9999, cap, keyholing off); a look pass so four
families read as one set; a frame-rate budget for baked rooms.

**Draft data worth keeping:** the 40 floorplans (`09_original_floorplans.csv`), the group dispositions
(`GROUP_MIGRATION_DECISIONS.csv`: which fantasy groups to hide), the envkit crosswalk as a first guess, and the
family order of tile numbers (udp2 0–228, tfb01 229–566, tbx78 567–650, nac01 651–667).

## What the four sets are

| | Office `udp2` | Modern Interior `tfb01` | Facility `tbx78` | Ducts `nac01` |
|---|---|---|---|---|
| Tiles / groups | 229 / 93 | 338 / 61 | 84 / 14 | 17 / 0 |
| Floor terrains | Service, Tiled, Office_Vinyl, Office_Wood, Office_Alum, Foyer_L, Foyer_U | Livingroom, Kitchen, Inn, Shop | facility | Service |
| Hub terrain | Wall | Wall | wall | Wall |
| Crossers | Door, Hallway1, Hallway2, Door_Garage_Sm/Lg | Corridor, Doorway, Subway | corridor, doorway1–3, cell, raised | Duct |
| Door hooks / types | 169 / all 0 | 166 / 0, 24, 42, 43 | 73 / 0, 146, 54 | 5 / 0 |
| Primary rules | 0 | 25 | 0 | 4 |
| EnvMap | `tdc01__ref01` | `tfb01__ref01` | `tdc01__ref01` | `env_tti` |
| Edge table | `udp2_edge` (17 `gi_z*` models absent) | none | `tbx78_edge` | none |
| Pack models | ASCII | ASCII | ASCII | ASCII |

Clashes: `Wall`/`wall` (fold into one hub), `Service` in udp2 and nac01 (rename one, as `Water` was), `Corridor`/`corridor`.

Existing room shells (all-Wall corners, a door crosser on an edge): udp2 `*_SmRm1/2`, `*_MidRm 2x1`, `Restrooms`,
`Break_Room`; tfb01 `Livingroom`, `KitchenRoom`, `InnRoom`, `ShopRoom`, `HomeLower/Upper 2x2`, `Baracks`,
`SlumHome01/02`; tbx78 `room`, `room2x1`, `room3x1`, `giant_cage`.

## Stage 0 results (2026-11-24)

Baselines: `docs/tilesets/udp2/`, `tfb01/`, `tbx78/` and `nac01/` each hold `inventory.json`, `textures.csv` and
`walkmesh.json`; the first three also `openings.json` (their door hooks). The census of all four is
`docs/tilesets/srx02/census.json`; the opening at every crosser edge is `edges.json`; the room shells are
`shells.json`; the prop census is `props.json`. No review module was laid and no client was run in this stage.

**Cost to draw** (`tilekit count`, no budget given):

| | Models | Faces: median / p90 / max | Mesh nodes: median / p90 / max | Materials: median / p90 / max |
|---|---|---|---|---|
| udp2 | 229 | 134 / 676 / 8,695 | 18 / 83 / 237 | 6 / 9 / 19 |
| tfb01 | 333 | 419 / 584 / 779 | 21 / 33 / 47 | 8 / 11 / 18 |
| tbx78 | 90 | 259 / 518 / 738 | 32 / 56 / 68 | 7 / 9 / 9 |
| nac01 | 17 | 112 / 671 / 754 | 4 / 14 / 18 | 2 / 6 / 7 |

Textures: udp2 51, tfb01 67, tbx78 20, nac01 9. A furnished room adds far more faces than its shell has: one envkit
prop is 4,000 to 11,000 triangles against a shell of a few hundred.

**Census:** no undeclared and no unused terrain, no raised tile, every floor terrain paired only with the hub.

**Openings at the crosser edges** (walkable width at the cell's side, and the clear height over it; Top taken as +y):

| Family | Passage crossers | Door crossers |
|---|---|---|
| udp2 | `Hallway1`, `Hallway2`: 9.5 m wide, 4.0 m clear | `Door`: 4.25 m (64 edges) or the whole 10 m side (51); 3.0 m clear |
| tfb01 | `Corridor`: 7.0 to 7.75 m, nothing drawn overhead; `Subway`: floor 2.95 m down | `Doorway`: 2.25 to 2.5 m, 3.0 m clear (some 4.2) |
| tbx78 | `corridor`: 4.75 to 5.0 m, 3.6 m clear; `raised`, `cell`: 9.0 m | `doorway1`: 3.0 m; `doorway2`: 2.5 m, 3.26 m clear; `doorway3`: 2.5 m on a floor 0.6 m up |
| nac01 | `Duct`: 1.5 to 3.0 m, floor 0 to 0.88 m up, 2.0 to 3.5 m clear | none |

**What follows for stage 3:** no two families' passages are one width, so every passage pair needs an adapter
tile. Only tfb01 `Doorway` and tbx78 `doorway2` (both about 2.5 m wide) are near enough to try as one crosser, and
that is judged from client pictures. The ducts need a hatch tile in any case: their floor is raised.

**Door hooks** (`tilekit openings`): udp2 169, mostly 4.0 by 3.0 m, some 2.1 m wide; tfb01 166, 2.0 m wide, 3.0 or
4.2 m high; tbx78 73, 2.9 by 2.9 m. `nac01.set` has a malformed hook (`[TILE8DOOR1]`, `X==-4.75`: the source's own,
kept at the import), so `openings` refuses the set. The merge writes that hook's coordinate right in `srx02.set`.

**Room shells** (all corners the hub, walkable): udp2 31, among them ten `SmRm` of 100 m2 and ten `MidRm 2x1` of
203 m2 over five floor finishes, `Restrooms` and `Break_Room`; tfb01 49, its single rooms 42 to 54 m2, its two-tile
rooms 89 to 121 m2, eight `Home` groups of 173 to 200 m2 and `Baracks` (2x3, 290 m2); tbx78 14 (`room` 67 m2,
`room2x1` 149 m2, `room3x1` 235 m2); nac01 one. The tfb01 `Home`, `SlumHome` and `Baracks` groups have no crosser
on any edge: they are entered by a door hook alone, as a building's inside reached from an exterior area.

**Prop census:** `placeables.2da` has 6,219 labelled rows: 4,226 modern (`[mdrn]` and UDP2), 178 envkit, 526 others
with a model in a pack, 1,289 base game. By label, 86 of the draft's 87 furnishing families have a modern or envkit
candidate; only the alchemy fume hood has none. A label match is a candidate, not a fit: the matching is by word
and loose (a "screen" matches Partition), so thin families stay open until a room is furnished: Stage, Partition,
Surgical Table, Exam Bed, Conference Table (4), Safe (2), Autodoc, Ritual Focus, Ward Anchor. Every envkit model the
draft names is in the table.

**Other findings:**
- **SR_NWN areas:** none of its 167 area files names udp2, tfb01, tbx78 or nac01. Six use `tjsb0` (Secret Base),
  which bears on decision 1.
- **The newer udp2 hak** (`udp2_off_int.hak`) is not on this machine (looked in `F:\Dev`, the archives, Downloads
  and the game's hak folder). The comparison waits for the file.
- **Client pictures (2026-11-24):** review specs `docs/tilesets/<set>/review.json` (every floor terrain as a room on
  Wall, the passage crossers run across) and `groups.json` (groups laid apart; udp2 one floor finish only). Over 250
  views, in `output/tilekit/s0i-*` (not kept in the repository).
  - **User rule:** interiors are judged with their ceilings. Captures include eye-level views, the camera level or
    tilted up a little. `tilekit review` takes them from a block's `eye` (1.7 m up, pitch 90 level, more looks up).
    Views from above of a small room show mostly the black top of its ceiling and are of little use.
  - **udp2 (Office):** clean modern rooms with a tiled acoustic ceiling and light panels. The floor terrains differ
    mostly by wall: Service is concrete and brown brick, Tiled terracotta and stained plaster, Office_Vinyl, _Wood and
    _Alum one dark green carpet with cream, wood panelled and grey panelled walls, Foyer_L and Foyer_U the two levels
    of an atrium. Hallway1 and Hallway2 look alike.
  - **tfb01 (Modern Interior):** no ceiling anywhere (open to the sky), low walls, and a medieval look: damask
    wallpaper, timber framing, fireplaces. Furniture is built into its floor tiles and groups. It needs ceilings and
    the heaviest restyle, and its rooms are furnished already, so few of its shells suit an unfurnished variant.
  - **tbx78 (Facility):** rusted green metal plate rooms, panel ceiling, yellow lights; the corridor is an octagonal
    riveted tunnel.
  - **nac01 (Ducts):** a white junction room with two drum machines and a ceiling; the duct is a narrow round pipe.
  - Groups laid apart show sky through their door openings: the review areas are written as exteriors. Not a fault
    of the tiles.
  - Not pictured: udp2 garage doors, tbx78 `cell`, `raised`, `doorway3`. Two tfb01 group views were taken late.
- **nwn-director** (github.com/plenarius/nwn-director, suggested by the user): not adopted. It needs Linux (X11 or
  Xvfb), a Docker server and a CD-key login, and draws stills on the CPU with the high-quality shaders off. Its
  eye-level camera is what `eye` views now do; its holding of a view until the picture is saved is worth copying to
  end late captures.

## Stage 1: names (approved by the user 2026-11-24)

`docs/tilesets/srx02/names.json`: 14 terrains, 3 folds, 15 crossers, 166 groups, 13 categories.
`tools/tilekit/test_names.py` holds it to the four set files.

- A source name stays the key unless it clashes or differs by case: one `Wall` (three folds), nac01 `Service` becomes
  `Duct_Room`, tbx78 `corridor` becomes `Fac_Corridor` and its other crossers take the `Fac_` prefix, `facility`
  becomes `Facility`. The display says what the pictures show ("Office: Carpet, Wood Panelling").
- Nine fantasy groups of tfb01 are `palette: false` (category Legacy).
- **Stage 2 code this needs:** the merge leaves no group off the palette today, and it refuses a third group of one
  name (tbx78 names three groups `room2x1`; the entry lists a display for each under `repeats`).
- **For the review:** what tells Hallway A from B; whether the tfb01 names (Home, Retail) stand before its restyle;
  the five crossers not pictured.
- **Decided by the user (2026-11-24): restyle first.** tfb01's restyle (ceilings, full-height modern walls, period
  furniture out of its floor tiles) comes before any furnished room on its shells. Order now: names review, merge
  (stage 2), crosser joins (3), release A with source looks (4), **tfb01 restyle (new stage 4b, the dgt04 process)**,
  room tooling (5), pilots (6). The pilots on udp2 and tbx78 shells (R02, O04, S01, S03) do not wait for 4b; R04 and
  C01 do. Walkmeshes stay as the baseline records them; built-in furniture that blocks walking keeps its footprint
  or the baseline is revised with the user's approval.

## Stage 2: merge (2026-11-24)

`docs/tilesets/srx02/merge.json` and `tilekit merge` write `srn_t_srx02/srx02.set`, `srx02palstd.itp` and
`srn_2da/srx02_edge.2da`: 668 tiles (udp2 0-228, tfb01 229-566, tbx78 567-650, nac01 651-667; `numbers.json` holds
them there), 164 groups, 130 rules, shown as "SRN City Interior". `tools/tilekit/test_merge_interior.py` guards it.

- **Merge code added:** a group with `palette: false` stays in the set and off the palette; a names entry's `repeats`
  names each of several groups a set calls alike (the later ones `<name>_2`, `_3`); a family with `edge: false` has no
  edge table (tfb01, nac01).
- **Rules:** the source sets' own 29, and one for every pair of floors of two families, each changing the neighbour
  to Wall.
- **Doors:** tfb01 and tbx78 hooks name types keyed to the base game's TIN01 and TTF01 (24, 42, 43, 54, 146);
  `doortypes.2da` rows 269-273 are their copies keyed SRX02 and the merged hooks name those.
- **Edge table:** udp2's calls its fifth floor `Study`, which no tile does; `edgeNames` maps it to `Office_Alum`.
  Its 17 `gi_z*` models are in no pack (listed under `absent` with four base game models).
- **Groups left out (4):** tfb01 `HomeLower03`, `04`, `05` and `HomeUpper03` begin with the first tile of an earlier
  group, so the Toolset lays the earlier one for them in tfb01 too. Their tiles stay.
- **Source fix:** `nac01.set` hook `[TILE8DOOR1] X==-4.75` is now `X=-4.75`.
- **Client check:** `docs/tilesets/srx02/review.json` lays rooms of all four families and their four passages in one
  area of the merged set; 20 eye-level views, none late, every tile drawn (`output/tilekit/s2-srx02-eye`).
- **Toolset check (2026-11-24, by computer use on an isolated user folder):** the review module opens; the palette
  lists 107 features, 48 groups (155, the 164 less the nine fantasy ones) and 29 terrains and crossers with the eraser
  and raise tools. A floor of each family painted on Wall beside the others (Home kitchen, Facility, Duct junction
  room, Office terracotta), then a tile or group of each family with groups laid (Office Restrooms, Facility Room 1x2
  B, Home Slum Home A). Undo took a paint back. Saved ("Area verified successfully") and read back: tileset `srx02`,
  18 of 418 tiles changed, to tiles of all four families (udp2 4, tfb01 6, tbx78 3, nac01 5), none past 667.
  Not tried: redo (Ctrl+Y did nothing; the Edit menu was not used), rotating a group, reopening the saved module.
- **Open:** one EnvMap for the set (udp2's `tdc01__ref01` is kept; tfb01 and nac01 named others) is judged at the
  release A look check. Crosser joins are stage 3.

## Stage 3: passage joins (2026-11-24)

`docs/tilesets/srx02/joins.json` and `tilekit joins` build nine join tiles (`srx02_j[a-i]x_01`, tiles 668-676), each
between walls with one family's passage at the top and another's at the bottom. One tile serves both ways, since the
Toolset turns it. `tools/tilekit/test_joins_passage.py` guards them.

| Tile | North | South | Opening (wide x high, m) |
|---|---|---|---|
| a, g | Hallway A, B (udp2) | Corridor (tfb01) | 6.7 x 4.0 |
| b, h | Hallway A, B | Facility corridor (tbx78) | 4.5 x 3.6 |
| c | Corridor | Facility corridor | 4.5 x 3.6 |
| d, i | Hallway A, B | Duct (nac01) | 2.7 x 2.85 |
| e | Corridor | Duct | 2.7 x 2.85 |
| f | Facility corridor | Duct | 2.7 x 2.85 |

- **How one is made** (`joins.passage_model`): the north half of one family's straight passage tile and the south
  half of the other's, and across the seam a bulkhead 0.2 m thick, open where both passages are open (see the look
  fixes below). Each face of the bulkhead wears the wall material of the family it faces (the look with the most
  upright surface), so a later restyle carries. The walkmesh is the two halves' own; the duct's round floor is walked
  level over the last 2 m before the seam.
- **Found on the way:** the ground cut left out every face that is exactly upright, so a hallway lost a wall; a
  passage is cut with `solid=True`. The duct walkmesh folds back under its own wall, so a levelled side keeps its
  walked floor and gets plain non-walk ground either side.
- **Checked:** every join's walkmesh leads from its north edge to its south edge (test); in the client, 24 eye-level
  views through all nine (`docs/tilesets/srx02/review-joins.json`, `output/tilekit/s3-joins-eye2`), none late.
- **Look faults fixed the same day (user: fix join looks first):** the bulkhead's opening is no longer a rectangle
  but what both passages leave open where the seam cuts them (`joins.hole`: 72 rays from the middle of the walked
  floor, each as far as the nearer passage's surface), so a duct gives a round opening and the Facility tunnel an
  eight-sided one, with nothing black behind. A face's wall material is the one the level rays meet, which is what
  stands beside a walker (the Facility's largest upright surface is a black trim; its face is now rusted plate). Each
  join has a main light over each half (`MainLight1`, `MainLight2` on). Views: `output/tilekit/s3-joins-eye3`.
- **Still open for the release A look pass:** a section is taken 14 mm off the seam, since a ring of corners exactly
  on it cuts no triangle; a lamp or banner hanging in a passage's middle at the seam would dent the opening (none of
  the nine has one).
- **Not done:** doors. The plan's fold of tfb01 `Doorway` with tbx78 `doorway2` is left out: two rooms would meet at
  a tile edge with walls of different thickness. Rooms of two families join through a passage. A creature has not
  been walked through the joins in the client, and painting a join in the Toolset is not tried.

## Stage 4b: Modern Interior built-in furniture, survey and trial (2026-11-24, brought forward by the user)

- **Survey.** 333 of tfb01's 338 tiles have models, about 7,000 drawn parts. Texture names do not tell a room from
  its furniture (a table and a door frame share `tfb01_door2`, a bookcase and the floor `tfb01_shpflr1`), nor does
  the walkmesh (a bookcase is walked as wall). Where a part stands does: `tools/tilekit/strip.py` sorts each part as
  floor, rug, top, shell, built-in or furniture.
- **User rule: what would leave a hole stays and is given a new look in place.** The walls behind most of the
  set's furniture were never drawn (the living room's bookcase and desk both stand in front of nothing), so
  removing them opens the room to the sky. `strip.sort` looks through the room from its floor toward each standing
  part; one with nothing of the room behind it is `builtin`, as is what touches it (a bed's mattress on its frame)
  and what reaches the walls' top (a partition, a chimney breast). Set-wide: built-in 1,501, furniture 301, rugs
  102, shell 2,290, floor 520, tops 2,242; 150 tiles have something that comes out.
- **Stripping** (`strip.shell`): the furniture and rugs are left out, and the walkmesh faces not walked that they
  stood on become the room's walked floor. This changes a tile's walkmesh, so each stripped tile's baseline changes
  with it: **needs the user's approval** before it reaches a pack.
- **Trial room:** group `Livingroom` (tile `tfb01_e01_01`, "Home: Living Room"). Out: the bed and a chair. Kept:
  the bookcase (east wall) and the dresser (south wall). Added: a ceiling over the whole tile at the walls' top
  (3.0 m, seen from below only, Office's `udp2_msc_clg`), a new `tfb01_lwalls` picture (Office's off-white vinyl;
  the walls map the picture in bands, so one picture restyles every tile that draws it), and, furnished, a couch,
  armchair, coffee table, plant and standing lamp from `[mdrn]` placeables baked with `detail.place` as obstacles,
  with a television on the dresser (user). Pictures: `output/tilekit/trial4-b` (unfurnished) and `trial4-c`.
- **Found:** these `[mdrn]` placeables front on -y, not +y (the first bake had them facing the wall). The wall has a
  ledge at the old rail's height, which is geometry and stays. The door frame is still pale timber. The review lays
  no door in the doorway.
- **Textures (user, 2026-11-24): the kept furniture's pictures need upscaling at least, better replacement.** The
  tiles draw 68 textures: 22 at 128 px, 23 at 256, 7 at 512, the rest smaller. The cabinet, bookcase (books and
  electronics), floor and bedding pictures are modern in subject but 128 to 256 px. How they are remade is open.
- **Bookcase with a built-in screen (user, 2026-11-24):** the television is out; the bookcase's face is drawn once
  across a picture of its own (`tfb01_bookscr`, 1024 px, shelves of books round a screen), so no other tile changes.
  The picture is a procedural stand-in. A quad on the screen with the animated `fxpa_screen` (the `[mdrn]`
  television's own, additive, 4 x 4 frames) drew nothing in the client: **the screen is dark, nothing plays yet.**
  Codex image generation is out of quota until 2026-11-28; the user allows local Qwen. `tilekit redraw` is the tool
  for drawn-again textures and takes any generator; a local Qwen runner for it is the next step.
- **Local Qwen (user, 2026-11-24: "you can use local qwen if needed").** `tilekit redraw --bindings` already draws
  with the local Qwen edit model on the shared ComfyUI; it lacked interior kinds, now `furniture` and `floor`, and a
  district `home`. Its bindings file is local: absolute `comfyInput` and `comfyOutput` (the shared ComfyUI's
  `ComfyUI-Shared/input` and `output`) and the three Qwen model files with their hashes. One job drew the bookcase
  from the procedural stand-in (screen marked as a plain blue rectangle, said in the note to be a screen showing a
  news broadcast): a walnut bookcase of real books round a lit city-news screen, about two minutes. On the tile the
  screen's part of the picture is drawn again on a quad lit by itself, so it glows in a dark room. It does not move:
  a playing picture would need a frame sheet and is not made.
- **The room's textures drawn again** (`docs/tilesets/tfb01/redraw.json`, `tilekit redraw --bindings`, local Qwen,
  seed 1, four jobs in about eight minutes, none failed): `tfb01_lwalls` (off-white painted wall, a flat grey rail,
  grey panelling below, in the old bands), `tfb01_furnish2` (the dresser), `tfb01_shpflr1` (the floor, tiling),
  `tfb01_door2` (the door frame's wood and metal), each 1024 px on the layout it had. Pictures are in
  `output/tilekit/tfb01-redrawn` (not in a pack); client views in `output/tilekit/trial8-c`. These four are drawn
  by tiles all over the set, so every room that uses them changes with them. The wall's skirting does not show at
  the floor, and the walls are near white under the review's bright lights.
- **The screen plays (user, 2026-11-24: "animate the tv first").** The screen's quad draws `tfb01_scrn`, a sheet
  of 32 frames (4 x 8, each 512 x 256) made from the drawn picture: the ticker runs left past its badge, the neon
  flickers, the skyline drifts in and out; `tfb01_scrn.txi` says `proceduretype cycle`, `defaultwidth 512`,
  `defaultheight 256`, `numx 4`, `numy 8`, `fps 8`, a four second loop. In the client two views from one spot show
  the ticker at different places. The sheet is a 2048 x 2048 TGA, not yet DDS. (The television placeable's
  `fxpa_screen`, additive and a decal, drew nothing on a tile; a plain cycle does.)
- **The screen shows an explosion (user, 2026-11-24).** Local Qwen drew the screen's still again three times
  (`output/_boom.py`: the blast on the central tower, the fireball, the tower burning under smoke); the buildings
  stayed where they were, so the frames blend between them: skyline, flash, fireball, smoke, and the footage begins
  again. Seen in the client.
- **Ghost shapes on the walls (user, 2026-11-24)** were the baked placeables' stencil shadows. A node with no `shadow`
  line casts one, and nearly all of the set's own furniture has none (1,793 parts of 1,893), so it casts too. A first
  fix rewrote only explicit `shadow 1` lines and changed nothing, though it was reported as done; `shadow 0` is now
  written into every baked piece and built-in part of the trial tile, seen at full size in `output/tilekit/trial12-c`.
  A rule for the room tooling. The lamp is `pkt_slamp01`.
- **Steps in tone between wall panels** were the redrawn wall, not the mesh's shading as first recorded: its left and
  right edges differed by 20 levels (old picture 0.6). `redraw` now levels a texture (`level`: `across`, `both`).
- **Watched in a recording (user, 2026-11-24).** The client's window recorded with ffmpeg's screen capture at 30
  frames a second (`output/_clip.py`) showed the footage out of order: **the game plays a frame sheet's rows from
  the bottom up**, each left to right, so the first frames go in the bottom row. Also fixed: the flash is at the
  tower, not over the whole picture; a fourth key picture (the fireball dying into smoke) sits between the fireball
  and the burning tower, and the blend keeps what burns bright, so it no longer goes green; the loop ends on a cut
  to black instead of the tower un-burning. Checked again frame by frame in a second recording.
- **The set's textures drawn again (user, 2026-11-24).** `docs/tilesets/tfb01/redraw.json`: 43 of the 68 the tiles draw,
  local Qwen, none failed; 25 are left as they are, each with its reason (`left`: black, cut-outs, under 128 px, the
  512 px subway set). Eight came out wrong at first and were done again with new entry keys, tested: `bands` (the
  reference is each row's mean colour: shown the old wallpaper, Qwen drew it again), `blank` (a part of the reference
  filled over, so a portrait or an old print is not copied; a fill left standing is refused), `opening: none` (black
  is not put back: it left specks on dark bands). Pictures in `output/tilekit/tfb01-redrawn`, first pass in
  `tfb01-first`, old beside new in `output/trial/pairs`, six rooms in the client in `output/tilekit/set1`. The shapes
  stay period (cauldrons, urns, barrels, banners, timber braces) and the rooms have no ceilings yet.
- **Approved and in the packs (user, 2026-11-24: "Approve textures").** `docs/tilesets/tfb01/materials.json` builds the
  43 as plain DDS, 1024 by 1024 (a plain texture may now have a 15 or 16 letter name), and `tilekit apply` put them in
  place of their TGAs: 38 in `srn_t_tfb01`, 5 in `srn_door` (each is drawn by one door model there). The srx02 join
  tiles draw some of them by name. Both packs rebuilt; the six rooms captured from the rebuilt packs
  (`output/tilekit/set3`) match the approved views but for flames and clouds. The five door textures were not seen on
  their doors. Known flaws kept: `tfb01_sac`'s cream panel overlaps the bottom of its frame, `tfb01_rock1` has a small
  step in tone.
- **The room tool (stage 5; user, 2026-11-24: "Yes, build room tool").** `tools/tilekit/rooms.py`, command `tilekit
  rooms --spec docs/tilesets/srx02/merge.json` (then `merge`, `compile`), reads `docs/tilesets/srx02/rooms/<id>.json`
  and writes each room unfurnished and furnished as tiles of their own (`srx02_<id>u_NN`, `srx02_<id>f_NN`). The source
  sets' tiles and their walkmeshes are left as they are, so no baseline changes. Merge numbers the rooms after the joins
  (`["room", model]` in `numbers.json`) and shows both groups. `rooms-built.json` pins what a build read and wrote.
- **The trial room through the tool:** `liv01`, "Home: Living Room, media wall" and "..., furnished" (tiles 677, 678;
  398 and 1,868 triangles; 46.1 and 40.4 square metres walked), in `srn_t_srx02` with its bookcase picture
  (`srx02_bookscr.dds`) and its screen (`srx02_scrnews.tga`, 12 MB, with its TXI). Seen in the client from the packs:
  both rooms in `output/tilekit/rooms1`, the screen playing in `output/trial/liv01-screen-30fps.mp4`. The screen's key
  pictures and scripts are kept in the shared tool root, `.tools/tilekit/art/srx02-liv01`.
- **Found by the tool's checks, with a guard each:** `cuts` took a whole walkmesh triangle where a footprint only nicked
  it, so the trial room lost 7 square metres of floor round its coffee table (fixed, `cuts.outside`; of the 106 changed
  walkmeshes of the exterior packs none lost any); a flipbook in a DDS, standard or BioWare, draws as a pale film and
  does not play (`rooms.textured` wants a TGA and its TXI); a thing that lies on the floor or stands on furniture was
  taken for a wall fixture (`detail` `rests`); a piece that faces a wall, a room cut in two, a shut doorway are refused.
- **Changed from the plan:** a room keeps its shell's minimap; a baked lamp gets no tile light of its own; the triangle
  count is told, not held to a budget (the pilots set it).
- **Not done:** a room's groups are not laid or turned in the Toolset, and no creature has walked one (pilots); nothing
  has been made of a shell of several tiles but in code; 4 m walls to match Office were not tried.

## Decisions for the user (defaults used unless changed)

1. **Families.** Default: the draft's four. Secret Base `tjsb0` (174 tiles), SciFi Base `zsf01` (73), Bunker `fifi`
   (51), Parking Garage `flow_pa` (32) and Metal Interior `sjm01` (153) are also interiors in the repository; a
   family can be appended later without moving a tile number.
2. **Prop generations.** Default: furnished rooms may mix old `[mdrn]`/UDP placeables (low-poly, plain textures) and
   envkit props (PBR). The pilot rooms show whether the mix reads well; if not, old props get a material pass or
   envkit replacements.
3. **Look.** Default: merge with source looks first (release A), restyle per family afterwards as srx01 did. Rooms
   name each family's textures, so they follow a later restyle.
4. **Room scope.** Default: six pilot pairs (R02, R04, O04, S01, S03, C01) gate the method; the other 34 follow in
   category batches.
5. **Name.** `srx02`, shown as "SRN City Interior"; confirmed at the names review.
6. **Meshy.** Nothing is generated until the stage 0 prop census names the real gaps and the user raises the cap.

- **Stage 6, the six pilots (user, 2026-11-24: "Yes, start pilots"; 2026-11-25).** R02, R04, O04, S01, S03 and C01 are in
  the pack unfurnished and furnished (specs in `rooms/`, tiles `srx02_<id>u_NN` and `srx02_<id>f_NN`).
  - Shells: O04, S01 and S03 furnish existing rooms. R02, R04 and C01 are drawn (`tools/tilekit/walls.py`): outer and inner
    walls, doorways, floor zones, in the sets' textures. Modern Interior's house is mostly furniture fused to its walls.
  - Ceilings (user: "more appropriate ceilings"): plaster with a moulding, dome lamps and spots in homes; acoustic tile with
    light panels and a hung strip in the office; strip lights in the store; concrete with beams in the barracks; concrete in
    the armory (`tools/tilekit/ceilings.py`, also on `liv01`).
  - Facings (user: a couch faced its wall): couch, armchairs, dressers, wardrobes, candy rack, desk and all envkit pieces
    had been taken for front -y. Guards: `fronts.json` records each piece's front after it is looked at; a seat recorded
    back to front is refused; a seat out of line with the table it faces is refused (user: a chair not lined up).
  - A rifle rack's rifles drew white (user): `vos_rfl_stand1` names `jzg_m4a1`, which no pack holds (nor for `vos_ar_gun4`).
    It is out of the room; a piece with a missing texture is refused. The placeables themselves are not repaired.
  - Walkmesh: furniture cut out of the triangles left cracks a Troll and a Human stopped at. A furnished floor is now laid
    again in rectangles round squared footprints; `cracks` refuses a cracked one. A tile's floor is one piece and is open to
    each next tile in one place only: the first house had three rooms across one seam, and creatures took the wrong one.
  - Walked in the client by a Human and a Troll on the final build (`output/_walk.py`): each reached 54 of 55 points. The
    one that fails for both asks for a way out of the house's study straight through its wall; the creature stops and the
    next order succeeds. That is taken for the game's own path search; builds before this one left it stuck there.
  - Triangles: at most 39,600 a tile (store), 20,100 (armory), 12,500 (apartment). Props over 2,500 triangles are baked
    reduced: a store of whole envkit racks passed the engine's 65,535 vertices a mesh. Frame rate on a block of
    furnished rooms 174-178 against 174-178 unfurnished, cap 200 (before the last placement changes).
  - Views: bird's eye (user asked), and eye level, `review-pilots.json`; `review` takes named places with a height, distance
    and pitch of their own.
  - Gaps the pilots could not fill: a low-poly store gondola, a reach-in chiller, checkout with a scanner, a modern
    wardrobe, a bathtub that is not yellow, a coffee table, a TV stand, a nightstand, a kitchen counter top with no upper
    cabinet, a working rifle rack.
  - Toolset (2026-11-25, by computer use on an isolated user folder): the palette lists the six pairs under Home, Office,
    Security and Retail. Each furnished room painted turned (a quarter turn; the barracks a half), the bare apartment
    unturned; a group is refused at the area's edge and where its door faces a wall it cannot change. Saved ('Area verified
    successfully'), read back (every tile of each group in place with one orientation) and reopened.
  - Not done: the Toolset undo of a room; doors in the inner doorways; eye-level views tilted far up.
  - Seen beside this: the same crack test finds a few in exterior tiles (`dgt05_b07_06`, `dgt05_r07_31`, `dgt05_r07_32`,
    `rdt02_a01_03`; the `dgt05_w25` tiles look like levels over one another). Not looked into.
  - **Gate passed (user, 2026-11-25: "Approve pilots"):** look, prop mix (old placeables beside envkit props) and the
    triangle counts above. They are the standard for the 34 other rooms (stage 8).

## Stage 8, Home batch (user, 2026-11-25: "Yes, Home batch")

R01 studio, R03 two-bedroom apartment, R05 safehouse, R06 penthouse and R07 flophouse, unfurnished and furnished, all
drawn shells on Office lights; 20 tiles numbered after the pilots', no earlier number moved. With R02 and R04 the Home
floorplans are done.
- **Pieces** were picked from pictures of 150 candidates. Pieces the pilots called gaps exist after all: a coffee table
  (`jvb_tab05`, `jz_sfp072`), nightstands (`jhb_chev01`, `jvb_tab07`), a modern bed (`jvb_bed06`), a white wardrobe
  (`jhb_armoir01`). Still missing: a modern wardrobe that is not of another style, a white bathtub, a TV stand, a counter
  without an upper cabinet, a white shower tray, a wall mirror whose texture is in a pack (`plc_reflect` is in none;
  `purp_mirror`, `plc_mirror2`/`3` draw white), a flat TV for a wall. `drb_h01`, `plc_x52` and `tv` name absent textures too.
- **Back to front again:** a bookcase (`jz_sfp066`) was recorded by its plain back, and the piano's stool stood at its side.
  Guard: `bare` refuses a piece whose recorded front has under a third of its back's triangles (0.15 for that one; the least
  of the other pieces is 0.50). It cannot tell for a piano: its keys are looked at.
- **Walls:** a piece must stand 0.075 m clear of a wall (baseboard and crown). Block walls repeat at 4 m; at 2 m their
  shading drew a band at head height.
- **Walked** by a Human and a Troll on the final build: 88 of 88 points each. The Troll first stopped between the studio's
  couch and its wall and beside a chair of the safehouse's table; both were moved. The lane check lets through gaps that
  stop a Troll, so the walk stays the check.
- **Triangles** a furnished tile: studio 12.9k, two-bedroom 8.6k and 8.5k, safehouse 17.6k, penthouse 4.4-10.4k, flophouse
  14.2k and 3.2k, all under the approved pilots' 39.6k; frame rate not measured again.
- **Toolset:** each furnished room laid a quarter turn, saved and read back. A group is refused where its door would open
  on a wall that cannot change, over another group, and at the area's edge. Not reopened.
- **Views:** `review-home.json` (bird's eye and eye level; `output/tilekit/home3`).

## Work order

Each stage is one pull request into a `restyle/srx02` branch; `main` gets one merge per release. The running record
is `docs/tilesets/srx02-plan.md`, written at stage 0 from this plan.

### 0. Inventory, census, baselines

- `tilekit inventory --set udp2|tfb01|tbx78|nac01` → `docs/tilesets/<set>/inventory.json`, `textures.csv`,
  `walkmesh.json`; `tilekit count` for cost.
- `docs/tilesets/srx02/census.json`: terrains, crossers, rules, groups, door hooks and types, edge rows.
- `tilekit openings` on every door hook and corridor end: width, height, floor level and position of each crosser's
  opening per family. This table decides stage 3.
- `tilekit review` module per set, a handful of day views each (interiors: one lighting unless a set animates).
- **Shell list:** every all-Wall room tile and group, with size and door edges, pictured assembled.
- **Prop census** (`docs/tilesets/srx02/props.json`): the draft's 87 families against `placeables.2da` labels (all
  6,219, not only UDP and envkit), each with its candidate rows, faces and whether the pack model is ASCII or
  compiled. Output: the real gap list.
- **udp2 EE update:** the draft names a newer `udp2_off_int.hak` (23 more resources, changed set and palette). Diff
  it against `srn_t_udp2`; adopting it is its own small PR and must land before the merge freezes tile numbers.
- Check SR_NWN for areas on the four sets.

### 1. Names

`docs/tilesets/srx02/names.json`, from pictures, approved by the user:
- terrains and crossers with `key` (16 characters) and `display`; the `Wall` fold, the `Service` rename;
- group names led by a category: Office, Home, Facility, Ducts, Security, Retail, Industrial, Medical, Magical, Joins;
- the draft's deferred fantasy groups (Temple, Wizards Den, Smithy, Barn, Tent, Portal, Chessboard) `palette: false`;
  their tiles stay in the set;
- a new placeable category only if interior props need one (`blueprints.py`, `srn_tlk` rows);
- guard: extend `tools/tilekit/test_names.py`.

### 2. Merge

`docs/tilesets/srx02/merge.json` + `tilekit merge` → `srn_t_srx02/srx02.set`, `srx02palstd.itp`,
`srn_2da/srx02_edge.2da`, with `numbers.json` and the lock `merged.json`.
- Family order udp2, tfb01, tbx78, nac01. GENERAL from udp2 (`Interior=1`, Border/Default `Wall`, no height
  transition). EnvMap: one only, picked at the release A look check.
- Rules: each set's own, plus generated rules that route any two families' floors through Wall (`merge.rules`
  already does this for grounds).
- Doors: copies of types 24, 42, 43, 54, 146 keyed to `SRX02` in `doortypes.2da`, written into the hooks
  (`merge.json` `doors`, as rows 266–268 were).
- Edge table: absent models listed under `absent`, as in srx01.
- Register: `hakbuilder.json`, `PROVENANCE.md`, `tools/ci-test-durations.json`, `test_merge.py` cases.
- Toolset check by computer use: fill Wall, paint each family's floors, lay a group of each, save, read back.

### 3. Crosser joins (the interior's join tiles)

Stage 0 measured the openings (see its results): the passages all differ, so the adapter is the usual case.
The opening table sorts each cross-family crosser pair:
- **same opening** (within a tolerance set from the measurements): fold both names into one crosser key, so a udp2
  `Door` meets a tfb01 `Doorway` with no new tile;
- **different opening:** an adapter tile, all corners Wall, crosser A on one edge and B on the opposite, cut from
  the two families' own straight corridor tiles and meeting at the middle (a new shape in `tools/tilekit/joins.py`
  beside the ground shapes; walkmesh cut the same way);
- **ducts:** `Duct` joins only through a hatch tile to one corridor crosser per family.

Needed code: crosser folds in `merge.maps` (folds are terrain-only today), the adapter shape in `joins.py`,
`test_joins.py` cases. Joins ship compiled, sources in `sources/srn_t_srx02/`.
Checks: Toolset paint/rotate/undo/reopen of every pair; client walk through each; wall tops and ceilings seen across
a family boundary.

### 4. Release A

The merged set with source looks and the joins: packs built, `Test-Repository`, a review area with all four
families joined, look approved by the user, frame rate and load by the dgt04 baseline method (`tilekit perf`).
Terrain and crosser names freeze here.

### 5. Room tooling (new `tools/tilekit/rooms.py`, command `tilekit rooms`)

A room spec per floorplan, `docs/tilesets/srx02/rooms/<id>.json`:
`{id, name, category, shell: {set, group}, doors: [edge], props: [{placeable row or model, at, turn, scale, obstacle}]}`.

- **U variant:** the shell group's tiles copied under new model names (`srx02_<id>u_NN`), walkmesh unchanged, as
  `terrain.py` copies a terrain's tiles. Textures keep their family names, so a restyle carries.
- **F variant:** the U tiles copied again (`srx02_<id>f_NN`) and furnished with `detail.place`.
- **Kit pieces from placeables:** a piece is the placeable's own pack model. An ASCII model is used as it is; a
  compiled one (all envkit props, ~30% of `srn_placeable`) is decompiled the way `compiled.py` does for its audit.
  The furnished tile names the prop's own textures and materials, so the module loads `srn_placeable` and
  `srn_envprop` (already required by srx01).
- **Walkmesh:** furniture is `obstacle` (footprint NonWalk). `detail` already refuses a piece in a walking lane
  unless it is one. Check that `obstacle` works at floor level indoors; it was written for streets.
- **Budget:** a furnished tile is held by `tilekit count --budget`; envkit props run 4,000–11,000 triangles, so a
  dense room needs a reduced bake copy of a prop. The budget is set from the pilot's `perf` numbers.
- **Lights:** a baked screen keeps its glow; a baked lamp gets a tile light. No halo models are baked.
- **Never baked:** doors (they stay door hooks), containers, terminals, cameras, turrets meant to be used. The spec
  lists them under `placeLater`, and the room's notes tell the builder which blueprint goes where.
- **Into the set:** `rooms` writes tiles, minimaps (`envkit/tile.py` `minimaps`) and a group record; `tilekit merge`
  numbers them after the joins and puts both groups on the palette ("Home: One-Bedroom" / "Home: One-Bedroom,
  furnished").
- **Guards** (`test_rooms.py`): U and F share footprint, door edges and outer walkmesh edge; F's walkmesh differs
  from U's only inside obstacle footprints; every baked piece is a row of `placeables.2da`; first-tile models are
  unique in the set.

**Shell fit.** Sort the 40 floorplans before building any:
- (i) furnish an existing single-room shell (most 1×1 plans: O04, S01, S03, S05, S06, I04, I05, M01, A01–A03…);
- (ii) furnish an existing multi-tile group (R04/R06 on `HomeLower 2x2`, C01/C02 on `Shop`, S02 on `Baracks`);
- (iii) needs interior partitions the shells lack (R02, R03, O01, S08). Partition walls and doorways are code-made
  kit pieces in the family's wall texture (`kit.py` style) with a walkmesh cut; R02 is the pilot that proves or
  drops this class.

### 6. Pilot rooms (gate)

R02, R04, O04, S01, S03, C01 as U/F pairs: Toolset paint and rotate, client walk (Human, plus one Troll pass through
each door and aisle), day views, `perf` on a block of furnished rooms. User gate on look, prop mix and budget.
The gap list is revised from what the pilots could not furnish.

### 7. Gap props

Only for families the census and pilots leave empty (expected: Shadowrun-specific pieces such as biometric reader,
autodoc, ward anchor, bar and booth). They are made as ordinary envkit props on an interior sheet
(`docs/envkit/sheet-runbook.md`: 2K references, five-submission cap, shared ledger), land in `srn_envprop` with
rows and blueprints, and are then baked like any other. Needs the user's Meshy cap decision.

### 8. Room batches, then release B

The other 34 floorplans by category (Home, Office, Security, Retail, Industrial, Medical, Magical), one contact
sheet per batch for the user. Release B merges them.

### 9. Restyle and cohesion (release C)

The dgt04 process per family (`material`, `lamps`, `shadows`, `compile --adopt`, `unique` first where node names
repeat), so the four families share a material standard; joins and rooms re-checked; whole-set look pass and
`perf` against the stage 4 baseline.

## Files

- New: `docs/tilesets/srx02-plan.md`, `docs/tilesets/srx02/*` (census, names, merge, numbers, joins, props, rooms),
  `docs/tilesets/{udp2,tfb01,tbx78,nac01}/*` baselines, `srn_t_srx02/`, `sources/srn_t_srx02/`,
  `srn_2da/srx02_edge.2da`, `tools/tilekit/rooms.py`, `test_rooms.py`.
- Changed: `tools/tilekit/merge.py` (crosser folds), `joins.py` (adapter shape), `__main__.py`/`commands.py`
  (`rooms`), `test_merge.py`, `test_joins.py`, `test_names.py`, `srn_2da/doortypes.2da`, `hakbuilder.json`,
  `PROVENANCE.md`, `tools/ci-test-durations.json`, `tools/test-impact.json`, `docs/tilesets/tilekit-tools.md`.
- Reused as they are: `inventory.py`, `review.py`, `family_review.py`, `openings.py`, `detail.py`, `cuts.py`,
  `terrain.py`, `compiled.py`, `unique.py`, `count.py`, `perf.py`, `apply.py`, `tools/envkit/tile.py`,
  `blueprints.py`.

## Verification (each stage)

- `python -B tools/test_impact.py --changed <files> --run`; the full helper suite when `merge.py`, `joins.py` or
  `detail.py` change.
- `tilekit merge --check`, `joins --check`, `compile --check`, `tilekit walkmesh` against the baselines.
- `tools/Test-Repository.ps1 -ChangedSince main` and a rebuild of `srn_t_srx02` and any changed pack.
- Toolset by computer use: paint, rotate, undo/redo, save, reopen, read the saved area back.
- Client by computer use: no second client, 200 cap, keyholing off, fog clip 9999, a handful of targeted views;
  screenshots to the user at each look gate.

## Out of scope

Retiring the four source sets; the other interior sets unless decision 1 adds them; scripts for interactive props
(SR_NWN); the draft's 60-feature grammar (features are whatever tiles the census finds).
