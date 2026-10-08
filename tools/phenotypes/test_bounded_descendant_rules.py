"""Bounded descendant normal/tangent rule and female crease fairing tests (synthetic, fail-closed)."""
import unittest
import numpy as np
import bounded_descendant_rules as rules
import fair_female_limb_creases as fair


def tube(n_theta=48, n_z=40, radius=0.05, crease=0.0):
    """Closed-ish limb tube along z in [-0.4, 0]; optional posterior valley (crease) of depth `crease`."""
    th = np.linspace(-np.pi, np.pi, n_theta, endpoint=False); z = np.linspace(-0.4, 0.0, n_z)
    T, Z = np.meshgrid(th, z, indexing='ij')
    r = radius - crease * np.exp(-((np.degrees(np.abs((T + np.pi) % (2 * np.pi) - np.pi)) - 180) ** 2) / (2 * 4.0 ** 2)) * np.cos(Z * 40) ** 2
    V = np.stack((r * np.sin(T), r * np.cos(T), Z), -1).reshape(-1, 3)
    idx = lambda i, j: (i % n_theta) * n_z + j
    F = []
    for i in range(n_theta):
        for j in range(n_z - 1):
            F += [(idx(i, j), idx(i + 1, j), idx(i + 1, j + 1)), (idx(i, j), idx(i + 1, j + 1), idx(i, j + 1))]
    F = np.asarray(F)
    if np.mean(np.einsum('ij,ij->i', fair.face_normals(V, F), np.c_[V[F].mean(1)[:, :2], np.zeros(len(F))])) < 0:
        F = F[:, ::-1]
    return V, F


def corners(V, F, scale=1.0):
    P = V[F]; N = fair.vertex_normals(V, F)[F] * scale
    return P, N


def full_region(**kw):
    r = {'axisCentre': [0.0, 0.0], 'thetaCentre': 0.0, 'thetaHalfFull': 180.0, 'thetaHalfZero': 180.0, 'zFull': [-1.0, 1.0], 'zZero': [-2.0, 2.0], 'weight': 1.0}
    r.update(kw); return r


