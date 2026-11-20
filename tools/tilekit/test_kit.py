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
