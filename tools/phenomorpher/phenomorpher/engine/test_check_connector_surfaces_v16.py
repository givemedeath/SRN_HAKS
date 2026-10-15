import unittest
import numpy as np
from .check_connector_surfaces_v15 import closed_owner_triangles
from .check_connector_surfaces_v16 import NECK_LINKS, audit, closed_oriented_triangles, penetration
from .check_terminal_connectivity_v13 import LINKS

TETRA = (np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1]], float), np.array([[0, 2, 1], [0, 1, 3], [0, 3, 2], [1, 2, 3]]))


def box(part, lo, hi, name=None):
    """Closed, outward-oriented box mesh."""
    (x0, y0, z0), (x1, y1, z1) = lo, hi
    p = np.array([[x, y, z] for z in (z0, z1) for y in (y0, y1) for x in (x0, x1)], float)
    f = np.array([[0, 2, 1], [1, 2, 3], [4, 5, 6], [5, 7, 6], [0, 1, 4], [1, 5, 4],
                  [2, 6, 3], [3, 6, 7], [0, 4, 2], [2, 4, 6], [1, 3, 5], [3, 7, 5]])
    return {'part': part, 'name': name or part, 'position': p, 'faces': f}


def frame(z):
    m = np.eye(4); m[2, 3] = z; return m


class ConnectorV16Tests(unittest.TestCase):
    def test_nonmanifold_closed_oriented_surfaces_measure_penetration(self):
        # Two tetrahedra sharing one edge: each edge cancels, but the shared edge has four uses.
        p, f = TETRA; second = (p * [-1, -1, 1]).copy()
        meshes = [{'part': 'pelvis', 'name': 'a', 'position': p, 'faces': f},
                  {'part': 'pelvis', 'name': 'b', 'position': second, 'faces': f[:, [0, 2, 1]]}]
        self.assertIsNone(closed_owner_triangles(meshes, 'pelvis'))
        triangles, report = closed_oriented_triangles(meshes, 'pelvis')
        self.assertIsNotNone(triangles)
        self.assertEqual((report['surface'], report['unbalancedEdges'], report['nonManifoldEdges']), ('closed-oriented-nonmanifold', 0, 1))
        closed = (triangles, report)
        r = penetration(np.array([[-.1, -.1, .1]]), np.array([[-.1, -.1, .1]]), np.ones(1), closed, closed, 1.)
        self.assertEqual(r['status'], 'measured'); self.assertAlmostEqual(r['candidateInsideAreaFraction'], 1.)

    def test_open_surfaces_stay_unavailable(self):
        m = {'part': 'chest', 'name': 'open', 'position': np.eye(3), 'faces': np.array([[0, 1, 2]])}
        triangles, report = closed_oriented_triangles([m], 'chest')
        self.assertIsNone(triangles); self.assertEqual(report['surface'], 'open')
        r = penetration(np.zeros((1, 3)), np.zeros((1, 3)), np.ones(1), (triangles, report), (triangles, report), 1.)
        self.assertEqual(r['status'], 'unavailable')

    def test_a_submesh_seam_crack_within_tolerance_counts_as_joined(self):
        whole = box('pelvis', (0, 0, 0), (1, 1, 1))
        def split(gap):
            second = whole['position'].copy(); second[7, 0] += gap
            return [{**whole, 'name': 'p1', 'faces': whole['faces'][:6]}, {**whole, 'name': 'p3', 'position': second, 'faces': whole['faces'][6:]}]
        triangles, report = closed_oriented_triangles(split(2.7e-5), 'pelvis')
        self.assertIsNotNone(triangles)
        self.assertEqual((report['surface'], report['exactUnbalancedEdges'], report['seamJoinedPositions']), ('closed-manifold', 4, 1))
        self.assertAlmostEqual(report['seamMaximumGapMeters'], 2.7e-5)
        # The exact positions are kept for the winding number.
        self.assertIn(1 + 2.7e-5, triangles[:, :, 0])
        triangles, report = closed_oriented_triangles(split(5e-4), 'pelvis')
        self.assertIsNone(triangles); self.assertEqual((report['surface'], report['seamJoinedPositions']), ('open', 0))

    def test_close_positions_inside_one_mesh_are_never_joined(self):
        whole = box('pelvis', (0, 0, 0), (1, 1, 1)); p = whole['position'].copy(); p[7, 0] += 2.7e-5
        cracked = {**whole, 'position': np.vstack([whole['position'], p[7:]]), 'faces': np.where(np.arange(12)[:, None] >= 6,
                   np.where(whole['faces'] == 7, 8, whole['faces']), whole['faces'])}
        triangles, report = closed_oriented_triangles([cracked], 'pelvis')
        self.assertIsNone(triangles); self.assertEqual((report['surface'], report['seamJoinedPositions']), ('open', 0))

    def test_neck_links_are_measured_from_the_assembly_frames(self):
        meshes = [box('chest', (-.2, -.1, 0.), (.2, .1, 1.)), box('neck', (-.05, -.05, .98), (.05, .05, 1.2)),
                  box('head', (-.1, -.1, 1.18), (.1, .1, 1.45))]
        frames = {'torso_g': frame(0.), 'neck_g': frame(1.), 'head_g': frame(1.3)}
        result = audit(meshes, meshes, frames, frames, links=NECK_LINKS)
        self.assertTrue(result['allRequestedConnectorsMeasured'], result['connectors'])
        neck = result['connectors'][0]
        self.assertEqual(neck['parts'], ['chest', 'neck'])
        self.assertEqual({d['penetration']['status'] for d in neck['directions']}, {'measured'})
        self.assertEqual(result['links'], [list(l) for l in NECK_LINKS])
        self.assertNotIn(('chest', 'neck'), LINKS)

    def test_a_topology_change_only_drops_the_affected_link(self):
        meshes = [box('chest', (-.2, -.1, 0.), (.2, .1, 1.)), box('neck', (-.05, -.05, .98), (.05, .05, 1.2)),
                  box('head', (-.1, -.1, 1.18), (.1, .1, 1.45))]
        changed = [dict(m) for m in meshes]; changed[2] = {**changed[2], 'faces': changed[2]['faces'][:, [0, 2, 1]]}
        frames = {'torso_g': frame(0.), 'neck_g': frame(1.), 'head_g': frame(1.3)}
        rows = {tuple(r['parts']): r for r in audit(meshes, changed, frames, frames, links=NECK_LINKS)['connectors']}
        self.assertEqual(rows[('chest', 'neck')]['status'], 'measured')
        self.assertEqual(rows[('neck', 'head')]['status'], 'unavailable')
        self.assertIn('lineage differs for head', rows[('neck', 'head')]['reason'])


if __name__ == '__main__':
    unittest.main()
