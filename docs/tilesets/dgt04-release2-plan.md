# Modern Exterior (`dgt04`) upfit, release 2 — plan

Status: revision 2, 2026-11-19. The scope was decided by the user, and the baseline method was revised after a
review with the user. Nothing has been built yet. Release 1 (materials, lamps, shadows,
edge tiles, strata 4 and 5; `docs/tilesets/dgt04-upfit-plan.md`) is on `main` (PR 181, 816c5aa6). Release 2 works on
`restyle/dgt04-r2`.

## Decisions (user, 2026-11-19)

| Topic | Decision |
|---|---|
| Order | Release 1 (PR 181) merges to `main` first. Release 2 is a fresh restyle branch with a PR per stage, then one merge to `main`. |
| Tracks | Detail kit, selective remeshing, and doors. Placeables are out. |
| Geometry source | Decided per track after the pilot: Meshy for complex pieces and local Blender for simple ones (envkit's split) are the candidates. |
| Pilot | The Slums (Barrens), then the other families one batch each, with a look gate per batch as in release 1. |
| Face budget | Not set in advance. A frame-rate and load-time baseline is taken first, and the budget comes from a pilot tile measured against it. |
| Remeshing | May change the silhouette above ground: roof lines, parapets and upper massing. The walkable footprint and the walkmesh stay exactly as they are. |
| Doors | Inventory first: the 113 door models in `srn_door` listed by type, with pictures. The user picks the set. |
| Roof clutter | Cover for rooftop battles (user, 2026-11-19): roof clutter blocks movement and line of sight. Its footprint is raised out of the walkable roof's walkmesh to the piece's top, as a walled block of Obscuring faces. Street level stays fixed. |
| Signage | By district: Shadowrun megacorps' names and logos on corporate towers; invented local brands in the Barrens and on shops. This replaces release 1's no-brands rule for new signs only; release 1's generic signs stay as they are. |

## What the tiles are today (measured 2026-11-19)

| Fact | Value |
|---|---|
| ASCII models drawn by `dgt04` | 481 (set tiles and edge tiles) |
| Faces per model | median 255, 10th percentile 52, 90th percentile 538, largest 970 |
| Slums 1–3 | 104 tiles; median 367–429 faces |
| Highrises 01–09 | 61 tiles; median 213–596 faces |
| Concrete (streets, ground) | 269 tiles; median 40 faces |
| Envkit buildings beside them | compiled, up to about 100,000 faces per model |
| Door models in `srn_door` | 113 |

## Constraints

Release 1's constraints hold, except that original models are now edited:

- **Walkmesh:** no change, except under blocking roof clutter. Every other `.wok` and `aabb` node still hashes as
  `docs/tilesets/dgt04/walkmesh.json` records.
  - A kit piece marked `blocks` stands on a walkable roof, more than 2.5 m above the tile's root.
  - Its footprint (the piece's convex hull from above) is cut out of that roof and raised to the piece's top, with
    walls down to the roof. All of it is Obscuring (surfacemat 2), as envkit builds its building masses.
  - Client check, 2026-11-19, two test boxes on tile 98 (`dgt04_e10_01`, roof at 20 m):
    - the player cannot stand inside a box, and walks around it;
    - sight between two objects across a box is blocked, while across clear roof and across the street it is clear.
    - A flat Nonwalk patch, tried first, stopped walking but not sight: in NWN the walkmesh's height blocks a line of
      sight.
    - `LineOfSightVector` reported blocked even across clear street, so checks use `LineOfSightObject`.
  - The cut may not reach the cell's side: a neighbour's walkmesh still meets it.
  - `apply` replaces a walkmesh only as the overlay's `walk-cuts.json` records it, then writes the new hashes, with
    the number of cuts, into the baseline.
- **Set file:** no tile number, terrain, crosser or group moves in `dgt04.set`. New tiles, if any, are appended.
- **Door hooks and lamps:** door hooks, tile lamps (`ml1`/`ml2`) and their positions are kept.
- **Silhouette:** may change only above head height, about 2.5 m. Nothing that does not block is added between
  0.25 and 2.5 m above any walkable face, whether street or roof. The walkmesh is unchanged there, so a player would
  walk through it. Many buildings have walkable roofs: 59 of the 105 Slums tiles.
- **Neighbours:** kit pieces stay inside the tile's 10 m cell, so neighbours never overlap. Edges that meet a neighbour
  keep their profile, so a detailed tile still joins an undetailed one.
- **Textures:** a kit piece draws release 1's materials or a shared kit atlas, one material file plus its DDS maps. Signs follow the
  signage rule above.
- **Copied terrains:** the copies (`Highrise_08`, `Highrise_09`) are their own models. Each copy gets the kit that
  suits its district: residential clutter, or boarded and stripped.
- **Acceptance:** the Toolset and the game client, day and night, plus the performance check against the baseline.
  Preview renders accept nothing.

## Work order

### 0 — Merge and baseline

- PR 181 merged to `main` (816c5aa6); `restyle/dgt04-r2` branched from it (done 2026-11-19).
- Take the performance baseline on two areas in the review module:
  - the review block;
  - a generated 32×32 area, mostly Slums. The pilot is measured on this same area.
- Measure:
  - frame rate standing at three fixed views, by day and by night;
  - area load time;
  - pack sizes;
  - faces, mesh nodes and materials per tile.
- Client settings for the measurement, in the review client's own `settings.tml` only (your own settings are not
  touched):
  - frame counter on (`graphics.stats.enabled`, "FPS Stats Display"), read from the window grabs;
  - vsync off and frame limiter off. Today vsync is "adaptive" at 60 Hz, which would cap a cheap tile and a heavy
    one at the same 60;
  - the fixed 1600×900 window.
- Load time is timed by the launcher, which polls the client log every few milliseconds for the area-entry line.
  The log itself has whole seconds only, and the review block loads in about one second.
- The method is confirmed in a short probe first.
- The numbers hold for this machine at 1600×900 only, and are recorded with that note.
- Done when the numbers are recorded here and repeat within a few percent on a second run.

#### Baseline, taken 2026-11-19

This machine only, 1600×900 window. Tiles and packs as merged in PR 181. Two runs, each holding every view for 14 s
and reading the client's 6-second average 10 s in.

Lessons from the probe:

- With no frame limit at all, the client renders at 200–440 fps. That pinned the graphics card and hung the PC
  during one run, so every limit is now capped at 200 fps: foreground, background and non-interactive.
- At the default background limit of 10 fps, readings collapse whenever the window loses focus.
- The client reaches about 180 fps under its 200 cap.

**Frame rate**: 6-second average, three views each, run 1 / run 2.

| Area | Day | Night |
|---|---|---|
| Review block, 15×15 | 181 180 182 / 181 180 181 | 165 163 178 / 182 182 181 |
| Slums, 32×32 | 178 174 177 / 178 175 177 | 174 175 170 / 177 179 181 |

- Every view holds the cap. The repeat run agrees within 2%, except the block by night in run 1, which was up to 10% lower.
- Headroom above the cap, from the uncapped probe's 1-second readings:
  - review block: about 310–440 fps;
  - Slums area by day: about 220–270 fps;
  - Slums area by night: about 280–290 fps.
- **Budget test:** a pilot tile passes when the Slums views still hold the cap (175 fps or more at a 200 cap). An
  uncapped spot check of the same views then shows the remaining headroom.

**Area load**: the load screen's length in the window grabs, ±0.1 s. Three capped runs, plus the probe.

| Load | Seconds |
|---|---|
| Review block, night (from the block by day) | 0.9–1.2 |
| Slums 32×32, day (from the block by night) | 1.25–1.45 |
| Slums 32×32, night (from the Slums area by day) | 1.5–2.1 |

Loads vary by up to 20% from run to run. A pilot is compared on the mean of three runs.

**Packs** (built): `srn_t_dgt04` 43 MB, `srn_t_udp1` 79 MB, `srn_t_common` 841 MB, `srn_door` 29 MB.

**Per tile model**: the 445 ASCII models the set draws. Mesh nodes count only those rendered; materials are distinct
material or bitmap names.

| Models | Faces (median / p90 / max) | Mesh nodes | Materials |
|---|---|---|---|
| All | 263 / 552 / 970 | 23 / 111 / 222 | 7 / 10 / 16 |
| With a Slums corner (105) | 391 / 585 / 790 | 87 / 138 / 222 | 8 / 11 / 15 |
| With a Highrise corner (61) | 298 / 512 / 880 | 66 / 111 / 138 | 7 / 10 / 12 |

Slums tiles already average 87 mesh nodes. Kit pieces are therefore merged per material, and the budget counts nodes.

The measurement script becomes a `tilekit` command in stage 1. Until then the run's records are in
`output/tilekit/perf/` (`base5`, `base6`).

### 1 — Tooling

Built 2026-11-19 (`tools/tilekit/geometry.py`, `detail.py`, `cuts.py`, `remesh.py`, `count.py`):

- `tilekit count --tileset dgt04 [--overlay] [--faces N --nodes N --materials N]` lists each tile's faces, rendered
  mesh nodes and materials, and exits 1 when any tile is over the budget.
- `tilekit detail --spec <placements.json> --kit <folder> --out <overlay>` adds kit pieces. The spec is
  `{tileset, tiles: {model: [{piece, at, turn, scale, blocks}]}}`.
  - Pieces are baked into tile coordinates and merged into one node per look.
  - A run is repeatable: earlier pieces are replaced, and a cut is always made from the pack's walkmesh.
- `tilekit remesh --tileset dgt04 --tiles a,b --source <folder> --out <overlay>` replaces a tile's rendered meshes.
  It refuses a rebuild that:
  - reaches past the original's own overhang;
  - changes massing between 0.25 and 2.5 m;
  - stands where a player walks;
  - drops a floor over a walkable face;
  - changes the profile on the cell's sides.
- Every Slums tile passes `remesh` when rebuilt as itself, so the checks raise no false refusals on today's tiles.

As planned:

- `tilekit detail`:
  - adds kit pieces to a tile model as mesh nodes under the tile's root, from a placement spec per tile (piece, position,
    turn, scale);
  - refuses a piece that leaves the cell, enters the walkable footprint below 2.5 m, or changes the walkmesh;
  - writes into a review overlay, as `lamps` and `shadows` do, with `models-from.json`.
