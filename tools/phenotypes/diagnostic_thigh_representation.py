"""Scratch finite thigh chain factory. Current sealed baseline is mandatory.
Historical producer scripts are inert provenance. No runtime/material approval.
"""
from pathlib import Path
from types import MappingProxyType
import sys
import numpy as np
import diagnostic_descendant_representation as base
import diagnostic_thigh_operator_replay as replay

OPERATIONS=(
 'bounded-connected-boundary-conforming-rounded-terminal-dome-diagnostic',
 'generated-cap-only-positive-uniform-UV-original-skin-atlas-diagnostic',
 'bounded-connected-boundary-conforming-rounded-terminal-dome-diagnostic',
 'generated-knee-cap-only-smooth-boundary-normal-transport-v1',
 'bounded-source-patella-chop-true-axis-elongation-and-connected-round-terminal-diagnostic',
 'bounded-bottom-thigh-55native-pose-average-radial-field-connected40mm-rounded-dome-diagnostic',
 'new-generated-thigh-cap-encoded-float64-normal-unit-tangent-orthogonalization-diagnostic')

def validate_operation_rows(operations,part):
 replay.require(isinstance(operations,list)and len(operations)==7,'Exactly seven explicit operations required')
 fields=('receipt','literalOperation','part','space','statureApplications','nativeCornerArchive','candidate','source','sourceSha256','sourceReceipt','sourceReceiptSha256')
 for i,row in enumerate(operations):
  base.keys(row,fields)
  replay.require(row['literalOperation']==OPERATIONS[i]and row['part']==part and row['space']=='working'and type(row['statureApplications'])is int and row['statureApplications']==0,'Malformed or unsupported operation row')
 return operations

def prepare_thigh_representation(contract_pin,*,target_path,target,part,baseline_context,space='working'):
 try:return _prepare_thigh_representation(contract_pin,target_path=target_path,target=target,part=part,baseline_context=baseline_context,space=space)
 except base.RepresentationError:raise
 except (KeyError,TypeError,ValueError,IndexError,OSError) as error:raise base.RepresentationError('Malformed thigh representation input: '+str(error))from error

