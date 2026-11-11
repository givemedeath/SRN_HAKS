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
        at = lambda x, y: found['material'][int((y - corner[1]) / 0.5), int((x - corner[0]) / 0.5)]
        self.assertEqual(at(-2.9, 0), tile.OBSCURING)  # a wall
        self.assertEqual(at(0, -0.5), tile.OBSCURING)  # the floor the walls enclose, though the model has none
        self.assertEqual(at(0.75, 2.6), tile.NONWALK)  # the bollard: in the way, seen over
        self.assertEqual(at(-1.0, 2.1), tile.STONE)  # under the canopy
        self.assertEqual(at(-4.5, 4.0), tile.STONE)
        self.assertAlmostEqual(found['slab'], 0.2, places=2); self.assertAlmostEqual(found['roof'], 3.0)
        vertices, faces = tile.walkmesh(found, 0, 0)
        grid = vertices[:(tile.CELLS + 1) ** 2]
        np.testing.assert_allclose([grid[:, :2].min(), grid[:, :2].max()], [-5, 5])  # the whole tile and no more
        rim = (np.abs(grid[:, 0]) == 5) | (np.abs(grid[:, 1]) == 5); self.assertEqual(float(np.abs(grid[rim, 2]).max()), 0.0)
        height = lambda x, y: grid[(np.abs(grid[:, 0] - x) < 1e-9) & (np.abs(grid[:, 1] - y) < 1e-9), 2][0]
        self.assertAlmostEqual(height(-1.5, 2.0), found['slab'], places=6); self.assertEqual(height(-4.5, 0.0), 0.0)
        self.assertEqual(height(4.0, 0.0), 0.0)  # the slab's own edge: the ramp starts here
        level = (faces[:, :3] < len(grid)).all(1); flat, upright = faces[level], faces[~level]  # an upright face reaches a roof vertex
        self.assertEqual(len(flat), 2 * tile.CELLS ** 2)
        up = np.cross(vertices[flat[:, 1]] - vertices[flat[:, 0]], vertices[flat[:, 2]] - vertices[flat[:, 0]])[:, 2]
        self.assertTrue((up > 0).all())  # every floor face looks up
        self.assertTrue(len(upright) and (upright[:, 3] == tile.OBSCURING).all())
        self.assertAlmostEqual(float(vertices[upright[:, :3]][..., 2].max()), 3.0)  # walls of sight, up to the roof
        # An upright pair of faces on every half metre of the building's outline: each side of a closed cell that looks out.
        closed = np.pad(found['material'] == tile.OBSCURING, 1)
        sides = sum(int((closed & ~np.roll(closed, turn, axis)).sum()) for axis in (0, 1) for turn in (1, -1))
        self.assertEqual(len(upright), 2 * sides); self.assertGreaterEqual(sides, 2 * (12 + 6))  # at least the 6 by 3 metres of walls

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

    def test_each_tile_of_a_two_by_two_group_says_which_corner_the_building_closes(self):
        made = {'rows': 2, 'columns': 2, 'tiles': [{'model': f'ek_test_t{row}{column}', 'row': row, 'column': column, 'closedCells': 9} for row in (0, 1) for column in (0, 1)]}
        records = [dict(record) for record in tile.tile_records(made, 'Concrete')]
        self.assertEqual([record['Orientation'] for record in records], [180, 270, 90, 0])  # south-west, south-east, north-west, north-east
        self.assertTrue(all(record['PathNode'] == record['VisibilityNode'] == 'H' and record['TopLeft'] == 'Concrete' and record['Doors'] == 0 for record in records))
        self.assertEqual(tuple(key for key, _ in tile.tile_records(made, 'Concrete')[0]), tile.TILE_KEYS)

    def test_tiles_and_their_group_are_appended_and_nothing_there_is_renumbered(self):
        made = {'rows': 2, 'columns': 2, 'tiles': [{'model': f'ek_test_t{row}{column}', 'row': row, 'column': column, 'closedCells': 9} for row in (0, 1) for column in (0, 1)]}
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

    def test_the_palette_offers_the_group_among_the_groups_once(self):
        document = {'MAIN': {'value': [{'ID': {'value': 0}, 'LIST': {'value': []}}, {'ID': {'value': 1}, 'LIST': {'value': []}}]}}
        tile.palette(document, 'New Group 2x2', 'ek_test_t00')
        self.assertEqual(document['MAIN']['value'][1]['LIST']['value'], [{'__struct_id': 0, 'NAME': {'type': 'cexostring', 'value': 'New Group 2x2'},
                                                                         'RESREF': {'type': 'resref', 'value': 'ek_test_t00'}}])
        self.assertEqual(document['MAIN']['value'][0]['LIST']['value'], [])
        with self.assertRaisesRegex(ValueError, 'already lists'):
            tile.palette(document, 'Again', 'ek_test_t00')


if __name__ == '__main__':
    unittest.main()
