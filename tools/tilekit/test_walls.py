"""Rooms drawn in code: their walls, doorways and walkmeshes, what hangs from their ceilings, and what is refused."""
import json
import tempfile
import unittest
from pathlib import Path

from tools.tilekit import ceilings, geometry, joins, rooms, walls
from tools.tilekit.test_rooms import PIECES, piece
from tools.tilekit.test_strip import box as block

LOOK = {'floor': 'wood', 'wall': 'plaster', 'ceiling': 'white', 'base': 'oak', 'trim': 'oak', 'top': 'black'}
BOX = {'rows': 2, 'columns': 2, 'like': [1, 2, 2, 2], 'height': 3.4, 'look': LOOK, 'openings': [{'side': 's', 'at': 5.0, 'width': 4.0, 'high': 3.0}],
       'walls': [{'from': [10, 0], 'to': [10, 20], 'doors': [{'at': 5.0, 'width': 2.0}]}, {'from': [0, 10], 'to': [10, 10], 'doors': [{'at': 4.0}]}],
       'zones': [{'rect': [10, 0, 20, 20], 'floor': 'tiles'}]}
SPEC = {'id': 'hut', 'category': 'Home', 'name': 'Hut', 'shell': {'set': 'a', 'box': BOX}}
LIKE = '\n'.join(['newmodel like', 'beginmodelgeom like', 'node dummy like', '  parent null', 'endnode', *block('floor1', -5, 5, -5, 5, -0.1, 0.0), 'node light likeml1', '  parent like', 'endnode',
                  'node aabb wm', '  parent like', '  verts 3', '    -5 -5 0', '    5 -5 0', '    5 5 0', '  faces 1', '    0 1 2 1 0 0 0 9', '  aabb -5 -5 0 5 5 0 0', 'endnode',
                  'endmodelgeom like', 'newanim tiledefault like', '  length 0', 'node dummy like', '  parent null', 'endnode', 'node trimesh floor1', '  parent like', 'endnode', 'doneanim tiledefault like', 'donemodel like'])


class Walls(unittest.TestCase):
    def test_a_tile_is_open_where_the_room_s_own_walls_are_not(self):
        plan = walls.Plan(SPEC); self.assertEqual([plan.sides(index) for index in range(4)], [{'s', 'e', 'n'}, {'w', 'n'}, {'s'}, {'s'}])
        self.assertEqual([walls.path(plan.sides(index)) for index in range(4)], [('I', 180), ('H', 270), ('N', 180), ('N', 180)])

    def test_a_drawn_tile_keeps_its_lights_and_has_a_floor_of_its_own_that_meets_the_next_tile_s(self):
        made = [walls.shell(LIKE, f'm_hut_{index}', SPEC, index) for index in range(4)]; names = {node.name for node in geometry.parse(made[0][0])[2]}
        self.assertIn('m_hut_0ml1', names); self.assertNotIn('floor1', made[0][0]); self.assertEqual(made[0][2], ['floor1'])
        floors = [sum(abs(joins.flat_area(one)) for one in joins.bake(text)[1] if int(one[0, 3]) == 9) for text, _, _ in made]
        self.assertAlmostEqual(sum(floors), 19.6 * 19.6 - 0.2 * 19.6 - 9.7 * 0.2 + 0.2 * 2.0 + 0.2 * 1.4 + 4.0 * 0.2, places=2)  # the walls gone, the doorways and the way in back
        self.assertEqual([rooms.cracks(text) for text, _, _ in made], [[]] * 4)
        east, west = rooms._rim(made[0][0]), rooms._rim(made[1][0]); self.assertEqual({step for side, step in east if side == 'e'}, {step for side, step in west if side == 'w'})

    def test_a_zone_s_look_is_on_its_own_floor(self):
        plan = walls.Plan(SPEC); self.assertIn('tiles', walls.drawn(plan, 1).by); self.assertNotIn('wood', walls.drawn(plan, 1).by); self.assertIn('wood', walls.drawn(plan, 0).by)

    def test_a_doorway_that_leaves_its_wall_and_a_wall_askew(self):
        for wall, wanted in (({'from': [0, 5], 'to': [4, 5], 'doors': [{'at': 3.9}]}, 'leaves the wall'), ({'from': [0, 5], 'to': [4, 6]}, 'neither x nor y')):
            with self.assertRaisesRegex(ValueError, wanted):
                walls.Plan({**SPEC, 'shell': {'set': 'a', 'box': {**BOX, 'walls': [wall]}}})


class Ceilings(unittest.TestCase):
    def test_a_lamp_s_face_is_lit_by_itself_and_hangs_below_its_housing(self):
        text = '\n'.join(['newmodel t', 'beginmodelgeom t', 'node dummy t', '  parent null', 'endnode', *ceilings.overhead('t', [{'kind': 'strip', 'at': [0, 0], 'under': 4.0, 'drop': 0.5}], [{'rect': [-1, -1, 1, 1], 'z': [3.5, 4.0], 'texture': 'plaster'}]), 'endmodelgeom t', 'donemodel t'])
        by = {node.material: node for node in geometry.parse(text)[2] if node.rendered}; self.assertEqual(set(by), {ceilings.HOUSING, ceilings.DIFFUSER, 'plaster'})
        self.assertIn('selfillumcolor 1.0 1.0 1.0', by[ceilings.DIFFUSER].look); low = lambda node: min(vertex[2] for vertex in node.verts)
        self.assertLess(low(by[ceilings.DIFFUSER]), low(by[ceilings.HOUSING])); self.assertAlmostEqual(low(by['plaster']), 3.5)

    def test_a_lamp_that_leaves_its_tile(self):
        with self.assertRaisesRegex(ValueError, 'leaves its tile'):
            ceilings.overhead('t', [{'kind': 'strip', 'at': [4.8, 0], 'under': 4.0}], [])

    def test_the_pictures_are_seamless_and_of_whole_sizes(self):
        for name, picture in ceilings.pictures(256).items():
            self.assertTrue(len(name) <= 16 and picture.shape[0] == picture.shape[1] and picture.ndim == 3, name)


