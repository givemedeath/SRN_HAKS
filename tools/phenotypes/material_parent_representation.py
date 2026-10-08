"""Strict archived-parent PNUT representation; no geometry or material production.
Original encoded float32 and native-double fields remain separate authorities.
Only immutable fit/taper/mirror parents reached by a reviewed material graph qualify.
"""
from dataclasses import dataclass
from pathlib import Path
import numpy as np
import phenotype_infrastructure_adoption as a
import source_representation_contract as s
import target_contract as c
from place_purposebuilt_pelvis import read_glb, raw_corners
from mirror_stock_limb_part import detached_affine_bake
KIND='target-original-material-parent-direct-representation'
FIELDS={'schemaVersion','kind','target','part','coordinateSpace','adoptionProof','geometryReceipt','candidate','nativeCornerArchive','receiptScope','currentHelpers','fitNativeProtocol'}
_SEAL=object()
@dataclass(frozen=True,init=False)
class VerifiedParent:
 def verify(self):
  c.require(getattr(self,'_seal',None) is _SEAL,'Unverified parent representation')
  for p,h in self.inputs.items():c.require(c.sha(p)==h,'Parent representation input changed: '+p)

def verify(pin,*,verified,target_path,target,part,closure,receipt_scope):
 c.require(type(verified) is a.VerifiedAdoption,'Sealed infrastructure proof required');verified.verify()
 cp,ch=s.pin(pin);c.require(c.sha(cp)==ch,'Parent representation contract changed');cfg=s.read_json(cp)
 c.require(set(cfg)==FIELDS and type(cfg['schemaVersion']) is int and cfg['schemaVersion']==1 and cfg['kind']==KIND,'Exact original parent representation required')
 # Proof pin is checked by the factory; verify target/owner again independently.
 c.require(cfg['target']=={'path':str(Path(target_path).resolve()),'sha256':c.sha(target_path)} and cfg['part']==part and cfg['coordinateSpace']=='working' and cfg['receiptScope']==receipt_scope,'Parent representation target/scope differs')
 helper=Path(__file__).resolve();c.require(cfg['currentHelpers']=={str(helper):c.sha(helper)} and verified.proof['currentHelpers'].get(str(helper))==c.sha(helper),'Current parent verifier missing or stale')
 rp,rh=s.pin(cfg['geometryReceipt']);c.require(c.sha(rp)==rh,'Original parent receipt changed');rec=s.read_json(rp)
 c.verify_binding(rec,target_path,target,'working');c.require(rec['kind']=='target-part-geometry' and rec['schemaVersion']==2 and rec['operation'] in ('fit','mirror','measured-angular-profile-ankle-taper') and rec['part']==part and rec['joint']==c.PART_JOINTS[part] and rec['model']==c.model(target,part) and rec['statureApplications']==0 and rec['diagnosticOnly'] is True,'Narrow original material geometry parent required')
 s.equal(np.asarray(rec['attachmentWorld']),c.frame(target,c.PART_JOINTS[part],'working'),'parent attachment')
 c.require(cfg['fitNativeProtocol'] in ('historical-fractional-power-native-v1','current-cbrt-native-v1') if rec['operation']=='fit' else cfg['fitNativeProtocol'] is None,'Exact original fit native protocol declaration required')
 c.require(cfg['candidate']=={'path':rec['candidate'],'sha256':rec['candidateSha256']} and cfg['nativeCornerArchive']==rec['nativeCornerArchive'],'Original parent candidate/archive differs')
 if receipt_scope is None:
  c.require((rp,'frozenInputs') in verified.receiptClosures,'Original parent closure not declared')
  exact_closure=a.plain(verified.receiptClosures[rp,'frozenInputs'])
 else:
  receipts,scopes,physical,scope_inputs,evidence=s.ancestor_contract(receipt_scope,bank_pin=cfg['adoptionProof'],verified=verified,target_path=Path(target_path).resolve(),target=target)
  c.require(set(receipts)=={rp},'Original parent receipt scope imported another receipt')
  exact_closure={v['path']:v['sha256'] for v in physical.values()};exact_closure.update(scope_inputs)
 c.require(closure==exact_closure,'Original parent physical closure differs')
 inputs=dict(closure);inputs[cp]=ch;inputs[rp]=rh;inputs.update(cfg['currentHelpers'])
 for row in (cfg['candidate'],cfg['nativeCornerArchive']):
  p,h=s.pin(row);c.require(c.sha(p)==h,'Parent physical input changed');inputs[p]=h
 doc,binary=read_glb(cfg['candidate']['path']);c.require(doc['nodes']==[{'name':'detached_geometry','mesh':0}] and not doc.get('skins') and not doc.get('animations'),'Detached original parent required')
 extra={};P,N,U,_=raw_corners(doc,binary,extra=extra);V=U.copy();V[:,:,1]=1-V[:,:,1]
 with np.load(cfg['nativeCornerArchive']['path'],allow_pickle=False) as z:
  native={k:z[k].copy() for k in z.files}
  for k,v in [('positions',P),('normals',N),('uvGltf',U),('uvNative',V)]:s.equal(native[k].astype('<f4'),v.astype('<f4'),'original parent float32 '+k)
  if 'TANGENT' in extra:
   k='authoredTangents' if 'authoredTangents' in native else 'tangents';s.equal(native[k].astype('<f4'),np.concatenate(extra['TANGENT']['rows']).astype('<f4'),'original parent tangent')
  else:c.require('authoredTangents' not in native and 'tangents' not in native,'Absent parent tangent cannot be invented')
 proof={'protocol':'original-material-parent-direct-float32-v1','nativeEncodedFloat32PNUTExact':True,'nativeDoubleFieldsRetained':True,'originalClaimsUnchanged':True,'historicalCodeExecuted':False}
 if rec['operation']=='fit':
  c.require(closure.get(rec['source'])==rec['sourceSha256'],'Original fit source outside verified receipt closure')
  source_doc,source_bin=read_glb(rec['source']);nd,nb,native_replay,_=detached_affine_bake(source_doc,source_bin,np.asarray(rec['sourceToAttachmentLocal']),False)
  c.require(nd==doc and nb==binary,'Original positive uniform fit serialized replay differs')
  rotation=fit_native_rotation(rec,cfg['fitNativeProtocol'])
  source_extra={};_,source_n,_,_=raw_corners(source_doc,source_bin,extra=source_extra)
  native_replay['normals']=source_n@rotation.T
  if 'TANGENT' in source_extra:
   tt=np.concatenate(source_extra['TANGENT']['rows']).copy();tt[:,:,:3]=tt[:,:,:3]@rotation.T;native_replay['tangents']=tt
  for k,v in native_replay.items():s.equal(native[k],v,'original fit native '+k)
  proof['fitNativeProtocol']=cfg['fitNativeProtocol']
  proof['originalPositiveUniformFitReplayedExactly']=True
 result=object.__new__(VerifiedParent)
 for key,val in {'_seal':_SEAL,'inputs':a.immutable(inputs),'proof':a.immutable(proof)}.items():object.__setattr__(result,key,val)
 result.verify();return result

def fit_native_rotation(receipt, protocol):
 """Exact recorded float arithmetic; never adjust an attribute tolerance."""
 c.require(protocol in ('historical-fractional-power-native-v1','current-cbrt-native-v1'),'Explicit original fit native equation required')
 matrix=np.asarray(receipt['sourceToAttachmentLocal'],float)
 determinant=float(abs(np.linalg.det(matrix[:3,:3])))
 scale=float(determinant**(1/3)) if protocol=='historical-fractional-power-native-v1' else float(np.cbrt(determinant))
 c.require(np.isfinite(scale) and scale>0 and receipt['proof']['uniformScale']==scale and receipt['proof']['reflected'] is False,'Original fit recorded native scale differs from named equation')
 factor=matrix[:3,:3]/scale
 s.equal(factor,np.asarray(receipt['proof']['orthogonalFactorNwn'],float),'original fit named orthogonal factor')
 return factor
