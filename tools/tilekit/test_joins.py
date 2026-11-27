"""The join tiles of the unified city tileset: how a join is cut, and that the pack holds what today's tiles give."""
import json
import unittest
from pathlib import Path

import numpy as np

from tools.tilekit import geometry, inventory, joins

REPO = Path(__file__).resolve().parents[2]
PACKS = ('srn_t_srx01', 'srn_t_dgt04', 'srn_t_udp1', 'srn_t_fcx01', 'srn_t_common')  # what this reads: named so the test selector runs it when one changes
SPEC_PATH = REPO / 'docs' / 'tilesets' / 'srx01' / 'joins.json'
SPEC = json.loads(SPEC_PATH.read_text(encoding='utf-8'))
SQUARE = [np.array([[-5, -5, 0, 0, 0], [5, -5, 0, 1, 0], [5, 5, 0, 1, 1]], float), np.array([[-5, -5, 0, 0, 0], [5, 5, 0, 1, 1], [-5, 5, 0, 0, 1]], float)]


def area(triangles):
    return sum(abs(joins.flat_area(one)) for one in triangles)


class Cutting(unittest.TestCase):
    def test_the_two_sides_of_every_shape_fill_the_tile_and_lie_where_the_set_says(self):
        for shape, theirs in joins.SHAPES.items():
            with self.subTest(shape=shape):
                city, other = joins.sides(shape, SQUARE, SQUARE)
                self.assertAlmostEqual(area(city) + area(other), 100.0, places=6)
                for triangles, wanted in ((city, False), (other, True)):
                    for triangle in triangles:
                        self.assertEqual(joins.other_side(shape, *triangle[:, :2].mean(0)), wanted)
                for corner, (x, y) in joins.CORNERS.items():  # just inside each corner
                    self.assertEqual(joins.other_side(shape, x * 0.98, y * 0.98), corner in theirs, corner)

    def test_a_cut_keeps_the_picture_where_it_was(self):
        for piece in joins.inside(SQUARE, joins.disc('TopLeft')) + joins.outside(SQUARE, joins.disc('BottomRight')):
            np.testing.assert_allclose(piece[:, 3:5], (piece[:, :2] + 5) / 10, atol=1e-9)

    def test_a_boundary_meets_each_tile_edge_at_its_middle(self):
        for shape in joins.SHAPES:
            for line in joins.seams(shape):
                for x, y in (line[0], line[-1]):
                    self.assertTrue((abs(abs(x) - 5) < 1e-9 and abs(y) < 1e-9) or (abs(abs(y) - 5) < 1e-9 and abs(x) < 1e-9), (shape, x, y))

    def test_a_ramp_is_flat_at_the_seam_and_whole_beyond_its_reach(self):
        high = [np.array([[-5, -5, 1, 0, 0], [5, -5, 1, 0, 0], [5, 0, 1, 0, 0]], float), np.array([[-5, -5, 1, 0, 0], [5, 0, 1, 0, 0], [-5, 0, 1, 0, 0]], float)]
        for triangle in joins.ramp(high):
            np.testing.assert_allclose(triangle[:, 2], np.clip(-triangle[:, 1] / joins.RAMP, 0, 1), atol=1e-9)

    def test_a_sliver_with_no_area_is_left_out_and_ends(self):
        whole = np.array([[0, 0, 0, 4, 0], [2, 0, 0, 4, 0], [0, 2, 0, 4, 0]], float)
        sliver = np.array([[0, 0, 0, 4, 0], [2, 0, 0, 4, 0], [1, 0, 0, 4, 0]], float)  # three corners on one line, one of them on its own other edges
        vertices, faces = joins.conformed([whole, sliver, np.array([[1, 0, 0, 4, 0], [2, 0, 0, 4, 0], [1, -1, 0, 4, 0]], float)])
        self.assertEqual(len(faces), 3)  # the whole face split at (1, 0), and the face below it; the sliver gone

    def test_two_corners_a_millimetre_apart_split_once(self):
        far = np.array([[4.9, 5.0, 5, 4, 0], [-2.001, 4.8, 5, 4, 0], [-4.8, 4.8, 5, 4, 0]], float)
        near = np.array([[-4.8, 4.8, 5, 4, 0], [-2.0, 4.8, 5, 4, 0], [-2.001, 4.8, 5, 4, 0]], float)
        vertices, faces = joins.conformed([far, np.array([[-2.0, 4.8, 5, 4, 0], [4.9, 4.8, 5, 4, 0], [4.9, 5.0, 5, 4, 0]], float), near])
        self.assertLessEqual(len(faces), 4)

    def test_walk_faces_share_every_corner_along_a_cut(self):
        split = joins._half(SQUARE, (0, -5), (0, 5)) + joins._half(joins._half(SQUARE, (0, -5), (0, 5), False), (-5, 2), (5, 2)) \
            + joins._half(joins._half(SQUARE, (0, -5), (0, 5), False), (-5, 2), (5, 2), False)
        vertices, faces = joins.conformed([np.c_[one[:, :3], np.full(3, 4.0), np.zeros(3)] for one in split])
        edges = {}
        for a, b, c, surface in faces.tolist():
            self.assertEqual(surface, 4)
            for edge in ((a, b), (b, c), (c, a)):
                edges[tuple(sorted(edge))] = edges.get(tuple(sorted(edge)), 0) + 1
        for (a, b), count in edges.items():  # an edge used once lies on the tile's rim
            if count == 1:
                self.assertTrue(any(abs(abs(vertices[a][axis]) - 5) < 1e-6 and abs(abs(vertices[b][axis]) - 5) < 1e-6 and vertices[a][axis] == vertices[b][axis] for axis in (0, 1)), (vertices[a], vertices[b]))
        self.assertAlmostEqual(sum(np.linalg.norm(np.cross(vertices[b] - vertices[a], vertices[c] - vertices[a])) / 2 for a, b, c, _ in faces.tolist()), 100.0, places=5)


