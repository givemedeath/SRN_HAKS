import unittest
import numpy as np
from reference_color_semantics import reference_roles,sample_role,semantic_cases
class Tests(unittest.TestCase):
 def test_dark_skin_is_not_luminance_cloth(self):
  rgb=np.asarray([[[65,39,18],[40,46,54],[30,15,5],[255,255,255],[140,130,120]]],dtype='u1');roles=reference_roles(rgb,np.ones((1,5),bool));np.testing.assert_array_equal(roles,[[1,2,1,0,0]])
 def test_alpha_background_and_uncertain_boundaries(self):
  rgb=np.asarray([[[180,130,70],[50,55,60]]],dtype='u1');np.testing.assert_array_equal(reference_roles(rgb,np.array([[False,True]])),[[0,2]])
 def test_bilinear_role_requires_four_equal_neighbors(self):
  role=np.asarray([[1,1,2],[1,1,2],[0,0,0]],dtype='u1');np.testing.assert_array_equal(sample_role(role,np.asarray([[.2,.2],[1.1,.1],[-.1,0],[0,1.1]])),[1,0,0,0])
 def test_cross_role_and_unknown_preclude_consensus(self):
  role=np.array([[1,1,0,0],[1,2,0,0],[2,0,0,0]],dtype='u1');eligible=np.array([[True,True,False,False],[True,True,False,False],[True,True,False,False]])
  c=semantic_cases(role,eligible);np.testing.assert_array_equal(c['consensusRole'],[1,0,0]);np.testing.assert_array_equal(c['crossSkinCloth'],[False,True,False]);np.testing.assert_array_equal(c['hasUnknownVisibleSample'],[False,False,True])
if __name__=='__main__':unittest.main()