- `tilekit remesh`:
  - replaces a tile's visible meshes with rebuilt ones;
  - keeps every `aabb` node, door hook and lamp;
  - checks the silhouette rule;
  - writes into the same kind of overlay.
- A count per tile of faces, mesh nodes and materials, checked against the budget once it is set. In this engine
  separate nodes and materials (draw calls) may cost more than faces, so the budget covers all three.
- The kit-piece library: models, their materials, and a contact sheet. Kit pieces share one atlas, and pieces on a
  tile are merged into as few nodes as their materials allow. The library's source is settled in the pilot (Meshy
  or Blender, piece by piece).
- Alongside this stage: the door inventory (stage 5's first step). It is read-only and depends on nothing else.

### 2 — Slums pilot

- About six Slums tiles covering corner, side, middle and the three looks (brick, shopfronts, timber).
- A first kit of pieces:
  - air-conditioning units;
  - pipes and conduit;
  - fire escapes;
  - satellite dishes and antennae;
  - boarded and barred windows;
  - invented-brand shop signs;
  - roof clutter.
- Remesh one or two of the plainest tiles to try the silhouette rule.
- Blocking roof clutter checked in the client: a creature cannot walk through it, and it blocks line of sight across a
  roof.
- Measure frame rate and load time against the baseline, and set the face budget from that.
- Look gate: you approve the pilot, the kit, the budget, and the geometry source for each piece type.

#### Pilot result (approved by the user, 2026-11-19)

- **Tiles:** `e09_18`, `e09_08`, `e09_02` (side) and `e11_01`, `e11_03`, `e11_04` (corner); placements in
  `docs/tilesets/dgt04/detail-pilot.json`, proposed by `tilekit/placer.py` and checked by `detail`.
- **Kit:** AC units, downpipes, fire escapes (a stairless top platform under the cornice), boards, bars, a junction
  box, and roof clutter that is cover (HVAC, tank, vent, dish, antenna), on one 2048 atlas from the tiling masters.
- **Geometry source:** every piece is built in code (`tilekit/kit.py`); none needed Meshy. Effect sprite sheets are
  drawn with the local Qwen model and packed by `effects.sheet` / `effects.sparse`.
- **Effects:** electric arcs at the junction box, drips under fire escapes and AC units, smoke from some roof vents.
  Emitters run at a steady rate; a tile never plays a birth rate keyed in its animations, so arcs and drips are
  made random by sparse sheets (mostly empty frames): an arc about every 8 s, a drop about every 3 s.
- **Guards added:** a wall piece may not run into a tile's own fixtures (lamps, its own AC units, cornices); the
  placer skips fitted windows and needs two clear storeys for a fire escape.
- **Budget (set from the pilot):** per tile up to about 2,700 added faces, 2 added mesh nodes, 1 added material and
  4 emitters. Every pilot view held 177–180 fps at a 200 cap (the test is 175). Frame rate with the effects in, and
  load times, are still to be measured on the first batch.
- **Not done in the pilot, carried into stage 3:** invented-brand shop signs; the remesh trial of a plain tile.

### 3 — Families, one batch each

1. Slums 1–3 (104 tiles).
2. Corporate highrises 01–03 and 05–07: rooftop plant, antennae, ledges and megacorp signage.
3. The copies `Highrise_08` (residential) and `Highrise_09` (derelict).
4. `Highrise_04` (ruin), Apartments, Warehouses, Police, Hospital and Lab.
5. Streets and ground, the Concrete tiles: kerbs, drains, bollards and street furniture baked in. Only if the budget
   allows it at that tile count.

Each batch ends with a day-and-night contact sheet and a look gate. Each lands as one PR into `restyle/dgt04-r2`.

#### Batch 1 result: Slums (approved by the user, 2026-11-20)

- **Tiles:** all 105 Slums models (`dgt04_*` and the `dgt05_s*` copies), placements in
  `docs/tilesets/dgt04/detail-slums.json`, proposed by `placer.py`; the six pilot tiles keep their approved pieces.
  1,105 pieces, 178 effects, 25 junction boxes, 55 roofs with blocking clutter cut into the walkmesh; the largest
  addition is under 1,800 faces, inside the budget.
- **Placer rules added in the batch:** no wall pieces on a cell-side facade that meets the next building (the set
  file's corners say which sides face a street); a downpipe keeps out of a column with a street-level door or window
  (one ran down into a doorway on `e09_19`), taking the facade's other end or none. A door counts whole, set back
  up to 2.5 m (`e09_19`'s black opening stands 2 m behind its frame, which the first version of the rule missed).
- **Detail starts from the copy before an apply:** `detail` refuses a pack copy that already has kit pieces; after
  batch 1 was applied, proposing from the packs cut the cut roofs again and refused their clutter tile by tile.
- **Textures:** the motel sign (`motel2`) reads COFFINS, its letters set by script on the release 1 sign. The wide
  shop window `win2` / `win2_g` is drawn anew to its face's shape (5 × 2.2 m, UVs over the whole picture), with the
  local Qwen model on a scripted layout: frame, two mullions, three panes of blinds; the release 1 picture had its
  square layout stretched across the glass. Records in `output/tilekit/redrawn` (`tilekit-made-by-hand`).
- **Frame rate:** at a 200 cap the Slums views held 173–180 fps in the steadiest run; one run fell to 129–172 with
  the review block falling too, which has no detail (another load on the PC). **Loads** from the overlay's loose
  files were 1.7–5.3 s against the packed baseline's 0.9–2.1 s; accepted by the user as the cost of loose ASCII
  files, which compiled, packed models should not have.
- **Applied:** `tilekit apply` moved the overlay into `srn_t_common` (models) and `srn_t_dgt04` (the kit's atlas
  and the effects' pictures, recorded by `detail` in `kit-files.json`).

#### Batch 2: corporate highrises (look decision deferred to the final review, user 2026-11-20)

- **Placements:** `docs/tilesets/dgt04/detail-highrise.json`, 42 tiles of Highrise 1, 2, 3, 5, 6 and 7, proposed by
  `placer.propose_corporate`: steel ledges on about half the tower walls, a canopy and a security camera at each
  street door, roof masts with red warning lights, plant and dishes. At most 440 added faces a tile, no effects.
- **Dropped:** megacorp signage (user, 2026-11-20).
- **Review:** whole towers laid by the set's rules, each side from the street and a view looking up at the top; the
  review camera may now look up (pitch 150, distance 200). The pieces read faintly: the masts barely show over the
  parapets. Choices at the final review: approve as it is, or make it stronger (masts at the roof edge, brighter
  lights, heavier podium ledges).
- **Not applied:** nothing of batch 2 is in the packs until that decision.

#### Batch 3 result: Residential Block and Derelict Tower (approved by the user, 2026-11-20)

- **Placements:** `docs/tilesets/dgt04/detail-batch3.json`, the 12 tiles of Highrise 8 and 9. Their windows are
  painted into `hr08_wall` and `hr09_build`; `placer.grid_windows` finds them from the texture's window grid.
  Residential look: air conditioners under about half the windows, downpipes and roof plant; no fire escapes, bars
  or boards. Derelict look: boards over about half the windows, no air conditioners. The derelict tower stands in
  the middle of lower plaza blocks and is dressed from its first window row (13 m) up.
- **Boards fixed:** the kit's boards faced the wall and were culled, so batch 1's boards never showed. The kit is
  fixed, a test checks every piece's front, and batch 1 was detailed again from its pre-apply copies and applied
  with batch 3; all 97 boards in the packs face the street.
- **Glass:** `window_tex07`, `09`, `23` and `24` had kept their black openings as if doors were hooked up there, but
  every use is a window 0.8 m or more above the ground. They are redrawn glazed (`"glazed": true` in the redraw
  list); `redraw` now refuses a window texture over half pure black that does not say `glazed` or
  `"opening": "door"`. The corporate glass was too clean for the Slums (user), so 15 Slums tiles take Barrens copies
  `sl_win07/23/24` and the three Highrise 9 tiles a broken `hr09_win07` (`dgt04/retexture-glass.json`). Real
  doorways (`dgt04_black`) stay black.
- **Applied:** to `srn_t_common` and `srn_t_dgt04`, 117 models, both packs built.

#### Batch 4 result: ruin, Apartments, Warehouses, Police, Hospital and Lab (approved by the user and applied, 2026-11-20)

- **Placements:** `docs/tilesets/dgt04/detail-batch4.json`, 73 tiles. Each family has a look: ruin (burn barrels
  smoking on the upper floors, no roof plant), residential, industrial, secure (bars on every lowest window, a camera
  by each street door), civic (a canopy and a lit red-cross sign at each entrance), and lab (watched walls: a large
  camera at each end and a hazard panel). Three roofs (`dgt05_i07_11`, `i07_13`, `rdt02_a05_51`) run 2,828–3,054
  added faces, over the 2,700 budget, since the kit rework.
- **Not applied:** the batch waits for its look gate. The camera tiles need `AnimLoop1` set in `dgt04.set` when it
  is applied, and areas built before that need `Tile_AnimLoop1` on for those tiles.

- **Review fixes (user, 2026-11-20):**
  - A kit AC unit sat inside the tile's own AC on `rdt02_a01_01`. Two guards missed it: the placer's fitted-window
    check and `detail`'s fixture guard only saw what sticks out past the cell's side, and only at mesh corners. Both
    now also count what the tile draws more than 0.3 m in front of the wall, sampled across faces. Fire escapes,
    downpipes, drains and manholes, which run past trim or lie on the ground, keep the old check.
  - The ruin's burn barrels hung in the air from the street, because its upper floors are drawn from above only.
    Barrels now go only where a ceiling is drawn under the floor (`placer._ceiling`), which leaves 2 barrels on one tile.
  - A hazard plate was on a Lab's glass. Plates now mount on solid wall the way cameras do (`SIGN_REACH`).
  - Cameras were too frequent on the Lab: one at each end of every wall without a door put two a metre apart where
    tiles met, and four on a corner tile. It is now one watch camera per tile.
  - Batch 2 (not applied): 2 canopies and 6 ledges that ran into the tiles' own wall lights and boxes were taken out.

#### Kit rework (approved by the user, 2026-11-20)

- **Meshes:** bevelled boxes, smooth pipes and cylinders (shared corners), mitred tubes, and one picture projection
  for each quad and each cylinder cap. Every piece was remade with real detail. AC units are window units on the
  sill, about 62% of the window's width. Other pieces: clamped downpipes, grated fire escapes with pickets, nailed
  planks, welded grilles, louvred roof plant with fan guards, a hooped tank with a lid and ladder, aerials, and a
  burning drum. Offline renders in `output/tilekit/prop-renders`.
- **Sweeping cameras:** the head is its own node, swept ±35° over 24 s in a free `animloop`. The client animates only
  tile geometry under the animation dummy `<tile>a` (nwn.wiki, Animations), and `tiledefault` only resets a tile. The
  first two attempts, with the keys in `tiledefault` and the head under the root, stayed still. Cameras mount only on
  flush, solid wall: no glass and no recessed window behind them.
- **Walkmesh mend:** the round footprints of the new roof pieces made the mend split the same sliver faces back and
  forth forever. Footprints are now at most eight-sided with no side under 5 cm, sliver splits are skipped, and the
  mend stops after `MENDS` splits.
- **Re-applied:** batches 1 and 3. The kit was taken out of the pack copies and each tile's pre-apply walkmesh put
  back; only the later glass bitmaps differ from the pre-apply copies. Then both batches were detailed and applied
  again with the new kit.

#### Batch 5 result: Concrete streets (approved by the user and applied, 2026-11-20)

- **Scope (user, 2026-11-20):** the 147 uncompiled Concrete tiles. The other 122 are compiled envkit tiles (`ek_*`),
  left as they are. Flat pieces everywhere, plus a few pieces of street furniture cut out of the street's walkmesh;
  steam off some manholes.
- **Kit:** a kerb drain (a grating in the gutter and an inlet in the kerb's face), a manhole cover, a steel bollard,
  a fire hydrant and a litter bin, built in code like the rest.
- **Placer (`placer.propose_street`):** kerbs are found in the walkmesh, as an edge along x or y with the sidewalk at
  its height on one side and the road 0.1–0.35 m lower on the other. Most kerbs are 0.2 m. A tile gets each piece at
  most once, each on its own share of the tiles (`ONE_IN`):

  | Piece | Share of tiles | Where |
  |---|---|---|
  | Drain | 1 in 3 | in the gutter of a kerb |
  | Manhole | 1 in 4 of those with none of their own | in the road, clear of the kerbs |
  | Bollards | 1 in 8 | a row of three, 1.5 m apart, 0.45 m behind the kerb |
  | Hydrant | 1 in 10 | on the sidewalk behind a kerb |
  | Litter bin | 1 in 8 | on the sidewalk behind a kerb |
  | Steam | 1 in 4 of those with a manhole | off the manhole |

  The first proposal was far too dense: a drain every 6 m along every kerb, and bollards, hydrants and bins behind
  most kerbs. The user had all of them thinned (2026-11-20).

  Every piece goes only where the tile draws nothing above the ground there, such as a lamp post, a traffic light or
  its own manhole. Furniture also needs walkable sidewalk all round it and stays 0.8 m in from the cell's side.
- **Obstacles (`detail`, `"obstacle": true`):** a piece of street furniture stands on the street. Its footprint is
  cut out of the street's walkmesh flat, as NonWalk (surfacemat 7): players can't walk through it but can see past
  it. A roof's cover pieces stay walled Obscuring blocks.
- **Placed:** 36 tiles in `docs/tilesets/dgt04/detail-streets.json`: 12 drains, 20 manholes, 5 rows of bollards
  (15 bollards), 5 hydrants, 3 litter bins and 5 steam emitters.

  The review overlay is `output/tilekit/b5-ov`. Client views are in `output/tilekit/b5-review2`: a block of 12 street
  tiles seen from above from two sides, a bollard row by day and steam by night.

### 4 — Selective remeshing

- A candidate list from the review captures: the tiles whose shape reads worst once they are detailed.
- The list comes to you with pictures and you pick.
- Remeshed under the silhouette rule, in the same batches, or as one batch after them.

#### Candidates (2026-11-20)

- **Ranking:** every building tile's own geometry (kit pieces left out) by faces per m² above head height, the share of
  that area on box planes, and the number of roof levels.
- **Result:** the corporate towers are by far the plainest, at 0.16–0.28 faces/m² against 0.6–0.8 for the Slums. In
  order:
  1. Highrise_07
  2. Highrise_02 (and its copy 09)
  3. Highrise_01
  4. Highrise_05 (and its copy 08)
  5. Highrise_06
  6. Highrise_03
- **Sheet:** `output/tilekit/remesh-candidates/towers.jpg`. The ranking data and script are in the same folder.
- **User's pick:** a trial on Highrise_07, made as a new terrain so the original stays, with a crown and parapet: no
  setbacks.

#### Highrise_07 trial: a crowned copy

- **The copy:** `Highrise_10`, "Walled Compound, Glass, Crowned".
  - Tiles 568–574 (`srt04_c01_01`–`c07_01`), plus the edge tile `srt04_c08_01`.
  - Spec: `docs/tilesets/dgt04/terrains-crowned.json`.
- **The crown** (`tilekit crown`) is drawn from the set file's corners alone, so every tile of the terrain draws it
  alike:
  - a parapet, coping and cornice on each facade (a side whose two corners are the street's);
  - a 6 m screen 1 m back from the facade, with posts and a lit band along its top;
  - the parapet's and the screen's turn at an inner corner.
- **`remesh --add --joins <terrain>`:**
  - `--add` keeps the tile's own meshes and draws the crown as well. Replacing them lost the lit windows: they hang
    from the animated `<tile>a` dummy, and merging them changed how the glass and the wall draw.
  - With `--joins`, a facade may rise only where it already reaches its top.
  - Any other side may change only where every side of the terrain that can meet it draws the same.
  - A side's samples past its ends no longer count as on it: a cornice wrapped round a corner meets the diagonal
    neighbour.
- **Edge tile:** the edge tile (`c08`) is not crowned, since it is laid outside the area.
- **Approved and applied** (user, 2026-11-20): `Highrise_10` is in `srn_t_dgt04`.
- **On hold** (user, 2026-11-20): crowned copies of the other towers.
  - Batch 2's look is to be decided on the crowned towers in one client check, once that work resumes.

**Other decisions** (user interview, 2026-11-20):
- Concrete tiles are left to envkit and placeables.
- Invented-brand shop signs are on hold.
- Release order: what is done goes out first. That is the crown trial and the door set.
- **Open, left for later by the user (2026-11-20):** the lit windows of Highrise_06 and Highrise_07 seem to float when
  their tower is seen from far off.
  - The fog fades the tower's walls into the sky, but not the self-lit `window_lit` panes (`selfillumcolor 0.8`).
  - This is an assumed cause, not yet confirmed by a capture of the original alone.

### 5 — Doors

- Inventory of the 113 door models, taken during stage 1: type (exterior entrance, interior, gate, curtain), the tilesets and placeables that
  use each, current textures and faces, and one picture each.
- You pick the set. It is then restyled with release 1's material route, and remeshed where the inventory shows a need.
- Door hooks and door types (`doortypes.2da` rows) do not move.

#### Universal door set (user, 2026-11-19)

- **The pack today** (`docs/tilesets/doors/`, written by `tilekit doors`):
  - 113 door models;
  - 93 are only placed through `genericdoors.2da`;
  - 16 are tied to a tileset through `doortypes.2da`;
  - 3 are used nowhere.
- **`dgt04`'s 97 door hooks:**
  - 80 are Generic (row 0): the builder fills them with any `genericdoors` door;
  - 15 are type 58, envkit's invisible transition door;
  - 1 is a tile-specific glass window.
- **Decided:**
  - The set is new `genericdoors.2da` rows appended after the existing ones. Built areas keep their doors exactly.
  - Kinds: street doors (single, shop door with glass, double), security (steel door, roller shutter), gates, and
    interior (plain door, curtain or strip door).
  - Other tilesets' tile-specific hooks (38 in `tbx78`, and those in `fcx01`, `vmr01`, `vmp01`) keep their fitted
    doors.
  - Sizes come from measuring the doorways first.
- **Doorways measured** by casting rays across and up from each of the 80 Generic hooks (width × height, to 0.1 m):

| Opening | Hooks |
|---|---|
| 2.0 × 2.9 m | 52 |
| 4.0 × 2.9 m | 8 |
| 4.0 × 2.7 m | 2 |
| 6.0 × 2.9 m | 3 |
| 6.0 × 3.9 m | 2 |
| 8.0 × 2.9 m | 4 |
| Unclear: open yards (`dgt04_i02`, `i05`), or a low step hit | 9 |

NWN's doors are large, so each door is scaled to fill its whole opening, with no frame or transom above the leaf
(user, 2026-11-19).

**Existing door models** (bounds of the 107 ASCII models in `srn_door`):

- 2.0 × 3.0 m is the standard. 31 models, including every `gn_door` (the generic doors) and every `shp_door`.
- Doubles and gates are 3.9–4.0 × 3.0 m (`t1doora`, `tn_gdoor`, `vmr_gdoor`), and one 6.0 × 3.0 m.
- Many `t_door` models measure 4.0 × 8.0 or 2.0 × 8.0 m: those bounds take in a tall frame or wall piece, not the leaf.
- The doorways agree: 2.0 × 2.9 m measured from 0.1 m above the hook, so 2.0 × 3.0 m from the hook itself.

Sizes, matching the existing doors (approved by the user, 2026-11-19):

- 2.0 × 3.0 m single: doors, shop doors, steel doors, interior doors, curtains.
- 4.0 × 3.0 m double or roller shutter.
- 6.0 × 3.0 m gate, and 6.0 × 4.0 m loading shutter for the two taller warehouse openings.
- The four 8.0 m openings may be open yards rather than doorways.

The unclear hooks are checked against pictures.

**Unclear hooks, checked against client pictures** (2026-11-20, `output/tilekit/door-hooks/unclear.jpg`; user's
answers):

- **`dgt04_e01_05` (Highrise_01):** its four hooks stand side by side in one black 8 × 3 m opening. Each takes a
  2 × 3 m roller shutter.
- **`dgt04_i02_01`–`03` and `i05_02`/`03`:** these hooks stand in open walled yards, with no doorway. Nothing new is
  made for them.
- **`dgt04_e09_17` and `e09_37`:** these hooks stand on roofs among the clutter. Nothing new is made for them either.
- **`dgt05_h41_01`, `h51_01` and `srt04_r05_01`:** each hook stands at the jamb of a black 2 × 3 m opening. They are
  sized as 2 × 3 m singles, and the client test shows whether a door stands off-centre.
- **`dgt05_s15_32` and `s15_52`:** clear 2 × 3 m doorways. The measurement hit a low step.

**Built and approved** (user, 2026-11-20). `tools/tilekit/doorset.py` builds ten doors in `srn_door`. They share
their own atlas, `srn_doors`, and take rows 1094–1103 of `genericdoors.2da`:

| Row | Door | Size |
|---|---|---|
| 1094 | `srn_dr_street` street door | 2 × 3 m |
| 1095 | `srn_dr_shop` shop door | 2 × 3 m |
| 1096 | `srn_dr_double` double door | 4 × 3 m |
| 1097 | `srn_dr_steel` steel security door | 2 × 3 m |
| 1098 | `srn_dr_shut2` roller shutter | 2 × 3 m |
| 1099 | `srn_dr_shut4` roller shutter | 4 × 3 m |
| 1100 | `srn_dr_load` loading shutter | 6 × 4 m |
| 1101 | `srn_dr_gate` gate | 6 × 3 m |
| 1102 | `srn_dr_inner` interior door | 2 × 3 m |
| 1103 | `srn_dr_strip` strip curtain | 2 × 3 m |

The client review stood each door at a dgt04 hook of its size, shut and opened (`output/tilekit/doorset-review2`).
It also tried Highrise_01's four shutters. The jamb hooks above were not tried: whether a door stands off-centre
there is still open.

### 6 — Cohesion and release

- Performance against the baseline on the same views.
- One look pass over the whole block, then `PROVENANCE.md`.
- One merge to `main`.

## Carried over from release 1

- **Done 2026-11-20:** `hr08_trim`, `hr09_build_g` and `hr09_win08_g` are redrawn with records into
  `output/tilekit/redrawn-terrains`. They have entries in `redraw-terrains.json` now.
  - The user chose local Qwen for this (seed 2).
  - The trim is redrawn by Qwen.
  - The two derelict lit variants are composed with the new `keep` option: a share of whole windows, lit warm only
    where the day picture is dark. The tower shows two squatters' windows, and the boarded window glows through its
    gaps, not the office light of its source.
  - Seen in the client: `output/tilekit/redraw3-review`.
  - Applied to `srn_t_dgt04`.
- The new edge tiles `srt04_r07_01` and `srt04_x07_01` have not been seen in the client. Look again with a view from
  outside the border once the detail kit makes edges matter.
- envkit's check area now stages the maps of restyled materials, which affects `pavement`. It has not been seen in
  a client check yet.

## Open after the pilot

- The budget and the geometry source are settled (see the pilot result).
- Whether the Concrete tiles are detailed at all, or left to envkit and placeables.
- Frame rate with effects in, and load times: measured on the first batch (see its result).
- Desk time per batch: estimated from the first batch.
