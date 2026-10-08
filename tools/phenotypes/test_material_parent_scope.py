"""Focused strict schema and sealed parent-consumer boundary regressions."""
import json,unittest,tempfile
from pathlib import Path
from unittest.mock import patch
import phenotype_material_parent_scope as s
import phenotype_material_execution_adoption as m
import target_part_stage as stage
import target_contract as c
class ParentScope(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name).resolve();self.pin=lambda p:{'path':str(p),'sha256':c.sha(p)}
  def save(name,v):
   p=self.root/name;p.write_text(json.dumps(v));return self.pin(p)
  self.geo=save('geo.json',{'kind':'target-part-geometry','part':'chest','coordinateSpace':'working','statureApplications':0,'candidate':str(self.root/'source'),'candidateSha256':'0'*64});(self.root/'source').write_bytes(b'raw');g=json.loads(Path(self.geo['path']).read_text());g['candidateSha256']=c.sha(self.root/'source');self.geo=save('geo.json',g)
  self.pp=save('proposal.json',{'kind':'target-garment-face-proposal','part':'chest','sourceReceipt':self.geo['path'],'sourceReceiptSha256':self.geo['sha256'],'frozenInputs':{str(self.root/'source'):c.sha(self.root/'source')}});self.rp=save('review.json',{'kind':'target-garment-face-review','part':'chest'});self.recipe={'kind':'target-compiler-skin-intensity-calibration','part':'chest','parent':{'mode':'reviewed-per-face-garment','controls':{'proposal':self.pp,'review':self.rp}},'geometryReceipt':self.geo,'materialSource':{'coordinateSpace':'working','geometryReceipt':self.geo}};self.recipe_pin=save('recipe.json',self.recipe)
 def tearDown(self):self.temp.cleanup()
 def test_closed_graph(self):
  x=s.graph(self.recipe_pin,self.recipe,'chest');self.assertEqual(len(x['records']),4);self.assertEqual(set(x['geometries']),{self.geo['path']});row=next(x for x in x['records'] if x['kind']=='target-part-geometry');self.assertEqual(row['consumers'],['calibration.geometry','garment.reviewed'])
 def test_unknown_owner_and_parent(self):
  with self.assertRaises(ValueError):s.graph(self.recipe_pin,self.recipe,'pelvis')
  self.recipe['parent']['mode']='invented-parent'
  with self.assertRaises(ValueError):s.graph(self.recipe_pin,self.recipe,'chest')
 def test_foreign_source(self):
  v=json.loads(Path(self.pp['path']).read_text());v['sourceReceiptSha256']='0'*64;Path(self.pp['path']).write_text(json.dumps(v));self.recipe['parent']['controls']['proposal']=self.pin(Path(self.pp['path']))
  with self.assertRaises(ValueError):s.graph(self.recipe_pin,self.recipe,'chest')
 def test_fourth_pin_controls(self):
  v={'proof':self.geo,'recipe':self.recipe_pin,'representation':self.geo,'parentScope':self.rp};stage.material_execution_controls(v,{'recipe':self.recipe_pin});stage.material_execution_controls({k:x for k,x in v.items() if k!='parentScope'},{'recipe':self.recipe_pin})
  with self.assertRaises(ValueError):stage.material_execution_controls({**v,'ambientScope':self.geo},{'recipe':self.recipe_pin})
  with self.assertRaises(ValueError):stage.material_execution_controls(v,{'recipe':self.geo})
 def test_exact_scope_schema_and_reachable_set(self):
  import copy
  expected=s.graph(self.recipe_pin,self.recipe,'chest');bank=Path(s.__file__).resolve().parent
  helpers={str(bank/name):c.sha(bank/name) for name in {'phenotype_material_execution_adoption.py','phenotype_material_parent_scope.py','replay_stage_skin_calibration.py','target_part_stage.py','audit_target_native_part.py',*(s.CONSUMERS[x][0] for row in expected['records'] for x in row['consumers'])}}
  scope={'schemaVersion':1,'kind':s.KIND,'target':self.geo,'part':'chest','coordinateSpace':'working','adoptionProof':self.geo,'originalRecipe':self.recipe_pin,'parent':self.recipe['parent'],'records':expected['records'],'geometryRepresentations':{self.geo['path']:self.geo},'currentConsumers':helpers}
  def check(v):return s.validate_scope(v,proof_pin=self.geo,recipe_pin=self.recipe_pin,recipe=self.recipe,target_pin=self.geo,part='chest',expected=expected,bank=bank)
  self.assertEqual(check(scope),scope)
  for key,value in [('part','pelvis'),('coordinateSpace','runtime'),('records',[]),('geometryRepresentations',{}),('currentConsumers',{})]:
   x=copy.deepcopy(scope);x[key]=value
   with self.subTest(key=key):
    with self.assertRaises(ValueError):check(x)
  x=copy.deepcopy(scope);x['records'][0]['consumers']=['ambient.parent']
  with self.assertRaises(ValueError):check(x)
  x=copy.deepcopy(scope);x['unknown']=True
  with self.assertRaises(ValueError):check(x)
 def test_unsealed_context(self):
  with self.assertRaises(ValueError):m.resolve(object(),module_file=__file__,path=self.recipe_pin['path'],value=self.recipe,tp=self.recipe_pin['path'],target={},part='chest',space='working',consumer='garment.reviewed')
 def test_no_implicit_parent_scope(self):
  with patch.object(m,'_prepare_legacy_material_execution',return_value='legacy') as f:
   self.assertEqual(m.prepare_material_execution({}, {}, {},target_path='none',target={},part='chest',space='working'),'legacy');self.assertEqual(f.call_count,1)

 def test_version_two_scope_cannot_import_non_geometry_receipts(self):
  expected=s.graph(self.recipe_pin,self.recipe,'chest');bank=Path(s.__file__).resolve().parent
  helpers={str(bank/name):c.sha(bank/name) for name in {'phenotype_material_execution_adoption.py','phenotype_material_parent_scope.py','replay_stage_skin_calibration.py','target_part_stage.py','audit_target_native_part.py',*(s.CONSUMERS[x][0] for row in expected['records'] for x in row['consumers'])}}
  scope={'schemaVersion':2,'kind':s.KIND,'target':self.geo,'part':'chest','coordinateSpace':'working','adoptionProof':self.geo,'originalRecipe':self.recipe_pin,'parent':self.recipe['parent'],'records':expected['records'],'geometryRepresentations':{self.geo['path']:self.geo},'currentConsumers':helpers,'receiptScopes':{self.geo['path']:self.rp}}
  s.validate_scope(scope,proof_pin=self.geo,recipe_pin=self.recipe_pin,recipe=self.recipe,target_pin=self.geo,part='chest',expected=expected,bank=bank)
  scope['receiptScopes'][self.pp['path']]=self.rp
  with self.assertRaises(ValueError):s.validate_scope(scope,proof_pin=self.geo,recipe_pin=self.recipe_pin,recipe=self.recipe,target_pin=self.geo,part='chest',expected=expected,bank=bank)
 def test_original_parent_representation_rejects_unsealed_proof(self):
  import material_parent_representation as direct
  with self.assertRaises(ValueError):direct.verify(self.geo,verified=object(),target_path=self.geo['path'],target={},part='chest',closure={},receipt_scope=None)


