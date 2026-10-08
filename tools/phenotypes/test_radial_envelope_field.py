import unittest
import numpy as np
from radial_envelope_field import Cylinder, frame, hermite, cosine_falloff, angular_weight, smooth_grid, surface_samples, width_depth_profile
from test_descendant_mesh_edit import capped_cylinder


class RadialEnvelopeFieldTest(unittest.TestCase):
    def test_fill_nan_rows_respects_max_missing(self):
        from radial_envelope_field import fill_nan_rows
        G = np.array([[1.0, np.nan, 3.0, 4.0], [np.nan, np.nan, np.nan, 2.0], [np.nan] * 4])
        F = fill_nan_rows(G, max_missing=0.5)
        self.assertAlmostEqual(F[0, 1], 2.0)
        self.assertTrue(np.isnan(F[1, :3]).all())      # too sparse: left as measured
        self.assertTrue(np.isnan(F[2]).all())
        self.assertFalse(np.isnan(fill_nan_rows(G)[1]).any())

    def test_frame_convention(self):
        R = frame([0, 0, 1])
        self.assertTrue(np.allclose(R, [[0, 1, 0], [1, 0, 0], [0, 0, 1]]))

    def test_profile_and_identity_apply(self):
        pos, faces = capped_cylinder(radius=0.05, height=0.3, rings=30, segments=36)
        cyl = Cylinder([0, 0, 0], [0, 0, 1], pos, 0.0, 0.3, step=0.01)
        G, th = cyl.outer_profile(surface_samples(pos, faces, 20000), 10)
        self.assertAlmostEqual(np.nanmedian(G), 0.05, delta=0.002)
        X, val = cyl.apply(pos, np.ones_like(G), th)
        self.assertTrue(np.allclose(X, pos))
        F = np.ones_like(G); F[10:20] = 0.8
        X, val = cyl.apply(pos, F, th)
        mid = np.abs(pos[:, 2] - 0.15) < 0.04
        self.assertTrue(np.allclose(np.hypot(X[mid, 0], X[mid, 1])[np.hypot(pos[mid, 0], pos[mid, 1]) > 0.04], 0.04, atol=1e-6))
        self.assertTrue(np.allclose(X[:, 2], pos[:, 2]))

    def test_scalar_helpers(self):
        self.assertAlmostEqual(float(hermite(np.array(0.0), 0, 1, 0, 1, 2, 0)), 1.0)
        self.assertAlmostEqual(float(hermite(np.array(1.0), 0, 1, 0, 1, 2, 0)), 2.0)
        w = cosine_falloff(np.array([-1, 0, 0.5, 1, 2]), 0, 1, -1, 2)
        self.assertTrue(np.allclose(w, [0, 1, 1, 1, 0]))
        self.assertAlmostEqual(float(angular_weight(np.array([175.0]), -175, 20, 40)[0]), 1.0)
        G = np.zeros((30, 36)); G[15, 0] = 1
        S = smooth_grid(G, 1, 1)
        self.assertAlmostEqual(S.sum(), 1.0, places=6)
        pos, faces = capped_cylinder(radius=0.05, height=0.3)
        rows = width_depth_profile(pos, faces, [0.157])
        self.assertAlmostEqual(rows[0]['widthX'], 0.1, delta=0.002)


if __name__ == '__main__':
    unittest.main()
