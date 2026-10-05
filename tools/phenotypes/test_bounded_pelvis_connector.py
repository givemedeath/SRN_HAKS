import unittest
import numpy as np
from bounded_pelvis_connector import (allowed_shared_contact, build_cap, chart_attributes,
    ear_partition, intersect_meshes, triangle_contact)


class BoundedConnectorTests(unittest.TestCase):
    def ring(self):
        return np.array([[0.,0.,0.],[2.,.001,0.],[2.,0.,2.],[1.,.002,1.],[0.,0.,2.]])

    def test_concave_projection_coverage_and_fixed_ring(self):
        ring=self.ring(); cap=build_cap(ring,.01,.001)
        self.assertTrue(np.array_equal(cap['positions'][:len(ring)],ring))
        cross=np.cross(np.diff(cap['positions'][cap['faces']][:,[0,1]],axis=1)[:,0],
                       cap['positions'][cap['faces']][:,2]-cap['positions'][cap['faces']][:,0])
        self.assertAlmostEqual(float(-cross[:,1].sum()/2),3.)
        self.assertLessEqual(cap['positions'][:,1].max(),ring[:,1].max())
        self.assertAlmostEqual(float(cap['positions'][:,1].min()),-.001)

    def test_internal_original_diagonal_is_not_reused(self):
        ring=self.ring(); cap=build_cap(ring,.01,.001); n=len(ring)
        boundary={tuple(sorted((i,(i+1)%n))) for i in range(n)}
        for face in cap['faces']:
            for a,b in zip(face,np.roll(face,-1)):
                if a<n and b<n:self.assertIn(tuple(sorted((a,b))),boundary)

    def test_triangle_graph_has_disk_boundary_and_opposed_internal_edges(self):
        cap=build_cap(self.ring(),.01,.001); owners={}
        for face in cap['faces']:
            for a,b in zip(face,np.roll(face,-1)):owners.setdefault(tuple(sorted((int(a),int(b)))),[]).append((int(a),int(b)))
        boundary=[key for key,v in owners.items() if len(v)==1]
        self.assertEqual(len(boundary),5)
        for v in owners.values():
            self.assertIn(len(v),(1,2))
            if len(v)==2:self.assertEqual(v[0],v[1][::-1])

    def test_chart_normal_uv_tangent_orientation(self):
        cap=build_cap(self.ring(),.01,.001); attrs=chart_attributes(cap['positions'],cap['faces'])
        self.assertTrue(np.isfinite(attrs['TANGENT']).all())
        self.assertTrue(np.allclose(np.linalg.norm(attrs['NORMAL'],axis=1),1))
        self.assertTrue(np.allclose(np.linalg.norm(attrs['TANGENT'][:,:3],axis=1),1))
        self.assertTrue(np.allclose(np.sum(attrs['NORMAL']*attrs['TANGENT'][:,:3],axis=1),0,atol=1e-12))
        self.assertTrue(np.all(np.abs(attrs['TANGENT'][:,3])==1))
        self.assertTrue(np.all(attrs['TEXCOORD_0']>=0) and np.all(attrs['TEXCOORD_0']<=1))

    def test_self_crossing_port_rejected(self):
        with self.assertRaisesRegex(ValueError,'Self-crossing'):ear_partition(np.array([[0.,0.],[2.,2.],[0.,2.],[2.,0.]]))

    def test_repeated_vertex_rejected(self):
        with self.assertRaisesRegex(ValueError,'Repeated'):ear_partition(np.array([[0.,0.],[1.,0.],[0.,0.],[0.,1.]]))

    def test_bad_orientation_rejected(self):
        with self.assertRaisesRegex(ValueError,'downward'):build_cap(self.ring()[::-1],.01,.001)

    def test_broad_displacement_or_inset_rejected(self):
        for fraction,drop in ((0,.001),(.11,.001),(.01,.006),(.01,0)):
            with self.assertRaises(ValueError):build_cap(self.ring(),fraction,drop)

    def test_caps_have_no_self_intersections(self):
        cap=build_cap(self.ring(),.01,.001); xyz=cap['positions'][cap['faces']]
        self.assertEqual(intersect_meshes(xyz,xyz,same=True)['forbiddenContacts'],[])

    def test_parallel_disjoint_triangles(self):
        a=np.array([[0.,0.,0.],[1.,0.,0.],[0.,1.,0.]])
        self.assertEqual(triangle_contact(a,a+[0,0,1]),[])

    def test_noncoplanar_crossing_detected(self):
        a=np.array([[0.,0.,0.],[1.,0.,0.],[0.,1.,0.]])
        b=np.array([[.2,.2,-1.],[.2,.2,1.],[.8,.2,0.]])
        contacts=triangle_contact(a,b)
        self.assertEqual(len(contacts),2)
        self.assertFalse(allowed_shared_contact(a,b,contacts))

    def test_coplanar_overlap_detected(self):
        a=np.array([[0.,0.,0.],[1.,0.,0.],[0.,1.,0.]])
        b=a+[.1,.1,0]
        self.assertGreaterEqual(len(triangle_contact(a,b)),3)
        self.assertFalse(allowed_shared_contact(a,b,triangle_contact(a,b)))

    def test_coplanar_disjoint_with_overlapping_bounds(self):
        a=np.array([[0.,0.,0.],[1.,0.,0.],[0.,1.,0.]])
        b=np.array([[.8,.8,0.],[1.1,.8,0.],[.8,1.1,0.]])
        self.assertEqual(triangle_contact(a,b),[])

    def test_shared_edge_permitted(self):
        a=np.array([[0.,0.,0.],[1.,0.,0.],[0.,1.,0.]])
        b=np.array([[1.,0.,0.],[0.,0.,0.],[0.,0.,1.]])
        self.assertTrue(allowed_shared_contact(a,b,triangle_contact(a,b)))

    def test_shared_vertex_does_not_allow_other_crossing(self):
        a=np.array([[0.,0.,0.],[1.,0.,0.],[0.,1.,0.]])
        b=np.array([[0.,0.,0.],[.3,.3,-1.],[.3,.3,1.]])
        self.assertFalse(allowed_shared_contact(a,b,triangle_contact(a,b)))

    def test_coincident_triangles_rejected(self):
        a=np.array([[0.,0.,0.],[1.,0.,0.],[0.,1.,0.]])
        self.assertFalse(allowed_shared_contact(a,a[::-1],triangle_contact(a,a[::-1])))

    def test_contact_invariant_under_proper_similarity(self):
        a=np.array([[0.,0.,0.],[1.,0.,0.],[0.,1.,0.]])
        b=np.array([[.2,.2,-1.],[.2,.2,1.],[.8,.2,0.]])
        rotation=np.array([[0.,0.,1.],[1.,0.,0.],[0.,1.,0.]])
        transformed=lambda x:x@rotation.T*.54+[.1,.2,.3]
        actual=np.array(triangle_contact(transformed(a),transformed(b)))
        expected=transformed(np.array(triangle_contact(a,b)))
        self.assertTrue(np.allclose(np.sort(actual,axis=0),np.sort(expected,axis=0)))


if __name__=='__main__':unittest.main()
