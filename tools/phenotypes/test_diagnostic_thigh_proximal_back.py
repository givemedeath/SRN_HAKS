"""Focused tests for the exact world-Z-supported backward-Y diagnostic."""
import copy,tempfile,unittest
from pathlib import Path
import numpy as np
import diagnostic_thigh_proximal_back as back
import target_contract as tc
from place_purposebuilt_pelvis import BASIS,accessor
from test_mirror_stock_limb_part import fixture

C={'part':'legl','joint':'lthigh_g','coordinateSpace':'working','statureApplications':0,'factor85Reapplied':False,'deltaWorldMetres':[0.,-.020,0.],'supportOriginWorld':[0.,0.,0.],'supportAxisWorld':[0.,0.,1.],'supportCenterWorldZMetres':.9335863177830892,'innerPlateauHalfWidthMetres':.005,'outerSupportHalfWidthMetres':.035}

class BackwardFieldTests(unittest.TestCase):
 def setUp(self):self.f=back.field(C)
 def test_exact_backward_direction_support_and_inverse(self):
  z=C['supportCenterWorldZMetres']+np.array([-.04,-.02,0,.02,.04]);p=np.column_stack([np.arange(5)*.01,np.arange(5)*.03,z]);q=self.f.transform(p)
  np.testing.assert_array_equal(q[:,[0,2]],p[:,[0,2]]);np.testing.assert_array_equal(q[[0,4]],p[[0,4]]);self.assertAlmostEqual(q[2,1]-p[2,1],-.020)
  np.testing.assert_allclose(self.f.transform(q,inverse=True),p,atol=2e-16,rtol=0);self.assertTrue(np.all(q[:,1]<=p[:,1]))
 def test_rank_one_positive_J_and_actual_inclined_axis_component(self):
  p=np.array([[.1,.2,C['supportCenterWorldZMetres']+.020]]);J=self.f.jacobian(p)[0];self.assertAlmostEqual(np.linalg.det(J),1.,places=14)
  np.testing.assert_allclose(np.linalg.inv(J),np.eye(3)-(J-np.eye(3)),atol=1e-15,rtol=0)
  for k in range(3):
   e=np.eye(3)[k]*1e-7;np.testing.assert_allclose((self.f.transform(p+e)-self.f.transform(p-e))[0]/2e-7,J[:,k],atol=3e-9,rtol=0)
  d=np.array([.06624573709529104,-.03563278972072993,-.9971668900507176]);self.assertAlmostEqual(d@np.array(C['deltaWorldMetres']),.0007126557944145986,places=15)
 def test_active_mask_unused_outside_and_identity_J_authored_basis_literal(self):
  center=C['supportCenterWorldZMetres'];world=np.array([[0,.1,center],[.1,.2,center+.020],[.2,.3,center+.04],[.3,.4,center+.020]])
  P=(world@BASIS).astype('<f4');N=np.array([[.3,.4,1.7]]*4,dtype='<f4');T=np.array([[1.2,.05,.2,-1.]]*4,dtype='<f4');F=np.array([[0,1,2]])
  rows,actual,changed,shade=back.mapped_rows(P,N,T,F,np.eye(4),self.f);np.testing.assert_array_equal(changed,[True,True,False,False]);np.testing.assert_array_equal(shade,[False,True,False,False])
  self.assertEqual(rows['POSITION'][:,[0,1]].tobytes(),P[:,[0,1]].tobytes())
  for sem,old in [('POSITION',P),('NORMAL',N),('TANGENT',T)]:self.assertEqual(rows[sem][[2,3]].tobytes(),old[[2,3]].tobytes())
  self.assertEqual(rows['NORMAL'][0].tobytes(),N[0].tobytes());self.assertEqual(rows['TANGENT'][0].tobytes(),T[0].tobytes());self.assertEqual(rows['TANGENT'][:,3].tobytes(),T[:,3].tobytes())
 def test_shading_covector_magnitude_and_orthogonality(self):
  p=np.array([[.1,.2,C['supportCenterWorldZMetres']+.020]]);n=np.array([[.3,.4,1.7]]);t=np.array([[1.2,.05,.2,-1.]])
  nn,tt=self.f.transport(p,n,t);expected=np.linalg.solve(self.f.jacobian(p)[0].T,n[0]);expected*=np.linalg.norm(n)/np.linalg.norm(expected)
  np.testing.assert_allclose(nn[0],expected,atol=1e-15,rtol=0);self.assertAlmostEqual(np.linalg.norm(tt[0,:3]),np.linalg.norm(t[0,:3]),places=14);self.assertAlmostEqual(nn[0]@tt[0,:3],0,places=14)
 def test_wrong_direction_support_side_or_scaling_rejected(self):
  for key,value in [('deltaWorldMetres',[0.,-.01,0.]),('supportAxisWorld',[0.,1.,0.]),('supportCenterWorldZMetres',.93),('innerPlateauHalfWidthMetres',.004),('part','legr'),('factor85Reapplied',True),('statureApplications',1)]:
   c=copy.deepcopy(C);c[key]=value;a={'kind':'root-approved-thigh-proximal-backward-Y20-diagnostic','reviewedBy':'/root','authorizeImplementationAndOneFreshExport':True,'configuration':c}
   with self.subTest(key=key),self.assertRaises(ValueError):back.validate_approval(a,c)
 def test_append_preserves_old_binary_maps_indices_and_accessors(self):
  doc,blob=fixture();attrs=doc['meshes'][0]['primitives'][0]['attributes'];rows={s:accessor(doc,blob,attrs[s]).copy() for s in ['POSITION','NORMAL','TANGENT']};rows['POSITION'][:,2]+=.001;child,nb=back.append_attributes(doc,blob,rows)
  self.assertEqual(nb[:len(blob)],blob);self.assertEqual(child['accessors'][:-3],doc['accessors']);self.assertEqual(child['bufferViews'][:-3],doc['bufferViews']);self.assertEqual(child['images'],doc['images']);self.assertEqual(child['materials'],doc['materials']);self.assertEqual(child['meshes'][0]['primitives'][0]['indices'],doc['meshes'][0]['primitives'][0]['indices'])
  for sem,aid in attrs.items():self.assertEqual(accessor(child,nb,aid,allow_normalized=True).tobytes(),accessor(doc,blob,aid,allow_normalized=True).tobytes())
 def test_reviewed_sliver_guard_not_a_generic_inversion_waiver(self):
  P=(np.array([[0,0,.9335863],[.01,0,.9435863],[0,.01,.9435863]])@BASIS).astype('<f4');F=np.array([[0,1,2]])
  with self.assertRaisesRegex(ValueError,'exact reviewed2slivers'):back.discrete(P,P,F,np.eye(4),self.f)
  with self.assertRaisesRegex(ValueError,'Introduced topology|Degenerate'):back.discrete(P,np.zeros_like(P),F,np.eye(4),self.f)

