"""Closed literal graph of the original reviewed garment/ankle material parents.
This module describes scope; the sealed factory verifies adoption and representations.
"""
from pathlib import Path
import phenotype_infrastructure_adoption as a
import target_contract as c
CONSUMERS={
 'calibration.root':('replay_stage_skin_calibration.py',{'target-compiler-skin-intensity-calibration'}),
 'calibration.geometry':('replay_stage_skin_calibration.py',{'target-part-geometry'}),
 'garment.reviewed':('target_garment_face_ownership.py',{'target-part-geometry','target-garment-face-proposal','target-garment-face-review'}),
 'detail.frozen':('replay_stage_skin_detail.py',{'one-original-source-body-microdetail-transport-material-diagnostic','two-unselected-derived-ankle-color-calibration-controls'}),
 'detail.geometry':('replay_stage_skin_detail.py',{'target-part-geometry'}),
 'detail.original':('replay_stage_skin_detail.py',{'target-part-geometry'}),
 'detail.mirror':('replay_stage_skin_detail.py',{'target-part-geometry'}),
 'sourceface.recipient':('target_source_face_material_lineage.py',{'target-source-face-material-recipient-lineage-v1'}),
 'sourceface.geometry':('target_source_face_material_lineage.py',{'target-part-geometry'}),
}
FIELDS={'schemaVersion','kind','target','part','coordinateSpace','adoptionProof','originalRecipe','parent','records','geometryRepresentations','currentConsumers'}
KIND='typed-original-material-parent-execution-scope'

def pinned(row):
 p,h=a.row(row);c.require(c.sha(p)==h,'Material parent pin changed: '+str(p));return p

def graph(recipe_pin,recipe,part):
 """Enumerate only known replay fields, never recursively crawl frozenInputs."""
 records={};geometries={};inputs={};values={};helper_claims=[]
 def leaf(row):
  p=pinned(row);inputs[str(p)]=c.sha(p);return p
 def load(row):
  p=leaf(row);v=a.read_json(p);values[str(p)]=v;return p,v
 def add(row,consumer,owner,expected_kind=None):
  p,v=load(row);kind=v.get('kind');c.require(consumer in CONSUMERS and kind in CONSUMERS[consumer][1],'Unsupported typed material parent kind')
  if expected_kind is not None:c.require(kind==expected_kind,'Typed material parent kind differs')
  name=str(p)
  if name not in records:records[name]={'receipt':dict(row),'kind':kind,'owner':owner,'coordinateSpace':'working','closure':'frozenInputs' if 'frozenInputs' in v else None,'consumers':[]}
  c.require(records[name]['receipt']==dict(row) and records[name]['owner']==owner,'Conflicting material graph owner or pin')
  if consumer not in records[name]['consumers']:records[name]['consumers'].append(consumer)
  return p,v
 def geometry(row,consumer,owner):
  p,v=add(row,consumer,owner,'target-part-geometry');add(row,'calibration.geometry',owner,'target-part-geometry');c.require(v['coordinateSpace']=='working' and v['part']==owner and v['statureApplications']==0,'Working material parent geometry owner differs')
  cp={'path':v['candidate'],'sha256':v['candidateSha256']};leaf(cp);geometries[str(p)]={'receipt':dict(row),'candidate':cp,'owner':owner};return p,v
 add(recipe_pin,'calibration.root',part,'target-compiler-skin-intensity-calibration')
 geometry(recipe['geometryReceipt'],'calibration.geometry',part)
 ms=recipe['materialSource'];c.require(ms['coordinateSpace']=='working','Working material source required')
 geometry(ms['geometryReceipt'],'calibration.geometry',part)
 mode=recipe['parent']['mode'];controls=recipe['parent']['controls']
 if mode=='reviewed-per-face-garment':
  c.require(part=='chest' and set(controls)=={'proposal','review'},'Original chest garment controls required')
  pp,proposal=add(controls['proposal'],'garment.reviewed',part,'target-garment-face-proposal');add(controls['review'],'garment.reviewed',part,'target-garment-face-review')
  row={'path':proposal['sourceReceipt'],'sha256':proposal['sourceReceiptSha256']};c.require(row==ms['geometryReceipt'],'Original garment source differs from material source');geometry(row,'garment.reviewed',part)
 elif mode=='original-source-uv-detail-v1':
  c.require(part in ('footl','footr','shinl','shinr') and set(controls)=={'mode','receipt','sourceManifest'} and controls['mode']==mode,'Exact original four-owner detail controls required')
  mp,material=add(controls['receipt'],'detail.frozen',None,'one-original-source-body-microdetail-transport-material-diagnostic')
  _,manifest=load(controls['sourceManifest']);c.require(manifest['kind']=='target-source-chart-detail-material-binding' and set(manifest['parts'])=={'footl','footr','shinl','shinr'} and manifest['materialReceipt']==controls['receipt'],'Original detail manifest differs')
  _,appearance=load(manifest['favoredAppearance']);c.require(appearance['kind']=='user-favored-working-ankle-geometry-and-original-detail-appearance-baseline' and appearance['material']==controls['receipt'],'Original detail appearance differs')
  _,parent=add(material['parentMaterials'],'detail.frozen',None,'two-unselected-derived-ankle-color-calibration-controls')
  _,cfg=load(parent['configuration']);c.require(cfg['kind']=='derived-ankle-strip-and-common-tone-diagnostic-controls' and set(cfg['parts'])=={'shinl','footl'},'Original detail configuration differs');load(cfg['measurement'])
  for owner,entry in manifest['parts'].items():
   favored=(appearance['leftGeometry'] if owner.endswith('l') else appearance['rightDerivedMirrorGeometry'])[owner]
   c.require(entry['part']==owner and favored==entry['workingGeometryReceipt'],'Original detail favored owner differs')
   geometry(favored,'detail.geometry',owner)
   if owner.endswith('r'):geometry(favored,'detail.mirror',owner)
  for owner in ('shinl','footl'):
   c.require(cfg['parts'][owner]['originalFitReceipt']==manifest['parts'][owner]['originalFitReceipt'],'Original detail fit pin differs')
   geometry(cfg['parts'][owner]['originalFitReceipt'],'detail.original',owner)
  if 'lineageReceipt' in ms:
   _,recipient=add(ms['lineageReceipt'],'sourceface.recipient',part,'target-source-face-material-recipient-lineage-v1')
   c.require(recipient['materialSource']=={'candidate':ms['candidate'],'geometryReceipt':ms['geometryReceipt']} and recipient['currentWorkingSource']=={'candidate':recipe['candidate'],'geometryReceipt':recipe['geometryReceipt']},'Original detail recipient source graph differs')
   geometry(ms['geometryReceipt'],'sourceface.geometry',part)
 else:c.require(False,'Scoped adapter supports original reviewed chest and four ankle owners only')
 # Original replay pins are data, not additional scope authority. All get physical hash verification.
 def leaves(v,origin):
  if isinstance(v,dict):
   if set(v)=={'path','sha256'}:
    p,h=a.row(v)
    if p.parent==Path(__file__).resolve().parent and p.suffix=='.py' and c.sha(p)!=h:
     literal=values[origin].get('frozenInputs',{})
     c.require(literal.get(str(p))==h,'Historical helper metadata outside original receipt closure')
     helper_claims.append({'receipt':records[origin]['receipt'],'original':dict(v)})
    else:leaf(v)
    return
   for k,x in v.items():
    if k not in ('frozenInputs','sourceClosure','helperSnapshots','outputHashes'):leaves(x,origin)
  elif isinstance(v,list):
   for x in v:leaves(x,origin)
 for origin,value in tuple(values.items()):leaves(value,origin)
 for row in records.values():row['consumers'].sort()
 return {'records':[records[x] for x in sorted(records)],'geometries':geometries,'pins':inputs,'values':values,'historicalHelperClaims':helper_claims}


