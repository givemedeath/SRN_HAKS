import unittest
import numpy as np
from reference_color_reprojection import to_linear,to_srgb,image_sample,blend_visible_colors,project_rgb
from orthographic_reference_projection import CARDINALS,raster_depth
from skin_lighting_atlas import geometry_masks
class Tests(unittest.TestCase):
 def test_linear_roundtrip_and_texel_center(self):
  a=np.asarray([[[0,128,255],[255,0,32]],[[40,90,150],[50,70,80]]],dtype='u1')
  np.testing.assert_allclose(to_srgb(to_linear(a/255)),a/255,atol=1e-15)
  np.testing.assert_allclose(image_sample(a,np.array([[0.,0.],[1,1]])),to_linear(a[[0,1],[0,1]]/255),atol=1e-15)
  with self.assertRaises(ValueError):image_sample(a,np.array([[-1.,0]]))
 def test_background_vote_and_conflict_fallback(self):
  colors=to_linear(np.asarray([[[.2,.3,.4],[1,1,1]],[[0,0,0],[1,1,1]]]))
  rgb,accepted,conflict,winner,count=blend_visible_colors(colors,np.array([[1,0],[1,1.]]))
  np.testing.assert_array_equal(accepted,[True,False]);np.testing.assert_array_equal(conflict,[False,True]);np.testing.assert_array_equal(winner,[0,-1]);np.testing.assert_array_equal(count,[1,2])
  np.testing.assert_allclose(rgb[0],colors[0,0]);np.testing.assert_array_equal(rgb[1],0)
 def test_weighted_linear_blend_and_tie_order(self):
  a=to_linear(np.array([[[.2,.3,.4],[.3,.4,.5]]]))
  rgb,accepted,conflict,winner,_=blend_visible_colors(a,np.array([[1.,1.]]));np.testing.assert_allclose(rgb[0],a.mean(1)[0]);self.assertEqual(winner[0],0)
 def test_alpha_and_overlap_unresolved_exact(self):
  # Front-facing triangle winding -Y and raw UV in one chart.
  p=np.array([[[-.3,0,-.3],[.3,0,-.3],[0,0,.3]]]);n=np.tile([0,-1,0],(1,3,1));uv=np.array([[[.1,.1],[.9,.1],[.5,.9]]]);maps=geometry_masks(p,n,uv,['skin'],32,[],1)
  original=np.full((32,32,3),77,dtype='u1');views={}
  for view in CARDINALS:
   d=raster_depth(p,view,32);views[view]={'depth':d['depth'],'rgb':np.full((32,32,3),200,dtype='u1'),'alpha':np.zeros((32,32),bool)}
  out,fields=project_rgb(p,maps,original,views);np.testing.assert_array_equal(out,original);self.assertFalse(fields['accepted'].any())
 def test_occluded_opposite_color_not_sampled(self):
  p=np.array([[[-.3,0,-.3],[.3,0,-.3],[0,0,.3]]]);n=np.tile([0,-1,0],(1,3,1));uv=np.array([[[.1,.1],[.9,.1],[.5,.9]]]);maps=geometry_masks(p,n,uv,['skin'],32,[],1)
  original=np.full((32,32,3),77,dtype='u1');views={}
  for view in CARDINALS:
   d=raster_depth(p,view,32);views[view]={'depth':d['depth'],'rgb':np.full((32,32,3),100 if view=='front' else 250,dtype='u1'),'alpha':d['silhouette']}
  out,fields=project_rgb(p,maps,original,views,alpha_guard=1);self.assertTrue(fields['accepted'].any());np.testing.assert_array_equal(out[fields['accepted']],100);self.assertFalse(fields['visibilityAlphaFrontfaceEligible'][:,:,2].any())
if __name__=='__main__':unittest.main()
