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
- **Not done in this stage:** review modules and client pictures of the four sets and of the shells assembled.

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
