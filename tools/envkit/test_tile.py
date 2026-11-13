"""A building becomes tiles: its walkmesh closes what stands in the way, and its records join a set file untouched."""
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from . import convert, glow, tile

BOX = np.array([[0, 1, 3], [0, 3, 2], [4, 6, 7], [4, 7, 5], [0, 4, 5], [0, 5, 1], [2, 3, 7], [2, 7, 6], [0, 2, 6], [0, 6, 4], [1, 5, 7], [1, 7, 3]])


def box(low, high):
    return np.array([[x, y, z] for x in (low[0], high[0]) for y in (low[1], high[1]) for z in (low[2], high[2])], float), BOX


def scene(*boxes):
    points, faces = [], []
    for corners, triangles in boxes:
        faces.append(triangles + sum(len(part) for part in points)); points.append(corners)
    return np.concatenate(points), np.concatenate(faces)


# A shop on a slab: four walls with nothing inside, a canopy over the pavement in front (north), a bollard under it.
SHOP = scene(box((-4, -3, 0), (4, 3, 0.2)),  # the slab
             box((-3, -2, 0.2), (-2.8, 1, 3)), box((2.8, -2, 0.2), (3, 1, 3)), box((-3, -2, 0.2), (3, -1.8, 3)), box((-3, 0.8, 0.2), (3, 1, 3)),
             box((-3, 1, 2.6), (3, 2.9, 3)),  # the canopy: overhead, so nothing to walk into
             box((0.55, 2.3, 0.2), (0.95, 2.7, 1.2)))  # the bollard

CELL = tile.SIZE / tile.CELLS


def floor(found, row=0, column=0):
    """(vertices, floor faces, upright faces) of a tile's walkmesh: the floor's vertices come first, one to each crossing of its lines."""
    vertices, faces = tile.walkmesh(found, row, column); xs, ys = tile.lines(found, row, column)
    level = (faces[:, :3] < len(xs) * len(ys)).all(1)  # an upright face reaches a roof vertex
    return vertices, faces[level], faces[~level]


def ground(vertices, flat, x, y):
    """(height, material) of the floor under a point."""
    for a, b, c, kind in flat:
        (ax, ay, az), (bx, by, bz), (cx, cy, cz) = vertices[[a, b, c]]
        whole = (bx - ax) * (cy - ay) - (cx - ax) * (by - ay)
        v, w = ((x - ax) * (cy - ay) - (cx - ax) * (y - ay)) / whole, ((bx - ax) * (y - ay) - (x - ax) * (by - ay)) / whole
        if min(v, w, 1 - v - w) >= -1e-9:
            return az + v * (bz - az) + w * (cz - az), kind
    raise AssertionError(f'No floor under {x}, {y}')


SET = '\r\n'.join(['[GENERAL]', 'Name=T', '', '[TILES]', 'Count=2', '', '[TILE0]', 'Model=a', '', '[TILE1]', 'Model=b', '', '[GROUPS]', 'Count=1', '',
                   '[GROUP0]', 'Name=Old', 'Rows=1', 'Columns=1', 'Tile0=1'])


