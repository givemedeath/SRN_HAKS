# Unified Shadowrun exterior tileset: Modern Exterior + Suburbs + Futuristic City

Revision 2 (2026-11-21): the first plan, with the review corrections and the three picks the user accepted.

## Context

The Modern Exterior (`dgt04`) upfit is done: release 2 merged in PR 188, and the CI follow-up in PR 189. The user now
wants one Shadowrun city tileset that combines three sets:

- the upfitted Modern Exterior (`srn_t_dgt04/dgt04.set`);
- D20 Suburbs UDP (`srn_t_udp1/udp1.set`);
- D20 Futuristic City SW (`srn_t_fcx01/fcx01.set`).

A builder can then paint Barrens, suburbs and a corporate core side by side in one area.

**User decisions (2026-11-21):**
- **Set form:** a new set with its own resref. The three source sets stay, so existing areas keep working.
- **Order:** merge first, with join tiles; then give Suburbs and Futuristic City the dgt04 upfit treatment.
- **Joins:** built join tiles, for the ground transitions and the road junctions.
- **Futuristic City's role:** the corporate arcology zone. It is restyled clean, lit, glass and steel, with the Star
  Wars details redrawn as generic ones.

**Accepted at the plan review (2026-11-21):**
- **Suburbs meet the city through Asphalt only.** Concrete never touches Grass, so no three-terrain join tiles are
  built. Every suburb border is a paved strip.
- **Joins follow the restyle.** A join tile draws each family's ground with that family's own texture name, so it
  takes the new look when releases B and C restyle the ground. B and C each re-check the joins.
- **Both envkit copies are kept.** The Concrete copies and the Asphalt copies both go into the new set, with palette
  names that say which ground each sits on.

## What the three sets are (measured on main, f5a9c5e8)

| | Modern Exterior `dgt04` | Suburbs `udp1` | Futuristic City `fcx01` |
|---|---|---|---|
| Tiles / groups | 575 / 69 | 798 / 117 | 239 / 38 |
| Tile models | `dgt04_`, `dgt05_`, `srt04_`, `rdt0x_`, `dgw01_` | `udp1_` | `fcx01_`, `cor01_`, `nar01_` |
| Envkit tiles (`ek_`) | 122, on Concrete | the same 122, on Asphalt | none |
| Terrains declared | 25 | 7 | 3: Cobble, Cobble2, holes |
| Terrains used but not declared | `Slums` (4 corners), `concrte` (2), `freeway` (6, beside `Freeway`) | `Forest_Clearing` (46) | none |
| Crossers | 14, incl. Street, Street_Edge_L/R, Alley 01–03 | 6, incl. Road, Driveway, Sidewalk, Parking | 3: pont, Routes, murs |
| Raised corners | 53 (Transition 15) | 0 (Transition 10) | 0 (Transition 3) |
| Primary rules | 4 | 15 | 9 |
| Ground / default | Concrete | Grass | Cobble |
| `[GRASS]` section | none | yes | yes, different values |
| EnvMap | `ttr01__ref01` | `tdc01_ref01` | `tnc01__ref01` |
| Door types keyed to the set | 117 (`DGT04`) | none | 260, 261 (`FCX01`) |
| Pack size / compiled | 82 MB, compiled | 82 MB, ASCII | 24 MB, ASCII |

**What follows from this:**
- **Raise height:** only dgt04 has raised corners, so dgt04's Transition (15) serves the whole set.
- **Model names:** every family's models have their own prefixes, so the models stay in their own packs. The new pack
  holds the set, the palette, the join tiles and nothing else. A module loads it together with the three source packs.
- **Name clash:** `Water` is in both dgt04 and udp1.
- **Undeclared terrains:** four names, in two sets (table above). `Forest_Clearing` also has three missing edge models
  (`docs/imports/mdrnee_tile-deferred-work.md`).
- **Where roads run:** dgt04's `Street` runs on all-Concrete tiles, udp1's `Road` on all-Asphalt tiles, fcx01's
  `Routes` on all-Cobble or all-Cobble2 tiles. So a road junction is the straight ground join with a road on each side.
