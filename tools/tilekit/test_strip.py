"""A furnished interior tile is sorted into its room and its furniture, and stripped to the room."""
import unittest
from pathlib import Path

import numpy as np

from tools.envkit import tile
from tools.tilekit import geometry, inventory, joins, strip

REPO = Path(__file__).resolve().parents[2]
PACKS = ('srn_t_tfb01',)  # what this reads: named so the test selector runs it when one changes
LOOK = ('bitmap wood',)


def box(name, x0, x1, y0, y1, z0, z1, look=LOOK):
    corners = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    quads = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)] if z1 > z0 else [(0, 1, 2, 3)]
    faces = [(a, b, c, 1, 0, 0, 0, 0) for q in quads for a, b, c in ((q[0], q[1], q[2]), (q[0], q[2], q[3]))]
    return geometry.mesh_text(name, 'tst', look, corners, [(0.0, 0.0)], faces)


def room(extra=()):
    """A tile's uncompiled model: a floor between four walls with a lid on them, a rug, a table and a bookcase against
    the east wall. Its walkmesh walks the table as a raised block that is not walked, and the bookcase as wall."""
    lines = ['newmodel tst', 'setsupermodel tst null', 'beginmodelgeom tst', 'node dummy tst', '  parent null', 'endnode']
    lines += box('floor', -3.5, 3.5, -3.5, 3.5, 0, 0) + box('rug', -1, 1, -1, 1, 0.01, 0.01, ('bitmap rug',))
    for name, (x0, x1, y0, y1) in (('wall_w', (-4.5, -3.5, -4.5, 4.5)), ('wall_e', (3.5, 4.5, -4.5, 4.5)), ('wall_s', (-3.5, 3.5, -4.5, -3.5)), ('wall_n', (-3.5, 3.5, 3.5, 4.5))):
        lines += box(name, x0, x1, y0, y1, 0, 3)
    lines += box('lid', -5, 5, -5, 5, 3, 3, ('bitmap black',)) + box('table', -3, -2, -3, -1, 0, 0.8) + box('books', 2.5, 3.5, -1.5, 1.5, 0, 2.9) + box('leaf', -1, 1, 4.9, 5, 0, 3)
    for part in extra:
        lines += part
    xs, ys = (-5, -3.5, -3, -2, 2.5, 3.5, 5), (-5, -3.5, -3, -1.5, -1, 1.5, 3.5, 5); points, faces = [], []
    for x0, x1 in zip(xs, xs[1:]):
        for y0, y1 in zip(ys, ys[1:]):
            table = -3 <= x0 and x1 <= -2 and -3 <= y0 and y1 <= -1; books = 2.5 <= x0 and x1 <= 3.5 and -1.5 <= y0 and y1 <= 1.5
            surface = 7 if table else 2 if books or min(x0, y0) < -3.5 or max(x1, y1) > 3.5 else 5; z = 0.8 if table else 0  # the table's top, the bookcase as wall
            first = len(points); points += [(x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z)]; faces += [(first, first + 1, first + 2, surface), (first, first + 2, first + 3, surface)]
    lines += tile._walk_node('tst', 'tst', np.array(points, float), np.array(faces, int)) + ['endmodelgeom tst', 'donemodel tst']
    return '\n'.join(lines) + '\n'


class Sorting(unittest.TestCase):
    def test_what_stands_on_the_floor_is_furniture_and_what_stands_off_it_is_the_room(self):
        _, _, nodes = geometry.parse(room()); kinds = {name: kind for name, (kind, _) in strip.sort(nodes).items()}
        self.assertEqual(kinds, {'floor': 'floor', 'rug': 'rug', 'wall_w': 'shell', 'wall_e': 'shell', 'wall_s': 'shell', 'wall_n': 'shell', 'lid': 'top',
                                 'table': 'furniture', 'books': 'furniture', 'leaf': 'shell'})  # a bookcase is walked as wall and is furniture still; a door's leaf at the rim is not

    def test_a_carpet_that_is_the_floor_is_no_rug(self):
        carpet = box('carpet', -3.5, 3.5, -3.5, 3.5, 0.01, 0.01, ('bitmap rug',))
        _, _, nodes = geometry.parse(room().replace('\n'.join(box('floor', -3.5, 3.5, -3.5, 3.5, 0, 0)), '\n'.join(carpet)))
        kinds = {name: kind for name, (kind, _) in strip.sort(nodes).items()}
        self.assertEqual((kinds['carpet'], kinds['rug'], kinds['table']), ('floor', 'floor', 'furniture'))  # two flat parts a finger apart: neither lies on the other

    def test_a_beam_from_wall_to_wall_stays(self):
        _, _, nodes = geometry.parse(room([box('beam', -3.5, 3.5, -0.1, 0.1, 2.5, 2.8)]))
        self.assertEqual(strip.sort(nodes)['beam'][0], 'shell')