class OriginalFitNativeEquation(unittest.TestCase):
 def setUp(self):
  import numpy as np
  self.matrix=np.array([[-.4362379913635813,-.0048850505885519755,-.03349329964379162,.016569138236739667],[.0003214052723925361,-.43354650079036655,.059047254807426314,-.0413790420640476],[-.03384614511184992,.05884571252342467,.43225093467555586,-.2007865582474943],[0,0,0,1.]])
  scale=float(abs(np.linalg.det(self.matrix[:3,:3]))**(1/3));self.rec={'sourceToAttachmentLocal':self.matrix.tolist(),'proof':{'uniformScale':scale,'orthogonalFactorNwn':(self.matrix[:3,:3]/scale).tolist(),'reflected':False}}
 def test_named_original_fractional_power_is_exact(self):
  import material_parent_representation as p,numpy as np
  self.assertEqual(p.fit_native_rotation(self.rec,'historical-fractional-power-native-v1').tobytes(),np.asarray(self.rec['proof']['orthogonalFactorNwn']).tobytes())
 def test_cross_equation_and_unknown_rejected(self):
  import material_parent_representation as p
  for name in ('current-cbrt-native-v1','approximate',''):
   with self.assertRaises(ValueError):p.fit_native_rotation(self.rec,name)
 def test_changed_recorded_factor_rejected(self):
  import material_parent_representation as p
  self.rec['proof']['orthogonalFactorNwn'][0][0]+=1e-15
  with self.assertRaises(ValueError):p.fit_native_rotation(self.rec,'historical-fractional-power-native-v1')


class MirrorConfigurationEnumeration(unittest.TestCase):
 def test_scoped_receipt_is_not_a_second_operation_configuration(self):
  import replay_stage_skin_detail as d
  import numpy as np
  from types import SimpleNamespace
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp).resolve();left_source=root/'left.glb';left_source.write_bytes(b'left');left_receipt=root/'left.json';left_receipt.write_text('{}')
   right_receipt=root/'right.json';configuration=root/'operation.json';target_path=root/'target.json';target_path.write_text('{}');target={'id':'synthetic-mirror-target'}
   rec={'operation':'mirror','part':'footr','sourcePart':'footl','source':str(left_source),'sourceReceipt':str(left_receipt),'sourceReceiptSha256':c.sha(left_receipt),'sourceSha256':c.sha(left_source),'sourceToAttachmentLocal':np.eye(4).tolist(),'reflectionWorld':np.eye(4).tolist()}
   cfg={**rec,'planeOriginWorld':[0,0,0],'planeNormalWorld':[1,0,0]};right_receipt.write_text(json.dumps(rec));configuration.write_text(json.dumps(cfg))
   left={'receipt':{'part':'footl'},'receiptPath':left_receipt,'source':left_source,'document':{},'binary':b'left'};right={'receipt':rec,'receiptPath':right_receipt,'document':{'right':True},'binary':b'right'}
   pins={str(x):c.sha(x) for x in (right_receipt,configuration)}
   context=SimpleNamespace(physical_closure=lambda **kwargs:pins);inputs=SimpleNamespace(material_execution=context)
   with patch.object(d,'read_target',return_value=(target_path,target)),patch.object(c,'frame',return_value=np.eye(4)),patch.object(d,'reflection_between_frames',return_value=(np.eye(4),np.eye(4))),patch.object(d,'detached_affine_bake',return_value=(right['document'],right['binary'],None,None)):
    result=d.mirror_binding('footr',left,right,target_path,target,inputs);self.assertEqual(result['configuration']['path'],str(configuration))
    duplicate=root/'duplicate.json';duplicate.write_text(json.dumps(cfg));pins[str(duplicate)]=c.sha(duplicate)
    with self.assertRaisesRegex(ValueError,'One pinned actual-frame mirror operation required'):d.mirror_binding('footr',left,right,target_path,target,inputs)
    pins.clear();pins[str(right_receipt)]=c.sha(right_receipt)
    with self.assertRaisesRegex(ValueError,'One pinned actual-frame mirror operation required'):d.mirror_binding('footr',left,right,target_path,target,inputs)

if __name__=='__main__':unittest.main()
