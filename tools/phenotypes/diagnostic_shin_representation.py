"""Sealed finite current shin chain; generated fields never substitute preview f32 for native f64."""
from pathlib import Path
from types import MappingProxyType
import sys,numpy as np
import diagnostic_descendant_representation as base
import diagnostic_shin_operator_replay as replay
PARTS=('shinl','shinr')
OPS=('bounded-connected-boundary-conforming-rounded-terminal-dome-diagnostic','generated-cap-only-positive-uniform-UV-original-skin-atlas-diagnostic','generated-knee-cap-only-smooth-boundary-normal-transport-v1','bounded-both-owner-dense-source-gradual-equator-joint-centered-ellipsoid-diagnostic','equator-shin-finite-derived-RGB-binding-only')
FIELDS=('kind','schemaVersion','target','stockReference','part','space','baselineRepresentation','baselineConsumer','operations','support','consumers','physicalInputs')
OPFIELDS=('operation','part','space','receipt','candidate','nativeCornerArchive','proof','lineage')
def validate_operations(rows,part):
 replay.require(part in PARTS and isinstance(rows,list)and len(rows)==5,'Exactly five supported shin operators required')
 for i,row in enumerate(rows):
  base.keys(row,OPFIELDS);replay.require(row['operation']==OPS[i]and row['part']==part and row['space']=='working','Wrong shin operation/domain')
  for k in ('receipt','candidate','nativeCornerArchive','proof'):base.checked_pin(row[k])
  replay.require((row['lineage']is None)==(i in (1,2)),'Wrong explicit lineage policy')
  if row['lineage']is not None:base.checked_pin(row['lineage'])
 return rows

def prepare_shin_representation(contract_pin,*,target_path,target,part,baseline_context,space='working'):
 if sys.flags.optimize:raise base.RepresentationError('Optimized assertions forbidden')
 try:return _prepare(contract_pin,target_path,target,part,baseline_context,space)
 except base.RepresentationError:raise
 except (KeyError,TypeError,ValueError,IndexError,OSError,AttributeError)as error:raise base.RepresentationError('Malformed shin representation: '+str(error))from error

