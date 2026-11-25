"""The passage joins of the unified interior tileset (srx02): how one is cut from two families' passage tiles, and that
the pack holds what today's tiles give."""
import json
import unittest
from pathlib import Path

import numpy as np

from tools.tilekit import inventory, joins

REPO = Path(__file__).resolve().parents[2]
PACKS = ('srn_t_srx02', 'srn_t_udp2', 'srn_t_tfb01', 'srn_t_tbx78', 'srn_t_nac01')  # what this reads: named so the test selector runs it when one changes
SPEC_PATH = REPO / 'docs' / 'tilesets' / 'srx02' / 'joins.json'
SPEC = json.loads(SPEC_PATH.read_text(encoding='utf-8'))
WALL, FLOOR, ROOF = ('bitmap wall',), ('bitmap floor',), ('bitmap roof',)


def quad(a, b, c, d, scale=1.0):
    rows = [[*point, point[1] * scale, point[2] * scale] for point in (a, b, c, d)]
    return [np.array([rows[0], rows[1], rows[2]], float), np.array([rows[0], rows[2], rows[3]], float)]


def passage(half_width, ceiling=None, rise=0.0):
    """A baked passage tile running north to south: walls at ±half_width, a ceiling where one is given, and a floor that
    is `rise` higher at its sides than along its middle."""
    w = half_width; drawn = {WALL: quad((-w, -5, 0), (-w, 5, 0), (-w, 5, 3), (-w, -5, 3), 0.5) + quad((w, 5, 0), (w, -5, 0), (w, -5, 3), (w, 5, 3), 0.5),
                             FLOOR: quad((-w, -5, 0), (w, -5, 0), (w, 5, 0), (-w, 5, 0))}
    if ceiling:
        drawn[ROOF] = quad((-w, 5, ceiling), (w, 5, ceiling), (w, -5, ceiling), (-w, -5, ceiling))
    walk = []
    for x0, x1, z0, z1, surface in ((-5, -w, 0, 0, 7), (-w, 0, rise, 0, 4), (0, w, 0, rise, 4), (w, 5, 0, 0, 7)):
        corners = [(x0, -5, z0), (x1, -5, z1), (x1, 5, z1), (x0, 5, z0)]
        walk += [np.array([[*corners[at], surface, 0.0] for at in face], float) for face in ((0, 1, 2), (0, 2, 3))]
    return drawn, walk


def crosses(vertices, faces):
    """Whether walked faces lead from the tile's north edge to its south edge by shared sides."""
    walked = [tuple(face[:3]) for face in faces if joins.walked(int(face[3]))]; sides = {}
    for index, face in enumerate(walked):
        for at in range(3):
            sides.setdefault(frozenset((face[at], face[(at + 1) % 3])), []).append(index)
    touching = lambda index, y: sum(abs(vertices[corner][1] - y) < 0.05 for corner in walked[index]) >= 2
    seen = {index for index in range(len(walked)) if touching(index, 5.0)}; queue = list(seen)
    while queue:
        here = queue.pop()
        for at in range(3):
            for there in sides[frozenset((walked[here][at], walked[here][(at + 1) % 3]))]:
                if there not in seen:
                    seen.add(there); queue.append(there)
    return any(touching(index, -5.0) for index in seen)


