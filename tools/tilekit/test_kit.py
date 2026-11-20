import math
import unittest

from tools.tilekit import geometry, kit, placer
from tools.tilekit.test_detail import MODEL


def _normal(mesh, face):
    a, b, c = (mesh.verts[corner] for corner in face[:3])
    u = [b[axis] - a[axis] for axis in range(3)]; v = [c[axis] - a[axis] for axis in range(3)]
    return (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])


class PiecesTest(unittest.TestCase):
    def test_every_piece_has_faces_inside_its_lists(self):
        for name, build in kit.PIECES.items():
            mesh, _ = build()
            with self.subTest(name):
                self.assertTrue(mesh.faces)
                for face in mesh.faces:
                    self.assertLess(max(face[:3]), len(mesh.verts)); self.assertLess(max(face[4:7]), len(mesh.tverts))
                self.assertTrue(all(0 <= u <= 1 and 0 <= v <= 1 for u, v in mesh.tverts))

    def test_the_tank_is_closed_and_faces_outward(self):
        mesh = kit.Mesh(); mesh.cylinder((0.0, 0.0, 0.8), 0.9, 1.6, 'rust', sides=8, bottom=True)
        centre = (0.0, 0.0, 1.6)
        for face in mesh.faces:
            middle = [sum(mesh.verts[corner][axis] for corner in face[:3]) / 3 for axis in range(3)]
            normal = _normal(mesh, face)
            self.assertGreater(sum(normal[axis] * (middle[axis] - centre[axis]) for axis in range(3)), 0)
        self.assertEqual(sum(1 for face in mesh.faces if _normal(mesh, face)[2] < -1e-9), 8)  # the foot is closed

    def test_a_piece_model_is_one_textured_mesh(self):
        mesh, blocks = kit.tank(); text = mesh.text('tank', shadow=blocks)
        _, root, nodes = geometry.parse(text)
        self.assertEqual(root, 'tank'); self.assertEqual([node.name for node in nodes if node.rendered], ['body'])
        self.assertIn(f'  bitmap {kit.ATLAS}', text); self.assertIn('  shadow 1', text)


class PlacerTest(unittest.TestCase):
    def test_roof_clutter_stands_on_the_roof_clear_of_the_side_and_apart(self):
        found = placer.propose(MODEL.format(z=10.0), 'seed')
        roof = [entry for entry in found if entry.get('blocks')]
        self.assertGreaterEqual(len(roof), 3)
        for entry in roof:
            x, y, z = entry['at']
            self.assertAlmostEqual(z, 10.0); self.assertLessEqual(max(abs(x), abs(y)), geometry.HALF - placer.EDGE)
        for one in roof:
            for other in roof:
                if one is not other:
                    self.assertGreaterEqual(math.dist(one['at'][:2], other['at'][:2]), placer.APART)

    def test_no_roof_clutter_on_a_street_level_tile(self):
        self.assertEqual([entry for entry in placer.propose(MODEL.format(z=0.0), 'seed') if entry.get('blocks')], [])

    def test_a_proposal_is_the_same_for_the_same_seed(self):
        self.assertEqual(placer.propose(MODEL.format(z=10.0), 7), placer.propose(MODEL.format(z=10.0), 7))


if __name__ == '__main__':
    unittest.main()


class PlacerEffectsTest(unittest.TestCase):
    def test_drips_hang_under_the_lowest_platform_and_air_conditioner_and_smoke_rises_from_a_vent(self):
        found = [{'piece': 'fire_escape', 'at': [-5.01, -2.5, 5.83], 'turn': 90.0}, {'piece': 'fire_escape_top', 'at': [-5.01, -2.5, 10.63], 'turn': 90.0},
                 {'piece': 'ac_unit', 'at': [-5.01, 2.9, 5.35], 'turn': 90.0}]
        roof = [{'piece': 'vent', 'at': [1.0, 1.0, 20.0], 'turn': 0, 'blocks': True}]
        fx = placer._effects([], found, [], roof, 0)
        drips = [one for one in fx if one['piece'] == 'drip']
        self.assertEqual([one['at'] for one in drips], [[-6.01, -1.5, 5.76], [-5.56, 3.0, 5.34]])
        self.assertTrue(all(one['fall'] == one['at'][2] for one in drips))
        self.assertIn({'piece': 'smoke', 'at': [1.0, 1.0, 20.75]}, fx)
        self.assertLessEqual(len(fx), 4)

    def test_a_proposal_stays_within_four_effects(self):
        for seed in range(12):
            found = placer.propose(MODEL.format(z=10.0), seed)
            self.assertLessEqual(sum(one['piece'] in ('sparks', 'drip', 'smoke') for one in found), 4)


