"""Explicit sealed native-f64 authoring authority and face ownership for compilation."""
from pathlib import Path
import json
import numpy as np
import target_contract as c
import source_representation_contract as original
from diagnostic_descendant_representation import checked_pin,prepare_diagnostic_representation
def analytic_representation(*args,**kwargs):
 from diagnostic_analytic_representation import prepare_analytic_representation
 return prepare_analytic_representation(*args,**kwargs)[0]
def rebuilt_patch_representation(*args,**kwargs):
 from diagnostic_rebuilt_patch_representation import prepare_rebuilt_patch_representation
 return prepare_rebuilt_patch_representation(*args,**kwargs)[0]
def bounded_representation(*args,**kwargs):
 from diagnostic_bounded_descendant_representation import prepare_bounded_representation
 return prepare_bounded_representation(*args,**kwargs)[0]

FIELDS={'representation','baselineRepresentation','authority','faceOwnership'}
def controls(value):
 c.require(isinstance(value,dict) and set(value)==FIELDS,'Explicit native representation, baseline, authority and face ownership required')
 c.require(value['authority']=='literalNativeArchive','Native compiler authority must be literalNativeArchive, never GLB float32')
 for key in ('representation','baselineRepresentation','faceOwnership'):checked_pin(value[key])

def validate_arrays(arrays,material_ids):
 count=len(arrays['positions']);c.require(count>0,'Nonempty native body required')
 for name,width in [('positions',3),('normals',3),('uvNative',2)]:
  a=arrays[name];c.require(a.dtype==np.dtype('float64') and a.shape==(count,3,width) and np.isfinite(a).all(),'Finite native-f64 corner authority required: '+name)
 c.require(np.asarray(material_ids).shape==(count,) and np.asarray(material_ids).dtype.kind in 'iu' and np.all(material_ids>=0),'Exact one material ID per native triangle required')
 c.require(np.all(np.linalg.norm(arrays['normals'],axis=2)>0),'Nonzero authored normals required')
 if 'tangents'in arrays:c.require(arrays['tangents'].shape==(count,3,4) and arrays['tangents'].dtype==np.dtype('float64') and np.isfinite(arrays['tangents']).all(),'Native authored tangent authority differs')
 return count

