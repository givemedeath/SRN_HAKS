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

    def test_every_piece_shows_its_front_off_the_wall(self):
        # a piece's frontmost faces (+y, away from the wall) face +y: the client culls a face from behind, and boards
        # wound toward the wall were never seen (batch 3 review, 2026-11-20)
        for name, build in kit.PIECES.items():
            mesh, _ = build(); front = max(vert[1] for vert in mesh.verts)
            with self.subTest(name):
                for face in mesh.faces:
                    normal = _normal(mesh, face); size = sum(axis * axis for axis in normal) ** 0.5
                    if size < 1e-12:
                        continue
                    normal = [axis / size for axis in normal]
                    if all(abs(mesh.verts[corner][1] - front) < 1e-6 for corner in face[:3]) and abs(normal[1]) > 0.9:
                        self.assertGreater(normal[1], 0)
                    if name == 'boards' and abs(normal[0]) > 0.9:  # the ends face out of the piece
                        self.assertGreater(normal[0] * sum(mesh.verts[corner][0] for corner in face[:3]), 0)

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


PAINTED = """newmodel t
beginmodelgeom t
node dummy t
  parent NULL
endnode
node trimesh wall
  parent t
  position 0.0 0.0 0.0
  orientation 0.0 0.0 0.0 0.0
  bitmap grid
  verts 4
    -5.0 5.0 12.0
    -5.0 -5.0 12.0
    -5.0 -5.0 32.0
    -5.0 5.0 32.0
  tverts 4
    0 0 0
    1 0 0
    1 1 0
    0 1 0
  faces 2
    0 1 2 1 0 1 2 1
    0 2 3 1 0 2 3 1
endnode
endmodelgeom t
donemodel t
"""
GRID = {'grid': (2, 4, 0.2, 0.8, 0.7)}  # 5 m columns, glass 3.5 m wide


class PaintedWindowsTest(unittest.TestCase):
    def test_windows_painted_in_a_texture_are_found_through_its_coordinates(self):
        _, _, nodes = geometry.parse(PAINTED)
        found = placer.grid_windows(nodes, GRID)
        self.assertEqual(list(found), [(-1, 0)])
        self.assertEqual(found[(-1, 0)], sorted((along, 12.0 + 5 * row + 1, 12.0 + 5 * row + 4, 5.0, 3.5)
                                                for along in (-2.5, 2.5) for row in range(4)))
        self.assertEqual(placer.grid_windows(nodes, {'other': (2, 4, 0.2, 0.8, 0.7)}), {})

    def test_a_tower_over_lower_neighbours_is_dressed_from_its_windows_up(self):
        closed = placer.propose(PAINTED, 'seed', look='derelict', grids=GRID, open=set())
        self.assertFalse([one for one in closed if one['piece'] in ('boards', 'downpipe', 'ac_unit', 'bars')])
        found = placer.propose(PAINTED, 'seed', look='derelict', grids=GRID, open=set(), above=13.0)
        pieces = {one['piece'] for one in found}
        self.assertIn('boards', pieces); self.assertNotIn('ac_unit', pieces)
        self.assertGreaterEqual(min(one['at'][2] for one in found if one['piece'] == 'downpipe'), 12.0)

    def test_residential_walls_get_air_conditioners_and_no_escapes_or_bars(self):
        found = placer.propose(PAINTED, 'seed', look='residential', grids=GRID)
        pieces = {one['piece'] for one in found}
        self.assertIn('ac_unit', pieces)
        self.assertFalse(pieces & {'fire_escape', 'fire_escape_top', 'bars', 'boards'})

FLOORED = TOWER.replace('endmodelgeom t', """node aabb floor
  parent t
  position 0.0 0.0 0.0
  orientation 0.0 0.0 0.0 0.0
  bitmap NULL
  verts 4
    -4.0 -4.0 6.0
    4.0 -4.0 6.0
    4.0 4.0 6.0
    -4.0 4.0 6.0
  faces 2
    0 1 2 1 0 0 0 4
    0 2 3 1 0 0 0 4
endnode
endmodelgeom t""")  # a walkable upper floor, 6 m up


class FamilyLooksTest(unittest.TestCase):
    def test_a_secure_site_bars_every_lowest_window_and_a_civic_one_none(self):
        _, _, nodes = geometry.parse(PAINTED); lowest = min(bottom for _, bottom, *_ in placer.grid_windows(nodes, GRID)[(-1, 0)])
        secure = placer.propose(PAINTED, 'seed', look='secure', grids=GRID)
        bars = [one for one in secure if one['piece'] == 'bars']
        for along in (-2.5, 2.5):  # each 3.5 by 3 m window is barred whole, by two panels side by side
            mine = [one for one in bars if abs(one['at'][1] - along) < 1.75]
            self.assertEqual(len(mine), 2)
            self.assertAlmostEqual(sum(one['scale'][0] for one in mine) * placer.PANEL[0], 3.5 - 2 * placer.INSET, places=2)
            self.assertTrue(all(abs(one['at'][2] - lowest - placer.INSET) < 1e-6 and abs(one['scale'][2] * placer.PANEL[1] - (3.0 - 2 * placer.INSET)) < 0.01 for one in mine))
        civic = {one['piece'] for one in placer.propose(PAINTED, 'seed', look='civic', grids=GRID)}
        self.assertFalse(civic & {'bars', 'boards', 'ac_unit', 'fire_escape'})

    def test_no_plant_means_no_roof_pieces(self):
        for look in ('ruin', 'industrial'):
            found = placer.propose(PAINTED, 'seed', look=look, grids=GRID, plant=None)
            self.assertFalse([one for one in found if one.get('blocks')], look)

    def test_a_watched_wall_without_a_door_gets_a_camera(self):
        self.assertFalse([one for one in placer.propose_corporate(TOWER, 'seed', plant=None, ledges=False) if one['piece'] == 'camera'])
        found = placer.propose_corporate(TOWER, 'seed', plant=None, ledges=False, watch=True, sign='hazard_sign', eye=1.6)
        cameras = [one for one in found if one['piece'] == 'camera']
        self.assertEqual(sorted(one['at'][1] for one in cameras), [-3.4, 3.4]); self.assertTrue(all(one['scale'] == 1.6 and one['turn'] == placer._turn((-1, 0)) for one in cameras))
        self.assertEqual([one['at'] for one in found if one['piece'] == 'hazard_sign'], [[-2.5, 0.0, round(geometry.OVER + 0.05, 3)]])

    def test_a_ruin_has_smoking_barrels_and_no_roof_plant(self):
        found = placer.propose(FLOORED, 'seed', look='ruin', plant=None)
        barrels = [one for one in found if one['piece'] == 'barrel']; smoke = [one for one in found if one['piece'] == 'smoke']
        self.assertTrue(1 <= len(barrels) <= 2); self.assertEqual(len(smoke), len(barrels))
        self.assertFalse({one['piece'] for one in found} & {'hvac', 'tank', 'dish', 'antenna', 'vent'})
