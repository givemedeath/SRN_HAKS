import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
import diagnostic_foot_uniform120 as f
from place_purposebuilt_pelvis import accessor,BASIS,embedded_maps

def fixture():
 arrays=[np.array([[0,0,0],[1,.2,.3],[-.5,.4,.1]],dtype='<f4'),np.array([[0,0,2]]*3,dtype='<f4'),np.array([[2,0,.3,1],[2,0,.3,-1],[2,0,.3,1]],dtype='<f4'),np.array([[.1,.2],[.3,.4],[.5,.6]],dtype='<f4'),np.array([0,1,2],dtype='<u4')]
 views=[];acs=[];binary=bytearray()
 for i,a in enumerate(arrays):
  off=len(binary);binary.extend(a.tobytes());views.append({'buffer':0,'byteOffset':off,'byteLength':a.nbytes});acs.append({'bufferView':i,'componentType':5125 if i==4 else 5126,'count':len(a),'type':['VEC3','VEC3','VEC4','VEC2','SCALAR'][i]})
 off=len(binary);binary.extend(b'exact-embedded-map');views.append({'buffer':0,'byteOffset':off,'byteLength':18});binary.extend(b'\0'*(-len(binary)%4))
 d={'asset':{'version':'2.0'},'nodes':[{'mesh':0}],'meshes':[{'primitives':[{'attributes':{'POSITION':0,'NORMAL':1,'TANGENT':2,'TEXCOORD_0':3},'indices':4,'material':0}]}],'scenes':[{'nodes':[0]}],'scene':0,'bufferViews':views,'accessors':acs,'buffers':[{'byteLength':len(binary)}],'materials':[{'pbrMetallicRoughness':{'baseColorTexture':{'index':0}},'normalTexture':{'index':0,'scale':1.}}],'textures':[{'source':0}],'images':[{'mimeType':'image/png','bufferView':5}]};return d,bytes(binary)

