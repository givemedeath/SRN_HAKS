"""Finite guarded-run boundaries; default full verification remains strict."""
import json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace,MappingProxyType
import phenotype_infrastructure_adoption as a
import phenotype_material_execution_adoption as m
import phenotype_material_run_scope as run
import target_contract as c
class RunScope(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
  def save(name,value):
   p=self.root/name;p.write_text(json.dumps(value));return {'path':str(p),'sha256':c.sha(p)}
  self.pin=lambda p:{'path':str(p),'sha256':c.sha(p)};self.save=save
  self.target=save('target.json',{'id':'test'});self.recipe=save('recipe.json',{'part':'footl'});self.rep=save('representation.json',{});self.scope=save('scope.json',{'geometryRepresentations':{str(self.root/'geometry.json'):self.rep}});self.native=save('native.json',{});self.candidate=save('candidate.json',{});self.geometry=save('geometry.json',{'kind':'target-part-geometry','part':'footl','candidate':self.candidate['path'],'candidateSha256':self.candidate['sha256'],'nativeCornerArchive':self.native});self.unrelated=save('unrelated.json',{'unchanged':True});self.proof=save('proof.json',{})
  helpers={str(Path(run.__file__).resolve()):c.sha(run.__file__),str(Path(m.__file__).resolve()):c.sha(m.__file__)}
  full={**helpers,**{x['path']:x['sha256'] for x in (self.target,self.recipe,self.rep,self.scope,self.native,self.candidate,self.geometry,self.unrelated,self.proof)}}
  def verify():
   for p,h in full.items():c.require(c.sha(p)==h,'Fixture full input changed')
  represented=SimpleNamespace(inputs=a.immutable(full),proof=a.immutable({'pass':True}),verify=verify)
  self.context=object.__new__(m.MaterialExecution)
  fields={'_seal':m._SEAL,'_verified':SimpleNamespace(inputs=a.immutable(full),proof=a.immutable({'currentHelpers':helpers}),verify=verify),'_recipe_pin':a.immutable(self.recipe),'_recipe':a.immutable({'part':'footl'}),'_target':a.immutable(self.target),'_representation_pin':a.immutable(self.rep),'_representation':represented,'_parent_scope_pin':a.immutable(self.scope),'_scoped_closures':a.immutable({}),'_representations':MappingProxyType({self.geometry['path']:represented}),'_graph':a.immutable({'pins':{self.geometry['path']:self.geometry['sha256'],self.candidate['path']:self.candidate['sha256']},'geometries':{self.geometry['path']:{'receipt':self.geometry,'candidate':self.candidate,'owner':'footl'}},'values':{self.geometry['path']:a.read_json(self.geometry['path'])}})}
  for k,v in fields.items():object.__setattr__(self.context,k,v)
 def tearDown(self):self.tmp.cleanup()
 def start(self,mutate=None):
  v=run.descriptor(self.context,self.proof)
  if mutate:mutate(v)
  return run.begin(self.context,self.save('run.json',v),proof_pin=self.proof)
 def test_open_nested_close_and_no_hash_cache(self):
  ctx=self.start();ctx.verify();ctx.geometry_proof(receipt_path=self.geometry['path'],candidate=self.candidate['path'],owner='footl',space='working');proof=run.finish(ctx);run.require_finished(ctx,proof);self.assertFalse(proof['nestedContentHashCache']);self.assertGreater(proof['hashCalls'],len(proof['readCounts']))
  with self.assertRaises(ValueError):ctx.verify()
 def test_unfinalized_cannot_pass(self):
  ctx=self.start()
  with self.assertRaises(ValueError):run.require_finished(ctx,{'pass':True,'run':self.pin(self.root/'run.json')})
 def test_wrong_part_scope_or_input_digest_rejects(self):
  for mutate in (lambda v:v.update(part='shinl'),lambda v:v.update(parentScope=self.recipe),lambda v:v['fullInputs'].update({self.unrelated['path']:'0'*64})):
   with self.assertRaises(ValueError):self.start(mutate)
 def test_schema_version_cannot_be_bool_float_or_string(self):
  for value in (True,1.0,'1',2):
   with self.subTest(value=value):
    with self.assertRaises(ValueError):self.start(lambda row:row.update(schemaVersion=value))
 def test_nested_candidate_and_native_corruption_reject(self):
  ctx=self.start();Path(self.native['path']).write_text('changed')
  with self.assertRaises(ValueError):ctx.geometry_proof(receipt_path=self.geometry['path'],candidate=self.candidate['path'],owner='footl',space='working')
 def test_closing_unrelated_drift_rejects_and_default_rejects_immediately(self):
  ctx=self.start();Path(self.unrelated['path']).write_text('changed');ctx.verify()
  with self.assertRaises(ValueError):self.context.verify()
  with self.assertRaises(ValueError):run.finish(ctx)
  with self.assertRaises(ValueError):run.require_finished(ctx,{'pass':True,'run':self.pin(self.root/'run.json')})
 def test_descriptor_changed_or_foreign_receipt_reject(self):
  ctx=self.start();Path(ctx._run_state.pin['path']).write_text('{}')
  with self.assertRaises(ValueError):ctx.verify()
 def test_collision_and_unsealed_nested_runs_reject(self):
  with self.assertRaises(ValueError):run.begin(object(),self.recipe,proof_pin=self.proof)
  ctx=self.start()
  with self.assertRaises(ValueError):run.begin(ctx,self.pin(self.root/'run.json'),proof_pin=self.proof)
  with self.assertRaises(ValueError):run.inputs_for(ctx)
 def test_closing_proof_cannot_be_reused_with_foreign_context(self):
  ctx=self.start();proof=run.finish(ctx);proof['run']=self.recipe
  with self.assertRaises(ValueError):run.require_finished(ctx,proof)
if __name__=='__main__':unittest.main()