class RuleTests(unittest.TestCase):
    def test_identity_map_renormalises_without_changing_direction(self):
        V, F = tube(); P, N = corners(V, F); N = N * np.linspace(0.13, 1.2, N.size // 3).reshape(N.shape[:2] + (1,))
        N1, _, rep = rules.apply(P, N, P.copy(), {'geometricSmoothing': 3, 'smoothingRegions': []})
        np.testing.assert_allclose(np.linalg.norm(N1, axis=2), 1, atol=1e-14)
        np.testing.assert_allclose(N1, N / np.linalg.norm(N, axis=2, keepdims=True), atol=1e-15)
        self.assertEqual(rep['movedVertices'], 0); self.assertGreater(rep['renormalisedCorners'], 0)

    def test_rigid_rotation_transports_authored_normals(self):
        V, F = tube(); P, N = corners(V, F); a = 0.3; R = np.array([[1, 0, 0], [0, np.cos(a), -np.sin(a)], [0, np.sin(a), np.cos(a)]])
        P1 = P @ R.T; N1, _, _ = rules.apply(P, N, P1, {'geometricSmoothing': 0, 'smoothingRegions': []})
        np.testing.assert_allclose(N1, unit(N) @ R.T, atol=1e-9)

    def test_smoothing_region_blends_toward_geometric(self):
        V, F = tube(); P, N = corners(V, F); noisy = N + 0.2 * np.random.default_rng(1).standard_normal(N.shape)
        N1, _, rep = rules.apply(P, noisy, P.copy(), {'geometricSmoothing': 0, 'smoothingRegions': [full_region()]})
        U, FF = rules.weld(P); np.testing.assert_allclose(N1, rules.smoothed_vertex_normals(U, FF, 0)[FF], atol=1e-12)
        self.assertEqual(rep['smoothedCorners'], N.size // 3)

    def test_tangents_orthogonal_length_and_handedness_kept(self):
        V, F = tube(); P, N = corners(V, F); P1 = P * np.array([1.1, 0.9, 1.0])
        T = np.concatenate([np.tile([[0.0, 0.0, 1.0]], (P.shape[0], 3, 1)) * 2.0, np.where(np.arange(P.shape[0]) % 2, 1.0, -1.0)[:, None, None] * np.ones((1, 3, 1))], -1)
        rows = np.arange(0, len(P), 3); N1, T1, _ = rules.apply(P, N, P1, {'geometricSmoothing': 1, 'smoothingRegions': []}, tangents=T[rows], tangent_rows=rows)
        np.testing.assert_allclose(np.sum(T1[..., :3] * N1[rows], -1), 0, atol=1e-12)
        np.testing.assert_allclose(np.linalg.norm(T1[..., :3], axis=-1), 2.0, atol=1e-12); np.testing.assert_array_equal(T1[..., 3], T[rows][..., 3])

    def test_child_splitting_a_weld_class_is_rejected(self):
        V, F = tube(); P, N = corners(V, F); P1 = P.copy(); P1[0, 0] += 1e-4          # one corner of a shared vertex moves alone
        with self.assertRaises(ValueError):
            rules.apply(P, N, P1, {'geometricSmoothing': 0, 'smoothingRegions': []})

    def test_near_duplicate_vertices_weld_and_move_together(self):
        V, F = tube(); P, N = corners(V, F); P = P.copy(); P[F == 5] += 3e-13          # dense-source split below the weld quantum
        U, FF = rules.weld(P); self.assertEqual(len(U), len(V))
        X = U.copy(); X[5] += [0, 0, 1e-3]; P1 = fair.child_corners(P, U, X, FF)
        N1, _, rep = rules.apply(P, N, P1, {'geometricSmoothing': 0, 'smoothingRegions': []}); self.assertEqual(rep['movedVertices'], 1)

    def test_malformed_region_rejected(self):
        for bad in (full_region(weight=0.0), full_region(zFull=[0.5, -0.5]), full_region(thetaHalfFull=90.0, thetaHalfZero=60.0), {**full_region(), 'extra': 1}):
            with self.assertRaises(ValueError):
                rules.region_weight(np.zeros((1, 3)), [bad])

    def test_region_window_is_cosine_and_bounded(self):
        r = full_region(thetaCentre=180.0, thetaHalfFull=60.0, thetaHalfZero=90.0, zFull=[-0.3, -0.1], zZero=[-0.35, -0.05])
        p = np.array([[0, -0.05, -0.2], [0, 0.05, -0.2], [0, -0.05, -0.36], [0.05, 0, -0.2]])
        w = rules.region_weight(p, [r]); np.testing.assert_allclose(w[:3], [1, 0, 0]); self.assertEqual(w[3], 0.0)


def unit(v):
    return v / np.linalg.norm(v, axis=-1, keepdims=True)


class FairingTests(unittest.TestCase):
    CFG = {'sRange': [-0.42, 0.02], 'band': {'thetaCentre': 180, 'thetaHalfFull': 60, 'thetaHalfZero': 90, 'sFull': [-0.3, -0.1], 'sZero': [-0.35, -0.05]},
           'radialPasses': 3, 'sigmaS': 0.015, 'sigmaArc': 0.01, 'tangentialIterations': 5, 'repairFoldAbove': 18.0, 'minAreaRatio': 0.02}

    def test_valley_fill_reduces_folds_and_keeps_outside_band_exact(self):
        V, F = tube(n_theta=96, n_z=80, crease=0.006)
        X, w, hist = fair.fair(V, F, self.CFG)
        self.assertLess(hist[-1]['p95'], hist[0]['p95']); np.testing.assert_array_equal(X[w == 0], V[w == 0])
        r0 = np.hypot(V[:, 0], V[:, 1]); r1 = np.hypot(X[:, 0], X[:, 1]); self.assertTrue(np.all(r1 >= r0 - 2e-4))   # fills valleys only
        self.assertFalse(np.any(fair.inverted_faces(X, F) & ~fair.inverted_faces(V, F)))

    def test_front_of_limb_untouched(self):
        V, F = tube(n_theta=96, n_z=80, crease=0.006); X, w, _ = fair.fair(V, F, self.CFG)
        front = V[:, 1] > 0.02; np.testing.assert_array_equal(X[front], V[front])

    def test_ambiguous_weld_rejected(self):
        P = np.array([[[0.4e-9, 0.0, 0.0], [0.6e-9, 0.0, 0.0], [0.0, 1.0, 0.0]]])          # straddles the 1e-9 grid
        with self.assertRaises(ValueError):
            fair.weld(P)


if __name__ == '__main__':
    unittest.main()
