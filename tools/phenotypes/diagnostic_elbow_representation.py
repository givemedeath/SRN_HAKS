"""Finite two-operation elbow descendant factory; sealed original source is mandatory.
Only the frozen BODY60 and plain B3/B5 with F20 recipes qualify. No staging or approval.
"""
from pathlib import Path
from types import MappingProxyType
import json,sys,numpy as np
import diagnostic_descendant_representation as base
import diagnostic_elbow_operator_replay as replay
PARTS=('bicepl','bicepr','forel','forer')
OPERATIONS=('bounded-source-center-aware-ownstock-anatomical-elbow-terminal-redistribution','source-fullness60x60-connected-plain-short-B3F20-caps')
CAP_OPERATIONS=(OPERATIONS[1],'source-fullness60x60-connected-plain-short-B5F20-caps')
OP_FIELDS=('receipt','candidate','nativeCornerArchive','proof','lineage','literalOperation','part','space','statureApplications')
CONTRACT_FIELDS=('kind','schemaVersion','target','stockReference','part','space','baselineRepresentation','baselineConsumer','sourceBank','operations','fieldRows','capConfiguration','skinSupport','normalPolicy','consumers','physicalInputs')

def validate_operation_rows(rows,part):
 replay.require(isinstance(rows,list)and len(rows)==2,'Exactly two explicit elbow operations required')
 replay.require(part in PARTS,'Unsupported elbow owner')
 for i,row in enumerate(rows):
  base.keys(row,OP_FIELDS)
  replay.require((row['literalOperation']==OPERATIONS[0]if i==0 else row['literalOperation']in CAP_OPERATIONS)and row['part']==part and row['space']=='working'and type(row['statureApplications'])is int and row['statureApplications']==0,'Malformed or unsupported elbow operator')
  for key in ('receipt','candidate','nativeCornerArchive','proof','lineage'):base.checked_pin(row[key])
 return rows

def prepare_elbow_representation(contract_pin,*,target_path,target,part,baseline_context,space='working'):
 if sys.flags.optimize:raise base.RepresentationError('Optimized validation removal forbidden')
 try:return _prepare(contract_pin,target_path=target_path,target=target,part=part,baseline_context=baseline_context,space=space)
 except base.RepresentationError:raise
 except (KeyError,TypeError,ValueError,IndexError,OSError,AttributeError)as error:raise base.RepresentationError('Malformed elbow representation input: '+str(error))from error