def validate_scope(scope,*,proof_pin,recipe_pin,recipe,target_pin,part,expected,bank):
 c.require(isinstance(scope,dict) and set(scope)==(FIELDS if scope.get('schemaVersion')==1 else FIELDS|{'receiptScopes'}) and type(scope['schemaVersion']) is int and scope['schemaVersion'] in (1,2) and scope['kind']==KIND,'Exact typed parent scope required')
 c.require(scope['target']==target_pin and scope['part']==part and scope['coordinateSpace']=='working' and scope['adoptionProof']==proof_pin and scope['originalRecipe']==recipe_pin and scope['parent']==recipe['parent'],'Material parent scope root/owner/proof differs')
 c.require(scope['records']==expected['records'],'Material scope differs from closed consumed parent graph')
 c.require(isinstance(scope['geometryRepresentations'],dict) and set(scope['geometryRepresentations'])==set(expected['geometries']),'Complete exact material geometry representation set required')
 needed={str(Path(bank)/name) for name in {'phenotype_material_execution_adoption.py','phenotype_material_parent_scope.py','replay_stage_skin_calibration.py','target_part_stage.py','audit_target_native_part.py',*(CONSUMERS[x][0] for row in expected['records'] for x in row['consumers'])}}
 c.require(set(scope['currentConsumers'])==needed and all(c.sha(p)==h for p,h in scope['currentConsumers'].items()),'Exact current material consumer closure required')
 if scope['schemaVersion']==2:
  c.require(isinstance(scope['receiptScopes'],dict) and set(scope['receiptScopes'])<=set(expected['geometries']),'Only exact consumed geometry receipt scopes allowed')
  for name,pin in scope['receiptScopes'].items():pinned(pin)
 for pin in scope['geometryRepresentations'].values():pinned(pin)
 return scope
