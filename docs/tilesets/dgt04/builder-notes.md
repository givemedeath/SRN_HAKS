# D20 Modern Exterior (`dgt04`): notes for area builders

## Areas with highrise towers: set the fog clip distance to about 200 m

Set the area's fog clip distance (`FogClipDist`) to about 200 m wherever towers can be seen from far off.

At a short clip distance (90 m, say), a tower farther away than that loses its walls, and its windows seem to float
in the sky:

- the client stops drawing a tile's static meshes past the clip distance;
- it goes on drawing the facades that switch between day and night windows, which hang under the tile's animated
  dummy.

At 200 m the whole tower is drawn (checked in the client on 2026-11-20, by day and night). A longer clip distance draws
more, so check the frame rate in large areas.

## Generic door hooks

Rows 1094-1103 of `genericdoors.2da` are the universal door set (`srn_dr_*` in `srn_door`). Each door fills its
opening, with no frame above it.

| Size | Doors |
|---|---|
| 2 × 3 m | street, shop, steel, interior doors, roller shutter, strip curtain |
| 4 × 3 m | double door, roller shutter |
| 6 × 3 m | gate |
| 6 × 4 m | loading shutter |

Pick the door that fits the hook's doorway. Highrise_01's 8 m opening takes four 2 m roller shutters, one on each of
its four hooks.
