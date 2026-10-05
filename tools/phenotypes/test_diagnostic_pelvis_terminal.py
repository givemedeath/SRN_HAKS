"""Actual bounded recipe, positiveJ/shading/cap graph/archive storage guards."""
import copy,json,unittest
import numpy as np
import diagnostic_pelvis_terminal as terminal
from place_purposebuilt_pelvis import BASIS,accessor,embedded_maps
from test_mirror_stock_limb_part import fixture

class TerminalTests(unittest.TestCase):
 def test_exact_protected_support_and_35mm_bound(self):
  p=np.array([[.1,0,.90],[.1,0,.985],[.020,0,.94],[.02,0,.90],[.1,0,1.2],[-.1,0,.9]])
  w,J=terminal.field(p);q=terminal.move(p);np.testing.assert_array_equal(w,[1,0,0,0,0,1]);np.testing.assert_array_equal(q[:,0:2],p[:,0:2]);np.testing.assert_array_equal(q[1:5],p[1:5]);np.testing.assert_allclose(q[[0,5],2]-p[[0,5],2],.035,atol=1e-15)
 def test_positive_J_finite_difference_and_monotone_vertical(self):
  p=np.array([[.1,.02,.9475],[-.04,.01,.94]]);w,J=terminal.field(p);self.assertAlmostEqual(np.linalg.det(J[0]),.125,places=13)
  for i in range(3):
   e=np.eye(3)[i]*1e-7;np.testing.assert_allclose((terminal.move(p+e)-terminal.move(p-e))/2e-7,J[:,:,i],atol=3e-9,rtol=0)
  z=np.linspace(.88,1.02,1000);q=terminal.move(np.column_stack([np.full(1000,.1),np.zeros(1000),z]));self.assertTrue((np.diff(q[:,2])>0).all())
 def test_authored_identity_J_and_outside_exact_NTW(self):
  p=np.array([[.1,0,.9],[.01,0,.94],[.1,0,1.05]]);n=np.array([[.3,.4,1.7]]*3,'<f4');t=np.array([[1.2,.05,.2,-1.]]*3,'<f4');nn,tt=terminal.transport(p,n,t);self.assertEqual(n.tobytes(),nn.tobytes());self.assertEqual(t.tobytes(),tt.tobytes())
 def test_inverse_transpose_and_GS_mag_W(self):
  p=np.array([[.04,.02,.94]]);n=np.array([[.3,.4,1.7]]);t=np.array([[1.2,.05,.2,-1.]]);_,J=terminal.field(p);nn,tt=terminal.transport(p,n,t);e=np.linalg.solve(J[0].T,n[0]);e*=np.linalg.norm(n)/np.linalg.norm(e);np.testing.assert_allclose(nn[0],e,atol=1e-15,rtol=0);self.assertAlmostEqual(np.linalg.norm(t[:,:3]),np.linalg.norm(tt[:,:3]),places=14);self.assertAlmostEqual(nn[0]@tt[0,:3],0,places=14);self.assertEqual(tt[0,3],-1)
 def test_nonfinite_and_degenerate_affected_shading_rejected(self):
  for p in [np.array([[np.nan,0,1.]]),np.array([[.1,0]])]:
   with self.assertRaises(ValueError):terminal.field(p)
  with self.assertRaises(ValueError):terminal.transport(np.array([[.1,0,.9]]),np.zeros((1,3)),np.array([[1.,0,0,1.]]))
 def test_cap_generated_shading_unchanged_XY_graph(self):
  p=np.array([[.03,-.04,.903],[.09,-.04,.905],[.09,.04,.904],[.03,.04,.902]]);F=np.array([[0,1,2],[0,2,3]]);UV=np.array([[0.,0],[1.,0],[1.,1],[0.,1]]);N=np.array([[0.,0,1.3]]*4);T=np.array([[1.2,0,0,1.]]*4);q=terminal.move(p);n,t=terminal.cap_shading(q,F,UV,N,T);np.testing.assert_array_equal(q[:,:2],p[:,:2]);np.testing.assert_allclose(np.linalg.norm(n,axis=1),1.3,atol=1e-15);np.testing.assert_allclose(np.linalg.norm(t[:,:3],axis=1),1.2,atol=1e-15);np.testing.assert_allclose(np.sum(n*t[:,:3],axis=1),0,atol=1e-15);np.testing.assert_array_equal(t[:,3],T[:,3])
  old=np.cross(p[F[:,1]]-p[F[:,0]],p[F[:,2]]-p[F[:,0]]);new=np.cross(q[F[:,1]]-q[F[:,0]],q[F[:,2]]-q[F[:,0]]);np.testing.assert_array_equal(old[:,2],new[:,2])
 def test_append_preserves_original_accessors_metadata_Bin_UV_materials(self):
  doc,blob=fixture();attrs=doc['meshes'][0]['primitives'][0]['attributes'];P=accessor(doc,blob,attrs['POSITION']);N=accessor(doc,blob,attrs['NORMAL']);T=accessor(doc,blob,attrs['TANGENT']);rows={'POSITION':P.copy(),'NORMAL':N.copy(),'TANGENT':T.copy()};rows['POSITION'][:,1]+=.01;d,b=terminal.append(doc,blob,[([0],rows)]);self.assertEqual(b[:len(blob)],blob);self.assertEqual(d['materials'],doc['materials']);self.assertEqual(embedded_maps(d,b),embedded_maps(doc,blob));self.assertEqual(d['accessors'][:-3],doc['accessors']);self.assertEqual(d['bufferViews'][:-3],doc['bufferViews']);self.assertEqual(d['meshes'][0]['primitives'][0]['indices'],doc['meshes'][0]['primitives'][0]['indices']);self.assertEqual(d['meshes'][0]['primitives'][0]['attributes']['TEXCOORD_0'],attrs['TEXCOORD_0'])
 def test_shared_accessor_active_rows_include_other_material_primitives(self):
  doc,blob=fixture();p=doc['meshes'][0]['primitives'][0];second=copy.deepcopy(p);second['material']=0;doc['meshes'][0]['primitives'].append(second);payload=bytearray(blob)
  for item,row in [(p,0),(second,1)]:
   payload.extend(b'\0'*(-len(payload)%4));start=len(payload);v=np.array([row,row,row],'<u2');payload.extend(v.tobytes());doc['bufferViews'].append({'buffer':0,'byteOffset':start,'byteLength':v.nbytes});doc['accessors'].append({'bufferView':len(doc['bufferViews'])-1,'count':3,'type':'SCALAR','componentType':5123});item['indices']=len(doc['accessors'])-1
  blob=bytes(payload);active=terminal.shared_active_rows(doc,blob,p);np.testing.assert_array_equal(active,[True,True,False,False]);np.testing.assert_array_equal(terminal.shared_active_rows(doc,blob,second),active)
  world=np.array([[.1,0,.94],[.1,0,.94],[.1,0,.94],[.1,0,1.05]]);P=world.copy();P[active]=terminal.move(world[active]);self.assertGreater(P[1,2],world[1,2]);self.assertEqual(P[2:].tobytes(),world[2:].tobytes())
  # A row owned only by primitive1 is mapped; genuinely unused and outside rows stay literal.
  N=np.tile([.3,.4,1.7],(4,1));T=np.tile([1.2,.05,.2,-1.],(4,1));nn,tt=terminal.transport(world[active],N[active],T[active]);newN=N.copy();newT=T.copy();newN[active]=nn;newT[active]=tt;self.assertEqual(newN[~active].tobytes(),N[~active].tobytes());self.assertEqual(newT[~active].tobytes(),T[~active].tobytes())
 def test_root_approval_recipe_rejects_wrong_field_dome_or_author(self):
  c={'part':'pelvis','coordinateSpace':'working','liftMetres':.035,'zFullMetres':.910,'zZeroMetres':.985,'centralProtectedHalfWidthMetres':.020,'lateralFullHalfWidthMetres':.060,'statureApplications':0,'capRoundMetres':0.};a={'kind':'root-approved-pelvis-local-shortening35-diagnostic','reviewedBy':'/root','authorizeImplementationAndOneFreshExport':True,'configuration':c,'capRoundAuthorizedByThisReceipt':False};terminal.validate_approval(a,c)
  for key,value in [('liftMetres',.020),('capRoundMetres',.004),('coordinateSpace','runtime')]:
   bad=copy.deepcopy(c);bad[key]=value;ba=copy.deepcopy(a);ba['configuration']=bad
   with self.assertRaises(ValueError):terminal.validate_approval(ba,bad)
  a['reviewedBy']='someone';
  with self.assertRaises(ValueError):terminal.validate_approval(a,c)

if __name__=='__main__':unittest.main()