class TileTests(unittest.TestCase):
    def test_a_model_wider_than_a_tile_takes_a_group_centred_on_it(self):
        wide = np.array([[-6.0, -5.3, 0], [6.1, 5.4, 5.6]])
        rows, columns, corner = tile.layout(wide)
        self.assertEqual((rows, columns), (2, 2)); np.testing.assert_allclose(corner, [-9.95, -9.95])
        self.assertEqual(tile.layout(SHOP[0])[:2], (1, 1))

    def test_the_walkmesh_closes_the_building_and_the_bollard_but_not_the_ground_under_the_canopy(self):
        rows, columns, corner = tile.layout(SHOP[0]); found = tile.survey(*SHOP, rows, columns, corner)
        at = lambda x, y: found['material'][int((y - corner[1]) / CELL), int((x - corner[0]) / CELL)]
        self.assertEqual(at(-2.9, 0), tile.OBSCURING)  # a wall
        self.assertEqual(at(0, -0.5), tile.OBSCURING)  # the floor the walls enclose, though the model has none
        self.assertEqual(at(0.75, 2.6), tile.NONWALK)  # the bollard: in the way, seen over
        self.assertEqual(at(-1.0, 2.1), tile.STONE)  # under the canopy
        self.assertEqual(at(-4.5, 4.0), tile.STONE)
        self.assertAlmostEqual(found['slab'], 0.2, places=2); self.assertAlmostEqual(found['roof'], 3.0)
        vertices, flat, upright = floor(found); xs, ys = tile.lines(found, 0, 0)
        grid = vertices[:len(xs) * len(ys)]
        np.testing.assert_allclose([grid[:, :2].min(), grid[:, :2].max()], [-5, 5])  # the whole tile and no more
        rim = (np.abs(grid[:, 0]) == 5) | (np.abs(grid[:, 1]) == 5); self.assertEqual(float(np.abs(grid[rim, 2]).max()), 0.0)
        height = lambda x, y: ground(vertices, flat, x, y)[0]
        self.assertAlmostEqual(height(-1.5, 2.0), found['slab'], places=6); self.assertEqual(height(-4.5, 0.0), 0.0)
        self.assertAlmostEqual(height(-4.0, 0.0), 0.0, places=6)  # the slab's own edge: the ramp starts here
        self.assertAlmostEqual(height(-3.75, 0.0), found['slab'] / 2, places=6); self.assertAlmostEqual(height(-3.5, 0.0), found['slab'], places=6)  # and is half a metre long
        # Lines only where the ground changes: far fewer faces than cells, and every cell still under a face of its own material.
        self.assertEqual(len(flat), 2 * (len(xs) - 1) * (len(ys) - 1)); self.assertLess(len(flat), 500)
        for r in range(tile.CELLS):
            for c in range(tile.CELLS):
                self.assertEqual(ground(vertices, flat, (c + 0.5) * CELL - 5, (r + 0.5) * CELL - 5)[1], found['material'][r, c], (r, c))
        up = np.cross(vertices[flat[:, 1]] - vertices[flat[:, 0]], vertices[flat[:, 2]] - vertices[flat[:, 0]])[:, 2]
        self.assertTrue((up > 0).all())  # every floor face looks up
        self.assertTrue(len(upright) and (upright[:, 3] == tile.OBSCURING).all())
        self.assertAlmostEqual(float(vertices[upright[:, :3]][..., 2].max()), 3.0)  # walls of sight, up to the roof
        # Upright faces all the way round the building's outline: along each side of a closed cell that looks out.
        closed = np.pad(found['material'] == tile.OBSCURING, 1)
        sides = sum(int((closed & ~np.roll(closed, turn, axis)).sum()) for axis in (0, 1) for turn in (1, -1))
        foot = vertices[upright[::2, :2]][..., :2]  # the two floor corners each pair of upright faces stands on
        self.assertAlmostEqual(float(np.linalg.norm(foot[:, 0] - foot[:, 1], axis=1).sum()), sides * CELL, places=6)
        self.assertGreaterEqual(sides * CELL, 2 * (6 + 3))  # at least the 6 by 3 metres of walls

    def test_a_bin_against_the_wall_stops_movement_but_is_seen_over(self):
        binned = scene(SHOP, box((-1.5, 1.0, 0.2), (-0.7, 1.7, 1.1)))  # touching the north wall, under the canopy
        rows, columns, corner = tile.layout(binned[0]); found = tile.survey(*binned, rows, columns, corner)
        at = lambda x, y: found['material'][int((y - corner[1]) / CELL), int((x - corner[0]) / CELL)]
        self.assertEqual(at(-1.1, 1.6), tile.NONWALK); self.assertEqual(at(-1.1, 0.9), tile.OBSCURING)
        vertices, flat, upright = floor(found)
        self.assertLess(float(vertices[upright[:, :3]][..., 1].max()), 1.26)  # no wall of sight round the bin: the building's ends with the cell of its own wall
        self.assertEqual(ground(vertices, flat, -1.1, 1.4)[1], tile.NONWALK); self.assertEqual(ground(vertices, flat, -1.1, 1.9)[1], tile.STONE)  # the bin's own outline, to the cell
        sample = CELL / tile.FINE
        self.assertFalse(found['footprint'][int((1.6 - corner[1]) / sample), int((-1.1 - corner[0]) / sample)])  # nor does the lid cover it

    def test_the_tiles_of_a_group_meet_corner_to_corner(self):
        wide = scene(box((-6, -5.3, 0), (6.1, 5.4, 0.2)), box((-4.3, -3.1, 0.2), (3.9, 2.6, 3)), box((4.9, 1.1, 0.2), (5.4, 1.6, 1.0)))
        rows, columns, corner = tile.layout(wide[0]); found = tile.survey(*wide, rows, columns, corner); self.assertEqual((rows, columns), (2, 2))

        def edge(row, column, axis, side):  # the walkmesh's corners along one edge of a tile: where along it, and how high
            vertices = tile.walkmesh(found, row, column)[0]
            return sorted(map(tuple, np.round(np.delete(vertices[np.abs(vertices[:, axis] - side) < 1e-9], axis, 1), 6).tolist()))
        for row in (0, 1):
            self.assertEqual(edge(row, 0, 0, 5.0), edge(row, 1, 0, -5.0))  # west tile's east edge, east tile's west: the same corners at the same heights
        for column in (0, 1):
            self.assertEqual(edge(0, column, 1, 5.0), edge(1, column, 1, -5.0))
        self.assertGreater(len(edge(0, 0, 0, 5.0)), 2)  # and the building's own lines cross it

    def test_a_model_that_leaves_no_ground_round_it_is_refused(self):
        with self.assertRaisesRegex(ValueError, 'edge of its tiles'):
            tile.survey(*box((-5, -5, 0), (5, 5, 3)), 1, 1, np.array([-5.0, -5.0]))

    def test_the_box_tree_names_every_face_once_and_starts_with_the_whole(self):
        rows, columns, corner = tile.layout(SHOP[0]); vertices, faces = tile.walkmesh(tile.survey(*SHOP, rows, columns, corner), 0, 0)
        boxes = tile.tree(vertices, faces)
        self.assertEqual(len(boxes), 2 * len(faces) - 1)
        self.assertEqual(sorted(b[6] for b in boxes if b[6] >= 0), list(range(len(faces))))
        np.testing.assert_allclose(boxes[0][:6], [-5, -5, 0, 5, 5, 3]); self.assertEqual(boxes[0][6], -1)
        first = boxes[1]; self.assertTrue(all(first[axis] >= boxes[0][axis] and first[axis + 3] <= boxes[0][axis + 3] for axis in range(3)))

    def test_a_tile_model_has_its_ground_its_mesh_its_halo_and_its_walkmesh(self):
        walk = (np.array([[-5.0, -5, 0], [5, -5, 0], [-5, 5, 0], [5, 5, 0]]), np.array([[2, 0, 3, tile.STONE], [3, 0, 1, tile.STONE]]))
        part = (np.array([[0.0, 0, 0], [1, 0, 0], [0, 0, 1]]), np.tile([0, 1.0, 0], (3, 1)), np.zeros((3, 2)), np.array([[0, 1, 2]]))
        card = [((1.0, 0.5, 0.0), (0.0, 1.0)), ((-1.0, 0.5, 0.0), (1.0, 1.0)), ((-1.0, 0.5, 1.0), (1.0, 0.0)), ((1.0, 0.5, 1.0), (0.0, 0.0))]
        text = tile.model_text('ek_test_t00', [part], 'ek_test', 'pavement', [card], walk)
        for line in ('classification TILE', 'node trimesh ek_test_t00_g', '  bitmap pavement', 'node trimesh ek_test_t00_m0', '  bitmap ek_test', '  tilefade 0',
                     'node trimesh ek_test_t00_halo0', '  bitmap ek_test_h', 'node aabb ek_test_t00_wm', '    2 0 3  1  0 0 0  4',
                     '  aabb -5.00000 -5.00000 0.00000 5.00000 5.00000 0.00000 -1', 'donemodel ek_test_t00'):
            self.assertIn(line, text)
        alone = tile.walk_text('ek_test_t00', walk)
        self.assertTrue(alone.startswith('beginwalkmeshgeom ek_test_t00\nnode aabb ek_test_t00_wm')); self.assertTrue(alone.endswith('endwalkmeshgeom ek_test_t00\n'))
        with self.assertRaisesRegex(ValueError, 'resref'):
            tile.model_text('ek_a_name_too_long', [], 'ek_test', 'pavement', [], walk)

    def test_a_halo_card_is_cut_where_it_crosses_into_the_next_tile(self):
        card = [((4.0, 3.0, 1.0), (0.0, 0.5)), ((-2.0, 3.0, 1.0), (0.6, 0.5)), ((-2.0, 3.0, 2.0), (0.6, 0.0)), ((4.0, 3.0, 2.0), (0.0, 0.0))]
        light = np.zeros((4, 60)); light[:, :10] = 1.0; light[:, 50:] = 2.0  # the card's picture: ten columns to the metre, lit at its two ends
        shared = tile.share_cards([card], 2, 2, np.array([-10.0, -10.0]), [light])
        self.assertEqual(sorted(shared), [(1, 0), (1, 1)])  # the north row, both tiles
        (east, lit_east), (west, lit_west) = shared[(1, 1)][0], shared[(1, 0)][0]
        self.assertEqual((lit_east.shape, float(lit_east.sum()), lit_west.shape, float(lit_west.sum())), ((4, 40), 40.0, (4, 20), 80.0))  # each piece keeps its own part of the light
        np.testing.assert_allclose([place for place, _ in east], [[-1, -2, 1], [-5, -2, 1], [-5, -2, 2], [-1, -2, 2]])  # in the tile's own space
        np.testing.assert_allclose([place[0] for place, _ in west], [5, 3, 3, 5])
        np.testing.assert_allclose([uv[0] for _, uv in east], [0.0, 0.4, 0.4, 0.0]); np.testing.assert_allclose([uv[0] for _, uv in west], [0.4, 0.6, 0.6, 0.4])

    def test_a_card_on_a_side_wall_is_cut_along_the_wall_it_stands_on(self):
        # Facing +X at x = 3: seen from the east its left corner is the southern one. It crosses from the south row into the north.
        card = [((3.0, -2.0, 1.0), (0.0, 0.5)), ((3.0, 4.0, 1.0), (0.6, 0.5)), ((3.0, 4.0, 2.0), (0.6, 0.0)), ((3.0, -2.0, 2.0), (0.0, 0.0))]
        shared = tile.share_cards([card], 2, 2, np.array([-10.0, -10.0]))
        self.assertEqual(sorted(shared), [(0, 1), (1, 1)])  # the east column, both rows
        (south, unlit), (north, _) = shared[(0, 1)][0], shared[(1, 1)][0]; self.assertIsNone(unlit)  # no light was given
        np.testing.assert_allclose([place for place, _ in south], [[-2, 3, 1], [-2, 5, 1], [-2, 5, 2], [-2, 3, 2]])
        np.testing.assert_allclose([place[1] for place, _ in north], [-5, -1, -1, -5])
        np.testing.assert_allclose([uv[0] for _, uv in south], [0.0, 0.2, 0.2, 0.0]); np.testing.assert_allclose([uv[0] for _, uv in north], [0.2, 0.6, 0.6, 0.2])

    def nodes(self, model):
        """{(row, column): (node, turn, exits, offPath)} of the group a model takes."""
        rows, columns, corner = tile.layout(model[0]); found = tile.survey(*model, rows, columns, corner)
        return {(row, column): tuple(tile.path_node(found, row, column).values()) for row in range(rows) for column in range(columns)}

    def test_each_tile_of_a_group_leaves_by_the_sides_its_ground_reaches(self):
        # A building across the middle of four tiles leaves each a strip round its outer corner, which reaches all four of the tile's sides:
        # the two outer ones whole, the two shared ones at their outer ends. An opening need not be at a side's middle. The two shared
        # sides do not see each other round the building's corner, so one of them is left alone (U); the rest are joined.
        wide = scene(box((-6, -5.3, 0), (6.1, 5.4, 0.2)), box((-5.6, -5.1, 0.2), (5.7, 5.2, 3)))
        self.assertEqual(self.nodes(wide), {(0, 0): ('U', 180, 'NWSE', 0), (0, 1): ('U', 0, 'NWSE', 0), (1, 0): ('U', 90, 'NWSE', 0), (1, 1): ('U', 0, 'NWSE', 0)})
        # One tile with the shop in its middle and ground all round it: the shop is too wide to go round from the south side's middle to the
        # north's within two metres of the straight way (ASIDE), so the south is left alone; west and east are joined round its narrow north.
        self.assertEqual(self.nodes(SHOP), {(0, 0): ('U', 90, 'NWSE', 0)})
        # A row of three with a long shed through them. The middle tile's ground is two strips that do not join, and its west and east sides
        # open onto both: no letter says that, so each side goes with one strip (the first found of two as near its middle) and the north is
        # left alone. The end tiles leave the north alone too: from its middle to the south's is round the end of the shed, too far aside.
        shed = scene(box((-13, -3.5, 0), (13, 3.5, 0.2)), box((-12, -2.5, 0.2), (12, 2.5, 3)))
        self.assertEqual(self.nodes(shed), {(0, 0): ('U', 270, 'NWSE', 0), (0, 1): ('U', 270, 'NWSE', 0), (0, 2): ('U', 270, 'NWSE', 0)})
        # Three by three under one block: the middle tile is closed whole, a tile at the middle of a side is left by all but its inner side
        # (I leaves north, west and south; a turn is counter-clockwise), a corner tile by all four, with the two round the corner apart.
        block = scene(box((-13, -13, 0), (13, 13, 0.2)), box((-11, -11, 0.2), (11, 11, 3)))
        found = self.nodes(block)
        self.assertEqual((found[(1, 1)], found[(1, 0)], found[(0, 1)], found[(1, 2)], found[(2, 1)]),
                         (('T', 0, '', 0), ('I', 0, 'NWS', 0), ('I', 90, 'WSE', 0), ('I', 180, 'NSE', 0), ('I', 270, 'NWE', 0)))
        self.assertEqual([found[spot] for spot in ((0, 0), (0, 2), (2, 2), (2, 0))], [('U', 180, 'NWSE', 0), ('U', 0, 'NWSE', 0), ('U', 0, 'NWSE', 0), ('U', 90, 'NWSE', 0)])

    def test_a_side_is_an_exit_wherever_a_metre_of_it_is_open_and_ground_no_exit_reaches_is_counted(self):
        # Two tiles side by side. A yard walled on three sides stands in the west one; its fourth wall, just inside the east tile, shuts the
        # middle of the side the tiles share and leaves the yard a way out 2.5 metres wide north of it. That is the west tile's east exit:
        # the yard's ground leaves by it alone, the ground round the yard by the other three (U: one side alone, the other three joined).
        walls = [box((-4.0, -3.0, 0), (-3.6, 4.4, 3)), box((-4.0, -3.0, 0), (0.4, -2.6, 3)), box((-4.0, 4.0, 0), (0.4, 4.4, 3))]
        nodes = lambda *fourth: [tuple(tile.path_node(found, 0, column).values()) for found in [tile.survey(*scene(*walls, *fourth), 1, 2, np.array([-10.0, -5.0]))] for column in (0, 1)]
        self.assertEqual(nodes(box((0.0, -3.0, 0), (0.4, 1.5, 3))), [('U', 180, 'NWSE', 0), ('A', 0, 'NWSE', 0)])
        self.assertEqual(nodes(), [('U', 180, 'NWSE', 0), ('A', 0, 'NWSE', 0)])  # the same with no fourth wall
        # A gap of three quarters of a metre is no exit. The side is still left by, south of the yard, but the yard's own ground is reached
        # by no exit: some 3.6 by 6.6 metres of quarter-metre cells. From the side's opening south of the yard the north is round the yard,
        # too far aside, so that side is left alone.
        west, east = nodes(box((0.0, -3.0, 0), (0.4, 3.25, 3)))
        self.assertEqual((west[:3], east), (('U', 180, 'NWSE'), ('A', 0, 'NWSE', 0))); self.assertGreater(west[3], 300)

    def test_the_set_file_states_each_tiles_node_and_a_group_built_before_nodes_is_refused(self):
        made = {'rows': 1, 'columns': 2, 'tiles': [{'model': 'ek_test_t00', 'row': 0, 'column': 0, 'path': {'node': 'I', 'turn': 0}},
                                                   {'model': 'ek_test_t01', 'row': 0, 'column': 1, 'path': {'node': 'N', 'turn': 270}}]}
        records = [dict(record) for record in tile.tile_records(made, 'Concrete')]
        self.assertEqual([(record['PathNode'], record['Orientation'], record['VisibilityNode'], record['VisibilityOrientation']) for record in records], [('I', 0, 'I', 0), ('N', 270, 'N', 270)])
        self.assertTrue(all(record['TopLeft'] == 'Concrete' and record['Doors'] == 0 for record in records))
        self.assertEqual(tuple(key for key, _ in tile.tile_records(made, 'Concrete')[0]), tile.TILE_KEYS)
        del made['tiles'][1]['path']
        with self.assertRaisesRegex(ValueError, 'build it again'):
            tile.tile_records(made, 'Concrete')

    def test_a_set_files_terrains_are_read_so_a_wrong_one_can_be_refused(self):
        text = '[TERRAIN TYPES]\r\nCount=2\r\n\r\n[TERRAIN0]\r\nName=Grass\r\n\r\n[TERRAIN1]\r\nName=Asphalt\r\nStrRef=5\r\n\r\n[CROSSER0]\r\nName=Road\r\n'
        self.assertEqual(tile.terrains(text), ['Grass', 'Asphalt'])

    def test_tiles_and_their_group_are_appended_and_nothing_there_is_renumbered(self):
        made = {'rows': 2, 'columns': 2, 'tiles': [{'model': f'ek_test_t{row}{column}', 'row': row, 'column': column, 'path': {'node': 'H', 'turn': 0}} for row in (0, 1) for column in (0, 1)]}
        text, first, number = tile.register(SET, tile.tile_records(made, 'Concrete'), 'New_Group', 2, 2)
        self.assertEqual((first, number), (2, 1))
        self.assertIn('[TILES]\r\nCount=6\r\n', text); self.assertIn('[GROUPS]\r\nCount=2\r\n', text)
        self.assertLess(text.index('[TILE5]'), text.index('[GROUPS]'))  # tiles stay ahead of the groups
        self.assertIn('[TILE1]\r\nModel=b\r\n', text); self.assertIn('[GROUP0]\r\nName=Old\r\nRows=1\r\nColumns=1\r\nTile0=1\r\n', text)
        self.assertTrue(text.endswith('[GROUP1]\r\nName=New_Group\r\nRows=2\r\nColumns=2\r\nTile0=2\r\nTile1=3\r\nTile2=4\r\nTile3=5\r\n'))
        self.assertNotIn('\n', text.replace('\r\n', ''))  # the file's own line ends throughout
        with self.assertRaisesRegex(ValueError, 'already lists'):
            tile.register(text, tile.tile_records(made, 'Concrete'), 'Another', 2, 2)
        with self.assertRaisesRegex(ValueError, 'already has a group'):
            tile.register(SET, tile.tile_records(made, 'Concrete'), 'Old', 2, 2)

    def test_the_area_map_picture_shows_each_tile_from_above_with_north_at_the_top(self):
        corners, faces = box((-2, 2, 0), (2, 4, 3))  # a red block in the north half of one tile
        pictures = tile.minimaps(corners, np.zeros((len(corners), 2)), faces, np.array([[[1.0, 0.0, 0.0]]]), 1, 1, np.array([-5.0, -5.0]), (0.2, 0.3, 0.4))
        picture = pictures[(0, 0)]; self.assertEqual(picture.shape, (tile.MINIMAP, tile.MINIMAP, 3))
        np.testing.assert_allclose(picture[5, 16], [1, 0, 0]); np.testing.assert_allclose(picture[26, 16], [0.2, 0.3, 0.4])  # row 0 is the north edge
        np.testing.assert_allclose(picture[5, 2], [0.2, 0.3, 0.4])

    def test_a_tile_carries_lights_a_fading_top_with_its_lid_and_halos_that_belong_to_the_night(self):
        walk = (np.array([[-5.0, -5, 0], [5, -5, 0], [-5, 5, 0], [5, 5, 0]]), np.array([[2, 0, 3, tile.STONE], [3, 0, 1, tile.STONE]]))
        low = (np.array([[0.0, 0, 0], [1, 0, 0], [0, 0, 1]]), np.tile([0, 1.0, 0], (3, 1)), np.zeros((3, 2)), np.array([[0, 1, 2]]), False)
        top = (low[0] + [0, 0, 3], low[1], low[2], low[3], True)
        sheet = lambda bottom: [((1.0, 0.5, bottom), (0.0, 1.0)), ((-1.0, 0.5, bottom), (1.0, 1.0)), ((-1.0, 0.5, bottom + 1), (1.0, 0.0)), ((1.0, 0.5, bottom + 1), (0.0, 0.0))]
        both = np.full((24, 48), 0.01)  # a card's light, lit all over: 11.52 square metres of it, half above the middle of the card
        text = tile.model_text('ek_test_t00', [low, top], 'ek_test', 'pavement', [sheet(1.0), sheet(2.0), sheet(3.0)], walk, lights=[(1.0, 2.0, 4.0), (0.0, 0.0, 7.1)], fade=2.5,
                               cap=[(-1.0, -1.0, 1.0, 1.0)], card_light=[both, both, both])
        with self.assertRaisesRegex(ValueError, 'its own light'):  # two cards and one light: refused, not paired off as far as they go
            tile.model_text('ek_test_t00', [low], 'ek_test', 'pavement', [sheet(1.0), sheet(2.0)], walk, fade=2.5, card_light=[both])
        geometry, _, animations = text.partition('endmodelgeom')
        nodes = {block.split('\n', 1)[0]: block for block in geometry.split('node ')[1:]}
        self.assertIn('  tilefade 0', nodes['trimesh ek_test_t00_m0']); self.assertIn('  tilefade 1', nodes['trimesh ek_test_t00_m1'])
        self.assertIn('  tilefade 0', nodes['trimesh ek_test_t00_halo0']); self.assertIn('  tilefade 1', nodes['trimesh ek_test_t00_halo3'])  # the sign's light goes with the sign
        # The sheet from 2 to 3 metres has light on both sides of the fade height: it is cut there, the lower half staying and the upper going, each with its half of the picture.
        under, over = nodes['trimesh ek_test_t00_halo1'], nodes['trimesh ek_test_t00_halo2']
        self.assertIn('  tilefade 0', under); self.assertIn('    -1.00000 0.50000 2.50000', under); self.assertNotIn('3.00000', under); self.assertIn('    1.00000 0.50000 0', under)
        self.assertIn('  tilefade 1', over); self.assertIn('    1.00000 0.50000 2.50000', over); self.assertNotIn(' 2.00000', over); self.assertIn('    0.00000 0.50000 0', over)
        whole = tile.model_text('ek_test_t00', [low], 'ek_test', 'pavement', [sheet(2.0)], walk)  # with nothing to hide, nothing is cut
        # A card goes or stays whole with its light, wherever the height crosses the card: the glow under a sign goes with the sign, though most
        # of the card is under the height; the glow over a window stays, though most of the card is above it.
        sign, window = np.zeros((20, 48)), np.zeros((20, 48)); sign[:4] = 0.01; window[16:] = 0.01
        self.assertEqual(tile._level_cut(sheet(1.7), 2.5, sign), [(sheet(1.7), True)]); self.assertEqual(tile._level_cut(sheet(2.3), 2.5, window), [(sheet(2.3), False)])
        merged = np.zeros((20, 48)); merged[:4, :10] = 0.01; merged[4:] = 0.01  # a small sign standing right on a wide lit wall: one patch, a ninth of it above the height
        self.assertEqual([above for _, above in tile._level_cut(sheet(1.75), 2.5, merged)], [False, True])  # cut all the same: the sign reaches a quarter metre past the height
        speck = window.copy(); speck[0, :4] = 0.01  # a patch of 0.04 square metres above the height: too small to say anything
        self.assertEqual(tile._level_cut(sheet(2.3), 2.5, speck), [(sheet(2.3), False)])
        # One light the height passes through. With five centimetres of it under the height that is the sign's foot, and the card goes whole
        # with the sign; with a quarter metre under, the light is on both sides and the card is cut.
        tall = np.zeros((20, 48)); tall[:10] = 0.01
        self.assertEqual(tile._level_cut(sheet(1.95), 2.5, tall), [(sheet(1.95), True)])
        self.assertEqual([above for _, above in tile._level_cut(sheet(1.75), 2.5, tall)], [False, True])
        self.assertEqual(len(tile._level_cut(sheet(2.0), 2.5, sign + window)), 2)  # a sign over a window on one card: cut between them
        wall = np.zeros((20, 48)); wall[8:] = 0.01  # and so it is with a small sign over a tall lit wall, where the height crosses near the card's top
        self.assertEqual([above for _, above in tile._level_cut(sheet(1.75), 2.5, sign + wall)], [False, True])
        # A card whose light is not known is never cut and goes by its middle.
        self.assertEqual(tile._level_cut(sheet(2.3), 2.5), [(sheet(2.3), True)]); self.assertEqual(tile._level_cut(sheet(1.7), 2.5), [(sheet(1.7), False)])
        self.assertEqual(tile._level_cut(sheet(2.0), 2.5), [(sheet(2.0), True)])
        self.assertEqual(whole.count('node trimesh ek_test_t00_halo'), 1 + 4)  # the one card, and its line in each of the four animations
        lid = nodes['trimesh ek_test_t00_cap']  # drawn only while the top is hidden
        self.assertIn('  tilefade 2', lid); self.assertIn('  bitmap ek_black', lid); self.assertIn('    -1.00000 -1.00000 2.50000', lid); self.assertIn('  faces 2', lid)
        self.assertIn('  position 1.00000 2.00000 4.00000', nodes['light ek_test_t00ml1']); self.assertIn('  radius 14', nodes['light ek_test_t00ml2'])
        self.assertEqual([line.split()[1] for line in animations.splitlines() if line.startswith('newanim')], ['day', 'day2night', 'night', 'night2day'])
        day, night = animations.split('newanim night ')[0].split('newanim day2night')[0], animations.split('newanim night ')[1].split('doneanim')[0]
        self.assertEqual(day.count('      0.00000 0\n'), 4); self.assertEqual(night.count('      0.00000 1\n'), 4)  # every halo: clear by day, full by night
        plain = tile.model_text('ek_test_t00', [low[:4]], 'ek_test', 'pavement', [], walk)
        self.assertNotIn('newanim', plain); self.assertNotIn('node light', plain); self.assertNotIn('_cap', plain)

    def test_the_lid_follows_the_buildings_outline_and_the_lights_hang_over_open_ground(self):
        rows, columns, corner = tile.layout(SHOP[0]); found = tile.survey(*SHOP, rows, columns, corner)
        strips = tile.lid(found, 0, 0); area = sum((x1 - x0) * (y1 - y0) for x0, y0, x1, y1 in strips)
        self.assertTrue(18.0 <= area <= 21.0)  # the 6 by 3 metres the walls enclose, to the grain of the survey
        self.assertTrue(all(-3.2 <= x0 < x1 <= 3.2 and -2.2 <= y0 < y1 <= 1.2 for x0, y0, x1, y1 in strips))
        first, second = tile.light_places(found, 0, 0)
        self.assertEqual(found['material'][int((first[1] + 5) / CELL), int((first[0] + 5) / CELL)], tile.STONE); self.assertEqual(first[2], tile.LIGHT_HEIGHT)
        self.assertEqual(second, (0.0, 0.0, 4.5))  # over the middle, clear of the 3 metre roof

    def test_a_built_group_reports_its_pictures_lights_fading_faces_and_door(self):
        import tempfile
        from pathlib import Path
        from PIL import Image
        vertices, faces = SHOP
        # Its halo, as `glow.halo` gives one: a picture (not the tile's business), a card on the front wall from 1 to 3 metres, and that card's
        # light, lit all over. The light lies on both sides of the 2 metre fade height, so the tile carries the card as two.
        card = [((2.0, -2.04, 1.0), (0.0, 1.0)), ((-2.0, -2.04, 1.0), (1.0, 1.0)), ((-2.0, -2.04, 3.0), (1.0, 0.0)), ((2.0, -2.04, 3.0), (0.0, 0.0))]
        made = {'vertices': vertices, 'normals': np.tile([0.0, 0, 1], (len(vertices), 1)), 'uvs': np.zeros((len(vertices), 2)), 'faces': faces,
                'card': glow.Halo(None, [card], [np.full((48, 96), 1 / 576)])}
        with tempfile.TemporaryDirectory() as scratch:
            report = tile.group('ek_shop', made, scratch, ground='pavement', colour=np.full((2, 2, 3), 0.5), fade=2.0,
                                door={'at': [0.0, 1.0, 0.2], 'facing': 90.0, 'type': 58})
            one = report['tiles'][0]
            # The door is stated on the wall, looking north: its hook is drawn out to where a character can stand, and turned
            # as the set file turns a door (one that looks north is turned 180).
            self.assertEqual((one['image'], one['lights'], one['doors']), ('ek_shop_m00', 2, [{'type': 58, 'x': 0.0, 'y': 1.75, 'z': 0.2, 'orientation': 180.0, 'drawnOut': 0.75}]))
            self.assertTrue(0 < one['fadingFaces'] < one['faces']); self.assertEqual(report['fade'], 2.0)
            self.assertEqual(one['path'], {'node': 'U', 'turn': 90, 'exits': 'NWSE', 'offPath': 0}); self.assertEqual(report['notes'], [])  # as `nodes` gives the shop
            # A node stated in the game set ({"t<row><column>": ...}) is the tile's.
            stated = tile.group('ek_shop', made, Path(scratch) / 'stated', ground='pavement', nodes={'t00': {'node': 'A', 'turn': 0}})
            self.assertEqual(stated['tiles'][0]['path'], {'node': 'A', 'turn': 0, 'exits': 'NWSE', 'offPath': 0})
            with Image.open(Path(scratch) / 'ek_shop_m00.tga') as picture:
                self.assertEqual((picture.size, picture.mode), ((tile.MINIMAP, tile.MINIMAP), 'RGB'))
            self.assertTrue((Path(scratch) / 'ek_black.tga').is_file())
            text = (Path(scratch) / 'ek_shop_t00.mdl').read_text(encoding='cp1252')
            self.assertIn('node trimesh ek_shop_t00_cap', text); self.assertIn('node light ek_shop_t00ml2', text)
            geometry = text.split('endmodelgeom')[0]; self.assertEqual(geometry.count('node trimesh ek_shop_t00_halo'), 2); self.assertIn('    2.00000 -2.04000 2.00000', geometry)
            with self.assertRaisesRegex(ValueError, 'between the slab and the roof'):
                tile.group('ek_shop', made, Path(scratch) / 'again', ground='pavement', fade=9.0)


    def test_a_fence_is_shared_out_among_the_tiles_it_stands_in_and_shows_its_own_picture(self):
        import tempfile
        from pathlib import Path
        vertices, faces = scene(box((-9, -4, 0), (9, 4, 0.2)), box((-8, -3, 0.2), (8, 3, 3)))  # a building two tiles wide
        wire = convert.sheets([{'from': [-8.5, 3.5], 'to': [8.5, 3.5], 'z': [0.2, 2.0], 'pitch': 0.09, 'wire': 0.016}])
        made = {'vertices': vertices, 'normals': np.tile([0.0, 0, 1], (len(vertices), 1)), 'uvs': np.zeros((len(vertices), 2)), 'faces': faces, 'card': None, 'wire': wire}
        bare = {**made, 'wire': None}
        with tempfile.TemporaryDirectory() as scratch:
            fenced = tile.group('ek_long', made, Path(scratch) / 'a', ground='pavement'); plain = tile.group('ek_long', bare, Path(scratch) / 'b', ground='pavement')
            self.assertEqual((fenced['rows'], fenced['columns']), (1, 2))
            more = [one['faces'] - other['faces'] for one, other in zip(fenced['tiles'], plain['tiles'])]
            self.assertEqual(sum(more), len(wire['faces'])); self.assertTrue(all(count > 0 for count in more))  # every square in one tile, some in each
            # A fence closes the ground it stands on, though its sheets are no part of the model's mesh: a generator leaves
            # the frames empty, and without the sheets the walkmesh between two posts would be open (review, 2026-11-12).
            rows, columns, corner = tile.layout(vertices); under = lambda found: found['material'][int((3.5 - corner[1]) / CELL + 1e-6), 8:-8]
            self.assertTrue((under(tile.survey(vertices, faces, rows, columns, corner)) == tile.STONE).all())
            self.assertTrue((under(tile.survey(vertices, faces, rows, columns, corner, barrier=(wire['vertices'], wire['faces']))) == tile.NONWALK).all())  # closed, and seen through
            self.assertNotEqual([one['walkFaces'] for one in fenced['tiles']], [one['walkFaces'] for one in plain['tiles']])
            faded = tile.group('ek_long', made, Path(scratch) / 'c', ground='pavement', fade=1.0); unfenced = tile.group('ek_long', bare, Path(scratch) / 'd', ground='pavement', fade=1.0)
            hidden = [one['fadingFaces'] - other['fadingFaces'] for one, other in zip(faded['tiles'], unfenced['tiles'])]
            self.assertTrue(all(0 < count < extra for count, extra in zip(hidden, more)))  # the squares above the fade height are counted as hidden too
            for one in fenced['tiles']:
                text = (Path(scratch) / 'a' / (one['model'] + '.mdl')).read_text(encoding='cp1252')
                self.assertIn('  bitmap ek_long_w\n', text); self.assertIn('  bitmap ek_long\n', text)
                self.assertNotIn('ek_long_w', (Path(scratch) / 'b' / (one['model'] + '.mdl')).read_text(encoding='cp1252'))

    def test_a_group_holds_other_models_placed_in_it_each_with_its_own_picture(self):
        """User, 2026-11-12: the concept's whole scene is the group, and it need not be one mesh. A model placed in the
        group is cut into its tiles with its own picture, halo and fence, and closes the ground it stands on."""
        import tempfile
        from pathlib import Path
        vertices, faces = scene(box((-4, -3, 0), (4, 3, 0.2)), box((-3, -2, 0.2), (3, 1, 3)))  # a building two tiles wide, with what is placed
        flat = lambda points, triangles, **more: {'vertices': points, 'normals': np.tile([0.0, 0, 1], (len(points), 1)), 'uvs': np.zeros((len(points), 2)),
                                                  'faces': triangles, 'card': None, 'wire': None, **more}
        building = flat(vertices, faces)
        crate = flat(*box((-0.5, -0.5, 0), (0.5, 0.5, 1.0)))
        card = [((0.4, -0.52, 0.2), (0.0, 1.0)), ((-0.4, -0.52, 0.2), (1.0, 1.0)), ((-0.4, -0.52, 0.8), (1.0, 0.0)), ((0.4, -0.52, 0.8), (0.0, 0.0))]
        lamp = flat(*box((-0.2, -0.5, 0), (0.2, 0.5, 1.0)), card=glow.Halo(None, [card], [None]))
        crate_there = convert.place(crate, [8.0, 0.0, 0.2]); lamp_there = convert.place(lamp, [-8.0, 0.0, 0.2], 90)
        np.testing.assert_allclose(lamp_there['card'].cards[0][0][0], (-7.48, 0.4, 0.4))  # turned a quarter: its card faces east now
        with tempfile.TemporaryDirectory() as scratch:
            report = tile.group('ek_yard', building, Path(scratch), ground='pavement', parts=[('ek_yardp1', crate_there, None), ('ek_yardp2', lamp_there, None)])
            self.assertEqual((report['rows'], report['columns']), (1, 2))  # the group grew to hold what is placed in it
            texts = [(Path(scratch) / f'{one["model"]}.mdl').read_text(encoding='cp1252') for one in report['tiles']]
            self.assertIn('  bitmap ek_yardp2\n', texts[0]); self.assertIn('  bitmap ek_yardp2_h\n', texts[0]); self.assertNotIn('ek_yardp1', texts[0])
            self.assertIn('  bitmap ek_yardp1\n', texts[1]); self.assertIn('  bitmap ek_yard\n', texts[0] + texts[1])
            self.assertEqual(sum(one['faces'] for one in report['tiles']), len(faces) + 2 * len(BOX))
            rows, columns, corner = tile.layout(np.vstack([vertices, crate_there['vertices'], lamp_there['vertices']]))
            found = tile.survey(np.vstack([vertices, crate_there['vertices']]), np.vstack([faces, crate['faces'] + len(vertices)]), rows, columns, corner)
            self.assertEqual(found['material'][int((0 - corner[1]) / CELL), int((8 - corner[0]) / CELL)], tile.NONWALK)  # the crate is walked round
            with self.assertRaisesRegex(ValueError, 'texture of its own'):
                tile.group('ek_yard', building, Path(scratch) / 'again', ground='pavement', parts=[('ek_yard', crate_there, None)])
            # A model placed twice comes once for each place and is joined into one model of the group, halo cards and all.
            second = convert.place(lamp, [-8.0, 2.0, 0.2], 90)
            joined, = tile.merge_parts([('ek_yardp2', lamp_there, None), ('ek_yardp2', second, None)])
            self.assertEqual((len(joined[1]['vertices']), len(joined[1]['card'].cards)), (2 * len(lamp['vertices']), 2))
            np.testing.assert_array_equal(joined[1]['faces'][len(BOX):], lamp['faces'] + len(lamp['vertices']))
            twice = tile.group('ek_yard', building, Path(scratch) / 'twice', ground='pavement', parts=[('ek_yardp2', lamp_there, None), ('ek_yardp2', second, None)])
            self.assertEqual(sum(one['faces'] for one in twice['tiles']), len(faces) + 2 * len(BOX))

    def test_a_part_laid_underfoot_is_walked_across_and_may_run_off_the_group(self):
        """User, 2026-11-13: the rail freight depot's tracks run through it and on into the tiles beside it. Surveyed,
        a track is a slab that reaches the group's edges, and the group is refused; laid underfoot it is drawn in the
        tiles and the ground is walked flat across it."""
        import tempfile
        vertices, faces = scene(box((-4, -3, 0), (4, 3, 0.2)), box((-3, -2, 0.2), (3, 1, 3)))
        flat = lambda points, triangles, **more: {'vertices': points, 'normals': np.tile([0.0, 0, 1], (len(points), 1)), 'uvs': np.zeros((len(points), 2)),
                                                  'faces': triangles, 'card': None, 'wire': None, **more}
        building, track = flat(vertices, faces), flat(*box((-10, 4.5, 0), (10, 6.1, 0.31)))
        with tempfile.TemporaryDirectory() as scratch:
            with self.assertRaisesRegex(ValueError, 'edge of its tiles'):
                tile.group('ek_yard', building, Path(scratch) / 'a', ground='pavement', parts=[('ek_yardp1', track, None)])
            laid = tile.group('ek_yard', building, Path(scratch) / 'b', ground='pavement', parts=[('ek_yardp1', {**track, 'underfoot': True}, None)])
            self.assertEqual((laid['rows'], laid['columns']), (1, 2))  # the group is as long as the track
            self.assertEqual(sum(one['faces'] for one in laid['tiles']), len(faces) + len(BOX))
            rows, columns, corner = tile.layout(np.vstack([vertices, track['vertices']]))
            roomy = tile.read_walk(Path(scratch) / 'b' / tile.WALK_PICTURE)
            under = slice(int((4.5 - corner[1]) / CELL), int((6.1 - corner[1]) / CELL))
            self.assertTrue(roomy[under].all())  # all along the track, to both edges of the group
            with self.assertRaisesRegex(ValueError, 'no higher than the knee'):
                tile.group('ek_yard', building, Path(scratch) / 'c', ground='pavement', parts=[('ek_yardp1', {**flat(*box((-10, 4.5, 0), (10, 6.1, 0.6))), 'underfoot': True}, None)])

    def test_a_door_hook_is_drawn_out_onto_open_ground_and_turned_as_the_set_file_turns_doors(self):
        """The Ares Depot's hook lay on its door leaf, inside the wall's closed ground, turned by the way the door faces:
        the invisible door stood out of the wall at a right angle and a player sent to it never arrived (client, 2026-11-11)."""
        vertices, faces = SHOP; rows, columns, corner = tile.layout(vertices); found = tile.survey(vertices, faces, rows, columns, corner)
        self.assertEqual(tile.doorstep(found, corner, [0.0, 1.0, 0.2], 90.0), ((0.0, 1.75, 0.2), 180.0, 0.75))  # north wall
        self.assertEqual(tile.doorstep(found, corner, [-3.0, 0.0, 0.2], 180.0), ((-3.5, 0.0, 0.2), 270.0, 0.5))  # west wall
        spot, _, drawn = tile.doorstep(found, corner, [0.0, 1.0, 0.2], 90.0)
        near = np.floor((np.array(spot[:2]) + [[-tile.DOOR_SIDE, -tile.DOOR_ROOM], [tile.DOOR_SIDE, tile.DOOR_ROOM]] - corner) / CELL).astype(int)
        self.assertTrue((found['material'][near[0, 1]:near[1, 1] + 1, near[0, 0]:near[1, 0] + 1] == tile.STONE).all())
        with self.assertRaisesRegex(ValueError, 'no open ground'):  # a door in the middle of the building
            tile.doorstep(found, corner, [0.0, -1.5, 0.2], 90.0)
        # The hook keeps the height of the door's foot: drawn out from a door on a high sill it would hang over the ground.
        with self.assertRaisesRegex(ValueError, 'on a sill or steps'):
            tile.doorstep(found, corner, [0.0, 1.0, 1.2], 90.0)
    def test_a_strip_of_slab_too_narrow_for_the_ramp_is_still_climbed(self):
        # Strips six metres long and 0.2 high across one tile. One a metre wide has no cell deeper than the ramp, so no line but its own
        # edge: it is up over its middle half metre all the same, climbed over the quarter metre either side.
        height = lambda south, north, y: ground(*floor(tile.survey(*scene(box((-3, south, 0), (3, north, 0.2))), 1, 1, np.array([-5.0, -5.0])))[:2], 0.1, y)[0]
        self.assertEqual([round(float(height(-0.5, 0.5, y)), 3) for y in (-0.6, -0.375, -0.2, 0.0, 0.2, 0.375, 0.6)], [0.0, 0.1, 0.2, 0.2, 0.2, 0.1, 0.0])
        self.assertEqual([round(float(height(-0.5, 0.25, y)), 3) for y in (-0.375, -0.125, 0.125)], [0.1, 0.2, 0.1])  # three quarters of a metre: up over its middle cell
        self.assertEqual(round(float(height(-0.25, 0.25, 0.0)), 3), 0.0)  # half a metre: too narrow to climb, left on the ground
        # A slab wide enough for the ramp has no crest: it is climbed over its outer half metre as before.
        self.assertEqual([round(float(height(-1.0, 1.0, y)), 3) for y in (-0.875, -0.75, -0.5, 0.0)], [0.05, 0.1, 0.2, 0.2])

    def test_a_gap_too_narrow_to_stand_in_is_closed(self):
        # Two fence sections half a metre apart in front of a building, and a metre and a half apart further along: the
        # Saeder-Krupp yard's walkers went for the half-metre gaps and stopped at the fence (client, 2026-11-12).
        corner = np.array([-5.0, -5.0])
        found = tile.survey(*scene(box((-3, 1, 0), (3, 4, 3)), box((-4.5, -2.05, 0), (-1.25, -1.95, 2)), box((-0.75, -2.05, 0), (1.0, -1.95, 2)),
                                   box((2.5, -2.05, 0), (4.5, -1.95, 2))), 1, 1, corner)
        at = lambda x, y: (int((y + 5) / CELL), int((x + 5) / CELL)); material = found['material']
        self.assertEqual(int(material[at(-1.0, -2.0)]), tile.NONWALK)  # the half-metre gap: closed, so no walk is planned through it
        self.assertEqual(int(material[at(1.75, -2.0)]), tile.STONE)  # the metre and a half: still a way through
        self.assertEqual(int(material[at(0.0, -3.5)]), tile.STONE); self.assertEqual(int(material[at(0.0, 0.0)]), tile.STONE)
        open_ground = found['material'] == tile.STONE
        self.assertTrue((found['roomy'] == open_ground).all())  # what is left open has room to stand on, all of it

    def test_a_broad_floor_raised_past_the_knee_is_a_deck_walked_at_its_own_height(self):
        # A loading bay's floor 0.55 high, six metres by four, the building's wall along its back and a crate on it; south
        # of it a block as high but under two metres square, and a platform as broad but 0.9 high (the Saeder-Krupp
        # yard's bay, 2026-11-12).
        corner = np.array([-5.0, -5.0])
        found = tile.survey(*scene(box((-3, -2, 0), (3, 2, 0.55)), box((-3, 1.6, 0.55), (3, 2, 3)), box((-3, 2, 0), (3, 4.5, 3)), box((-0.5, -0.5, 0.55), (0.5, 0.5, 1.5)),
                                   box((-4.6, -4.6, 0), (-3.6, -3.0, 0.55)), box((0.5, -4.6, 0), (4.6, -2.4, 0.9))), 1, 1, corner)
        at = lambda x, y: (int((y + 5) / CELL), int((x + 5) / CELL)); material = found['material']
        self.assertEqual([int(material[at(x, y)]) for x, y in ((1.5, 0.0), (-2.0, -1.0), (0.0, 0.0), (0.0, 1.8), (-4.1, -3.8), (2.0, -3.5))],
                         [tile.STONE, tile.STONE, tile.NONWALK, tile.OBSCURING, tile.NONWALK, tile.NONWALK])  # the deck open; the crate, wall, block and high platform not
        vertices, flat, _ = floor(found)
        height = lambda x, y: round(float(ground(vertices, flat, x, y)[0]), 3)
        self.assertEqual([height(x, 0.0) for x in (-3.3, -3.0, -2.75, -2.5, -1.5, 1.5)], [0.0, 0.0, 0.275, 0.55, 0.55, 0.55])  # up over its outer half metre
        self.assertEqual((height(0.6, 0.0), height(1.5, 1.45)), (0.55, 0.55))  # beside the crate and up to the wall it keeps its height
        self.assertFalse(found['raised'][at(1.5, 0.0)])  # its edge is no slab's rim
        self.assertGreater(float(found['deck'].max()), 0.5); self.assertEqual(int((found['deck'] > 0.8).sum()), 0)
        self.assertEqual(len(np.unique(found['deck'][found['deck'] > 0])), 1)  # one deck, one height: its rim cells are not an ulp off it
        plain = tile.survey(*SHOP, 1, 1, corner)  # a group with no deck: nothing changes
        self.assertEqual((float(plain['deck'].max()), plain['lines']), (0.0, tile.survey(*SHOP, 1, 1, corner)['lines']))

    def test_a_platform_too_high_to_step_onto_is_walked_on_where_stairs_lead_up_to_it(self):
        """User, 2026-11-13: "the stairs up onto platform, and the platform itself should be walkable" (the rail freight
        depot's loading platform, 1.2 metres high with five steps at one end)."""
        corner = np.array([-5.0, -5.0]); platform = box((-2, -1, 0), (4, 2, 1.2))
        steps = [box((-2 - 0.3 * (4 - index), -0.5, 0), (-2, 1.5, 0.24 * (index + 1))) for index in range(4)]  # 0.24 risers, 0.3 treads
        at = lambda x, y: (int((y + 5) / CELL), int((x + 5) / CELL))
        found = tile.survey(*scene(platform, *steps), 1, 1, corner); material = found['material']
        self.assertEqual([int(material[at(x, y)]) for x, y in ((1.0, 0.5), (-2.6, 0.5), (1.0, 1.9), (3.9, 0.5), (1.0, -0.9), (-1.9, -0.8))],
                         [tile.STONE, tile.STONE, tile.NONWALK, tile.NONWALK, tile.NONWALK, tile.NONWALK])  # deck and stairs open; its edge closed
        vertices, flat, _ = floor(found)
        height = lambda x, y: round(float(ground(vertices, flat, x, y)[0]), 3)
        climb = [height(x, 0.5) for x in (-3.6, -3.1, -2.8, -2.5, -2.2, -1.5, 1.0)]
        self.assertLess(climb[0], 0.24); self.assertEqual((climb[-2], climb[-1]), (1.2, 1.2)); self.assertEqual(climb, sorted(climb))  # up the stairs onto the deck
        self.assertTrue(all(ground(vertices, flat, x, 0.5)[1] == tile.STONE for x in (-3.1, -2.5, -1.5)))
        roomy = found['roomy']; self.assertTrue(roomy[at(1.0, 0.5)] and roomy[at(-2.6, 0.5)])
        labels, _ = tile._masses(roomy); self.assertEqual(labels[at(1.0, 0.5)], labels[at(-4.5, -4.5)])  # one ground, by the stairs
        # Without the stairs, or with only a bench beside it, it stands in the way as before.
        for beside in ((), (box((-3, -0.5, 0), (-2, 1.5, 0.6)),)):
            self.assertEqual(int(tile.survey(*scene(platform, *beside), 1, 1, corner)['material'][at(1.0, 0.5)]), tile.NONWALK)

    def test_a_halo_as_glow_makes_it_is_shared_and_cut_by_its_own_light(self):
        # A wall facing front, 4 wide and 2 tall, with a wide window low on it and a small sign above, towards +x: one card, as `glow.halo` makes it.
        points = np.array([[2.0, 1.0, 0.0], [-2.0, 1.0, 0.0], [-2.0, 1.0, 2.0], [2.0, 1.0, 2.0]]); uvs = np.array([[0.0, 1.0], [1.0, 1.0], [1.0, 0.0], [0.0, 0.0]])
        where, covered = glow.position_map(points, uvs, np.array([[0, 1, 2], [0, 2, 3]]), 64)
        lit = glow.glow(np.full((64, 64, 3), 0.9), where, covered, [{'box': [[-1.5, 0.5, 0.2], [1.5, 1.5, 0.8]]}, {'box': [[0.5, 0.5, 1.4], [1.5, 1.5, 1.9]]}])
        made = glow.halo(lit, where, covered, reach=0.25, strength=0.5)
        self.assertEqual((len(made.cards), len(made.light), made.light[0].shape), (1, 1, made.image.size[::-1]))
        (card, light), = tile.share_cards(made.cards, 1, 1, np.array([-5.0, -5.0]), made.light)[(0, 0)]
        self.assertEqual(light.shape, made.light[0].shape); self.assertAlmostEqual(card[0][0][2], -0.3, delta=0.05); self.assertAlmostEqual(card[2][0][2], 2.4, delta=0.05)  # half a metre past the lights
        # The light's rows run from the card's top and its columns from the card's left, which is the model's +x: the sign is in the top left of it.
        rows, columns = light.shape; top = light[:rows // 2]
        self.assertAlmostEqual(float(top.sum()), 0.5, delta=0.2); self.assertAlmostEqual(float(light[rows // 2:].sum()), 1.8, delta=0.4)
        self.assertEqual(float(top[:, columns // 2:].sum()), 0.0)
        # Hidden from 1.1 metres up, between the two: the card is cut there. From 2.2, over both, or from 0, under both, it is whole with its lights.
        self.assertEqual([(round(piece[0][0][2], 6), round(piece[2][0][2], 6), above) for piece, above in tile._level_cut(card, 1.1, light)],
                         [(round(card[0][0][2], 6), 1.1, False), (1.1, round(card[2][0][2], 6), True)])
        self.assertEqual(tile._level_cut(card, 2.2, light), [(card, False)]); self.assertEqual(tile._level_cut(card, 0.0, light), [(card, True)])
        with self.assertRaisesRegex(ValueError, 'its own light'):
            tile.share_cards(made.cards, 1, 1, np.array([-5.0, -5.0]), [])

    def test_a_built_group_notes_ground_no_exit_reaches(self):
        import tempfile
        # The walled yard on a slab two tiles wide, its only gap three quarters of a metre: the yard's ground is in the west tile and no exit reaches it.
        vertices, faces = scene(box((-8.0, -4.6, 0), (8.0, 4.6, 0.1)), box((-4.0, -3.0, 0.1), (-3.6, 4.4, 3)), box((-4.0, -3.0, 0.1), (0.4, -2.6, 3)),
                                box((-4.0, 4.0, 0.1), (0.4, 4.4, 3)), box((0.0, -3.0, 0.1), (0.4, 3.25, 3)))
        made = {'vertices': vertices, 'normals': np.tile([0.0, 0, 1], (len(vertices), 1)), 'uvs': np.zeros((len(vertices), 2)), 'faces': faces, 'card': None}
        with tempfile.TemporaryDirectory() as scratch:
            report = tile.group('ek_yard', made, scratch, ground='pavement')
            roomy = tile.read_walk(Path(scratch) / tile.WALK_PICTURE)  # and its walk picture beside the tiles, a pixel a cell
        self.assertEqual((report['rows'], report['columns'], len(report['notes'])), (1, 2, 1))
        self.assertRegex(report['notes'][0], r'^ek_yard_t00: \d{3} walk cells that no walk from round the group is planned onto')
        self.assertEqual((roomy.shape, bool(roomy[0, 0]), bool(roomy[20, 40])), ((tile.CELLS, 2 * tile.CELLS), True, False))  # the yard's east wall at x 0.2

    def test_a_walk_picture_reads_back_as_the_ground_with_room_to_stand_on(self):
        import tempfile
        material = np.full((8, 12), tile.STONE); material[2:6, 3:6] = tile.OBSCURING; material[1, 8] = tile.NONWALK
        roomy = np.zeros(material.shape, bool); roomy[:, :2] = True
        picture = tile.walk_picture({'material': material, 'roomy': roomy})
        self.assertEqual((picture.size, picture.getpixel((0, 0)), picture.getpixel((4, 3)), picture.getpixel((8, 6)), picture.getpixel((11, 0))),
                         ((12, 8), tile.WALK_COLOURS['roomy'], tile.WALK_COLOURS['building'], tile.WALK_COLOURS['closed'], tile.WALK_COLOURS['narrow']))  # north up
        with tempfile.TemporaryDirectory() as scratch:
            picture.save(Path(scratch) / 'walk.png'); self.assertTrue((tile.read_walk(Path(scratch) / 'walk.png') == roomy).all())
            Image.new('RGB', (12, 8), (1, 2, 3)).save(Path(scratch) / 'other.png')
            with self.assertRaisesRegex(ValueError, 'not a walk picture'):
                tile.read_walk(Path(scratch) / 'other.png')

    def test_walkers_are_sent_to_each_side_of_what_stands_in_the_middle_and_into_a_yard_with_one_way_in(self):
        # Three tiles square, a walled yard in the middle, its walls a metre thick, its only way in a gap two metres wide high in the east wall.
        roomy = np.ones((120, 120), bool); roomy[20:100, 20:100] = False; roomy[24:96, 24:96] = True; roomy[88:96, 96:100] = True
        targets = tile.walk_targets(roomy)
        self.assertEqual({label: at for label, at in targets.items() if label != 'pocket'},
                         {'south': (15.125, 4.375), 'north': (15.125, 25.625), 'west': (4.375, 15.125), 'east': (25.625, 15.125)})  # half a metre short of the walls
        x, y = targets['pocket']; self.assertTrue(6.0 < x < 10.0 and 6.0 < y < 10.0, targets['pocket'])  # the yard's corner furthest round from the gap
        roomy[88:96, 96:100] = False  # walled in: the yard is no walk at all
        self.assertNotIn('pocket', tile.walk_targets(roomy))
        open_ground = np.ones((120, 120), bool); self.assertEqual(tile.walk_targets(open_ground), {})  # nothing across the middle, nothing round
        open_ground[0, 60] = False; self.assertNotIn('south', tile.walk_targets(open_ground))  # an edge closed where a side's walker would come in

    def test_of_nodes_that_say_as_much_the_one_that_reaches_most_ground_is_taken(self):
        # One tile, shut on the east, with three grounds that do not join: a large one north, a small one south-west, a middling one south-east.
        # The west side opens on two of them and goes with the south-west (its opening spans the side's middle). No letter has three exits
        # apart, so two are stated: north and south, the two largest grounds, not north and west, which the table of letters comes to first.
        material = np.full((tile.CELLS, tile.CELLS), tile.STONE)
        material[:, 36:] = tile.OBSCURING; material[20:22] = tile.OBSCURING; material[:20, 10:12] = tile.OBSCURING
        self.assertEqual(tile.path_node({'material': material}, 0, 0), {'node': 'Y', 'turn': 0, 'exits': 'NS', 'offPath': 200})

    def test_a_strip_too_narrow_to_stand_in_joins_nothing(self):
        # A building fills the tile but for a metre and a half along the north and half a metre down the middle. The strip down the middle
        # is no way south (the Ares Depot's walkers stopped at such a corner, 2026-11-11); a metre and a half is, and joins north to south.
        material = np.full((tile.CELLS, tile.CELLS), tile.OBSCURING)
        material[34:] = tile.STONE; material[:, 19:21] = tile.STONE
        self.assertEqual(tile.path_node({'material': material}, 0, 0)['exits'], 'N')
        material[:, 17:23] = tile.STONE
        self.assertEqual(tile.path_node({'material': material}, 0, 0), {'node': 'L', 'turn': 0, 'exits': 'NS', 'offPath': 0})

    def test_an_exit_lies_near_its_sides_middle_and_two_are_joined_only_where_a_walk_between_them_stays_near_the_straight_way(self):
        # The engine puts each exit at its side's middle. A building fills the tile but for its north strip: its west and east sides are
        # open only at their north ends, 3.5 metres from their middles, and are no exits; open 2 metres from them, they are.
        material = np.full((tile.CELLS, tile.CELLS), tile.OBSCURING); material[34:] = tile.STONE
        self.assertEqual(tile.path_node({'material': material}, 0, 0)['exits'], 'N')
        material[28:] = tile.STONE
        self.assertEqual(tile.path_node({'material': material}, 0, 0)['exits'], 'NWE')
        # Open ground with a fence across it 2.5 metres up, from the east side to 2.25 metres short of the west: walkers sent from the south
        # side's middle for the north's stopped against such a fence rather than go 3 metres aside round its end (the Saeder-Krupp yard,
        # client, 2026-11-12). The south is joined to nothing but the west, so it is left alone (U); the others are joined.
        material = np.full((tile.CELLS, tile.CELLS), tile.STONE); material[10:12, 9:] = tile.OBSCURING
        self.assertEqual(tile.path_node({'material': material}, 0, 0), {'node': 'U', 'turn': 90, 'exits': 'NWSE', 'offPath': 0})

    def test_a_group_takes_the_nodes_that_let_walks_reach_the_most_of_its_ground(self):
        # Two tiles, one over the other. The south one is open but for a block over its north half, through which a channel two metres wide
        # runs up its middle into a closed bay in the north one, as the Saeder-Krupp yard's bay opens off its apron. Alone, the south tile
        # leaves the channel's side alone (U), so no walk reaches the bay. Taken together, it joins that side to its south one (L).
        material = np.full((2 * tile.CELLS, tile.CELLS), tile.OBSCURING)
        material[:20] = tile.STONE; material[20:56, 16:24] = tile.STONE
        found = {'material': material}
        self.assertEqual(tile.path_node(found, 0, 0)['node'], 'U')
        self.assertEqual(tile.path_nodes(found, 2, 1), {(0, 0): {'node': 'L', 'turn': 0, 'exits': 'NS', 'offPath': 0},
                                                        (1, 0): {'node': 'N', 'turn': 180, 'exits': 'S', 'offPath': 0}})
        # A node the client has shown walks need is stated, and the others are chosen round it; it leaves only by open sides.
        self.assertEqual(tile.path_nodes(found, 2, 1, {(0, 0): ('A', 0)})[(0, 0)], {'node': 'A', 'turn': 0, 'exits': 'NWSE', 'offPath': 0})
        for stated, message in (({(1, 0): ('A', 0)}, 'only by sides open there'), ({(2, 0): ('A', 0)}, 'for a tile of the group'),
                                ({(0, 0): ('Q', 0)}, 'a letter of PATH_NODES')):
            with self.assertRaisesRegex(ValueError, message):
                tile.path_nodes(found, 2, 1, stated)

    def test_no_exit_is_left_cut_off_where_a_building_stands_across_a_tile_line(self):
        # Two tiles side by side, a building across the line between them in their north halves, as the rail freight depot's warehouse and
        # crane stand across the line between its middle columns. Each tile alone can leave the shared side by itself (U) or its north side
        # (U turned): both reach all its ground. Left alone on both, the shared side joins nothing but itself, and the walker sent to the
        # target there, straight in from the middle of the group's south edge, walked straight at it and stopped short (client, 2026-11-13).
        material = np.full((tile.CELLS, 2 * tile.CELLS), tile.STONE); material[26:, 14:66] = tile.OBSCURING
        found = {'material': material}
        self.assertEqual([tile.path_node(found, 0, column)['node'] + str(tile.path_node(found, 0, column)['turn']) for column in (0, 1)], ['U180', 'U0'])
        self.assertEqual(tile.cut_off({(0, column): tile.path_node(found, 0, column) for column in (0, 1)}), [(0, 0, 'E'), (0, 1, 'W')])
        nodes = tile.path_nodes(found, 1, 2)
        self.assertEqual(tile.cut_off(nodes), []); self.assertEqual({key: (one['node'], one['turn']) for key, one in nodes.items()}, {(0, 0): ('U', 270), (0, 1): ('U', 0)})
        self.assertEqual(tile.walk_targets(tile._roomy(material == tile.STONE))['south'], (10.125, 5.875))  # on the line, by the shared side

    def test_a_tiles_record_names_its_picture_lights_and_doors_and_a_door_block_follows_it(self):
        made = {'rows': 2, 'columns': 2, 'tiles': [{'model': f'ek_test_t{row}{column}', 'row': row, 'column': column, 'path': {'node': 'H', 'turn': 0}, 'lights': 2,
                                                    'image': f'ek_test_m{row}{column}', 'doors': [{'type': 58, 'x': 4.75, 'y': -1.1, 'z': 0.18, 'orientation': 90.0}] if (row, column) == (1, 0) else []}
                                                   for row in (0, 1) for column in (0, 1)]}
        records = tile.tile_records(made, 'Concrete'); third = dict(records[2])
        self.assertEqual((third['MainLight1'], third['MainLight2'], third['SourceLight1'], third['Doors'], third['ImageMap2D']), (1, 1, 0, 1, 'ek_test_m10'))
        self.assertEqual(dict(records[0])['Doors'], 0)
        text, first, _ = tile.register(SET, records, 'New_Group', 2, 2, tile.doors(made))
        self.assertIn('ImageMap2D=ek_test_m10\r\n\r\n[TILE4DOOR0]\r\nType=58\r\nX=4.75\r\nY=-1.1\r\nZ=0.18\r\nOrientation=90.0\r\n\r\n[TILE5]\r\n', text)
        self.assertEqual(text.count('DOOR0]'), 1)

    def test_a_group_already_in_the_set_file_is_written_again_under_the_numbers_it_has(self):
        import tempfile
        from pathlib import Path
        bare = {'rows': 2, 'columns': 2, 'tiles': [{'model': f'ek_test_t{row}{column}', 'row': row, 'column': column, 'path': {'node': 'H', 'turn': 0}} for row in (0, 1) for column in (0, 1)]}
        text, _, _ = tile.register(SET.replace('[GENERAL]', '[TERRAIN0]\r\nName=Concrete\r\n\r\n[GENERAL]'), tile.tile_records(bare, 'Concrete'), 'New_Group', 2, 2)
        full = {**bare, 'tiles': [{**one, 'lights': 2, 'image': 'ek_test_m' + one['model'][-2:], 'doors': [{'type': 58, 'x': 1.0, 'y': 2.0, 'z': 0.2, 'orientation': 0.0}] if one['model'].endswith('10') else []}
                                  for one in bare['tiles']]}
        again, first = tile.revise(text, tile.tile_records(full, 'Concrete'), tile.doors(full))
        self.assertEqual(first, 2); self.assertEqual(again.count('[TILE'), text.count('[TILE') + 1)  # the same tiles, and one door block
        self.assertIn('[TILE4]\r\nModel=ek_test_t10\r\n', again); self.assertIn('ImageMap2D=ek_test_m10\r\n\r\n[TILE4DOOR0]\r\nType=58\r\n', again)
        self.assertIn('[TILE1]\r\nModel=b\r\n', again); self.assertTrue(again.endswith(text[text.index('[GROUPS]'):]))  # nothing else moved
        once_more, _ = tile.revise(again, tile.tile_records(full, 'Concrete'), tile.doors(full))
        self.assertEqual(once_more, again)  # the door block is replaced, not added to
        with self.assertRaisesRegex(ValueError, 'does not list exactly one'):
            tile.revise(SET, tile.tile_records(full, 'Concrete'), tile.doors(full))
        with tempfile.TemporaryDirectory() as scratch:  # through the install: no palette is touched for a group already there
            path = Path(scratch) / 't.set'; path.write_bytes(text.encode('cp1252'))
            prepared = tile.prepare(path, Path(scratch) / 'none.itp', full, terrain='Concrete', group_name='New_Group', label='New Group')
            self.assertIsNone(prepared['document']); self.assertEqual(tile.commit(prepared), {'firstTile': 2, 'group': 1})
            self.assertEqual(path.read_bytes().decode('cp1252'), again)
            half = text.replace('Model=ek_test_t11', 'Model=other')
            path.write_bytes(half.encode('cp1252'))
            with self.assertRaisesRegex(ValueError, 'some of the group'):
                tile.prepare(path, Path(scratch) / 'none.itp', full, terrain='Concrete', group_name='New_Group', label='New Group')

    def test_installing_a_group_again_ships_its_files_and_enters_it_and_its_lights_in_the_catalog(self):
        import argparse, contextlib, io, json, tempfile
        from pathlib import Path
        from . import additions, catalog, convert
        made = {'rows': 2, 'columns': 2, 'tiles': [{'model': f'ek_test_t{row}{column}', 'row': row, 'column': column, 'path': {'node': 'H', 'turn': 0}, 'lights': 2, 'doors': []}
                                                   for row in (0, 1) for column in (0, 1)]}
        text, _, _ = tile.register(SET.replace('[GENERAL]', '[TERRAIN0]\r\nName=Concrete\r\n\r\n[GENERAL]'), tile.tile_records(made, 'Concrete'), 'New_Group', 2, 2)
        with tempfile.TemporaryDirectory() as scratch:
            repo = Path(scratch); pack, dark, built, tileset = repo / 'tiles', repo / 'shared', repo / 'built' / 'ek_test', repo / ('srn_t_' + 'x')
            for folder in (pack, dark, tileset, built / 'compiled', built / 'source', built / 'shared', repo / 'sets', repo / 'docs'):
                folder.mkdir(parents=True)
            (tileset / 'x.set').write_bytes(text.encode('cp1252'))
            group = {'ground': 'pavement', 'group': 'New_Group', 'label': 'New Group', 'sets': {'x': 'Concrete'}}
            (repo / 'sets' / 'shop.json').write_text(json.dumps({'models': {'ek_test': {'source': 'models/a', 'height': 4.0, 'tiles': group}}}), encoding='utf-8')
            (built / 'report.json').write_text(json.dumps(made), encoding='utf-8')
            for one in made['tiles']:
                (built / 'compiled' / f'{one["model"]}.mdl').write_bytes(b'compiled'); (built / 'source' / f'{one["model"]}.wok').write_bytes(b'walk')
            (built / 'source' / 'ek_test_m00.tga').write_bytes(b'map')
            files = {name: name.encode() for name in ('ek_test.mtr', 'ek_test_i.dds', 'ek_test_o.mtr', 'ek_test_o.dds', 'ek_test_h.mtr', convert.HALO_OUT + '.mtr')}
            for name, content in files.items():
                (built / 'shared' / name).write_bytes(content)
            listed = repo / 'docs' / 'catalog.json'
            catalog.save(listed, {'schemaVersion': 1, 'kind': catalog.KIND, 'placeables': [], 'tileGroups': [], 'baseline': {
                'placeables': {'table': 'tables/placeables.2da', 'lastImportedRow': 7}, 'tilesets': {'x': {'set': 'x.set', 'importedTiles': 2, 'importedGroups': 1}}}})

            def run(provenance=None):
                with contextlib.redirect_stdout(io.StringIO()) as said:
                    additions.command_install(argparse.Namespace(models=str(repo / 'sets' / 'shop.json'), built=str(repo / 'built'), model='ek_test', repo=str(repo), pack='tiles',
                                                                 dark_pack='shared', catalog='docs/catalog.json', provenance=provenance))
                return json.loads(said.getvalue())
            with self.assertRaisesRegex(ValueError, 'name its PROVENANCE.md section'):
                run()
            self.assertEqual(list(pack.iterdir()), [])  # refused before anything was copied
            self.assertEqual(run('Shop tiles')['sets'], {'x': {'firstTile': 2, 'group': 1}}); run()  # and again: the group stands
            entry, = catalog.load(listed)['tileGroups']
            self.assertEqual((entry['tileset'], entry['group'], entry['tiles'], entry['models'][0], entry['provenance']), ('x', 1, [2, 3, 4, 5], 'ek_test_t00', 'Shop tiles'))
            self.assertEqual(entry['lights'], {'lit': 'ek_test', 'out': 'ek_test_o', 'glow': 'ek_test_i', 'halo': 'ek_test_h', 'dark': convert.HALO_OUT})
            self.assertEqual({path.name: path.read_bytes() for path in (built / 'shared').iterdir()}, files)  # what was built is only read
            self.assertTrue((dark / (convert.HALO_OUT + '.mtr')).is_file()); self.assertFalse((pack / (convert.HALO_OUT + '.mtr')).exists())  # the shared dark halo has one home
            self.assertTrue(all((pack / name).is_file() for name in ('ek_test_t10.mdl', 'ek_test_t10.wok', 'ek_test_m00.tga', 'ek_test_o.mtr')))
            self.assertEqual((tileset / 'x.set').read_bytes().count(b'Model=ek_test_t'), 4)  # written again in place, not appended
            lit = ('ek_test_i.dds', 'ek_test_o.mtr', 'ek_test_o.dds', 'ek_test_h.mtr')
            for name in lit:  # built again with no lit parts
                (built / 'shared' / name).unlink()
            self.assertEqual(sorted(run()['removed']), sorted(lit))
            self.assertNotIn('lights', catalog.load(listed)['tileGroups'][0]); self.assertFalse(any((pack / name).exists() for name in lit))
            # A part the group placed when it was installed before, and places no longer, takes its pictures with it.
            dropped = ('ek_testp2.mtr', 'ek_testp2.dds', 'ek_testp2_n.dds', 'ek_testp2_i.dds')
            others = ('ek_testp3.dds', 'ek_testp3_t00.mdl')  # another set's group that happens to be called so keeps its maps
            for name in (*dropped, *others, 'ek_testp1.dds'):
                (pack / name).write_bytes(b'old')
            (built / 'report.json').write_text(json.dumps({**made, 'parts': {'ek_crate': 'ek_testp1'}}), encoding='utf-8'); (built / 'shared' / 'ek_testp1.dds').write_bytes(b'new')
            self.assertEqual(sorted(run()['removed']), sorted(dropped))
            self.assertEqual((pack / 'ek_testp1.dds').read_bytes(), b'new'); self.assertFalse(any((pack / name).exists() for name in dropped))
            self.assertTrue(all((pack / name).exists() for name in others))

    def test_the_palette_offers_the_group_among_the_groups_once(self):
        document = {'MAIN': {'value': [{'ID': {'value': 0}, 'LIST': {'value': []}}, {'ID': {'value': 1}, 'LIST': {'value': []}}]}}
        tile.palette(document, 'New Group 2x2', 'ek_test_t00')
        self.assertEqual(document['MAIN']['value'][1]['LIST']['value'], [{'__struct_id': 0, 'NAME': {'type': 'cexostring', 'value': 'New Group 2x2'},
                                                                         'RESREF': {'type': 'resref', 'value': 'ek_test_t00'}}])
        self.assertEqual(document['MAIN']['value'][0]['LIST']['value'], [])
        with self.assertRaisesRegex(ValueError, 'already lists'):
            tile.palette(document, 'Again', 'ek_test_t00')
        tile.palette(document, 'Kiosk', 'ek_kiosk_t00', single=True)  # a one-tile group is a feature, as the palettes keep them
        self.assertEqual([row['RESREF']['value'] for row in document['MAIN']['value'][0]['LIST']['value']], ['ek_kiosk_t00'])
        self.assertEqual(len(document['MAIN']['value'][1]['LIST']['value']), 1)


if __name__ == '__main__':
    unittest.main()
