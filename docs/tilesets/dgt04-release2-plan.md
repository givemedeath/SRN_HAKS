# Modern Exterior (`dgt04`) upfit, release 2 — plan

Status: revision 1, 2026-11-19, scope decided by the user; nothing built yet. Release 1 (materials, lamps, shadows,
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

- **Walkmesh:** no change. Every `.wok` and every `aabb` node hashes as `docs/tilesets/dgt04/walkmesh.json`
  records. `tilekit` refuses a model whose walkmesh would change.
- **Set file:** no tile number, terrain, crosser or group moves in `dgt04.set`. New tiles, if any, are appended.
- **Door hooks and lamps:** door hooks, tile lamps (`ml1`/`ml2`) and their positions are kept.
- **Silhouette:** may change only above head height, about 2.5 m. Nothing is added inside the walkable footprint below it.
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
- Take the performance baseline on the review block and on one large built area:
  - frame rate standing at three fixed views, by day and by night;
  - area load time from the client log;
  - pack sizes.
- The capture method is confirmed in a probe first: the client's frame counter in the captures, and load times from
  the log's area-entry lines.
- Done when the numbers are recorded here and repeat within a few percent on a second run.

### 1 — Tooling

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
- A face and texture count per tile, against the budget once it is set.
- The kit-piece library: models, their materials, and a contact sheet. Its source is settled in the pilot (Meshy
  or Blender, piece by piece).

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

- Inventory of the 113 door models: type (exterior entrance, interior, gate, curtain), the tilesets and placeables that
  use each, current textures and faces, and one picture each.
- You pick the set. It is then restyled with release 1's material route, and remeshed where the inventory shows a need.
- Door hooks and door types (`doortypes.2da` rows) do not move.

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

- The face budget.
- The geometry source for each piece type.
- Whether the Concrete tiles are detailed at all, or left to envkit and placeables.
- Desk time: measured in the pilot, then estimated for each batch.