class VersionRecoveryTests(unittest.TestCase):
 def test_only_exact_executed_renderer_snapshot_can_replace_historical_path(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);source=root/'pose_preview.py';source.write_bytes(b'current reviewed renderer');snapshot=root/'executed-pose.py';snapshot.write_bytes(b'historical executed renderer');proof=root/'proof.json';proof.write_bytes(b'exact reviewed recovery evidence');h=tc.sha(snapshot)
   alias={'originalSourcePath':str(source.resolve()),'executedSha256':h,'snapshot':{'path':str(snapshot),'sha256':h},'recoveryEvidence':{'path':str(proof),'sha256':tc.sha(proof)}};c={'historicalExecutedSourceRecoveries':{str(source.resolve()):alias}};pins={};self.assertEqual(back.input_pin(source,h,pins,c),snapshot.resolve());self.assertNotIn(str(source.resolve()),pins);self.assertEqual(pins[str(snapshot.resolve())],h)
   snapshot.write_bytes(b'changed historical renderer')
   with self.assertRaisesRegex(ValueError,'snapshot differs'):back.input_pin(source,h,{},c)
 def test_asset_hash_change_cannot_use_renderer_recovery_channel(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'candidate.glb';p.write_bytes(b'changed geometry')
   with self.assertRaisesRegex(ValueError,'Only exact approved2historic'):back.input_pin(p,'0'*64,{}, {'historicalExecutedSourceRecoveries':{}})

if __name__=='__main__':unittest.main()
