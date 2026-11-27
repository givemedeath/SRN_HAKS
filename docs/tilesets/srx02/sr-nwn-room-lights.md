# Room lights in srx02: instructions for SR_NWN

Release C (2026-11-27, user: "script driven switching is probably best for interiors"). This is for whoever writes
the room light switch in SR_NWN. Nothing here is wired in SR_NWN yet, and the live switch has not been tried in the
client.

## What the tiles do

- Every light fitting of the interior families, and of the prefab rooms, has two looks:
  - an unlit copy, which stands in place;
  - the lit fitting, which rests 60 m under the tile.
- The tile's **third animation loop** (`animloop03`) lifts the lit fitting home and parks the unlit copy.
  - The fitting is lit while the tile's AnimLoop3 is on.
  - It is unlit while AnimLoop3 is off.
- The fittings switched are listed in `docs/tilesets/srx02/lights.json`.
  - These are room lamps and ceiling panels: the office's glow-map ceiling, the facility's lights and strips, Modern
    Interior's lamps, and the prefab rooms' lamps.
  - Screens, jukeboxes and devices stay lit; their glow lights nothing anyway.
  - Built by `tilekit roomlights`, the rooms build and the merge.
- The set file has AnimLoop3=1 for every switched tile, so a newly painted room is lit.
  - In the Toolset a builder can turn a tile's third loop off in the area to make a room that starts dark.
- A fitting's glow lights nothing. A room's light comes from its tiles' **main lights** (MainLight1/2 in the set file,
  coloured per tile in the area). Switching a room means switching both: the loop for the look, and the main lights
  for the light.

## Switching a room live

Plain NWScript cannot change a tile's animation loops: `nwscript.nss` has `SetTileMainLightColor`,
`SetTileSourceLightColor` and `RecomputeStaticLighting`, but no tile loop call. Anvil can.

1. **Remember the lights.** Before the first switch-off, remember each tile's main and source light colours, in
   locals on the switch or the area:
   - `GetTileMainLight1Color`, `GetTileMainLight2Color`, `GetTileSourceLight1Color`, `GetTileSourceLight2Color`;
   - each takes the location at the tile's centre: x = 10·column + 5, y = 10·row + 5.
2. **Set the loop.** Call `NwArea.SetTiles(List<TileData>, SettleFlags.RecomputeLighting)` with one `TileData` per
   tile of the room.
   - Each `TileData` keeps the tile's own TileId, Orientation, Height, AnimationLoop1 and AnimationLoop2, from the
     area's tile info.
   - `AnimationLoop3` is 0 for off and 1 for on.
   - `Index` = row · width + column.
3. **Set the lights.**
   - Off: `SetTileMainLightColor(tile, TILE_MAIN_LIGHT_COLOR_BLACK, TILE_MAIN_LIGHT_COLOR_BLACK)`, and the same for
     source lights.
   - On: the remembered colours.
4. **Recompute once.** Call `RecomputeStaticLighting(area)` once after all of the room's tiles, unless `SetTiles`
   already did it with its flag.

**A room's tiles.** These are the tiles inside its walls: a prefab room is one palette group, and its tiles are the
group's rows × columns from where it was painted. The simplest record is a light switch placeable with locals for the
room's first and last column and row.

## To prove before relying on it

- That `SetTiles` with only AnimationLoop3 changed shows the switch to players already in the area, without a
  re-enter or a visible rebuild of the tile.
- That the lighting recompute after the switch is quick enough for a light switch, in a room and in a large area.
- If either fails, the fallback is static: dark rooms are set in the Toolset (third loop off, black main lights),
  and a live switch changes only the main lights. The fittings then keep the look they were painted with.
