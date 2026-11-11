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

    def test_a_closed_tile_outside_a_two_by_two_group_is_refused_rather_than_called_open(self):
        kiosk = {'rows': 1, 'columns': 1, 'tiles': [{'model': 'ek_test_t00', 'row': 0, 'column': 0, 'closedCells': 30}]}
        with self.assertRaisesRegex(ValueError, 'pathfinding of its closed tiles'):
            tile.tile_records(kiosk, 'Concrete')
        kiosk['tiles'][0]['closedCells'] = 0  # a patch of paving is an open tile
        self.assertEqual(dict(tile.tile_records(kiosk, 'Concrete')[0])['PathNode'], 'A')

    def test_a_set_files_terrains_are_read_so_a_wrong_one_can_be_refused(self):
        text = '[TERRAIN TYPES]\r\nCount=2\r\n\r\n[TERRAIN0]\r\nName=Grass\r\n\r\n[TERRAIN1]\r\nName=Asphalt\r\nStrRef=5\r\n\r\n[CROSSER0]\r\nName=Road\r\n'
        self.assertEqual(tile.terrains(text), ['Grass', 'Asphalt'])

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
        strips = tile.lid(found, 0, 0, 2.0); area = sum((x1 - x0) * (y1 - y0) for x0, y0, x1, y1 in strips)
        self.assertTrue(18.0 <= area <= 21.0)  # the 6 by 3 metres the walls enclose, to the grain of the survey
        self.assertTrue(all(-3.2 <= x0 < x1 <= 3.2 and -2.2 <= y0 < y1 <= 1.2 for x0, y0, x1, y1 in strips))
        first, second = tile.light_places(found, 0, 0)
        self.assertEqual(found['material'][int((first[1] + 5) / 0.5), int((first[0] + 5) / 0.5)], tile.STONE); self.assertEqual(first[2], tile.LIGHT_HEIGHT)
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
            with Image.open(Path(scratch) / 'ek_shop_m00.tga') as picture:
                self.assertEqual((picture.size, picture.mode), ((tile.MINIMAP, tile.MINIMAP), 'RGB'))
            self.assertTrue((Path(scratch) / 'ek_black.tga').is_file())
            text = (Path(scratch) / 'ek_shop_t00.mdl').read_text(encoding='cp1252')
            self.assertIn('node trimesh ek_shop_t00_cap', text); self.assertIn('node light ek_shop_t00ml2', text)
            with self.assertRaisesRegex(ValueError, 'between the slab and the roof'):
                tile.group('ek_shop', made, Path(scratch) / 'again', ground='pavement', fade=9.0)

    def test_a_tiles_record_names_its_picture_lights_and_doors_and_a_door_block_follows_it(self):
        made = {'rows': 2, 'columns': 2, 'tiles': [{'model': f'ek_test_t{row}{column}', 'row': row, 'column': column, 'closedCells': 9, 'lights': 2,
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
        bare = {'rows': 2, 'columns': 2, 'tiles': [{'model': f'ek_test_t{row}{column}', 'row': row, 'column': column, 'closedCells': 9} for row in (0, 1) for column in (0, 1)]}
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