SEAT = piece('seat', block('seat', -0.4, 0.4, -0.4, 0.4, 0, 0.4), block('back', -0.4, 0.4, 0.3, 0.4, 0.4, 1.0))
TABLE = piece('table', block('table', -0.4, 0.4, -0.4, 0.4, 0, 0.5))


class Furnished(unittest.TestCase):
    def test_a_seat_s_back_is_behind_its_front(self):
        self.assertGreater(rooms.leaning(SEAT, 's'), 0.1); self.assertLess(rooms.leaning(SEAT, 'n'), -0.1); self.assertIsNone(rooms.leaning(PIECES['rug'], 's'))

    def test_a_bookcase_s_shelves_are_at_its_front(self):  # one was recorded by its plain back, 2026-11-25
        case = piece('case', block('body', -0.8, 0.8, -0.2, 0.2, 0, 2.0), *[block(f'shelf{step}', -0.7, 0.7, -0.3, -0.2, 0.2 * step, 0.2 * step + 0.05) for step in range(9)])
        self.assertEqual(rooms.bare(case, 's'), rooms.bare(case, 'n')); shown = [node for node in case]
        for node in shown:
            if node.name.startswith('shelf'):  # drawn from before only
                node.faces = [face for face in node.faces if all(node.verts[corner][1] < -0.25 for corner in face[:3])]
        self.assertGreater(rooms.bare(shown, 's'), 1); self.assertLess(rooms.bare(shown, 'n'), 1 / 3)

    def test_a_seat_out_of_line_with_the_table_it_faces(self):  # an armchair stood beside its coffee table, 2026-11-25
        seat = lambda x: {'piece': 'seat', 'at': [x, 1.5, 0.0], 'faces': 's', 'front': 's'}; table = {'piece': 'table', 'at': [0.0, 0.4, 0.0], 'turn': 0}; pieces = {'seat': SEAT, 'table': TABLE}
        self.assertEqual(rooms.misplaced([seat(0.05), table], pieces), []); self.assertRegex(rooms.misplaced([seat(0.5), table], pieces)[0], '0.50 m off its middle')
        self.assertRegex(rooms.misplaced([{**seat(0.0), 'at': [0.0, 1.1, 0.0]}, table], pieces)[0], 'stands in it')

    def test_a_piece_whose_front_nobody_recorded(self):
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / 'rooms').mkdir(); (Path(folder) / 'fronts.json').write_text('{}', encoding='utf-8')
            (Path(folder) / 'rooms' / 'den.json').write_text(json.dumps({'id': 'den', 'category': 'Home', 'name': 'Den', 'shell': {'set': 'a', 'group': 'Den'}, 'props': [{'piece': 'couch', 'at': [0, 0, 0], 'faces': 'e'}]}), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'does not say which way it looks'):
                rooms.specs(Path(folder) / 'rooms')

    def test_a_piece_with_a_texture_no_pack_holds(self):  # the rifle stand's rifles drew white, 2026-11-25
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / 'srn_x').mkdir(); (Path(folder) / 'srn_x' / 'a_long_name_of_s.dds').write_bytes(b'')
            rooms.untextured(folder, {'one': piece('one', block('one', 0, 1, 0, 1, 0, 1, ('bitmap a_long_name_of_sixteen',)))})
            with self.assertRaisesRegex(ValueError, 'rack draws white'):
                rooms.untextured(folder, {'rack': piece('rack', block('rack', 0, 1, 0, 1, 0, 1, ('bitmap white',)))})

    def test_a_floor_round_furniture_has_no_crack(self):  # a creature stopped dead at one in the middle of a room, 2026-11-25
        plan_spec = {**SPEC, 'shell': {'set': 'a', 'box': {**BOX, 'walls': []}}}; text, _, _ = walls.shell(LIKE, 'm_hut_0', plan_spec, 0)
        foot = [((-1.013, -2.377), (0.21, -2.377), (0.21, -1.004), (-1.013, -1.004)), ((1.5, 0.3), (2.2, 1.0), (1.5, 1.7), (0.8, 1.0))]
        made, wok, boxes = rooms.furnished_walk(text, 'm_hut_0', [(one, 0.0, None) for one in foot])
        self.assertEqual(boxes[0], (-1.05, -2.4, 0.25, -1.0)); self.assertEqual(rooms.cracks(made), []); self.assertTrue(wok.startswith('beginwalkmeshgeom m_hut_0'))
        self.assertAlmostEqual(rooms._walked(text) - rooms._walked(made), 1.3 * 1.4 + 1.4 * 1.4, places=3)


if __name__ == '__main__':
    unittest.main()
