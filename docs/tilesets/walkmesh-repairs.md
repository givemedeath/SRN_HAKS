# Walkmesh repairs (2026-11-25)

44 tiles have a walkmesh that differs from their tileset's first baseline, on purpose. Creatures walked round a floor
edge there instead of across it. Their `walkmesh.json` entries record the repaired walkmeshes; do not bring the older
ones back.

## What bends a route

The game joins walked faces edge by edge. Walked in the client by a Human and a Troll, both ways:

| Fault | Result |
| --- | --- |
| One long edge against two or more shorter ones (a T-junction) | Bent nearly every crossing: 1,343 of 1,364, 4 after the repair |
| A walked face of no area between two floor faces, where an edge is shared three times | Bends a route on some tiles; others are crossed straight (`udp1_c01_07`) |
| A walked face held twice | Bends a route (`udp1_c03_16`) |
| A kerb wall whose spans do not match the floor's | Bends a route (`fcx01_x01`, `fcx01_x05`) |
| A hair-wide walked face that joins both sides | Stops nobody (`dgt05_b07_06`) |

Floors one above the other look like a crack when compared in x and y only; compare them at the edge's own height.

## Repaired

- dgt04: `dgt05_b07_06`.
- udp1: `a02_03`, `a02_04`, `a03_09`, `a04_13`, `a05_05`, `a08_01` to `03`, `a08_06`, `a08_07`, `a11_11`, `a11_12`,
  `a12_13`, `a13_20`, `a14_20` to `24`, `a16_07`, `a18_01` to `03`, `c01_16` to `19`, `c02_16`, `c02_19`, `c03_16` to
  `19`, `c04_16`, `c04_19`, `c07_04`.
- fcx01: `h01_18`, `x01_01`, `x01_02`, `x02_01`, `x02_02`, `x05_01`, `x05_02`.

Corners are welded, faces dropped and edges split; the floor a creature stands on and the tile's sides stay.
`udp1_a08_07` also loses the floor hidden under its two boards. `udp1_a12_13` and `udp1_c07_04` were repaired without a
walk: they leave no room beside the edge.

## Left

- Corners that miss each other by millimetres, not walked: the tiles in `KNOWN` of `tools/tilekit/test_floor_edges.py`,
  and (10 to 31 mm) `udp1_a03_16`, `udp1_a07_02`, `fcx01_m01_06`.
- `udp1_a08_07`: 33 mm gaps at the feet of its two slopes, and routes lengthwise over the ends of its boards bend.
- `udp1_a08_06`: a 2 x 9 cm hole at each end of a kerb.
- `fcx01_h01_20`: one crossing near a corner bends; cause not found.