class Built(unittest.TestCase):
    def test_the_pack_holds_what_todays_tiles_give(self):
        self.assertEqual(joins.stale(REPO, SPEC_PATH, SPEC_PATH.with_name('joins-built.json')), [])  # a tile a join is cut from changed: `tilekit joins`, then compile

    def test_each_join_tile_of_the_set_is_built_with_its_walkmesh_and_minimap(self):
        laid = inventory.read_set((REPO / 'srn_t_srx01' / 'srx01.set').read_bytes().decode('cp1252')); models = {tile['model']: tile for tile in laid['tiles']}
        records = joins.tiles(SPEC); self.assertEqual(len({record['model'] for record in records}), len(records))
        for record in records:
            with self.subTest(model=record['model']):
                tile = models[record['model']]
                self.assertEqual(tile['corners'], [record['corners'][corner] for corner in ('TopLeft', 'TopRight', 'BottomLeft', 'BottomRight')])
                self.assertEqual(tile['crossers'], [record['crossers'][side] for side in joins.SIDES])
                for path in (f'sources/srn_t_srx01/{record["model"]}.mdl', f'srn_t_srx01/{record["model"]}.mdl', f'srn_t_srx01/{record["model"]}.wok', f'srn_t_srx01/{record["minimap"]}.tga'):
                    self.assertTrue((REPO / path).is_file(), path)
        edge = (REPO / 'srn_2da' / 'srx01_edge.2da').read_bytes().decode('cp1252')
        for one, other, model in joins.edges(SPEC):
            self.assertRegex(edge, rf'(?m)^\d+\s+{one}\s+\*\*\*\*\s+{other}\s+0\s+{model}\s*$')
            self.assertTrue((REPO / 'srn_t_srx01' / f'{model}.mdl').is_file(), model)

    def test_a_join_is_walked_across_and_stays_in_its_tile(self):
        for path in sorted((REPO / 'sources' / 'srn_t_srx01').glob('*.mdl')):
            with self.subTest(model=path.stem):
                _, _, nodes = geometry.parse(path.read_text(encoding='ascii')); walk = [node for node in nodes if node.kind == 'aabb']
                self.assertEqual(len(walk), 1); points = np.array(walk[0].verts)
                self.assertAlmostEqual(sum(joins.flat_area(points[[a, b, c]]) for a, b, c, *_ in walk[0].faces), 100.0, places=3)
                self.assertTrue(all(joins.flat_area(points[[a, b, c]]) > 0 for a, b, c, *_ in walk[0].faces))  # every face up
                for node in nodes:
                    if node.verts:
                        self.assertLessEqual(np.abs(np.array(node.verts)[:, :2]).max(), 5 + 1e-6, node.name)
                if path.stem[-4] in joins.ROADS:  # a road's heights are gone at the seam, and the city's half is flat
                    self.assertLess(np.abs(points[points[:, 1] >= -1e-6][:, 2]).max(), 1e-6)


if __name__ == '__main__':
    unittest.main()