def _prepare(contract_pin,*,target_path,target,part,baseline_context,space):
 cp,ch=base.checked_pin(contract_pin);c=base.strict_json(cp);base.keys(c,CONTRACT_FIELDS)
 replay.require(c['kind']=='diagnostic-elbow-descendant-representation'and type(c['schemaVersion'])is int and c['schemaVersion']==1,'Unknown elbow contract')
 replay.require(c['part']==part in PARTS and c['space']==space=='working','Cross target/part/space');validate_operation_rows(c['operations'],part)
 tp,th=base.checked_pin(c['target']);replay.require(Path(target_path).resolve()==Path(tp)and base.strict_json(tp)==target,'Cross target')
 replay.require(target['rig']['mode']=='stock-exact'and target['rig']['runtimeScale']==1,'Stock-exact identity rig required')
 replay.require(base.checked_pin(c['stockReference'])==base.checked_pin(target['rig']['stockReferenceReceipt']),'Wrong stock receipt')
 module=sys.modules.get('source_representation_contract');replay.require(module is not None and type(baseline_context)is module.VerifiedRepresentation,'Current sealed original source representation required')
 bc,bh=base.checked_pin(c['baselineConsumer']);replay.require(Path(module.__file__).resolve()==Path(bc)==Path(tp).parents[4]/'tools/phenotypes/source_representation_contract.py','Historical or wrong original consumer')
 baseline_context.verify();proof=baseline_context.proof
 replay.require(dict(proof['contract'])==c['baselineRepresentation']and proof['part']==part and proof['targetId']==target['id']and proof['coordinateSpace']=='working','Cross baseline representation')
 physical={}
 for item in c['physicalInputs']:
  p,h=base.checked_pin(item);replay.require(p not in physical,'Duplicate physical input');physical[p]=h
 expected=set()
 def consume(item):
  p,h=base.checked_pin(item);replay.require(physical.get(p)==h,'Undeclared current consumed pin');expected.add(p);return p
 for p,h in baseline_context.inputs.items():
  q=str(Path(p).resolve());replay.require(physical.get(q)==h,'Missing/stale sealed original closure');expected.add(q)
 consumers={str(Path(__file__).resolve()),str(Path(replay.__file__).resolve()),str(Path(base.__file__).resolve())}
 replay.require(len(c['consumers'])==3 and {base.checked_pin(p)[0]for p in c['consumers']}==consumers,'Exact current elbow consumer whitelist required')
 for item in c['consumers']+[c[k]for k in ('target','stockReference','baselineRepresentation','baselineConsumer','sourceBank','fieldRows','capConfiguration','skinSupport')]:consume(item)
 replay.require(c['normalPolicy']=='authored-seam-and-next-ring-blend-only','Unsupported generated normal policy')
 bank=base.strict_json(c['sourceBank']['path']);original=bank['parts'][part]
 replay.require(original['geometry']==dict(proof['originalGeometryReceipt'])and original['candidate']==dict(proof['candidate']),'Original source bank differs')
 originalg=base.strict_json(consume(original['geometry']));consume(original['candidate']);consume(originalg['nativeCornerArchive'])
 replay.require(originalg['nativeCornerArchive']==dict(proof['originalNativeCornerArchive']),'Original native authority differs')
 parentg=originalg;reports=[]
 configuration=base.strict_json(c['capConfiguration']['path']);skin=base.strict_json(c['skinSupport']['path']);consume(skin['parts'][part]['supportArchive'])
 fields=base.strict_json(c['fieldRows']['path']);fieldrows={row['part']:row for row in fields['proposedFieldRows']}
 for i,row in enumerate(c['operations']):
  for key in ('receipt','candidate','nativeCornerArchive','proof','lineage'):consume(row[key])
  g=base.strict_json(row['receipt']['path']);pr=base.strict_json(row['proof']['path'])
  replay.require(g['schemaVersion']==2 and g['kind']=='target-part-geometry'and g['operation']==row['literalOperation']and g['part']==part and g['coordinateSpace']=='working'and type(g['statureApplications'])is int and g['statureApplications']==0,'Wrong elbow operation context')
  replay.require(row['candidate']=={'path':g['candidate'],'sha256':g['candidateSha256']}and row['nativeCornerArchive']==g['nativeCornerArchive'],'Candidate/native receipt differs')
  replay.require(g['source']==parentg['candidate']and g['sourceSha256']==parentg['candidateSha256']and g['sourceReceipt']==(original['geometry']['path']if i==0 else c['operations'][0]['receipt']['path'])and g['sourceReceiptSha256']==(original['geometry']['sha256']if i==0 else c['operations'][0]['receipt']['sha256']),'Skipped or cross-owner parent')
  for key in ('targetContract','targetContractSha256','targetId','rigRevision','joint','model','attachmentWorld'):
   replay.require(g[key]==parentg[key],'Changed installed rig/owner frame')
  replay.require(g['targetContractSha256']==th and g['targetId']==target['id']and g['model']==target['models'][part]and g['rigRevision']==target['rig']['revision'],'Cross target rig/model')
  if i==0:
   replay.require(pr['parentCandidate']==original['candidate']and pr['parentGeometry']==original['geometry']and pr['parentNativeArchive']==originalg['nativeCornerArchive'],'Body source claims differ')
   replay.require(pr['measuredCase']==fieldrows[part],'Body field recipe differs')
   report=replay.validate_body(part,{'candidate':row['candidate'],'geometry':row['receipt'],'nativeCorners':row['nativeCornerArchive'],'proof':row['proof'],'protectedFields':row['lineage']})
  else:
   with np.load(row['nativeCornerArchive']['path'],allow_pickle=False)as z:
    replay.validate_generated_normal_ids(z['newGeneratedCapFaceIds'],z['sourceFaceIds'],z['newGeneratedCapFaceIds'],c['normalPolicy'])
   report=replay.validate_caps(part,{'candidate':row['candidate'],'geometry':row['receipt'],'nativeCorners':row['nativeCornerArchive'],'proof':row['proof'],'encodedNativeLineage':row['lineage']},configuration,skin)
  reports.append(report);parentg=g
 replay.require(set(physical)==expected,'Unreachable or undeclared physical input')
 baseline_context.verify()
 for p,h in physical.items():replay.require(base.sha(p)==h,'Changed closing elbow input')
 final=c['operations'][-1];doc,b,actual,_=replay.raw(final['candidate']['path']);native=dict(np.load(final['nativeCornerArchive']['path'],allow_pickle=False));lineage=dict(np.load(final['lineage']['path'],allow_pickle=False))
 arrays={**{('serializedGlbF32',k):v for k,v in actual.items()},**{('literalNativeArchive',k):v for k,v in native.items()},**{('constructionF64',k[8:]):v for k,v in lineage.items()if k.startswith('encoded_')}}
 immutable=MappingProxyType({k:(v.dtype.str,v.shape,v.tobytes())for k,v in arrays.items()})
 context=base.DiagnosticRepresentation(base._SEAL,(target['id'],part),tuple(sorted(physical.items()))+((cp,ch),),immutable,(base.checked_pin(final['receipt']),base.checked_pin(final['candidate'])))
 return context.verify(),tuple(MappingProxyType(row)for row in reports)
