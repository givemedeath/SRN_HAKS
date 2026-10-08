"""Literal visibility, occlusion, camera signs and registration counterexamples."""
import unittest
import numpy as np
from orthographic_reference_projection import project,raster_depth,visibility,silhouette_metrics,CARDINALS


class OrthographicReferenceProjectionTests(unittest.TestCase):
    def square(self,y):
        return np.array([[[-.3,y,-.3],[.3,y,-.3],[.3,y,.3]],[[-.3,y,-.3],[.3,y,.3],[-.3,y,.3]]])
    def test_front_and_back_depth_order_rejects_hidden_surface(self):
        p=np.concatenate([self.square(-.2),self.square(.2)]);query=np.array([[0,-.2,0],[0,.2,0]])
        for view,expected in [('front',[True,False]),('back',[False,True])]:
            raster=raster_depth(p,view,64,1.1);v,error=visibility(query,raster['depth'],view,1.1,tolerance=1e-6)
            np.testing.assert_array_equal(v,expected);self.assertAlmostEqual(error[1 if view=='front' else 0],.4,places=6)
    def test_cardinal_bases_match_proper_z_up_orbit_and_image_y(self):
        for view,(right,up,back) in CARDINALS.items():
            matrix=np.asarray([right,up,back]).T;self.assertAlmostEqual(np.linalg.det(matrix),1)
        image,depth=project(np.array([[.1,-.2,.3]]),'front',110,1.1)
        np.testing.assert_allclose(image,[[64.5,24.5]]);np.testing.assert_allclose(depth,[.2])
        for view,point in [('left',[.2,.1,.3]),('right',[-.2,-.1,.3])]:
            xy,d=project(np.asarray([point]),view,110,1.1);np.testing.assert_allclose(xy,[[64.5,24.5]]);np.testing.assert_allclose(d,[.2])
    def test_parallel_projection_does_not_change_pixel_for_depth_change(self):
        uv,_=project(np.array([[.1,-.1,.2],[.1,-.8,.2]]),'front',1024,1.1)
        np.testing.assert_array_equal(uv[0],uv[1])
    def test_visibility_rejects_outside_silhouette_and_off_camera(self):
        raster=raster_depth(self.square(-.2),'front',64,1.1);p=np.array([[.4,-.2,.4],[1,-.2,0],[0,-.1,0]])
        v,_=visibility(p,raster['depth'],'front',1.1,tolerance=1e-5);self.assertFalse(v.any())
    def test_registration_detects_shift_and_clipped_shape(self):
        reference=np.zeros((64,64),dtype=bool);reference[16:48,16:48]=True;candidate=np.roll(reference,8,axis=1)
        m=silhouette_metrics(candidate,reference);self.assertAlmostEqual(m['intersectionOverUnion'],.6);self.assertEqual(m['boundsCenterDeltaPixels'],[8,0])
        self.assertGreater(m['symmetricBoundaryChebyshevP50P95MaxCapped'][1],0)
        self.assertEqual(silhouette_metrics(reference,reference)['intersectionOverUnion'],1)

if __name__=='__main__':unittest.main()