class Stripping(unittest.TestCase):
    def test_a_stripped_tile_keeps_its_room_and_walks_where_the_furniture_stood(self):
        made, wok, out = strip.shell(room(), 'tst_u_01')
        self.assertEqual(sorted(out), ['books', 'rug', 'table'])
        _, root, nodes = geometry.parse(made); self.assertEqual(root, 'tst_u_01')
        self.assertEqual(sorted(node.name for node in nodes if node.kind != 'dummy'), sorted(['floor', 'leaf', 'lid', 'tst_u_01_wm', 'wall_e', 'wall_n', 'wall_s', 'wall_w']))
        _, walk = joins.bake(made); walked = [triangle for triangle in walk if int(triangle[0, 3]) == 5]
        self.assertAlmostEqual(sum(abs(joins.flat_area(triangle)) for triangle in walked), 49.0, places=6)  # the whole floor, the bookcase's foot too
        self.assertAlmostEqual(sum(abs(joins.flat_area(triangle)) for triangle in walk), 100.0, places=6)
        self.assertEqual(max(float(triangle[:, 2].max()) for triangle in walked), 0.0)  # the table's block is gone
        self.assertTrue(wok.startswith('beginwalkmeshgeom tst_u_01\nnode aabb tst_u_01_wm\n'))

    def test_what_no_furniture_stood_on_stays_as_it_was(self):
        _, _, faces = strip.stripped(room(), gone=('rug',))
        self.assertEqual(sorted({surface for _, surface in faces}), [2, 5, 7]); self.assertEqual(max(corner[2] for corners, _ in faces for corner in corners), 0.8)


class ModernInterior(unittest.TestCase):
    def test_the_living_room_tile_strips_to_an_empty_room(self):
        text = (REPO / 'srn_t_tfb01' / 'tfb01_e01_01.mdl').read_bytes().decode('cp1252'); _, _, nodes = geometry.parse(text); found = strip.sort(nodes)
        looks = {node.name: node.material for node in nodes}
        self.assertEqual({looks[name] for name, (kind, _) in found.items() if kind == 'shell'}, {'tfb01_lwalls', 'tfb01_door2', 'tfb01_metaldoor'})
        self.assertEqual(sorted({looks[name] for name, (kind, _) in found.items() if kind == 'furniture'}), ['tfb01_bed02', 'tfb01_books', 'tfb01_door2', 'tfb01_furnish2', 'tfb01_shpflr1'])
        made, _, out = strip.shell(text); self.assertEqual(len(out), 11)
        _, walk = joins.bake(made); area = lambda surface: sum(abs(joins.flat_area(triangle)) for triangle in walk if int(triangle[0, 3]) == surface)
        self.assertGreater(area(5), 51.0); self.assertEqual(area(7), 0.0)  # 38.7 square metres were walked before

    def test_every_tile_of_the_set_sorts(self):
        laid = inventory.read_set((REPO / 'srn_t_tfb01' / 'tfb01.set').read_bytes().decode('cp1252')); kinds = {}
        for model in sorted({one['model'].lower() for one in laid['tiles']}):
            path = REPO / 'srn_t_tfb01' / f'{model}.mdl'
            if path.is_file():
                _, _, nodes = geometry.parse(path.read_bytes().decode('cp1252'))
                for kind, _ in strip.sort(nodes).values():
                    kinds[kind] = kinds.get(kind, 0) + 1
        self.assertEqual(set(kinds), set(strip.KINDS)); self.assertGreater(kinds['furniture'], 1500)


if __name__ == '__main__':
    unittest.main()
