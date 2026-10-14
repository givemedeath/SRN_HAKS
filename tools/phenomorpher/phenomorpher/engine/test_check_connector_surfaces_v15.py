import unittest
import numpy as np
from .check_connector_surfaces_v15 import closest_surface,directional_coverage,penetration,closed_owner_triangles,quadrature,audit

class ConnectorCoverageTests(unittest.TestCase):
    def test_point_contact_does_not_hide_wide_surface_gap(self):
        source=np.array([[[0.,0.,0.],[1.,0.,0.],[0.,1.,0.]]])
        candidate=source.copy();candidate[0,1:,2]=.3
        r=directional_coverage(source,source,source,candidate,1.)
        # One authored vertex remains in contact, yet all interior samples gap.
        self.assertEqual(float(np.linalg.norm(source[0,0]-candidate[0,0])),0.)
        self.assertLess(r['sourceCalibratedCoveredAreaFraction'],.01)
        self.assertGreater(r['candidateSurfaceDistanceMeters']['median'],.1)
        self.assertGreater(r['sourcePairedCandidateSeamDistanceMeters']['median'],.1)
    def test_exact_uniform_scale_keeps_source_offset_budget(self):
        a=np.array([[[0.,0.,0.],[1.,0.,0.],[0.,1.,0.]]]);b=a+[0,0,.02]
        r=directional_coverage(a,a*.5,b,b*.5,.5)
        self.assertAlmostEqual(r['sourceCalibratedCoveredAreaFraction'],1.)
        self.assertAlmostEqual(r['candidateSurfaceDistanceMeters']['median'],.01)
        self.assertLess(r['sourcePairedVectorResidualMeters']['max'],1e-12)
    def test_triangle_interior_is_used_not_nearest_vertex(self):
        t=np.array([[[0.,0.,0.],[1.,0.,0.],[0.,1.,0.]]]);d,i,b=closest_surface([[.2,.2,.05]],t)
        self.assertAlmostEqual(d[0],.05);np.testing.assert_allclose(b[0],[.6,.2,.2]);self.assertEqual(i[0],0)
    def test_area_weights_prevent_triangle_count_bias(self):
        large=np.array([[0.,0.,0.],[10.,0.,0.],[0.,10.,0.]]);tiny=np.array([[20.,0.,0.],[20.01,0.,0.],[20.,.01,0.]])
        s=np.array([large,tiny]);c=s.copy();c[0,:,2]=.2
        r=directional_coverage(s,c,s,s,1.)
        self.assertGreater(r['sourceCalibratedWorsenedAreaFraction'],.999)
    def test_open_part_penetration_is_unavailable(self):
        m={'part':'chest','name':'open','position':np.array([[0.,0.,0.],[1.,0.,0.],[0.,1.,0.]]),'faces':np.array([[0,1,2]])}
        self.assertIsNone(closed_owner_triangles([m],'chest'))
        r=penetration(np.array([[0.,0.,0.]]),np.array([[0.,0.,0.]]),np.ones(1),None,None,1.)
        self.assertEqual(r['status'],'unavailable')
    def test_closed_solid_reports_new_depth_without_treating_authored_overlap_as_new(self):
        p=np.array([[0,0,0],[1,0,0],[0,1,0],[0,0,1]],float)
        f=np.array([[0,2,1],[0,1,3],[0,3,2],[1,2,3]])
        m={'part':'pelvis','name':'tetra','position':p,'faces':f};closed=closed_owner_triangles([m],'pelvis');self.assertIsNotNone(closed)
        r=penetration(np.array([[.1,.1,-.05]]),np.array([[.1,.1,.1]]),np.ones(1),closed,closed,1.)
        self.assertAlmostEqual(r['candidateInsideAreaFraction'],1.);self.assertAlmostEqual(r['sourceInsideAreaFraction'],0.)
        self.assertAlmostEqual(r['sourceCalibratedWorsenedPenetrationAreaFraction'],1.)
        same=penetration(np.array([[.1,.1,.1]]),np.array([[.1,.1,.1]]),np.ones(1),closed,closed,1.)
        self.assertEqual(same['sourceCalibratedWorsenedPenetrationAreaFraction'],0.)
    def test_topology_change_is_rejected_before_any_metric(self):
        m={'part':'chest','name':'n','position':np.eye(3),'faces':np.array([[0,1,2]])};c={**m,'faces':np.array([[0,2,1]])}
        with self.assertRaisesRegex(ValueError,'lineage'):audit([m],[c],{}, {},links=())
    def test_quadrature_transports_barycentric_points_without_mutating_source(self):
        s=np.array([[[0.,0.,0.],[1.,0.,0.],[0.,1.,0.]]]);before=s.copy();a,b,w=quadrature(s,s+[0,0,.1]);np.testing.assert_allclose(b-a,[[0,0,.1]]*3);np.testing.assert_array_equal(s,before);self.assertAlmostEqual(w.sum(),.5)
if __name__=='__main__':unittest.main()