def _prepare_thigh_representation(contract_pin,*,target_path,target,part,baseline_context,space='working'):
 cp,ch=base.checked_pin(contract_pin);c=base.strict_json(cp)
 base.keys(c,('kind','schemaVersion','target','stockReference','part','space','baselineRepresentation','baselineConsumer','ancestryManifest','operations','support','consumers','physicalInputs'))
 replay.require(c['kind']=='diagnostic-thigh-descendant-representation'and type(c['schemaVersion'])is int and c['schemaVersion']==1,'Unknown thigh contract')
 replay.require(part in ('legl','legr')and c['part']==part and c['space']==space=='working','Cross target/part/space');validate_operation_rows(c['operations'],part)
 tp,th=base.checked_pin(c['target']);replay.require(Path(target_path).resolve()==Path(tp)and base.strict_json(tp)==target,'Cross target')
 replay.require(target['rig']['mode']=='stock-exact'and target['rig']['runtimeScale']==1,'Stock exact identity rig required')
 replay.require(base.checked_pin(c['stockReference'])==base.checked_pin(target['rig']['stockReferenceReceipt']),'Wrong stock receipt')
 module=sys.modules.get('source_representation_contract');replay.require(module is not None and type(baseline_context)is module.VerifiedRepresentation,'Current sealed original source representation required')
 consumerPath,consumerHash=base.checked_pin(c['baselineConsumer']);expectedConsumer=Path(tp).parents[4]/'tools/phenotypes/source_representation_contract.py';replay.require(Path(module.__file__).resolve()==Path(consumerPath)==expectedConsumer,'Historical or wrong original consumer')
 baseline_context.verify();proof=baseline_context.proof
 replay.require(dict(proof['contract'])==c['baselineRepresentation']and proof['part']==part and proof['targetId']==target['id']and proof['coordinateSpace']=='working','Cross-baseline representation')
 manifestPin=base.checked_pin(c['ancestryManifest']);manifest=base.strict_json(manifestPin[0]);row=manifest['parts'][part]
 replay.require(c['operations']==row['orderedOperations']and len(c['operations'])==7,'Missing, reordered or unsupported ancestor')
 replay.require(tuple(x['literalOperation']for x in c['operations'])==OPERATIONS,'Unsupported chain operators')
 original=row['baseline'];replay.require(dict(proof['originalGeometryReceipt'])==original['receipt']and dict(proof['originalNativeCornerArchive'])==original['nativeCornerArchive'],'Thigh baseline native authority differs')
 physical={}
 for pin in c['physicalInputs']:
  p,h=base.checked_pin(pin);replay.require(p not in physical,'Duplicate physical input');physical[p]=h
 for p,h in baseline_context.inputs.items():
  q=str(Path(p).resolve());replay.require(physical.get(q)==h,'Missing/stale baseline closure')
 consumers={str(Path(__file__).resolve()),str(Path(replay.__file__).resolve()),str(Path(base.__file__).resolve())}
 replay.require({base.checked_pin(p)[0]for p in c['consumers']}==consumers and len(c['consumers'])==3,'Exact current consumer whitelist required')
 for pin in c['consumers']+[c['target'],c['stockReference'],c['baselineRepresentation'],c['baselineConsumer'],c['ancestryManifest'],c['support']]:
  p,h=base.checked_pin(pin);replay.require(physical.get(p)==h,'Undeclared current consumed pin')
 expected=set(str(Path(p).resolve())for p in baseline_context.inputs)
 for pin in c['consumers']+[c['target'],c['stockReference'],c['baselineRepresentation'],c['baselineConsumer'],c['ancestryManifest'],c['support']]:expected.add(base.checked_pin(pin)[0])
 support=base.strict_json(base.checked_pin(c['support'])[0]);maskPin=support['cases'][part]['mask'];p,h=base.checked_pin(maskPin);expected.add(p);replay.require(physical.get(p)==h,'Missing skin support mask')
 def consume(pin):
  p,h=base.checked_pin(pin);expected.add(p);replay.require(physical.get(p)==h,'Missing actual operation input: '+p);return p
 source=replay.node(consume(original['receipt']),baseline=True)
 for pin in [original['nativeCornerArchive'],proof['candidate']]:consume(dict(pin))
 reports=[]
 for i,operation in enumerate(c['operations']):
  path=consume(operation['receipt']);g=base.strict_json(path)
  replay.require(operation['nativeCornerArchive']==g['nativeCornerArchive']and operation['candidate']=={'path':g['candidate'],'sha256':g['candidateSha256']}and operation['source']==g['source']and operation['sourceSha256']==g['sourceSha256']and operation['sourceReceipt']==g['sourceReceipt']and operation['sourceReceiptSha256']==g['sourceReceiptSha256'],'Operation manifest literal claims differ from receipt')
  replay.require(g['operation']==OPERATIONS[i]and g['part']==part and g['coordinateSpace']=='working'and type(g['statureApplications'])is int and g['statureApplications']==0,'Wrong operation context')
  replay.require(g['sourceReceipt']==str(source['path'])and g['sourceReceiptSha256']==base.sha(source['path']),'Skipped or cross-operation parent')
  consume({'path':g['source'],'sha256':g['sourceSha256']});consume({'path':g['candidate'],'sha256':g['candidateSha256']});consume(g['nativeCornerArchive']);consume({'path':str(Path(path).parent/'proof.json'),'sha256':base.sha(Path(path).parent/'proof.json')})
  for key in ('targetContract','targetContractSha256','targetId','rigRevision','joint','model','attachmentWorld'):
   replay.require(g[key]==source['g'][key],'Changed installed rig/owner frame')
  replay.require(g['targetContractSha256']==th and g['targetId']==target['id']and g['model']==target['models'][part]and g['rigRevision']==target['rig']['revision'],'Cross target rig or model')
  if i!=3:consume({'path':str(Path(path).parent/'encoded-and-native-protected-lineage.npz'),'sha256':base.sha(Path(path).parent/'encoded-and-native-protected-lineage.npz')})
  n=replay.node(path)
  if i==0:result=replay.validate_cut_cap(n,source)
  elif i==1:result=replay.validate_chart(n,source,support)
  elif i==2:result=replay.validate_cut_cap(n,source,proximal=True)
  elif i==3:result=replay.validate_normal_polish(n,source)
  elif i==4:result=replay.validate_axial(n,source,support)
  elif i==5:result=replay.validate_radial(n,source,support)
  else:result=replay.validate_precision(n,source)
  reports.append(result);source=n
 replay.require(set(physical)==expected,'Unreachable or undeclared physical input')
 baseline_context.verify()
 for p,h in physical.items():replay.require(base.sha(p)==h,'Changed closing source input')
 arrays={**{('serializedGlbF32',k):v for k,v in source['raw'][2].items()},**{('literalNativeArchive',k):v for k,v in source['native'].items()},**{('constructionF64',k[8:]):v for k,v in source['lineage'].items()if k.startswith('encoded_')}}
 immutable=MappingProxyType({k:(v.dtype.str,v.shape,v.tobytes())for k,v in arrays.items()})
 result=base.DiagnosticRepresentation(base._SEAL,(target['id'],part),tuple(sorted(physical.items()))+((cp,ch),),immutable,(base.checked_pin(row['final']),base.checked_pin({'path':source['g']['candidate'],'sha256':source['g']['candidateSha256']})))
 return result.verify(),tuple(MappingProxyType(x)for x in reports)
