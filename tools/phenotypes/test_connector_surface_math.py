import unittest
import numpy as np
from connector_surface_math import triangle_relation,distinct_ray_hits,parity_consensus,closest_points_on_triangles


class SurfaceRelationTests(unittest.TestCase):
    def test_overlapping_boxes_do_not_imply_triangle_contact(self):
        first=np.asarray([[0,0,0],[2,0,0],[0,2,0.]])
        second=np.asarray([[1.5,1.5,0],[3,1.5,0],[1.5,3,0.]])
        self.assertTrue(np.all(np.minimum(first.max(0),second.max(0))>=np.maximum(first.min(0),second.min(0))))
        self.assertIsNone(triangle_relation(first,second))

    def test_crossing_surface_segment_and_symmetry(self):
        a=np.asarray([[0,0,0],[2,0,0],[0,2,0.]])
        b=np.asarray([[.5,-.5,-1],[.5,1.5,1],[.5,1.5,-1]])
        left,right=triangle_relation(a,b),triangle_relation(b,a)
        self.assertEqual(left['kind'],'segment');self.assertAlmostEqual(left['length'],1.)
        self.assertAlmostEqual(left['length'],right['length'])
        np.testing.assert_allclose(left['points'][:,[0,2]],[[.5,0],[.5,0]])

    def test_coplanar_containment_has_surface_area(self):
        a=np.asarray([[0,0,0],[2,0,0],[0,2,0.]])
        b=np.asarray([[.25,.25,0],[.75,.25,0],[.25,.75,0]])
        result=triangle_relation(a,b)
        self.assertEqual(result['kind'],'coplanar');self.assertAlmostEqual(result['area'],.125)

    def test_shared_edge_contact_and_parallel_separation(self):
        a=np.asarray([[0,0,0],[1,0,0],[0,1,0.]])
        b=np.asarray([[0,0,0],[1,0,0],[0,-1,0.]])
        result=triangle_relation(a,b);self.assertEqual(result['area'],0);self.assertAlmostEqual(result['length'],1)
        self.assertIsNone(triangle_relation(a,b+[0,0,.00001]))

    def test_degenerate_surface_fails_closed(self):
        with self.assertRaises(ValueError): triangle_relation(np.zeros((3,3)),np.eye(3))

    def test_duplicate_shared_edge_hits_and_consensus(self):
        self.assertEqual(distinct_ray_hits([2,1,1+1e-7]),2)
        self.assertEqual(parity_consensus([1,3,1,1,5]),'inside')
        self.assertEqual(parity_consensus([2,4,2,0,2]),'outside')
        self.assertEqual(parity_consensus([2,3,2,2,2]),'ambiguous')

    def test_surface_relation_is_rigid_frame_invariant(self):
        a=np.asarray([[0,0,0],[2,0,0],[0,2,0.]])
        b=np.asarray([[.5,-.5,-1],[.5,1.5,1],[.5,1.5,-1]])
        rotation=np.asarray([[0,-1,0],[1,0,0],[0,0,1.]])
        first=triangle_relation(a,b);second=triangle_relation(a@rotation.T+[2,3,4],b@rotation.T+[2,3,4])
        self.assertAlmostEqual(first['length'],second['length'])

    def test_actual_closest_triangle_interior_edge_and_vertex(self):
        triangle = np.asarray([[[0,0,0],[2,0,0],[0,2,0.]]])
        np.testing.assert_allclose(closest_points_on_triangles([.5,.5,3],triangle),[[.5,.5,0]])
        np.testing.assert_allclose(closest_points_on_triangles([2,2,3],triangle),[[1,1,0]])
        np.testing.assert_allclose(closest_points_on_triangles([-1,-2,3],triangle),[[0,0,0]])

    def test_closest_triangle_distance_preserves_rigid_frame_and_excludes_box(self):
        triangles = np.asarray([[[0,0,0],[2,0,0],[0,2,0]],[[1.5,1.5,0],[3,1.5,0],[1.5,3,0.]]])
        point = np.asarray([1.6,1.6,.2])
        values = closest_points_on_triangles(point,triangles)
        self.assertEqual(np.argmin(np.linalg.norm(values-point,axis=1)),1)
        rotation = np.asarray([[0,0,1],[1,0,0],[0,1,0.]])
        translated = closest_points_on_triangles(point@rotation.T+[4,5,6],triangles@rotation.T+[4,5,6])
        np.testing.assert_allclose(translated,values@rotation.T+[4,5,6],atol=1e-14)

    def test_closest_triangle_rejects_degenerate_or_nonfinite(self):
        with self.assertRaises(ValueError): closest_points_on_triangles([0,0,0],np.zeros((1,3,3)))
        with self.assertRaises(ValueError): closest_points_on_triangles([0,0,np.nan],np.eye(3)[None])


if __name__=='__main__':unittest.main()
