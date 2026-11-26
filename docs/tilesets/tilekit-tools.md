# Tilekit's working tools

The commands a restyle uses beside `inventory`, `material`, `detail` and `apply`. They came out of the Modern Exterior
restyle (dgt04), whose specs are in `docs/tilesets/dgt04/`. Run each as `python -B -m tools.tilekit <command>`; `--help`
lists its arguments. They read a tile's ASCII source where the pack ships a compiled model.

| Command | What it does | dgt04 stage |
| --- | --- | --- |
| `repair` | Reports broken animation blocks; `--write` puts the ASCII sources right (then run `compile`) | Release 2, compiled models |
| `propose` | Proposes a family's kit pieces from a family spec, each tile checked by `detail` | Batches 1 to 5 |
| `openings` | Measures the doorway at every door hook; lists faces drawn with black materials | Universal door set, glass |
| `family-review` | Captures tiles apart, painted blocks, streets, whole towers or door hooks in the client | Every batch review |
| `perf` | Frame rates and load times over a family review spec's areas | Release 2, stage 0 baseline |
| `rank` | Building tiles by how plain their own geometry is | Remesh and crown candidates |
| `shared` | Models outside the tileset that name its restyled textures | Release 1, shared textures |
| `placements` | Wall pieces of applied specs that run into their tile's own geometry | Batches 2 to 4, after the new guard |
| `sketch` | Tile models drawn from the top, front and side, without the game | Crowns, doors |
| `rooms` | Rooms of a merged interior set, unfurnished and furnished, as tiles of their own (srx02; `tools/tilekit/rooms.py` has the spec, `walls.py` the rooms drawn here, `ceilings.py` their lamps and beams; a new piece's front goes into `fronts.json` after it is looked at); a spec's `effects` are emitters (`effects.py`: candle flame, fire, embers, motes, glimmer); every doorway drawn 2 m wide or less gets a generic door hook, and a piece rests on furniture, hangs on its wall or hangs from the ceiling) | srx02, stage 5 |
| `door_names` | `python -B -m tools.tilekit.door_names`: names each door of the Toolset's appearance list, "<category>: <door>", from `docs/tilesets/doors/names.json` (TLK strings and the `genericdoors.2da` Name column) | srx02, doors |
| `props` | Every kit piece rendered in Blender (four threads), by day and night | Kit rework |

## Specs

- **Family spec** (`propose`): described in `tools/tilekit/family.py`. dgt04's are `family-slums.json`,
  `family-highrise.json`, `family-batch3.json`, `family-batch4.json` and `family-streets.json`. The proposal is a start:
  the committed `detail-*.json` have hand changes made after it. A tile that already has kit pieces in the repository is
  refused, so a proposal for an applied batch starts from a copy of the packs before it.
- **Family review spec** (`family-review`, `perf`): described in `tools/tilekit/family_review.py`. Examples:
  `family-review.json` and, for `perf`, `family-perf.json` (the stage 0 areas). Files a spec names are looked for beside it.
- **Openings file**: what `openings --out` writes; a `doors` layout reads it.

## Client runs

- `family-review` and `review` limit the frame rate (60 in front, 30 behind), turn keyholing off and lay areas with
  `FogClipDist` 9999. They wait for another client to close.
- At most 24 views are taken, evenly through those asked for; `--views` names them, `--most` or `--all` takes more. The
  labels left out are told.
- Interiors: a `review` block's `eye` takes views from inside a room at eye level (1.7 m, level or tilted up), so
  ceilings are seen. A view from above shows the top of a ceiling.
- `perf` sets every limiter to one cap (200 at most) with vsync off, and refuses to start while a client is running.
  Read the rates off `counters.png`; a rate at the cap means at least that. Load times are in `perf.json`.
- `--no-run` (`family-review`) builds the module only.
