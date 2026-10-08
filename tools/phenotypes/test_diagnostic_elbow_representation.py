"""Focused elbow contract, protected byte-domain and generated-normal rejection tests."""
import copy,hashlib,json,tempfile,unittest
from pathlib import Path
import numpy as np
import diagnostic_elbow_representation as factory
import diagnostic_elbow_operator_replay as replay
from diagnostic_descendant_representation import RepresentationError

class ElbowDomainTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);p=self.root/'input.json';p.write_text('{}');self.pin={'path':str(p.resolve()),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
  self.rows=[{'receipt':self.pin,'candidate':self.pin,'nativeCornerArchive':self.pin,'proof':self.pin,'lineage':self.pin,'literalOperation':op,'part':'forel','space':'working','statureApplications':0}for op in factory.OPERATIONS]
 def tearDown(self):self.tmp.cleanup()
 def rejected(self,mutate):
  rows=copy.deepcopy(self.rows);mutate(rows)
  with self.assertRaises(RepresentationError):factory.validate_operation_rows(rows,'forel')
 def test_exact_two_operations(self):self.assertEqual(len(factory.validate_operation_rows(self.rows,'forel')),2)
 def test_b5_cap_operation_allowed(self):
  rows=copy.deepcopy(self.rows);rows[1]['literalOperation']=factory.CAP_OPERATIONS[1];self.assertEqual(len(factory.validate_operation_rows(rows,'forel')),2)
 def test_missing_operation(self):self.rejected(lambda x:x.pop())
 def test_reordered_operation(self):self.rejected(lambda x:x.reverse())
 def test_unsupported_old_cap(self):self.rejected(lambda x:x[1].update(literalOperation='shared-sphere-cap'))
 def test_cross_owner(self):self.rejected(lambda x:x[0].update(part='bicepl'))
 def test_runtime(self):self.rejected(lambda x:x[1].update(space='runtime'))
 def test_noninteger_count(self):
  for value in (False,0.0,'0',1):
   with self.subTest(value=value):self.rejected(lambda x:x[0].update(statureApplications=value))
 def test_extra_approval_field(self):self.rejected(lambda x:x[0].update(approval=True))
 def test_stale_physical_pin(self):
  Path(self.pin['path']).write_text('{"different":true}')
  with self.assertRaises(RepresentationError):factory.validate_operation_rows(self.rows,'forel')
 def test_missing_pin_field(self):self.rejected(lambda x:x[0]['lineage'].pop('sha256'))
 def test_body_non_pnt_bytes_rejected(self):
  with self.assertRaises(RepresentationError):replay.check_non_pnt_binary(bytes([1,2,3]),bytes([1,9,3]),np.array([True,False,False]))
 def test_modified_pnt_region_only(self):replay.check_non_pnt_binary(bytes([1,2,3]),bytes([9,2,3]),np.array([True,False,False]))
 def test_buffer_extent_rejected(self):
  with self.assertRaises(RepresentationError):replay.check_non_pnt_binary(b'abc',b'ab',np.array([True,True,True]))
 def test_exact_new_generated_normal_domain(self):replay.validate_generated_normal_ids(np.array([2,3]),np.array([0,1,-1,-1]),np.array([2,3]),'authored-seam-and-next-ring-blend-only')
 def test_original_normal_domain_rejected(self):
  with self.assertRaises(RepresentationError):replay.validate_generated_normal_ids(np.array([1,2]),np.array([0,1,-1,-1]),np.array([2,3]),'authored-seam-and-next-ring-blend-only')
 def test_unsupported_normal_policy(self):
  with self.assertRaises(RepresentationError):replay.validate_generated_normal_ids(np.array([2,3]),np.array([0,1,-1,-1]),np.array([2,3]),'normalize-entire-source')
 def test_duplicate_normal_domain(self):
  with self.assertRaises(RepresentationError):replay.validate_generated_normal_ids(np.array([2,2]),np.array([0,1,-1,-1]),np.array([2,3]),'authored-seam-and-next-ring-blend-only')
 def test_noninteger_normal_domain(self):
  for ids in (np.array([2.,3.]),np.array([True,False])):
   with self.subTest(dtype=str(ids.dtype)),self.assertRaises(RepresentationError):replay.validate_generated_normal_ids(ids,np.array([0,1,-1,-1]),np.array([2,3]),'authored-seam-and-next-ring-blend-only')
if __name__=='__main__':unittest.main()