- **fcx01's two grounds:** its own rules route Cobble↔Cobble2 through `holes`. The joins meet `Cobble` only.
- **One `[GRASS]` and one EnvMap per set:** the new set can keep only one of each.
- **Textures already shared:** `glass`, `stone`, `lab_win1`, `dgt04_chrome` and three stock textures are drawn by
  both dgt04 and fcx01. The Futuristic City already takes dgt04's restyled look on those (a release 1 decision).
- **Envkit tiles:** each envkit sheet adds its tiles to both source sets
  (`tools/envkit/sets/*.json`: `"sets": {"dgt04": "Concrete", "udp1": "Asphalt"}`; 11 sheets).
- **Who uses the sets:** SR_NWN has no production areas on these sets, only test and spike areas. This is checked
  again before release A.

## Stage 0 results (2026-11-21)

Baselines: `docs/tilesets/udp1/` and `docs/tilesets/fcx01/` each hold `inventory.json`, `textures.csv`, `walkmesh.json`
and a `review.json`. The census of all three sets is `docs/tilesets/srx01/census.json`.

**Cost to draw** (`tilekit count`, no tile over budget):

| | Tile models | Faces: median / p90 / max | Mesh nodes: median / p90 / max | Materials: median / p90 / max |
|---|---|---|---|---|
| udp1 | 677 ASCII, 122 compiled (envkit), 3 absent | 99 / 634 / 5,534 | 6 / 36 / 209 | 4 / 12 / 21 |
| fcx01 | 243 ASCII | 96 / 486 / 1,856 | 6 / 12 / 37 | 4 / 6 / 11 |

**Census findings:**
- **Terrain pairs that have tiles.** udp1: Asphalt–Grass (183 tiles), Grass–Stripmall (49), Grass–Mall_Type_1 (27),
  Grass–Mall_Type_2 (27), Forest–Grass (20), Forest–Forest_Clearing (20), Grass–Water (18). So Grass is udp1's hub:
  nothing but Grass touches Asphalt. fcx01: Cobble–holes (9) and Cobble2–holes (9) only; Cobble never touches
  Cobble2.
- **dgt04:** `Cliff` is declared and no tile uses it. `Slums` is one all-`Slums` tile. `concrte` and `freeway` are on
  the Freeway tiles.
