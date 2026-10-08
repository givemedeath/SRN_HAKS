import hashlib,json,tempfile,unittest
from pathlib import Path
import current_skin_calibration_bridge as b

class BridgeGuards(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.p=Path(self.temp.name)/'input.json';self.p.write_text('{}');self.row={'path':str(self.p),'sha256':hashlib.sha256(self.p.read_bytes()).hexdigest()}
  self.value={'mode':b.MODE,'recipe':self.row,'materialExecution':{'proof':self.row,'representation':self.row,'parentScope':self.row},'faceRoleLineage':None}
 def test_literal_embedded_texture_comparison(self):
  doc={'materials':[{'normalTexture':{'index':0},'pbrMetallicRoughness':{'baseColorTexture':{'index':1},'metallicRoughnessTexture':{'index':2}}}],'textures':[{'source':i}for i in range(3)],'images':[{'bufferView':i}for i in range(3)],'bufferViews':[{'byteOffset':i*3,'byteLength':3}for i in range(3)]}
  self.assertEqual(b.map_bytes(doc,b'RGBNORORM',0,'color'),b'NOR');self.assertEqual(b.map_bytes(doc,b'RGBNORORM',0,'normal'),b'RGB');self.assertEqual(b.map_bytes(doc,b'RGBNORORM',0,'orm'),b'ORM')
  doc['images'][0]['uri']='borrowed.png'
  with self.assertRaisesRegex(ValueError,'Embedded'):b.map_bytes(doc,b'RGBNORORM',0,'normal')
 def test_valid_explicit_controls(self):b.controls(self.value)
 def test_stale_recipe_rejected(self):
  self.p.write_text('changed')
  with self.assertRaises(ValueError):b.controls(self.value)
 def test_unknown_control_rejected(self):
  self.value['selected']=True
  with self.assertRaisesRegex(ValueError,'Exact current'):b.controls(self.value)
 def test_missing_original_parent_scope_rejected(self):
  del self.value['materialExecution']['parentScope']
  with self.assertRaisesRegex(ValueError,'Explicit original'):b.controls(self.value)
 def test_unbound_chest_role_rejected(self):
  self.value['faceRoleLineage']={'roles':['skin']}
  with self.assertRaisesRegex(ValueError,'face-role'):b.controls(self.value)
 def test_null_scope_only_exact_simple_original(self):
  self.p.write_text(json.dumps({'part':'bicepl','parent':{'mode':'original-materialRoles-skin','controls':{'materialRoles':{'0':'skin'}}}}))
  row={'path':str(self.p),'sha256':hashlib.sha256(self.p.read_bytes()).hexdigest()}
  v={'mode':b.MODE,'recipe':row,'materialExecution':{'proof':row,'representation':row,'parentScope':None},'faceRoleLineage':None}
  b.controls(v)
 def test_null_scope_chest_rejected(self):
  self.p.write_text(json.dumps({'part':'chest','parent':{'mode':'original-materialRoles-skin','controls':{'materialRoles':{'0':'skin'}}}}))
  row={'path':str(self.p),'sha256':hashlib.sha256(self.p.read_bytes()).hexdigest()}
  v={'mode':b.MODE,'recipe':row,'materialExecution':{'proof':row,'representation':row,'parentScope':None},'faceRoleLineage':None}
  with self.assertRaisesRegex(ValueError,'restricted'):b.controls(v)
 def test_null_scope_detail_rejected(self):
  self.p.write_text(json.dumps({'part':'shinl','parent':{'mode':'original-source-uv-detail-v1','controls':{}}}))
  row={'path':str(self.p),'sha256':hashlib.sha256(self.p.read_bytes()).hexdigest()}
  v={'mode':b.MODE,'recipe':row,'materialExecution':{'proof':row,'representation':row,'parentScope':None},'faceRoleLineage':None}
  with self.assertRaisesRegex(ValueError,'restricted'):b.controls(v)
 def test_unsealed_native_geometry_rejected(self):
  with self.assertRaisesRegex(ValueError,'Sealed current native'):b.staging_inputs(self.value,self.p,{},'bicepl','working',self.p,self.p,native_geometry=object())

class RGBDescendantGuards(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  import io
  import numpy as np
  from PIL import Image
  cls.np=np
  def png(a):
   s=io.BytesIO();Image.fromarray(a).save(s,format='PNG');return s.getvalue()
  base=np.full((2048,2048,3),120,np.uint8);derived=base.copy();derived[100:110,200:220]=150
  cls.arrays={'orig':base,'derived':derived}
  cls.png={'orig':png(base),'derived':png(derived),'normal':png(np.full((2048,2048,3),128,np.uint8)),'orm':png(np.full((2048,2048,3),200,np.uint8)),'other':png(np.full((2048,2048,3),90,np.uint8))}
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);d=Path(self.temp.name)
  self.atlas=d/'derived.png';self.atlas.write_bytes(self.png['derived']);self.receipt=d/'geometry.json'
  self.atlas_pin={'path':str(self.atlas),'sha256':hashlib.sha256(self.atlas.read_bytes()).hexdigest()}
  self.rec={'materialRGBBindingHistoricalDerivedAtlas':self.atlas_pin};self.receipt.write_text(json.dumps(self.rec))
  self.rgbd={'derivedAtlas':self.atlas_pin,'bindingReceipt':{'path':str(self.receipt),'sha256':hashlib.sha256(self.receipt.read_bytes()).hexdigest()}}
  original=b.raw_corners;b.raw_corners=lambda doc,binary:(None,None,None,[{'material':m}for m in doc['_active']]);self.addCleanup(setattr,b,'raw_corners',original)
 def doc(self,color,normal='normal',orm='orm',active=(0,)):
  blobs=[self.png[color],self.png[normal],self.png[orm]];binary=b''.join(blobs);views=[];offset=0
  for blob in blobs:views.append({'byteOffset':offset,'byteLength':len(blob)});offset+=len(blob)
  material={'pbrMetallicRoughness':{'baseColorTexture':{'index':0},'metallicRoughnessTexture':{'index':2}},'normalTexture':{'index':1}}
  return {'_active':list(active),'materials':[material]*5,'textures':[{'source':i}for i in range(3)],'images':[{'bufferView':i}for i in range(3)],'bufferViews':views},binary
 def match(self,current,rgbd='default',part='shinl',ao=0,original=None):
  cd,cb=current;od,ob=original or self.doc('orig')
  return b.match_current_maps(self.rgbd if rgbd=='default' else rgbd,part,ao,self.receipt,self.rec,cd,cb,od,ob,{})
 def test_exact_derived_atlas_with_exact_normal_orm_accepted(self):
  matches,descendant,derived=self.match(self.doc('derived',active=(3,4)))
  self.assertEqual(descendant,{'3':[0],'4':[0]});self.assertEqual(matches,{'3':[0],'4':[0]});self.assertTrue(self.np.array_equal(derived,self.arrays['derived']))
 def test_without_route_derived_colour_rejected(self):
  with self.assertRaisesRegex(ValueError,'fresh RGB-descendant'):self.match(self.doc('derived'),rgbd=None)
 def test_wrong_part_rejected(self):
  with self.assertRaisesRegex(ValueError,'restricted to AO0 shinl/shinr'):self.match(self.doc('derived'),part='legl')
 def test_nonzero_ao_rejected(self):
  with self.assertRaisesRegex(ValueError,'restricted to AO0'):self.match(self.doc('derived'),ao=.15)
 def test_normal_differs_rejected(self):
  with self.assertRaisesRegex(ValueError,'byte-exact original normal/ORM'):self.match(self.doc('derived',normal='other'))
 def test_orm_differs_rejected(self):
  with self.assertRaisesRegex(ValueError,'byte-exact original normal/ORM'):self.match(self.doc('derived',orm='other'))
 def test_atlas_mismatch_rejected(self):
  with self.assertRaisesRegex(ValueError,'decode exactly to the pinned derived atlas'):self.match(self.doc('other'))
 def test_receipt_mismatch_rejected(self):
  other=Path(self.temp.name)/'other.json';other.write_text(json.dumps(self.rec));rgbd=dict(self.rgbd,bindingReceipt={'path':str(other),'sha256':hashlib.sha256(other.read_bytes()).hexdigest()})
  with self.assertRaisesRegex(ValueError,'current geometry receipt'):self.match(self.doc('derived'),rgbd=rgbd)
 def test_receipt_naming_other_atlas_rejected(self):
  self.rec={'materialRGBBindingHistoricalDerivedAtlas':dict(self.atlas_pin,sha256='0'*64)}
  with self.assertRaisesRegex(ValueError,'different derived atlas'):self.match(self.doc('derived'))
 def test_tampered_atlas_bytes_rejected(self):
  self.atlas.write_bytes(self.png['other'])
  with self.assertRaises(ValueError):self.match(self.doc('derived'))
 def test_unneeded_route_rejected(self):
  with self.assertRaisesRegex(ValueError,'Unneeded or ambiguous'):self.match(self.doc('orig'))
 def rows(self,effective):
  np=self.np;z=np.zeros((2048,2048),np.uint8)
  return {'skin':{'color':np.zeros((2048,2048,3),np.uint8),'normal':np.zeros((2048,2048,3),np.uint8),'roughness':z.copy(),'intensity':effective}}
 def proof(self,effective,**extra):
  import replay_stage_skin_calibration as cal
  return {'aoStrength':0,'calibrationApplications':1,'effectiveIntensitySha256':cal.fingerprint(effective),**extra}
 def test_delta_applied_once_on_changed_texels_only(self):
  np=self.np;import replay_stage_skin_calibration as cal;import source_skin_detail_contract as detail
  red=np.full((2048,2048),255,np.uint8);parent=detail.intensity(self.arrays['orig'],red,0)
  effective,_=cal.calibrated_intensity(parent,red,1.0,-36.86,0)
  out,proof=b.rgb_descendant_rows(self.rows(effective),self.proof(effective),{'gain':1.0,'offsetBytes':-36.86},self.arrays['orig'],self.arrays['derived'],red)
  changed=np.any(self.arrays['derived']!=self.arrays['orig'],axis=2);expected_parent=detail.intensity(self.arrays['derived'],red,0)
  expected,_=cal.calibrated_intensity(expected_parent,red,1.0,-36.86,0)
  self.assertTrue(np.array_equal(out['skin']['intensity'],expected));self.assertTrue(np.array_equal(out['skin']['intensity'][~changed],effective[~changed]))
  self.assertEqual(proof['changedRGBTexels'],200);self.assertEqual(proof['rgbDescendantApplications'],1);self.assertTrue(proof['unchangedTexelsEqualOriginalCalibratedAO0'])
 def test_double_application_rejected(self):
  np=self.np;effective=np.full((2048,2048),80,np.uint8);red=np.full((2048,2048),255,np.uint8)
  with self.assertRaisesRegex(ValueError,'one RGB-descendant application'):
   b.rgb_descendant_rows(self.rows(effective),self.proof(effective,rgbDescendantApplications=1),{'gain':1.0,'offsetBytes':-36.86},self.arrays['orig'],self.arrays['derived'],red)
 def test_nonunit_gain_rejected(self):
  np=self.np;effective=np.full((2048,2048),80,np.uint8);red=np.full((2048,2048),255,np.uint8)
  with self.assertRaisesRegex(ValueError,'unit-gain'):b.rgb_descendant_rows(self.rows(effective),self.proof(effective),{'gain':1.1,'offsetBytes':-36.86},self.arrays['orig'],self.arrays['derived'],red)
 def test_clamped_changed_texel_rejected(self):
  np=self.np;effective=np.full((2048,2048),80,np.uint8);effective[105,205]=0;red=np.full((2048,2048),255,np.uint8)
  with self.assertRaisesRegex(ValueError,'unclamped'):b.rgb_descendant_rows(self.rows(effective),self.proof(effective),{'gain':1.0,'offsetBytes':-36.86},self.arrays['orig'],self.arrays['derived'],red)
 def test_stale_effective_rejected(self):
  np=self.np;effective=np.full((2048,2048),80,np.uint8);red=np.full((2048,2048),255,np.uint8);proof=self.proof(effective);effective[0,0]=81
  with self.assertRaisesRegex(ValueError,'Replayed effective'):b.rgb_descendant_rows(self.rows(effective),proof,{'gain':1.0,'offsetBytes':-36.86},self.arrays['orig'],self.arrays['derived'],red)
 def control_value(self,part,**extra):
  recipe=Path(self.temp.name)/'recipe.json';recipe.write_text(json.dumps({'part':part}));row={'path':str(recipe),'sha256':hashlib.sha256(recipe.read_bytes()).hexdigest()}
  return {'mode':b.MODE,'recipe':row,'materialExecution':{'proof':row,'representation':row,'parentScope':row},'faceRoleLineage':None,'rgbDescendant':self.rgbd,**extra}
 def test_controls_accept_shin_route(self):b.controls(self.control_value('shinr'))
 def test_controls_reject_non_shin_route(self):
  with self.assertRaisesRegex(ValueError,'restricted to shinl/shinr'):b.controls(self.control_value('chest'))
 def test_controls_reject_extra_route_field(self):
  with self.assertRaisesRegex(ValueError,'Exact RGB-descendant'):b.controls(self.control_value('shinl',rgbDescendant=dict(self.rgbd,gain=1)))

if __name__=='__main__':unittest.main()
