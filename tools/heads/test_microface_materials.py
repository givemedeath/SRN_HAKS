import unittest
import numpy as np
from propose_material_masks import microface_neighbors


class MicrofaceMaterialTests(unittest.TestCase):
    def test_surface_inheritance_is_bounded_and_does_not_change_geometry(self):
        surface=np.array([[0.,0,0],[.01,0,0],[0,.01,0]])
        tiny=np.array([[.003,.003,.0005],[.00301,.003,.0005],[.003,.00301,.0005]])
        points=np.array([surface,tiny]);before=points.copy()
        neighbors,distance=microface_neighbors(points,1,2,[1])
        self.assertEqual(neighbors.tolist(),[0]);self.assertAlmostEqual(distance,.0005)
        np.testing.assert_array_equal(points,before)
        points[1,:,2]=.0011
        with self.assertRaisesRegex(ValueError,'distance bound'):microface_neighbors(points,1,2,[1])
        with self.assertRaisesRegex(ValueError,'No verified'):microface_neighbors(points,1,2,[0,1])


if __name__=='__main__':unittest.main()
