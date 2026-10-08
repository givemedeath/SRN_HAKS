import copy,unittest
import numpy as np
from reference_color_bounded_fallback import validate_pairs,apply_frozen_copy
class Tests(unittest.TestCase):
 def fixture(self):
  triangles=np.asarray([[[0,0,0],[.01,0,0],[0,.01,0]],[[.01,0,0],[.01,.01,0],[0,.01,0]],[[0,0,0],[0,.01,0],[0,0,.01]]])
  shape=(9,9);p=np.zeros(shape+(3,));p[4,4]=[.001,.001,0];p[4,5]=[.0015,.001,0];n=np.tile([0.,0.,1.],shape+(1,));face=np.zeros(shape,dtype=int)
  f={'uvCoverage':np.ones(shape,bool),'uvProtected':np.zeros(shape,bool),'uvAmbiguous':np.zeros(shape,bool),'sourceFace':face,'sourceBarycentricPosition':p,'sourceAuthoredUnitNormal':n};accepted=np.zeros(shape,bool);accepted[4,5]=True;role=np.zeros(shape,dtype='u1');role[4,5]=1;r={'accepted':accepted,'ownedRole':role,'paddingDestination':np.zeros(shape,bool)}
  s={'atlasY':np.array([4]),'atlasX':np.array([4]),'sourceSkinDonorTexel':np.array([4*9+5]),'proposedAtMostTwoMm':np.array([True]),'canonicalTargetPhotoRole':np.array([1]),'canonicalDonorPhotoRole':np.array([1]),'wholeFaceProposedSkin':np.array([True]),'compatibleLiteralClothVeto':np.array([False]),'visibleEightDirections':np.ones((1,8),bool),'geometricIncidenceEightDirections':np.ones((1,8)),'sourceFace':np.array([0]),'sourcePosition':p[4,4][None,:].copy(),'sourceAuthoredNormal':n[4,4][None,:].copy(),'sourceDonorDistanceMm':np.array([.5])};c={'proposedPhotoRole':np.ones(shape,dtype='u1')}
  return [s,f,r,c,triangles]
 def run_pairs(self,data):return validate_pairs(*data,1,1)
 def test_copy_exact_donor_preserves_other_pixels(self):
  d=self.fixture();pairs=self.run_pairs(d);rgb=np.arange(243,dtype='u1').reshape(9,9,3);result=apply_frozen_copy(rgb,pairs);np.testing.assert_array_equal(result[4,4],rgb[4,5]);mask=np.ones((9,9),bool);mask[4,4]=False;np.testing.assert_array_equal(result[mask],rgb[mask])
 def test_same_face_and_original_manifold_edge_only(self):
  d=self.fixture();d[1]['sourceFace'][4,5]=1;self.run_pairs(d)
  # Third face makes the shared (0,0,0)-(0,.01,0) edge nonmanifold.
  d=self.fixture();d[1]['sourceFace'][4,5]=2;d[4]=np.concatenate([d[4],d[4][2:3]]);
  with self.assertRaises(ValueError):self.run_pairs(d)
 def test_uv_distance_surface_distance_and_normal_reject(self):
  for mutate in (lambda d:(d[0]['atlasX'].__setitem__(0,3),d[0]['sourceSkinDonorTexel'].__setitem__(0,4*9+8)),lambda d:d[1]['sourceBarycentricPosition'].__setitem__((4,5),[.01,.001,0]),lambda d:d[1]['sourceAuthoredUnitNormal'].__setitem__((4,5),[1.,0,0])):
   d=self.fixture();mutate(d)
   with self.assertRaises(ValueError):self.run_pairs(d)
 def test_protected_unknown_unseen_and_accepted_target_reject(self):
  for mutate in (lambda d:d[1]['uvProtected'].__setitem__((4,4),True),lambda d:d[1]['uvAmbiguous'].__setitem__((4,5),True),lambda d:d[3]['proposedPhotoRole'].__setitem__((4,4),2),lambda d:d[0]['visibleEightDirections'].__setitem__(slice(None),False),lambda d:d[0]['wholeFaceProposedSkin'].__setitem__(0,False),lambda d:d[2]['accepted'].__setitem__((4,4),True)):
   d=self.fixture();mutate(d)
   with self.assertRaises(ValueError):self.run_pairs(d)
 def test_independent_cloth_veto_ignores_false_stored_veto(self):
  d=self.fixture();d[2]['accepted'][4,3]=True;d[2]['ownedRole'][4,3]=2;d[1]['sourceBarycentricPosition'][4,3]=[.001,.0015,0]
  with self.assertRaisesRegex(ValueError,'cloth prohibits'):self.run_pairs(d)
 def test_stale_source_pair_and_scope_count_reject(self):
  d=self.fixture();d[0]['sourcePosition'][0,0]+=.0001
  with self.assertRaisesRegex(ValueError,'position/normal'):self.run_pairs(d)
  d=self.fixture()
  with self.assertRaisesRegex(ValueError,'count'):validate_pairs(*d,1,2)
if __name__=='__main__':unittest.main()

