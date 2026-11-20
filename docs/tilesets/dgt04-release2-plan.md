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
| Roof clutter | Cover for rooftop battles (user, 2026-11-19): roof clutter blocks movement and line of sight. Its footprint is cut out of the walkable roof as Nonwalk. Street level stays fixed. |
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
  - Its footprint (the piece's convex hull from above) is cut out of that roof and marked Nonwalk (surfacemat 7).
    Nonwalk stops walking and blocks line of sight, so the piece is cover.
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

### 3 — Families, one batch each

1. Slums 1–3 (104 tiles).
2. Corporate highrises 01–03 and 05–07: rooftop plant, antennae, ledges and megacorp signage.
3. The copies `Highrise_08` (residential) and `Highrise_09` (derelict).
4. `Highrise_04` (ruin), Apartments, Warehouses, Police, Hospital and Lab.
5. Streets and ground, the Concrete tiles: kerbs, drains, bollards and street furniture baked in. Only if the budget
   allows it at that tile count.

Each batch ends with a day-and-night contact sheet and a look gate. Each lands as one PR into `restyle/dgt04-r2`.

### 4 — Selective remeshing

- A candidate list from the review captures: the tiles whose shape reads worst once they are detailed.
- The list comes to you with pictures and you pick.
- Remeshed under the silhouette rule, in the same batches, or as one batch after them.

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

Proposed sizes, matching the existing doors:

- 2.0 × 3.0 m single: doors, shop doors, steel doors, interior doors, curtains.
- 4.0 × 3.0 m double or roller shutter.
- 6.0 × 3.0 m gate, and 6.0 × 4.0 m loading shutter for the two taller warehouse openings.
- The four 8.0 m openings may be open yards rather than doorways.

The unclear hooks are checked against pictures.

### 6 — Cohesion and release

- Performance against the baseline on the same views.
- One look pass over the whole block, then `PROVENANCE.md`.
- One merge to `main`.

## Carried over from release 1

- `hr08_trim`, `hr09_build_g` and `hr09_win08_g` are not reproducible from their specs: they are redrawn with
  records when the Codex quota allows.
- The new edge tiles `srt04_r07_01` and `srt04_x07_01` have not been seen in the client. Look again with a view from
  outside the border once the detail kit makes edges matter.
- envkit's check area now stages the maps of restyled materials, which affects `pavement`. It has not been seen in
  a client check yet.

## Open until the pilot

- The budget: faces, mesh nodes and materials per tile.
- The geometry source for each piece type.
- Whether the Concrete tiles are detailed at all, or left to envkit and placeables.
- Desk time: measured in the pilot, then estimated for each batch.