- **Edge tables:** dgt04 144 rows, udp1 31, fcx01 14.
- **Packs the tiles draw from.** udp1 tiles draw nine textures that are only in `srn_door` and `srn_placeable`,
  among them `udp1-asph` (9.7% of the set's surface). fcx01 tiles draw five textures only in `srn_door` and three
  only in `srn_t_dgt04`. So `srx01` loads with `srn_door` and `srn_placeable` as well as the three tile packs,
  `srn_t_common` and `srn_2da`. Stage 2's model guard also covers textures.
- **fcx01 stock textures:** seven textures have no copy in the repository and come from the base game
  (`tcn01_watrstn02`, `ttr01_splotch01`, `mmc01_black`, `tcn01_marbl01`, `tcn01_marbl05`, `ttr01_leaf01`,
  `tcn01_stone20`), together under 0.3% of the surface.
- **udp1 is too large for one review grid:** 676 tiles need 22 rows and an area holds 15. Its review lays 41 chosen
  group tiles through the spec's `shared` part instead.

**Odd names, from the client** (18 views of each set, day and night, in the ignored `output/tilekit/s0-udp1` and
`output/tilekit/s0-fcx01`; made again with `tilekit review --spec docs/tilesets/<set>/review.json`):
- `holes` is open sky: a pit with clouds below the plaza level, the cloud-city void. Buildings and towers stand in
  it as columns rising out of the cloud.
- `Cobble` is the pale tiled plaza. `Cobble2` is a dark tiled deck, reached only across `holes`.
- `pont` is a bridge: a glass tube walkway across `holes`.
- `murs` is not yet seen: the block has no run of it. It is looked at in stage 1.

**Open findings:**
- **`holes` becomes the arcology void (user, 2026-11-21).** The geometry and every tower group are kept. Release C
  restyles the cloud layer as a dark atrium drop between raised decks. The names review gives it a name to match.
- **Black ground in the udp1 review rows is the layout, not a defect.** Many udp1 groups keep all their geometry in
  one tile's model and leave the group's other tiles empty (`udp1_c01_14`, `udp1_c02_14` and others name no
  texture). Laid apart in a row, the empty tiles show nothing. The stage 2 merge must keep such groups whole, and
  a review of udp1 buildings should lay whole groups.
- **udp1's ground is very dark by day** under the review lighting, darker than dgt04's Concrete beside it would be.
  This is a look item for release B, and for the release A side-by-side area.
- **fcx01 at night is nearly unlit** apart from its blue windows. Release C's lit signage and lamps address it.

## Stage 1 names (approved by the user, 2026-11-21)

The proposal is `docs/tilesets/srx01/names.json`: 35 terrains, 23 crossers, 224 groups, the 149 envkit placeable
blueprints and the door labels. Nothing in the packs has changed.

**How names work, found in the palettes:**
- A terrain or crosser has two names. The set file holds a key (16 characters at most); the palette (`.itp`) holds
  the name the Toolset shows. `names.json` gives both: `key` and `display`.
- The tile palettes are three flat lists: Features, Groups, Terrain. No palette in the repository nests further.
  So the district sits at the front of each display name ("Barrens: Tenement, Brick"), and the lists sort by it.
  Whether the Toolset shows nested tile categories is tried in the stage 3 Toolset check; until it is shown to work,
  the prefix is the categorization.
- Categories: Streets, Ground, Water, Barrens, Residential, Commercial, Corporate, Industrial, Civic, Arcology, Joins.

**Pictures** (ignored `output/tilekit/`; every group laid assembled, one view each, day):
- `s1-udp1g/sheets/groups-1.jpg` to `groups-9.jpg`: the 106 udp1 groups;
- `s1-fcx01g/sheets/groups-1.jpg` to `groups-4.jpg`: the 38 fcx01 groups;
- `s1-fcx01r/sheets/`: the fcx01 wall (`murs`, a pale stone perimeter wall) and road (`Routes`, a paved strip).

**Left for the user at the review:**
- `Wall01`, `Wall02` and `Chain_Fence2` keep numbered names: no picture of them was taken in this stage.
- The udp1 shop names (Zip, Hillman, Chicken King and the others) are kept. They are baked signs; release B decides
  whether the signs are redrawn, and the group names follow.
- `Slums` (one tile) folds into `Tenement_Brick`, subject to a Toolset paint test.
- Placeables: one new top-level category, Shadowrun City, with eleven kinds under it, in place of the split across
  Modern Exterior and Modern Interior.

**Applied after the approval (2026-11-21):**
- **Placeables:** `placeablepal.itp` has a new top-level category, Shadowrun City, with eleven kinds under it
  (palette categories 208–218, talk table rows 144–155). The 149 envkit blueprints carry their new category in the
  envkit game sets, the additions catalog and their `.utp` files, and `placeablepalstd.itp` is rebuilt with
  `envkit blueprints`. The Modern Exterior and Modern Interior categories they left are empty of envkit pieces.
- **Doors:** the ten universal doors each have a name (talk table rows 156–165); `tilekit/doorset.py` writes it into
  `genericdoors.2da`.
- **Guard:** `tools/tilekit/test_names.py` holds `names.json` against the three set files, the catalog, the talk
  table and the door table.
- **Not applied yet:** the terrain, crosser and group names. They go into `srx01.set` and its palette through the
  stage 2 merge.
- **Not checked in the Toolset yet:** that the new placeable categories and door names show. This joins the stage 3
  Toolset check.

**Client test rule (user, 2026-11-21):** every client test area sets its fog clip distance to 9999. All eight
fixtures that write an area now do.

## Stage 2 results (2026-11-21)

`python -m tools.tilekit merge --spec docs/tilesets/srx01/merge.json` writes `srn_t_srx01/srx01.set`,
`srx01palstd.itp` and `srn_2da/srx01_edge.2da`; `--check` holds them against the three sources and the lock
`docs/tilesets/srx01/merged.json`.

- **The set:** 1,612 tiles (dgt04 from 0, udp1 from 575, fcx01 from 1373), 213 groups (224 before the suburb copies of the envkit buildings were left out), 604 primary rules. The
  general block is dgt04's, the grass is udp1's. The pack `srn_t_srx01` holds only the set and its palette: the
  models stay in the three source packs.
- **Names:** the approved keys and palette names of `names.json` are in the set and the palette, each palette name
  led by its district.
- **Edge table:** twelve edge models that the source tables name are in no pack (they were missing before the
  merge). They are listed in `merge.json` under `absent` and left out.
- **Envkit:** `envkit install` re-merges and names a new group "<district or Unsorted>: <label> (<family>)".
- **Guards:** `tools/tilekit/test_merge.py`; the pack is in `hakbuilder.json` and `PROVENANCE.md`.

Toolset check (computer use, areas filled with Concrete, Grass and Plaza_Light, read back from the saved module):

| Painted | In | Result |
| --- | --- | --- |
| Tenement, Residential Block (city terrain) | Concrete area | laid, dgt04 tiles |
| Asphalt, Mall Red Block (suburb terrain) | Grass area | laid, udp1 tiles 595 and 921 |
| Void, Road (arcology terrain) | Plaza_Light area | laid, fcx01 tiles 1374 and 1584 |
| Asphalt, Mall Red Block | Concrete area | refused: no join tiles until stage 3 |
| Stuffer Shack 2x2 (city) and (suburb) | Concrete area | both lay the city copy, tiles 434 to 437 |
| Stuffer Shack 2x2 (suburb) | Grass area | refused |

Findings:

- **The Toolset cannot tell the two envkit copies apart.** A group is found by its first tile's model, so the
  "(suburb)" entry lays the city copy. Keeping both copies paintable needs the suburb copy's tile models under
  names of their own.
  **Decided (user, 2026-11-21): keep one copy.** `merged_set` leaves out a group whose first tile's model an
  earlier family's group begins with; its tiles stay in the set, so tile numbers do not move. The eleven envkit
  buildings stand on Concrete, without "(city)" in their names, and reach the suburbs through the stage 3 joins.
  The set now has 213 groups. This replaces the earlier pick to keep both copies.
- **A new area starts on Concrete**, so suburb and arcology terrain cannot be painted in a new area until the join
  tiles exist. Expected, and the reason stage 3 comes before release A.
- **Two palette entries show raw names** ("Barrens: Bridge_Collapsed", "Bridge_Collapsed_C"): to be named in
  `names.json`.
- The palette panel cuts long names off at the default width.
- Not checked yet: the Shadowrun City placeable categories and the door names in the Toolset (stage 3 check).

## Stage 3 results (2026-11-21)

`python -m tools.tilekit joins --spec docs/tilesets/srx01/joins.json` writes the join tiles; `tilekit compile`
compiles them; `tilekit merge` numbers them after the three families (1612 to 1625) and adds their border rows.
`joins --check` holds them against the tiles they are cut from (`docs/tilesets/srx01/joins-built.json`).

- **How a join is made:** each side of the boundary is its family's own plain ground tile, clipped to its side, so
  it draws that family's texture by name. A join built again after a restyle follows it. A flush concrete strip
  from the city kit's atlas lies on the boundary. No new texture.
- **Boundary shape:** it crosses a tile edge at its middle, at a right angle; a corner's ground is the quarter disc
  round it. So a painted patch has round corners.
- **Pairs:** Concrete with Asphalt (`srx01_ja...`) and Concrete with Plaza_Light (`srx01_jp...`).
- **Tiles for each pair (7):** one corner, two along an edge, two diagonal, three corners; and three road tiles on
  the edge shape: the city Street meeting the other family's road, the Street alone ending at the boundary, and the
  other road alone. The Toolset lays a road one tile edge at a time and needs the last two.
- **Roads:** the north half is the city's straight Street tile, the south half the other family's straight road
  tile. The other road's heights (the suburb kerb, 15 cm; the arcology road, sunk 25 cm) fall to the flat seam over
  2 m. The walkmesh is cut the same way, every corner shared along the cut.
- **Border:** an edge-table row for each pair, each way about (`..2_01` and `..z_01`).
- **Not built:** a T-junction, and any other crosser (fence, wall, sidewalk) across a boundary. A road cannot run
  along a boundary.
- **Guards:** `tools/tilekit/test_joins.py`, and `test_merge.py` holds the join tiles to the set.

Checks:

| Check | Where | Result |
| --- | --- | --- |
| Asphalt and Plaza_Light painted on Concrete | Toolset | laid, shapes meet |
| Mall Red Block painted on Concrete | Toolset | laid: the rules route Grass, Asphalt, join, Concrete in one click |
| Stuffer Shack 2x2 on Grass | Toolset | laid, with a ring of Concrete joins and a ring of Asphalt |
| Street, then Suburb Road, across a boundary | Toolset | laid: road end, then the through junction |
| Raise beside a join | Toolset | refused, nothing changed; a raise elsewhere works |
| Saved areas read back | `review.disagreements` | 0 in all three areas |
| Joins, road ends and both junctions | client, `docs/tilesets/srx01/review.json` | drawn, lanes meet |
| Join at the area's west, south, east and north border | client | each ground continues past the border |

Findings:

- **An envkit building takes more room in a suburb:** its Concrete pad needs a ring of joins and then a ring of
  Asphalt before Grass. A 2 by 2 building changes 6 by 6 tiles.
- **Painting Plaza_Light near Asphalt** turns the Asphalt between them to Concrete: there is no join of those two.
- **The families still look apart:** suburb asphalt is lighter than the city's street, and the arcology plaza far
  lighter. Releases B and C are for that.


Further checks (2026-11-21, on the user's go):

| Check | Where | Result |
| --- | --- | --- |
| Undo and redo of a paint across joins, several levels | Toolset | each restores the area as it was |
| Walk across a straight, a rounded and a diagonal join and both road junctions | client, six walks of 40 to 50 m | each arrived at its target |
| Door hook of a keyed door type (glass window 117, arcology gate 260) | Toolset | the door is made, but **its properties would not open** ("The selected model does not exist") |
| The same after the fix below | Toolset | properties open, with the door's picture and type; the door palette's Tileset Specific list holds the three |
| Shadowrun City placeable category and its eleven kinds | Toolset | shown, blueprints under each |

- **Fix: door types keyed to this set.** The Toolset lists a door's types by its area's tileset, and rows 117, 260
  and 261 of `doortypes.2da` are keyed to DGT04 and FCX01. Rows 266 to 268 are their copies keyed to SRX01, and the
  merge writes those into the merged set's nine door hooks (`merge.json`, `doors`). The source sets are unchanged.
  `test_merge.py` refuses a hook of a type keyed to another set.
- **Left as it is:** envkit's hook type 58, the invisible transition door, is keyed to TDS01 in every set that uses
  it (user, 2026-11-11: type 58 until further notice). Its properties were not opened here.
- **Two arcology door types share the name "Castle Door"** in the door palette (their source rows' name). To be
  named with the arcology release.
- **Bunker Hall 4x3 would not lay on Plaza_Light** in a 12-tile area: its Deck_Dark ground meets Plaza_Light only
  through the Void (the source set's own rule). Its door type (261) is remapped like the others but was not seen.
- **Still not checked:** a reopened area in the Toolset (the saved files were read instead), and the new door names
  in a placed door's Generic Appearance list: a door blueprint could not be placed by the palette helper. The names
  are held to the table and the talk table by `test_names.py`.

## Release A results (2026-11-21)

The district review area is `docs/tilesets/srx01/districts.json`: 24×14 tiles, suburb west, city in the middle, arcology
east, with the joins between them, by day and by night. It lays whole buildings (`groups` in a review block, new) and
buildings' terrains over a district's ground (a patch's `over`, new). Awaiting the user's look approval.

- **Reflective surfaces.** No change from the source sets. Compared in the client under the same settings:
  - the arcology void in `fcx01` alone and in `srx01`: the same picture;
  - a suburb house, the tennis court and the transmission tower in `udp1` alone and in `srx01`: the same picture.
  - The stage 0 pictures of the void look bluer only because they were taken before the fog rule (fog clip 9999,
    user 2026-11-21): the haze tinted the void. Nothing needed a TXI.
- **Frame rate**, dgt04 baseline method (this machine, 1600×900, 200 cap, vsync off, views held 14 s, the 6-second
  average read 10 s in). Views: suburb, city street, arcology void. Run 1 / run 2.

  | Area | Day | Night |
  |---|---|---|
  | Districts, 24×14, three packs | 180 179 179 / 184 181 181 | 184 – 177 / 186 181 181 |

  Every view holds the cap (the test is 175). The night city view of run 1 was captured late and is left out.
- **Area load**, the load screen's length in window grabs taken every 0.2–0.35 s: night area from the day area
  1.4–1.8 s in both runs. The dgt04 baseline's 32×32 Slums area took 1.25–2.1 s.
- **Packs** (built): `srn_t_srx01` 1.2 MB on top of `srn_t_dgt04` 80 MB, `srn_t_udp1` 76 MB, `srn_t_fcx01` 22 MB and
  `srn_t_common` 841 MB.
- **Names review:** closed at stage 1 (approved by the user); terrain and crosser names are frozen from here.

## Proposed name

`srx01`: pack `srn_t_srx01`, set `srx01.set`, palette `srx01palstd.itp`, edge table `srn_2da/srx01_edge.2da`.
Display name "SRN City Exterior". The user confirms the name at the names review (stage 1).

## Work order

Each stage is one pull request into a `restyle/srx01` branch. `main` gets one merge per release (A, B, C), as the
dgt04 upfit did.

### 0. Inventory and baselines

Run the existing tools on the two newcomers:
- `python -B -m tools.tilekit inventory --set udp1` and `--set fcx01` write their `inventory.json`,
  `textures.csv` and `walkmesh.json` baselines into `docs/tilesets/udp1/` and `docs/tilesets/fcx01/`;
- `tilekit count` says what each tile costs to draw.

**Census and look:**
- **Census:** terrains (declared and used), crossers, rules, groups, door hooks, door types and edge-table rows of all
  three sets. It also lists every cross-family terrain pair, for the rules in stage 2.
- **Odd names:** what `holes`, `pont` and `murs` are, from in-game pictures.
- **Review modules:** a `tilekit review` module of udp1 and one of fcx01, with a handful of targeted day and night
  views each. They follow the client rules: frame-rate cap, keyholing off, camera allowed to look up.

This document records the census results and the proposed terrain renames as they come in.

### 1. Names and Toolset categories (user, 2026-11-21)

This stage comes before the merge tool's final output, because the merge reads its name map.

The new set has no areas yet. So unlike dgt04's stratum 4, where descriptive names went into the palette alone, the
new names go into the set file itself as well as the palette. **Terrain and crosser names are frozen at release A:**
once areas exist on `srx01`, a rename breaks them. The names review is a gate for release A.

**What gets renamed, from in-game pictures:**
- **Terrains:** the numbered and inherited names: `Highrise_01`–`10`, `Slums1`–`3`, `Mall_Type_1/2`, `Cobble`,
  `Cobble2`, `holes`, and so on. Names follow district and role (Barrens, Residential, Commercial, Corporate,
  Industrial, Civic, Arcology). They fit the set's 16-character resref limit (`tools/tilekit/terrain.py` checks it).
- **Undeclared terrains:** each gets an explicit entry. `concrte` and `freeway` fold into `Concrete` and `Freeway`.
  `Slums` and `Forest_Clearing` are either declared or folded into a neighbour, decided from the pictures and a
  Toolset paint test.
- **The `Water` clash:** udp1's `Water` becomes `Pond`, unless the pictures show the two waters match.
- **Crossers:** `Wall01`/`Wall02`, `Alley_01`–`03`, `Chain_Fence2`, `pont`, `Routes`, `murs`, `Fence_Wood`.
- **Tile groups:** every palette group of the three sets, each with a descriptive display name. Duplicate or
  misleading names are reconciled, such as the many "Highrise" groups and the French fcx01 names. Each envkit
  building is in the palette once, on Concrete (user, 2026-11-21; see the stage 2 results).
- **Edge table:** the merged edge table names follow the new terrain names.

**How the tile palette is recategorized:**
- the tile palette (`srx01palstd.itp`) is laid out as a category tree by district, then by kind: Ground and roads,
  Buildings, Joins, Water, Landmarks;
- the envkit buildings sit under their districts, not in one flat list.

**Placeable blueprints:**
- the 149 envkit blueprints in `srn_placeable` are re-sorted on the `placeablepal.itp` category tree, where a city
  category fits better than the current one: Street furniture, Signs and screens, Lights, Barriers and fences,
  Vehicles, Rubble and debris, Corporate, Barrens;
- `tools/envkit/blueprints.py` (`palette`, `blueprint(... category)`) rebuilds `placeablepalstd.itp`;
- new category names take custom TLK rows in `srn_tlk`.

**Door types:**
- the Toolset door-type labels of the universal door set and the tiles' door hooks get names that say what each is:
  gate, roller shutter, glass entrance and so on;
- `doortypes.2da` rows 117, 260 and 261 are keyed to `DGT04` and `FCX01`. A Toolset test on `srx01` shows whether
  the five tiles that use them still offer those doors. If not, `srx01` rows are added.

**Spec and guards:**
- **Spec:** `docs/tilesets/srx01/names.json` holds an old→new map for terrains, crossers, groups and categories, with
  a reason for each rename. The user approves it at a picture review.
- **Guards** (`tools/tilekit/test_merge.py` and `tools/envkit/test_blueprints`):
  - every name is unique within its kind and fits its length limit;
  - every source name, declared or only used, maps to exactly one new name;
  - no blueprint is lost or doubled across categories;
  - every category a blueprint names exists in the palette tree;
  - the source sets keep their own names, so existing areas are untouched.

### 2. The merge tool: `tilekit merge` (new `tools/tilekit/merge.py`)

`srx01.set`, its palette and its edge table are merge output only. Nothing else writes them.

**Spec:** `docs/tilesets/srx01/merge.json` names, for each family:
- its source set and group prefix;
- terrain and crosser names, taken from `names.json` (stage 1);
- the envkit tiles: dgt04's Concrete copies and udp1's Asphalt copies, both kept.

**What it writes:**
- the `[TILE]` sections of all three sets, in a fixed family order, then the join tiles;
- `[GROUPS]` with their tile numbers remapped, and palette groups under the stage 1 category tree;
- `GENERAL` from dgt04: Transition 15, EnvMap `ttr01__ref01`, border, default and floor `Concrete`;
- `[GRASS]` from udp1, so the lawns keep their grass. fcx01's values are dropped; stage 0 checks whether any fcx01
  tile shows grass at all;
- the merged palette (`.itp`) and the merged edge table, including border rows for the join pairs.

**Rules:**
- every set's own primary rules, with the names mapped;
- the rules for the join pairs: Concrete↔Asphalt and Concrete↔Cobble;
- a rule for every other cross-family terrain pair, generated from the census, that routes through the grounds. For
  example a suburb building beside a city building changes to Grass, then Asphalt, then Concrete;
- rules that keep raised Concrete away from the joins, which are built at height 0 only.

**Reuse:**
- `tools/tilekit/inventory.py`: `read_set`, `sections`, `edge_models`, `_other_sets`;
- `tools/tilekit/terrain.py`: `renamed`, `_sections`, `_counted`, for writing sets;
- `tools/envkit/tile.py`: `prepare`, how a group goes into a set and its `.itp`.

**Guards** (a new `tools/tilekit/test_merge.py`):
- every source tile appears exactly once, with its model, walkmesh, lights, doors and path node unchanged and its
  corners renamed only as the spec says;
- every terrain and crosser a tile names is declared;
- every cross-family terrain pair has a rule, and every corner pair that can reach the border has an edge row;
- group tile numbers point at tiles of the right model;
- every model the set and the edge table name exists in `srn_t_srx01` or one of the three source packs;
- the merge is deterministic, so a rerun is byte-identical;
- a source set changed after the merge makes `srx01.set` stale. It is pinned by hash, like
  `sources/compiled.json`.

**Registration and envkit:**
- the new test module goes into `tools/ci-test-durations.json`, then the catalog is refreshed
  (`python -B tools/test_impact.py --write-catalog tools/test-impact.json`);
- `hakbuilder.json` gets the `srn_t_srx01` pack;
- envkit keeps adding tiles to the two source sets only. `tools/envkit/additions.py` then reruns the merge, which
  carries the new tiles into `srx01` and renews the pin. Envkit sheets do not name `srx01`.

### 3. Join tiles, built in code (new `tools/tilekit/joins.py`, like `doorset.py`)

**Ground transitions:** Concrete↔Asphalt and Concrete↔Cobble. There is no Concrete↔Grass join.
- Each pair needs the four corner shapes: one corner, two corners along an edge, two diagonal corners, three corners.
  That is 8 models plus a second variant where they repeat.
- **Look:** a kerb or step line with the dgt04 master materials on the Concrete side. The other side draws the
  family's own ground texture by its texture name, so it follows that family's restyle.
- **Walkmesh:** flat, with each half's surface material.
- **Minimaps:** drawn by `tools/envkit/tile.py` `minimaps`.
- **Border rows:** one edge-table row and border model for each join corner pair.

**Road junctions:** variants of the two-corners-along-an-edge shape.
- `Street` on the Concrete edge and `Road` on the Asphalt edge;
- `Street` on the Concrete edge and `Routes` on the Cobble edge;
- a T-junction for each, if the census shows the Toolset needs one.

**Shipping and checks:**
- **Compiled:** the joins ship compiled from the start, ASCII in `sources/srn_t_srx01/`, through
  `tools/tilekit/compiled.py` and `tilekit compile`. That pack joins `compiled.PACKS`/`PACKS` in `test_compiled.py`.
- **Toolset check:** by computer use, following `nwn-toolset-by-computer-use`. Paint each boundary, rotate, undo and
  redo, then reopen the area. Every pair must paint without a missing-tile hole. This also covers a suburb building
  painted beside a city building, raised Concrete beside a join, a join at the area border, and the keyed doors.
- **Client check:** a short review of each join type by day and night, with the user's look approval.

### 4. Release A

The unified set ships with the source looks, plus the joins:
- `srn_t_srx01` is built;
- `Test-Repository` and the affected pack validation pass;
- the names review is closed;
- a review area paints all three districts side by side, and the user approves it. This look check includes the
  reflective surfaces of udp1 and fcx01 under dgt04's EnvMap, compared with their stage 0 pictures;
- loads and frame rate are checked against the dgt04 baseline method (`docs/tilesets/dgt04-release2-plan.md`,
  stage 0), in an area that loads all three packs.

### 5. Release B: Suburbs upfit (udp1), batch by batch

This follows the dgt04 process (`docs/tilesets/dgt04-upfit-plan.md`):
- the material standard reuses dgt04's master materials, with a pilot block approved first;
- `lamps` and `shadows` fixes;
- `detail` kit pieces;
- `compile --adopt srn_t_udp1`;
- one day and night contact sheet per family batch: houses, malls, strip malls, roads and ground, forest.

**Constraints:**
- walkmeshes are held against the stage 0 baseline;
- restyles go in place in `srn_t_udp1`, so the old Suburbs set takes the new look too;
- redraws use local Qwen;
- no helper edits between a job and its collect.

**Join re-check:** after the roads and ground batch, the Concrete↔Asphalt joins and junctions are viewed again by day
and night. If the kerb line no longer fits the new Asphalt, `joins.py` is adjusted and the joins rebuilt.

### 6. Release C: Futuristic City as the corporate arcology (fcx01)

The same process on fcx01:
- clean corporate materials: glass, brushed steel, lit signage that glows at night;
- the Star Wars-specific textures redrawn with local Qwen as generic 2070s ones, with no brand names: monuments,
  `bespin_*`, `imp_modules_*`, `ctown_*` signs;
- lamps moved to main lights;
- `compile --adopt srn_t_fcx01`.

The four textures it shares with dgt04 keep dgt04's look.

**Join re-check:** the Concrete↔Cobble joins and junctions, as in release B.

### 7. Cohesion

- **Look pass:** the user's whole-city look pass across the three districts and the joins, by day and night.
- **Performance:** against the baseline.
- **Old sets:** whether to retire them is the user's call later. This plan keeps them.

## Verification (each stage)

- **Tests:** the focused tests chosen by `python -B tools/test_impact.py --changed <files> --run`. The full helper
  suite when shared helpers change.
- **Walkmeshes:** `tilekit walkmesh` against the baselines, after every model change.
- **Packs:** `tools/Test-Repository.ps1 -ChangedSince main` and a rebuild of the affected packs.
- **Toolset:** painting checks for the merge and the joins.
- **Client:** review modules in the client, driven by computer use. Check for a running nwmain first, cap the frame
  rate at 200, turn keyholing off, and take a handful of targeted views. Screenshots go to the user for look gates.

## Out of scope / on hold

- Suburbs office interiors (`udp2`).
- More dgt04 crowns and the invented-brand shop signs, which stay on hold.
- Retiring the source sets.
- Three-terrain join tiles (Concrete, Asphalt and Grass on one tile). They come back only if the paved suburb
  border proves too limiting.
