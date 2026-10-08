"""Portable operator-domain/schema regressions; no actual paths or asset writes."""
import copy,unittest
import numpy as np
import diagnostic_descendant_representation as base
import diagnostic_thigh_representation as factory
import diagnostic_thigh_operator_replay as replay

def operations():
 return [dict(receipt={},literalOperation=kind,part='legl',space='working',statureApplications=0,nativeCornerArchive={},candidate={},source='',sourceSha256='',sourceReceipt='',sourceReceiptSha256='')for kind in factory.OPERATIONS]

class ThighOperatorDomainTests(unittest.TestCase):
 def source(self):
  return {'positions':np.zeros((5,3,3)),'generatedCapFaceIds':np.array([2,3,4]),'inheritedGeneratedCapFaceIds':np.array([2,3]),'sourceFaceIds':np.array([10,11,-1,-1,-1])}
 def test_only_inherited_generated_knee_domain(self):
  np.testing.assert_array_equal(replay.normal_polish_domain(self.source(),[2,3]),[2,3])
 def test_original_face_rejected(self):
  with self.assertRaises(base.RepresentationError):replay.normal_polish_domain(self.source(),[0])
 def test_new_proximal_cap_rejected(self):
  with self.assertRaises(base.RepresentationError):replay.normal_polish_domain(self.source(),[4])
 def test_inherited_id_still_requires_generated_owner(self):
  s=self.source();s['generatedCapFaceIds']=np.array([3,4])
  with self.assertRaises(base.RepresentationError):replay.normal_polish_domain(s,[2])
 def test_source_face_ancestry_rejected(self):
  s=self.source();s['sourceFaceIds'][2]=100
  with self.assertRaises(base.RepresentationError):replay.normal_polish_domain(s,[2])
 def test_duplicate_ids_rejected(self):
  with self.assertRaises(base.RepresentationError):replay.normal_polish_domain(self.source(),[2,2])
 def test_noninteger_ids_rejected(self):
  for ids in ([True],[2.0],['2']):
   with self.assertRaises(base.RepresentationError):replay.normal_polish_domain(self.source(),ids)
 def test_invalid_domain_bounds_rejected(self):
  for ids in ([],[-1],[5]):
   with self.assertRaises(base.RepresentationError):replay.normal_polish_domain(self.source(),ids)
 def test_complete_named_operation_rows(self):
  self.assertEqual(factory.validate_operation_rows(operations(),'legl'),operations())
 def test_missing_reordered_and_unsupported_operators(self):
  for op in (operations()[:-1],list(reversed(operations()))):
   with self.assertRaises(base.RepresentationError):factory.validate_operation_rows(op,'legl')
  op=operations();op[0]['literalOperation']='fit'
  with self.assertRaises(base.RepresentationError):factory.validate_operation_rows(op,'legl')
 def test_extra_operation_field_rejected(self):
  op=operations();op[0]['assetApproval']=True
  with self.assertRaises(base.RepresentationError):factory.validate_operation_rows(op,'legl')
 def test_malformed_row_rejected(self):
  for bad in (None,1,[],{'unknown':'operator'}):
   op=operations();op[0]=bad
   with self.assertRaises(base.RepresentationError):factory.validate_operation_rows(op,'legl')
 def test_numeric_and_cross_owner_scope_rejected(self):
  for field,value in (('statureApplications',False),('statureApplications',0.0),('space','runtime'),('part','legr')):
   op=operations();op[0][field]=value
   with self.assertRaises(base.RepresentationError):factory.validate_operation_rows(op,'legl')

if __name__=='__main__':unittest.main()