def _prepare(contract_pin,target_path,target,part,baseline_context,space):
 cp,ch=base.checked_pin(contract_pin);c=base.strict_json(cp);base.keys(c,FIELDS);replay.require(c['kind']=='diagnostic-shin-descendant-representation'and type(c['schemaVersion'])is int and c['schemaVersion']==1,'Unsupported shin contract');replay.require(c['part']==part in PARTS and c['space']==space=='working','Cross part/space');validate_operations(c['operations'],part)
 tp,th=base.checked_pin(c['target']);replay.require(Path(target_path).resolve()==Path(tp)and base.strict_json(tp)==target,'Cross target');replay.require(target['rig']['mode']=='stock-exact'and target['rig']['runtimeScale']==1,'Exact rig required');replay.require(base.checked_pin(c['stockReference'])==base.checked_pin(target['rig']['stockReferenceReceipt']),'Cross stock rig')
 module=sys.modules.get('source_representation_contract');replay.require(module is not None and type(baseline_context)is module.VerifiedRepresentation,'Sealed original source required');replay.require(Path(module.__file__).resolve()==Path(base.checked_pin(c['baselineConsumer'])[0])==Path(tp).parents[4]/'tools/phenotypes/source_representation_contract.py','Current original consumer required');baseline_context.verify();pr=baseline_context.proof;replay.require(dict(pr['contract'])==c['baselineRepresentation']and pr['part']==part and pr['targetId']==target['id'],'Cross original baseline')
 physical={}
 for v in c['physicalInputs']:
  p,h=base.checked_pin(v);replay.require(p not in physical,'Repeated physical input');physical[p]=h
 expected=set()
 def consume(v):
  p,h=base.checked_pin(v);replay.require(physical.get(p)==h,'Undeclared consumed pin');expected.add(p);return p
 for p,h in baseline_context.inputs.items():replay.require(physical.get(p)==h,'Missing sealed original closure');expected.add(p)
 consumers={str(Path(__file__).resolve()),str(Path(replay.__file__).resolve()),str(Path(base.__file__).resolve()),str(Path(sys.modules['diagnostic_thigh_operator_replay'].__file__).resolve()),str(Path(sys.modules['measure_stock_target_basis'].__file__).resolve())};replay.require(len(c['consumers'])==5 and {base.checked_pin(v)[0]for v in c['consumers']}==consumers,'Exact current consumers required')
 for v in c['consumers']+[c[k]for k in ('target','stockReference','baselineRepresentation','baselineConsumer','support')]:consume(v)
 support=base.strict_json(c['support']['path']);consume(support['cases'][part]['mask']);original={'path':pr['originalGeometryReceipt']['path'],'sha256':pr['originalGeometryReceipt']['sha256']};consume(original);consume(dict(pr['candidate']));consume({'path':pr['originalNativeCornerArchive']['path'],'sha256':pr['originalNativeCornerArchive']['sha256']});s=replay.node(original['path'],baseline=True);reports=[]
 for i,row in enumerate(c['operations']):
  for k in ('receipt','candidate','nativeCornerArchive','proof'):
   consume(row[k])
  if row['lineage']is not None:consume(row['lineage'])
  n=replay.node(row['receipt']['path']);g=n['g'];replay.require(g['part']==part and g['coordinateSpace']=='working'and type(g['statureApplications'])is int and g['statureApplications']==0,'Wrong actual source context');replay.require(row['candidate']=={'path':g['candidate'],'sha256':g['candidateSha256']}and row['nativeCornerArchive']==g['nativeCornerArchive'],'Actual pins differ')
  for k in ('targetContract','targetContractSha256','targetId','rigRevision','joint','model','attachmentWorld'):replay.require(g[k]==s['g'][k],'Changed protected rig/neighbor frame')
  replay.require(g['targetContractSha256']==th and g['model']==target['models'][part],'Cross target/model')
  if i<4:
   replay.require(g['operation']==OPS[i]and g['source']==s['g']['candidate']and g['sourceSha256']==s['g']['candidateSha256']and g['sourceReceipt']==str(s['path'])and g['sourceReceiptSha256']==base.sha(s['path']),'Skipped/reordered/cross-owner source')
  else:
   parent=g['materialRGBBindingParent'];replay.require(parent['geometry']=={'path':str(s['path']),'sha256':base.sha(s['path'])}and parent['candidate']=={'path':s['g']['candidate'],'sha256':s['g']['candidateSha256']},'RGB binding skips actual equator parent');consume(n['proof']['newSkinRGBBindingDiagnostic']['originalDerivedRGB']);consume(g['materialRGBBindingSupportReceipt'])
  result=(replay.validate_initial_cut_cap(n,s)if i==0 else replay.validate_chart(n,s,support)if i==1 else replay.validate_shin_polish(n,s)if i==2 else replay.validate_equator(n,s,support)if i==3 else replay.validate_rgb(n,s));reports.append(result);s=n
 replay.require(set(physical)==expected,'Unreachable physical inputs');baseline_context.verify()
 for p,h in physical.items():replay.require(base.sha(p)==h,'Changed closing input')
 arrays={**{('serializedGlbF32',k):v for k,v in s['raw'][2].items()},**{('literalNativeArchive',k):v for k,v in s['native'].items()},**{('constructionF64',k[8:]):v for k,v in s['lineage'].items()if k.startswith('encoded_')}};immutable=MappingProxyType({k:(v.dtype.str,v.shape,v.tobytes())for k,v in arrays.items()});context=base.DiagnosticRepresentation(base._SEAL,(target['id'],part),tuple(sorted(physical.items()))+((cp,ch),),immutable,(base.checked_pin(c['operations'][-1]['receipt']),base.checked_pin(c['operations'][-1]['candidate'])))
 return context.verify(),tuple(MappingProxyType(x)for x in reports)
