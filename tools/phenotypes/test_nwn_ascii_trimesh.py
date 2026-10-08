import unittest
import numpy as np
from nwn_ascii_trimesh import AsciiModel, match_corners, vertex_average, rebuild_rows, closure, weld, fmt

TEXT = '\r\n'.join([
    'newmodel m', 'setsupermodel m NULL', 'beginmodelgeom m', 'node dummy m', '  parent NULL', 'endnode',
    'node trimesh mp', '  parent m', '  position 0 0 0', '  bitmap m', '  verts 4',
    '    0 0 0', '    1 0 0', '    0 1 0', '    0 0 1',
    '  normals 4', '    0 0 1', '    0 0 1', '    0 0 1', '    0 0 1',
    '  tverts 4', '    0 0 0', '    1 0 0', '    0 1 0', '    0.5 0.5 0',
    '  faces 4', '    0 2 1 1 0 2 1 1', '    0 1 3 1 0 1 3 1', '    1 2 3 1 1 2 3 1', '    2 0 3 1 2 0 3 1',
    'endnode', 'endmodelgeom m', 'donemodel m']) + '\r\n'


class AsciiTrimeshTest(unittest.TestCase):
    def test_parse_round_trip_and_sections(self):
        am = AsciiModel(TEXT)
        self.assertEqual(am.text(), TEXT)
        n = am.node('mp'); V, N, TV, F = am.arrays(n)
        self.assertEqual((len(V), len(TV), len(F)), (4, 4, 4))
        self.assertEqual(closure(F[:, :3])['boundaryEdges'], 0)

    def test_set_vectors_keeps_unchanged_rows_exactly(self):
        am = AsciiModel(TEXT); n = am.node('mp'); V = am.arrays(n)[0].copy(); V[3] = [0, 0, 1.25]
        self.assertEqual(am.set_vectors(n, 'verts', V), 1)
        lines = am.text().split('\r\n')
        self.assertIn('    0 0 0', lines); self.assertIn('    0 0 1.25', lines)
        self.assertEqual(AsciiModel(am.text()).arrays(am.node('mp'))[0][3, 2], 1.25)

    def test_match_corners_with_rotation_and_shuffle(self):
        am = AsciiModel(TEXT); P, T, _ = am.corners(am.node('mp'))
        order = np.array([2, 0, 3, 1]); rot = np.array([1, 2, 0])
        Pb = P[order][:, rot]; Tb = T[order][:, rot]
        face, perm, ep, et = match_corners(P, T, Pb, Tb)
        self.assertEqual(ep, 0.0); self.assertEqual(et, 0.0)
        self.assertTrue(np.array_equal(Pb[face[:, None], perm], P))

    def test_rebuild_rows_welds_and_closes(self):
        am = AsciiModel(TEXT); P, T, N = am.corners(am.node('mp'))
        rows, arr = rebuild_rows(P, N, T, [1] * 4, [1] * 4)
        self.assertEqual(len(rows['verts']), 4); self.assertEqual(closure(arr['vi'])['boundaryEdges'], 0)
        am.replace_section(am.node('mp'), 'faces', rows['faces'])
        self.assertEqual(len(am.arrays(am.node('mp'))[3]), 4)
        self.assertEqual(closure(weld(P))['boundaryEdges'], 0)

    def test_vertex_average_and_fmt(self):
        idx = np.array([[0, 1, 1]]); vals = np.array([[[1., 0, 0], [0, 2, 0], [0, 4, 0]]])
        m, n = vertex_average(idx, vals, 2)
        self.assertTrue(np.allclose(m[1], [0, 3, 0])); self.assertEqual(n.tolist(), [1, 2])
        self.assertEqual(fmt(0.0), '0'); self.assertEqual(float(fmt(0.1)), float(np.float32(0.1)))


if __name__ == '__main__':
    unittest.main()