class OpenSidesTest(unittest.TestCase):
    def test_a_side_is_on_a_street_when_both_its_corners_are(self):
        slums = lambda terrain: terrain.startswith('Slums')
        self.assertEqual(placer.open_sides(['Concrete', 'Slums3', 'Concrete', 'Slums3'], slums), {(-1, 0)})
        self.assertEqual(placer.open_sides(['Slums1', 'Concrete', 'Concrete', 'Concrete'], slums), {(1, 0), (0, -1)})
        self.assertEqual(placer.open_sides(['Slums1'] * 4, slums), set())


class DownpipeOpeningTest(unittest.TestCase):
    def test_a_downpipe_keeps_out_of_a_door_on_its_facade(self):
        door = [(-5.06, -5.03, -4.1, -2.0)]  # a door frame on the facade facing -x, as on dgt04_e09_19
        self.assertTrue(placer._over_opening(door, (-1, 0), 5.01, -3.5))
        self.assertFalse(placer._over_opening(door, (-1, 0), 5.01, 1.5))
        self.assertFalse(placer._over_opening(door, (1, 0), 5.01, -3.5))  # the facade across the cell


SET_BACK_DOOR = """newmodel t
beginmodelgeom t
node dummy t
  parent NULL
endnode
node trimesh jamb
  parent t
  position 0.0 0.0 0.0
  orientation 0.0 0.0 0.0 0.0
  bitmap doortrim1
  verts 4
    -5.06 -2.02 0.2
    -5.06 -1.9 0.2
    -5.06 -1.9 3.2
    -5.06 -2.02 3.2
  tverts 1
    0 0 0
  faces 2
    0 1 2 1 0 0 0 1
    0 2 3 1 0 0 0 1
endnode
node trimesh opening
  parent t
  position 0.0 0.0 0.0
  orientation 0.0 0.0 0.0 0.0
  bitmap dgt04_black
  verts 4
    -2.96 -3.98 0.2
    -2.96 -2.02 0.2
    -2.96 -2.02 3.2
    -2.96 -3.98 3.2
  tverts 1
    0 0 0
  faces 2
    0 1 2 1 0 0 0 1
    0 2 3 1 0 0 0 1
endnode
endmodelgeom t
donemodel t
"""


class SetBackDoorTest(unittest.TestCase):
    def test_a_door_set_back_into_the_building_counts_whole(self):  # dgt04_e09_19: a thin jamb on the wall, the opening 2 m in
        _, _, nodes = geometry.parse(SET_BACK_DOOR)
        self.assertTrue(placer._over_opening(placer._openings(nodes), (-1, 0), 5.01, -3.5))
        self.assertFalse(placer._over_opening(placer._openings(nodes), (-1, 0), 5.01, 1.5))


TOWER = """newmodel t
beginmodelgeom t
node dummy t
  parent NULL
endnode
node trimesh wall
  parent t
  position 0.0 0.0 0.0
  orientation 0.0 0.0 0.0 0.0
  bitmap hrise_05_wall
  verts 4
    -2.5 4.0 0.0
    -2.5 -4.0 0.0
    -2.5 -4.0 40.0
    -2.5 4.0 40.0
  tverts 1
    0 0 0
  faces 2
    0 1 2 1 0 0 0 1
    0 2 3 1 0 0 0 1
endnode
endmodelgeom t
donemodel t
"""


class CorporateTest(unittest.TestCase):
    def test_a_tower_set_back_behind_a_plaza_is_found(self):
        _, _, nodes = geometry.parse(TOWER)
        self.assertEqual(placer.facades(nodes), {(-1, 0): (2.5, -4.0, 4.0, 40.0)})
        self.assertEqual(placer.facades(nodes, open={(1, 0)}), {})
        found = placer.propose_corporate(TOWER, 'seed')
        self.assertTrue(all(one['turn'] == placer._turn((-1, 0)) for one in found))
        self.assertFalse(any(one['piece'].startswith(('sign', 'crown')) for one in found))
        self.assertLessEqual(len(kit.ORDER), kit.CELLS * kit.CELLS); self.assertIn('red', kit.GLOWS)
