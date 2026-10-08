import unittest
import numpy as np
from reference_color_region_ownership import own_regions,same_surface_role_padding
class Tests(unittest.TestCase):
 def test_same_skin_conflicting_rgb_blends_continuously(self):
  colors=np.array([[[.1,.2,.3],[.5,.6,.7],[0,0,0],[0,0,0]]]);roles=np.array([[1,1,0,0]],dtype='u1');eligible=np.array([[True,True,False,False]]);normal=np.array([[1,-1,0.]])/np.sqrt(2)
  result,f=own_regions(colors,roles,eligible,normal);np.testing.assert_allclose(result,(colors[:,0]+colors[:,1])/2);self.assertEqual(f['mode'][0],1);self.assertEqual(f['cameraOwner'][0],0)
 def test_cross_cloth_skin_selects_one_literal_no_blend(self):
  colors=np.array([[[.1,.2,.3],[.5,.6,.7],[0,0,0],[0,0,0]]]);roles=np.array([[1,2,0,0]],dtype='u1');eligible=np.array([[True,True,False,False]]);normal=np.array([[1,-2,0.]])/np.sqrt(5)
  result,f=own_regions(colors,roles,eligible,normal);np.testing.assert_array_equal(result,colors[:,0]);np.testing.assert_array_equal(f['blendWeights'],[[1,0,0,0]]);self.assertEqual(f['mode'][0],2)
 def test_unknown_camera_owner_and_invisible_stay_unresolved(self):
  colors=np.ones((2,4,3));roles=np.array([[0,1,0,0],[1,1,1,1]],dtype='u1');e=np.array([[True,True,False,False],[False]*4]);normal=np.array([[0,-1.,0],[0,-1,0]])
  _,f=own_regions(colors,roles,e,normal);self.assertFalse(f['accepted'].any());np.testing.assert_array_equal(f['ownedRole'],[0,0])
 def test_geometric_duplicate_chart_is_uv_independent(self):
  colors=np.ones((2,4,3));roles=np.ones((2,4),dtype='u1');e=np.ones((2,4),bool);n=np.repeat(np.array([[.8,-.6,0]]),2,axis=0);_,f=own_regions(colors,roles,e,n);np.testing.assert_array_equal(f['blendWeights'][0],f['blendWeights'][1])
 def test_padding_role_collision_unseen_and_geometry_barriers(self):
  cover=np.zeros((9,9),bool);cover[4,2]=cover[4,6]=cover[1,4]=True;accepted=cover.copy();accepted[1,4]=False;protected=np.zeros_like(cover);roles=np.zeros((9,9),dtype='u1');roles[4,2]=1;roles[4,6]=2;p=np.zeros((9,9,3));n=np.tile([0,0,1.],(9,9,1));pad=same_surface_role_padding(cover,accepted,protected,roles,p,n,4)
  self.assertFalse(pad['destination'][1,4]);self.assertFalse(pad['destination'][4,4]);self.assertTrue(pad['competingRoleOrSurfaceAmbiguous'][4,4]);self.assertLessEqual(pad['steps'].max(),4)
  roles[4,6]=1;p[4,6,0]=.1;pad=same_surface_role_padding(cover,accepted,protected,roles,p,n,4);self.assertFalse(pad['destination'][4,4])
if __name__=='__main__':unittest.main()