def prepare(value,*,target_path,target,part,source,receipt,document_material_ids,space='working'):
 controls(value);c.require(space=='working','Native authoring bridge accepts working geometry only; identity conversion is separate')
 rp,rh=checked_pin(value['representation']);bp,bh=checked_pin(value['baselineRepresentation']);cfg=json.loads(Path(rp).read_text());baseline=original.verify_source_representation(value['baselineRepresentation'],target_path=target_path,target=target,part=part,space='working')
 if cfg.get('kind')=='target-source-representation-contract':
  c.require((rp,rh)==(bp,bh),'Original bridge representation must equal baseline');ctx=baseline;proof=dict(ctx.proof);c.require(proof['candidate']=={'path':str(Path(source).resolve()),'sha256':c.sha(source)} and proof['originalGeometryReceipt']=={'path':str(Path(receipt).resolve()),'sha256':c.sha(receipt)},'Cross-owner original geometry bridge')
  ap,ah=checked_pin({k:proof['originalNativeCornerArchive'][k]for k in ('path','sha256')});arrays=dict(np.load(ap,allow_pickle=False));inputs=dict(ctx.inputs)
 else:
  ctx=(analytic_representation if cfg.get('kind')=='diagnostic-analytic-descendant-representation' else rebuilt_patch_representation if cfg.get('kind')=='diagnostic-rebuilt-patch-descendant-representation' else bounded_representation if cfg.get('kind')=='diagnostic-bounded-descendant-representation' else prepare_diagnostic_representation)(value['representation'],target_path=target_path,target=target,part=part,space='working',baseline_context=baseline if cfg.get('kind')in ('diagnostic-thigh-descendant-representation','diagnostic-elbow-descendant-representation','diagnostic-shin-descendant-representation','diagnostic-analytic-descendant-representation','diagnostic-rebuilt-patch-descendant-representation','diagnostic-bounded-descendant-representation')else None)
  ctx.geometry_proof({'path':str(Path(receipt).resolve()),'sha256':c.sha(receipt)},{'path':str(Path(source).resolve()),'sha256':c.sha(source)},part,'working');arrays={name:ctx.array('literalNativeArchive',name)for name in ('positions','normals','uvNative')}
  actual_archive=json.loads(Path(receipt).read_text())['nativeCornerArchive'];ap,ah=checked_pin({k:actual_archive[k]for k in ('path','sha256')});actual_arrays=dict(np.load(ap,allow_pickle=False))
  if 'tangents'in actual_arrays:arrays['tangents']=ctx.array('literalNativeArchive','tangents')
  if 'tangentTriangleIds'in actual_arrays:arrays['tangentTriangleIds']=actual_arrays['tangentTriangleIds']
  inputs={row['path']:row['sha256'] for row in ctx.physical_inputs}
 fp,fh=checked_pin(value['faceOwnership']);f=dict(np.load(fp,allow_pickle=False));c.require(set(f)=={'sourceCandidateSha256','sourceReceiptSha256','materialIds'},'Exact native face ownership schema required')
 c.require(str(f['sourceCandidateSha256'].item())==c.sha(source) and str(f['sourceReceiptSha256'].item())==c.sha(receipt),'Face ownership cross-source binding')
 tangent_policy='absent-authored-T; compiler-regenerated separately';tangent_count=0
 if 'tangents'in arrays:
  t=arrays['tangents'];tangent_count=len(t);count=len(arrays['positions'])
  if t.shape==(count,3,4)and np.isfinite(t).all():tangent_policy='dense native authored T archived; ASCII compiler regenerates T'
  else:
   ti=arrays.get('tangentTriangleIds');c.require(ti is not None and ti.dtype.kind in 'iu'and ti.ndim==1 and len(np.unique(ti))==len(ti)and np.all(ti>=0)and np.all(ti<count),'Explicit sparse native authored T triangle IDs required');c.require(t.shape==(len(ti),3,4)and np.isfinite(t).all(),'Finite sparse generated-cap authored T required');tangent_policy='sparse generated-cap native T preserved in pinned archive; absent original source T remains absent; ASCII compiler regenerates T';del arrays['tangents']
 ids=f['materialIds'];count=validate_arrays(arrays,ids);c.require(np.array_equal(ids,np.asarray(document_material_ids)),'Material document/native face order mismatch')
 ctx.verify();inputs.update({rp:rh,bp:bh,fp:fh,str(Path(__file__).resolve()):c.sha(__file__)})
 arrays={k:np.frombuffer(np.ascontiguousarray(v).tobytes(),dtype=v.dtype).reshape(v.shape)for k,v in arrays.items()if k in ('positions','normals','uvNative','tangents')}
 return arrays,ids,{'kind':'verified-native-f64-compiler-inputs','part':part,'authority':'literalNativeArchive','candidate':{'path':str(Path(source).resolve()),'sha256':c.sha(source)},'geometryReceipt':{'path':str(Path(receipt).resolve()),'sha256':c.sha(receipt)},'nativeCornerArchive':json.loads(Path(receipt).read_text())['nativeCornerArchive'],'representation':value['representation'],'baselineRepresentation':value['baselineRepresentation'],'faceOwnership':value['faceOwnership'],'triangleCount':count,'authoredTangentsPresent':tangent_count>0,'authoredTangentTriangleCount':tangent_count,'authoredTangentPolicy':tangent_policy,'asciiPNUTAuthority':'native f64; authored tangents archived separately because ASCII compiler regenerates T','encodedPreviewSubstituted':False,'identityConversionApplied':False,'frozenInputs':inputs}

_SEAL=object()
class VerifiedNativeCompilerInputs:
 def __init__(self,seal,arrays,ids,proof):
  c.require(seal is _SEAL,'Verified native inputs require module seal');self._seal=seal;self._arrays=arrays;self._ids=np.frombuffer(np.ascontiguousarray(ids).tobytes(),dtype=ids.dtype).reshape(ids.shape);self._proof=proof
 @property
 def proof(self):return __import__('types').MappingProxyType(__import__('copy').deepcopy(self._proof))
 @property
 def material_ids(self):self.verify();return self._ids
 def array(self,name):self.verify();return self._arrays[name]
 def verify(self):
  c.require(self._seal is _SEAL,'Unsealed native compiler inputs')
  for p,h in self._proof['frozenInputs'].items():c.require(c.sha(p)==h,'Changed native compiler input: '+p)
  return self

def prepare_native_geometry(value,**kwargs):
 arrays,ids,proof=prepare(value,**kwargs);return VerifiedNativeCompilerInputs(_SEAL,arrays,ids,proof).verify()
