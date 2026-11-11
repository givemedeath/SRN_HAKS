"""A building becomes tiles: its walkmesh closes what stands in the way, and its records join a set file untouched."""
import unittest

import numpy as np

from . import tile

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
        shared = tile.share_cards([card], 2, 2, np.array([-10.0, -10.0]))
        self.assertEqual(sorted(shared), [(1, 0), (1, 1)])  # the north row, both tiles
        east, west = shared[(1, 1)][0], shared[(1, 0)][0]
        np.testing.assert_allclose([place for place, _ in east], [[-1, -2, 1], [-5, -2, 1], [-5, -2, 2], [-1, -2, 2]])  # in the tile's own space
        np.testing.assert_allclose([place[0] for place, _ in west], [5, 3, 3, 5])
        np.testing.assert_allclose([uv[0] for _, uv in east], [0.0, 0.4, 0.4, 0.0]); np.testing.assert_allclose([uv[0] for _, uv in west], [0.4, 0.6, 0.6, 0.4])

    def test_a_card_on_a_side_wall_is_cut_along_the_wall_it_stands_on(self):
        # Facing +X at x = 3: seen from the east its left corner is the southern one. It crosses from the south row into the north.
        card = [((3.0, -2.0, 1.0), (0.0, 0.5)), ((3.0, 4.0, 1.0), (0.6, 0.5)), ((3.0, 4.0, 2.0), (0.6, 0.0)), ((3.0, -2.0, 2.0), (0.0, 0.0))]
        shared = tile.share_cards([card], 2, 2, np.array([-10.0, -10.0]))
        self.assertEqual(sorted(shared), [(0, 1), (1, 1)])  # the east column, both rows
        south, north = shared[(0, 1)][0], shared[(1, 1)][0]
        np.testing.assert_allclose([place for place, _ in south], [[-2, 3, 1], [-2, 5, 1], [-2, 5, 2], [-2, 3, 2]])
        np.testing.assert_allclose([place[1] for place, _ in north], [-5, -1, -1, -5])
        np.testing.assert_allclose([uv[0] for _, uv in south], [0.0, 0.2, 0.2, 0.0]); np.testing.assert_allclose([uv[0] for _, uv in north], [0.2, 0.6, 0.6, 0.2])

    def nodes(self, model):
        """{(row, column): (node, turn, exits, offPath)} of the group a model takes."""
        rows, columns, corner = tile.layout(model[0]); found = tile.survey(*model, rows, columns, corner)
        return {(row, column): tuple(tile.path_node(found, row, column).values()) for row in range(rows) for column in range(columns)}

    def test_each_tile_of_a_group_leaves_by_the_sides_its_ground_reaches(self):
        # A building across the middle of four tiles: each tile is walked round its outer corner. H leaves west and south; a turn is counter-clockwise.
        wide = scene(box((-6, -5.3, 0), (6.1, 5.4, 0.2)), box((-5.6, -5.1, 0.2), (5.7, 5.2, 3)))
        self.assertEqual(self.nodes(wide), {(0, 0): ('H', 0, 'WS', 0), (0, 1): ('H', 90, 'SE', 0), (1, 1): ('H', 180, 'NE', 0), (1, 0): ('H', 270, 'NW', 0)})
        # One tile with the shop in its middle and ground all round it: every side, all joined.
        self.assertEqual(self.nodes(SHOP), {(0, 0): ('A', 0, 'NWSE', 0)})
        # A row of three with a long shed through them: the ends are walked round, the middle is crossed by nobody, its two sides apart.
        shed = scene(box((-13, -3.5, 0), (13, 3.5, 0.2)), box((-12, -2.5, 0.2), (12, 2.5, 3)))
        self.assertEqual(self.nodes(shed), {(0, 0): ('I', 0, 'NWS', 0), (0, 1): ('Y', 0, 'NS', 0), (0, 2): ('I', 180, 'NSE', 0)})
        # Three by three under one block: the middle tile is closed whole, a tile at the middle of a side is left only outwards, a corner tile by its two outer sides.
        block = scene(box((-13, -13, 0), (13, 13, 0.2)), box((-11, -11, 0.2), (11, 11, 3)))
        found = self.nodes(block)
        self.assertEqual((found[(1, 1)], found[(0, 1)], found[(1, 0)], found[(2, 1)], found[(1, 2)]),
                         (('T', 0, '', 0), ('N', 180, 'S', 0), ('N', 90, 'W', 0), ('N', 0, 'N', 0), ('N', 270, 'E', 0)))
        self.assertEqual((found[(0, 0)], found[(0, 2)], found[(2, 2)], found[(2, 0)]), (('H', 0, 'WS', 0), ('H', 90, 'SE', 0), ('H', 180, 'NE', 0), ('H', 270, 'NW', 0)))

    def test_ground_no_exit_reaches_is_counted_and_a_side_shut_at_its_middle_is_no_exit(self):
        # Two tiles side by side. A yard walled on three sides stands in the west one; its fourth wall, just inside the east tile,
        # shuts the middle of the side the tiles share and leaves the yard a way out north of it, into the east tile only.
        yard = scene(box((-4.0, -3.0, 0), (-3.6, 4.4, 3)), box((-4.0, -3.0, 0), (0.4, -2.6, 3)), box((-4.0, 4.0, 0), (0.4, 4.4, 3)), box((0.0, -3.0, 0), (0.4, 1.5, 3)))
        found = tile.survey(*yard, 1, 2, np.array([-10.0, -5.0]))
        west, east = tile.path_node(found, 0, 0), tile.path_node(found, 0, 1)
        self.assertEqual((west['node'], west['turn'], west['exits']), ('I', 0, 'NWS'))  # round the yard, not into it and not east
        self.assertGreater(west['offPath'], 300)  # the yard's own ground, some 3.6 by 6.6 metres of quarter-metre cells
        self.assertEqual((east['node'], east['turn'], east['exits'], east['offPath']), ('I', 180, 'NSE', 0))
        # Without the fourth wall the yard opens on the middle of the shared side: the west tile then has two grounds, each with its exits.
        open_yard = scene(box((-4.0, -3.0, 0), (-3.6, 4.4, 3)), box((-4.0, -3.0, 0), (0.4, -2.6, 3)), box((-4.0, 4.0, 0), (0.4, 4.4, 3)))
        found = tile.survey(*open_yard, 1, 2, np.array([-10.0, -5.0])); west = tile.path_node(found, 0, 0)
        self.assertEqual((west['node'], west['turn'], west['exits'], west['offPath']), ('U', 180, 'NWSE', 0))  # U: one side alone, the other three joined
        self.assertEqual(tile.path_node(found, 0, 1)['node'], 'A')

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
        text = tile.model_text('ek_test_t00', [low, top], 'ek_test', 'pavement', [sheet(1.0), sheet(3.0)], walk, lights=[(1.0, 2.0, 4.0), (0.0, 0.0, 7.1)], fade=2.5,
                               cap=[(-1.0, -1.0, 1.0, 1.0)])
        geometry, _, animations = text.partition('endmodelgeom')
        nodes = {block.split('\n', 1)[0]: block for block in geometry.split('node ')[1:]}
        self.assertIn('  tilefade 0', nodes['trimesh ek_test_t00_m0']); self.assertIn('  tilefade 1', nodes['trimesh ek_test_t00_m1'])
        self.assertIn('  tilefade 0', nodes['trimesh ek_test_t00_halo0']); self.assertIn('  tilefade 1', nodes['trimesh ek_test_t00_halo1'])  # the sign's light goes with the sign
        lid = nodes['trimesh ek_test_t00_cap']  # drawn only while the top is hidden
        self.assertIn('  tilefade 2', lid); self.assertIn('  bitmap ek_black', lid); self.assertIn('    -1.00000 -1.00000 2.50000', lid); self.assertIn('  faces 2', lid)
        self.assertIn('  position 1.00000 2.00000 4.00000', nodes['light ek_test_t00ml1']); self.assertIn('  radius 14', nodes['light ek_test_t00ml2'])
        self.assertEqual([line.split()[1] for line in animations.splitlines() if line.startswith('newanim')], ['day', 'day2night', 'night', 'night2day'])
        day, night = animations.split('newanim night ')[0].split('newanim day2night')[0], animations.split('newanim night ')[1].split('doneanim')[0]
        self.assertEqual(day.count('      0.00000 0\n'), 2); self.assertEqual(night.count('      0.00000 1\n'), 2)  # both halos: clear by day, full by night
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
        made = {'vertices': vertices, 'normals': np.tile([0.0, 0, 1], (len(vertices), 1)), 'uvs': np.zeros((len(vertices), 2)), 'faces': faces, 'card': None}
        with tempfile.TemporaryDirectory() as scratch:
            report = tile.group('ek_shop', made, scratch, ground='pavement', colour=np.full((2, 2, 3), 0.5), fade=2.0,
                                door={'at': [0.0, 1.0, 0.2], 'facing': 90.0, 'type': 58})
            one = report['tiles'][0]
            self.assertEqual((one['image'], one['lights'], one['doors']), ('ek_shop_m00', 2, [{'type': 58, 'x': 0.0, 'y': 1.0, 'z': 0.2, 'orientation': 90.0}]))
            self.assertTrue(0 < one['fadingFaces'] < one['faces']); self.assertEqual(report['fade'], 2.0)
            self.assertEqual(one['path'], {'node': 'A', 'turn': 0, 'exits': 'NWSE', 'offPath': 0})
            with Image.open(Path(scratch) / 'ek_shop_m00.tga') as picture:
                self.assertEqual((picture.size, picture.mode), ((tile.MINIMAP, tile.MINIMAP), 'RGB'))
            self.assertTrue((Path(scratch) / 'ek_black.tga').is_file())
            text = (Path(scratch) / 'ek_shop_t00.mdl').read_text(encoding='cp1252')
            self.assertIn('node trimesh ek_shop_t00_cap', text); self.assertIn('node light ek_shop_t00ml2', text)
            with self.assertRaisesRegex(ValueError, 'between the slab and the roof'):
                tile.group('ek_shop', made, Path(scratch) / 'again', ground='pavement', fade=9.0)

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