class Foot120(unittest.TestCase):
 def test_sole_projection_and_uniform_ground_plane(self):
  A=np.eye(4);A[:3,3]=[-.07,-.075,.1366];P=np.array([[.02,.03,-.1366],[-.01,.2,.035]]);c,cw,z=f.sole_projection(A,P);Q=f.uniform_positions(P,c)
  self.assertEqual(z,0.);np.testing.assert_array_equal(c,[0,0,-.1366]);np.testing.assert_array_equal(cw,[-.07,-.075,0]);self.assertEqual((Q+A[:3,3])[:,2].min(),z);self.assertAlmostEqual(f.uniform_positions(np.zeros((1,3)),c)[0,2],.02732)
 def test_uniform_three_axes_and_no_length_axis_exception(self):
  P=np.array([[1.,2.,3.],[-2.,-4.,1.]]);c=np.array([.2,.3,-.5]);Q=f.uniform_positions(P,c);np.testing.assert_allclose(Q[1]-Q[0],1.2*(P[1]-P[0]),rtol=0,atol=1e-15)
 def test_rotated_frame_still_preserves_world_minimum(self):
  t=.4;A=np.eye(4);A[:3,:3]=[[1,0,0],[0,np.cos(t),-np.sin(t)],[0,np.sin(t),np.cos(t)]];A[:3,3]=[.1,.2,.3];P=np.array([[0,.1,-.4],[.05,.4,.2],[0,0,.1]]);c,cw,z=f.sole_projection(A,P);Q=f.uniform_positions(P,c);self.assertAlmostEqual((Q@A[:3,:3].T+A[:3,3])[:,2].min(),z,places=14);np.testing.assert_allclose(cw[:2],A[:2,3])
 def test_append_preserves_authored_nonorthogonal_shading_and_magnitudes(self):
  d,b=fixture();nd,nb,P=f.append_position(d,b,[0,0,-.1]);self.assertEqual(nb[:len(b)],b)
  for sem in ['NORMAL','TANGENT','TEXCOORD_0']:
   i=d['meshes'][0]['primitives'][0]['attributes'][sem];j=nd['meshes'][0]['primitives'][0]['attributes'][sem];self.assertEqual(i,j);self.assertTrue(f.exact(accessor(d,b,i),accessor(nd,nb,j)))
  self.assertEqual(float(np.linalg.norm(accessor(nd,nb,1)[0])),2.);self.assertNotEqual(float(accessor(nd,nb,1)[0]@accessor(nd,nb,2)[0,:3]),0.)
 def test_only_position_accessor_appended_indices_material_and_map_exact(self):
  d,b=fixture();original=copy.deepcopy(d);nd,nb,newP=f.append_position(d,b,[0,0,-.1]);self.assertEqual(d,original);self.assertEqual(len(nd['accessors']),len(d['accessors'])+1);self.assertEqual(nd['accessors'][:-1],d['accessors']);self.assertEqual(nd['materials'],d['materials']);self.assertEqual(embedded_maps(nd,nb),embedded_maps(d,b));self.assertEqual(nd['meshes'][0]['primitives'][0]['indices'],4)
  np.testing.assert_array_equal(newP,f.uniform_positions(accessor(d,b,0).astype(float),np.array([0,0,-.1])@BASIS).astype('<f4'))
 def test_wrong_sizes_and_nonfinite_rejected(self):
  for scale in [1.15,1.0,-1.,np.nan,[1.2,1.2,1.2]]:
   with self.assertRaises(ValueError):f.uniform_positions(np.zeros((3,3)),[0,0,0],scale)
  with self.assertRaises(ValueError):f.uniform_positions([[np.nan,0,0]],[0,0,0])
  with self.assertRaises(ValueError):f.uniform_positions([[0,0,0]],[0,0,np.inf])
 def test_reflected_or_scaled_frame_rejected(self):
  for v in [-1.,1.2]:
   A=np.eye(4);A[0,0]=v
   with self.assertRaises(ValueError):f.sole_projection(A,np.zeros((3,3)))
 def test_nonfinite_source_or_invalid_tangent_w_rejected(self):
  for value in [np.nan,0.]:
   d,b=fixture();raw=bytearray(b);view=d['bufferViews'][2];a=np.frombuffer(raw,dtype='<f4',count=12,offset=view['byteOffset']).reshape(3,4);a[0,3]=value
   with self.assertRaises(ValueError):f.append_position(d,bytes(raw),[0,0,0])
 def test_skin_nonidentity_node_and_unknown_attribute_rejected(self):
  for mode in ['skin','node','unknown']:
   d,b=fixture()
   if mode=='skin':d['skins']=[{}]
   if mode=='node':d['nodes'][0]['translation']=[1,0,0]
   if mode=='unknown':d['meshes'][0]['primitives'][0]['attributes']['COLOR_0']=0
   with self.assertRaises(ValueError):f.append_position(d,b,[0,0,0])
 def test_exact_current_direction_and_historical_baseline_required(self):
  d=f.read(f.DIRECTION);f.check_direction(d)
  for key,val in [('scaleXYZ',[1.2,1.,1.2]),('priorLargerFootTrialsOrCompressionReapplied',True),('statureApplications',1)]:
   bad=copy.deepcopy(d);bad[key]=val
   with self.assertRaises(ValueError):f.check_direction(bad)
  bad=copy.deepcopy(d);bad['leftOriginalBaseline']['sha256']='old-larger15'
  with self.assertRaises(ValueError):f.check_direction(bad)
 def test_explicit_historical_preview_version_only(self):
  name,(h,snapshot)=next(iter(f.NEIGHBOR_PREVIEW_SNAPSHOTS.items()));calls=[]
  result=f.pin_neighbor_ancestry({name:h},lambda p,v:calls.append((str(p),v)));self.assertEqual(calls,[(str(snapshot),h)]);self.assertEqual(result[0]['expectedSha256'],h)
  with self.assertRaisesRegex(ValueError,'Unknown historical'):f.pin_neighbor_ancestry({name:'different'},lambda p,v:None)
 def test_neighbor_geometry_pin_not_substituted(self):
  def strict(p,h):raise ValueError('literal geometry changed')
  with self.assertRaisesRegex(ValueError,'literal geometry'):f.pin_neighbor_ancestry({'pmg0_shinl001.mdl':'changed'},strict)

 def test_wrong_part_or_contract_config_rejected(self):
  with self.assertRaisesRegex(ValueError,'Dedicated LEFTfoot120'):f.validate_review_config({'schemaVersion':1,'kind':'review-proposed-original-left-foot120-uniform','part':'footr'},{},{},np.zeros(3),np.zeros(3),0.)
  target=f.tc.load(f.TARGET);cfg={'schemaVersion':1,'kind':'review-proposed-original-left-foot120-uniform','part':'footl',**f.tc.binding(f.TARGET,target,'working')};cfg['coordinateSpace']='runtime'
  with self.assertRaises(ValueError):f.validate_review_config(cfg,{},target,np.zeros(3),np.zeros(3),0.)

 def test_duplicate_export_guard_precedes_config_or_source_reads(self):
  with tempfile.TemporaryDirectory() as t,patch.object(f,'checked',side_effect=AssertionError('input read')):
   with self.assertRaisesRegex(ValueError,'Fresh output'):f.export('/nonexistent',Path(t),'x')
 def test_unapproved_export_or_global_path_rejected_before_sources(self):
  with tempfile.TemporaryDirectory() as t,patch.object(f,'checked',side_effect=AssertionError('input read')):
   with self.assertRaisesRegex(ValueError,'target-owned LEFT'):f.export('/nonexistent',Path(t)/'global','x')

if __name__=='__main__':unittest.main()