class Cutting(unittest.TestCase):
    def test_the_opening_is_as_wide_as_both_walk_and_as_high_as_the_lower_ceiling(self):
        wide, narrow, open_ = passage(4.5, 4.0), passage(2.25, 3.6), passage(3.3)
        self.assertEqual(joins.opening(wide)[:3], (-4.5, 4.5, 4.0)); self.assertIsNone(joins.opening(open_)[2])
        self.assertEqual(joins.frame(wide, narrow), (-2.25, 2.25, 3.6, 4.0))
        self.assertEqual(joins.frame(open_, wide)[:3], (-3.3, 3.3, 4.0))  # open above: the other side's ceiling
        with self.assertRaisesRegex(ValueError, 'do not meet'):
            joins.frame(wide, ({FLOOR: []}, [triangle + np.array([4.6, 0, 0, 0, 0]) for triangle in passage(0.4)[1]]))

    def test_a_cut_keeps_an_upright_wall(self):
        # seen from above an upright face has no area: the ground cut left it out, and a hallway lost a wall (2026-11-24)
        wall = passage(5.0)[0][WALL]
        self.assertEqual(joins.inside(wall, joins.NORTH), [])
        kept = joins.inside(wall, joins.NORTH, solid=True)
        self.assertAlmostEqual(sum(joins._space(triangle) for triangle in kept), 30.0, places=6)
        self.assertTrue(all(triangle[:, 1].min() >= -1e-9 for triangle in kept))

    def test_each_face_of_the_bulkhead_wears_the_wall_of_the_family_it_faces(self):
        north, south = passage(4.5, 4.0), passage(2.25, 3.6); south = ({('bitmap other',) if look == WALL else look: triangles for look, triangles in south[0].items()}, south[1])
        self.assertEqual(joins.wall_look(north[0]), (WALL, 0.5))
        made = joins.bulkhead(north, south); self.assertEqual(set(made), {WALL, ('bitmap other',)})
        facing = lambda triangle: np.cross(triangle[1, :3] - triangle[0, :3], triangle[2, :3] - triangle[0, :3])
        self.assertTrue(all(facing(triangle)[1] < 0 and triangle[:, 1].max() < 0 for triangle in made[('bitmap other',)]))  # the south faces, seen from the south
        outer = [triangle for triangle in made[WALL] if abs(facing(triangle)[1]) > 1e-9]
        self.assertTrue(all(facing(triangle)[1] > 0 for triangle in outer))
        for triangle in made[WALL] + made[('bitmap other',)]:  # nothing of it stands in the opening
            middle = triangle[:, :3].mean(0); self.assertFalse(abs(middle[0]) < 2.2 and middle[2] < 3.5, middle)
        self.assertAlmostEqual(sum(joins._space(triangle) for triangle in outer), 10 * 4.0 - 4.5 * 3.6, places=6)

    def test_a_floor_that_is_not_level_at_the_seam_is_walked_level_there(self):
        level, round_ = passage(4.5, 4.0), passage(1.3, 2.8, rise=1.8)
        text, walk = joins.passage_model('tst_jax_01', level, round_)
        self.assertIn('node trimesh tst_jax_01_n0', text); self.assertIn('node trimesh tst_jax_01_b0', text)
        cut = joins.level(joins.inside(round_[1], joins.SOUTH), joins.SOUTH)
        for triangle in cut:
            for x, y, z in triangle[:, :3]:  # the walked floor falls to the seam; the ground either side is flat and not walked
                self.assertAlmostEqual(z, min(1.0, abs(y) / joins.RAMP) * 1.8 * abs(x) / 1.3 if joins.walked(int(triangle[0, 3])) else 0.0, places=6)
        self.assertAlmostEqual(sum(abs(joins.flat_area(triangle)) for triangle in cut), 50.0, places=6)  # the half tile, nothing twice
        self.assertTrue(crosses(*joins.conformed(joins.bake(text)[1])))


class Built(unittest.TestCase):
    def test_the_pack_holds_what_todays_tiles_give(self):
        self.assertEqual(joins.stale(REPO, SPEC_PATH, SPEC_PATH.with_name('joins-built.json')), [])  # a passage tile or the spec changed: build again

    def test_each_join_is_in_the_set_between_its_two_passages_and_is_walked_through(self):
        laid = {tile['model']: tile for tile in inventory.read_set((REPO / 'srn_t_srx02' / 'srx02.set').read_bytes().decode('cp1252'))['tiles']}
        made = joins.tiles(SPEC); self.assertEqual(len(made), len(SPEC['passages']))
        self.assertEqual(len({(record['crossers']['Top'], record['crossers']['Bottom']) for record in made}), len(made))  # no pair twice
        for record in made:
            with self.subTest(model=record['model']):
                tile = laid[record['model']]
                self.assertEqual(tile['corners'], ['Wall'] * 4)
                self.assertEqual(tile['crossers'], [record['crossers'][side] for side in ('Top', 'Right', 'Bottom', 'Left')])
                for suffix, folder in (('.mdl', 'srn_t_srx02'), ('.wok', 'srn_t_srx02'), ('.mdl', 'sources/srn_t_srx02')):
                    self.assertTrue((REPO / folder / (record['model'] + suffix)).is_file(), folder + suffix)
                self.assertTrue((REPO / 'srn_t_srx02' / (record['minimap'] + '.tga')).is_file())
                _, walk = joins.bake((REPO / 'sources' / 'srn_t_srx02' / (record['model'] + '.mdl')).read_text(encoding='ascii'))
                self.assertTrue(crosses(*joins.conformed(walk)), 'no walked way from north to south')
                self.assertLessEqual(max(abs(triangle[:, :2]).max() for triangle in walk), 5.05)

    def test_a_join_tile_takes_a_straight_passage_s_path_node(self):
        text = (REPO / 'srn_t_srx02' / 'srx02.set').read_bytes().decode('cp1252'); keyed = dict(inventory.sections(text))
        found = [keys for keys in keyed.values() if keys.get('Model', '').startswith(SPEC['prefix'])]
        self.assertEqual(len(found), len(SPEC['passages']))
        self.assertEqual({(keys['PathNode'], keys['Orientation']) for keys in found}, {('L', '0')})


if __name__ == '__main__':
    unittest.main()
