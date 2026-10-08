"""Independently replay an explicit native T-only postcompile derivative.

Reads the actual emitted binary; recomputes eligibility/projection separately
from the writer. All other bytes, source P/N/UV and material dependencies remain
strict. This is a distinct audit, never the original compiler-output association.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

import numpy as np
import target_contract as c
from target_native_tangent_descendant import (load_parent, exact, file_row, KIND,
    POLICY, THRESHOLD, attribute_intervals)
from audit_target_native_part import decode, tangent_proof
from target_body_inventory import flat_hashes

KIND_AUDIT='target-derived-native-attribute-audit'


def compare_derivative_directions(before,after):
    """Actual decoded UV gradients, with finite signed corner and triangle areas."""
    ids=before['faces'];p=before['position'][ids].astype(float);u=before['uv'][ids].astype(float)
    d1=u[:,1]-u[:,0];d2=u[:,2]-u[:,0];det=d1[:,0]*d2[:,1]-d1[:,1]*d2[:,0];valid=abs(det)>1e-12
    dp1=p[:,1]-p[:,0];dp2=p[:,2]-p[:,0]
    tf=(dp1[valid]*d2[valid,1,None]-dp2[valid]*d1[valid,1,None])/det[valid,None]
    bf=(dp2[valid]*d1[valid,0,None]-dp1[valid]*d2[valid,0,None])/det[valid,None]
    faces=np.flatnonzero(valid);area=np.linalg.norm(np.cross(dp1,dp2),axis=1)/2;result={}
    def directions(value):
        n=value['normal'][ids[valid]].astype(float);t=value['tangent'][ids[valid]].astype(float)
        n=n/np.linalg.norm(n,axis=2)[:,:,None];b=np.cross(n,t)*value['sign'][ids[valid]]
        return t,b
    old= directions(before);new=directions(after)
    for label,a,b,gradient in [('tangent',old[0],new[0],tf),('bitangent',old[1],new[1],bf)]:
        den=np.linalg.norm(gradient,axis=1);c.require((den>0).all(),'Nondegenerate UV gradient produced zero derivative')
        def cosine(v):return np.einsum('fci,fi->fc',v,gradient)/(np.linalg.norm(v,axis=2)*den[:,None])
        a_cos=cosine(a);b_cos=cosine(b);newbad=(a_cos>=0)&(b_cos<0);badfaces=np.flatnonzero(newbad.any(1));direction=np.einsum('fci,fci->fc',a,b)/(np.linalg.norm(a,axis=2)*np.linalg.norm(b,axis=2))
        result[label]={'originalNegativeCorners':int((a_cos<0).sum()),'derivedNegativeCorners':int((b_cos<0).sum()),
           'newlyNegativeCorners':int(newbad.sum()),'newlyNegativeFaces':faces[badfaces].tolist(),
           'newlyNegativeFaceAreaSquareMetres':float(area[faces[badfaces]].sum()),
           'originalMinimumCosine':float(a_cos.min()),'derivedMinimumCosine':float(b_cos.min()),
           'oldVsDerivedDirectionMinimumCosine':float(direction.min())}
        c.require(not newbad.any(),'Newly negative native UV derivative direction; stop for review')
    result['degenerateUVFacesExcludedFromDirectionOnly']=np.flatnonzero(~valid).tolist()
    result['notNormalMappedVisualAcceptance']=True
    return result


def audit_emitted_bytes(original,derived,model,expected_meshes,roles):
    """Independent actual-byte reconstruction, including every noneligible word."""
    c.require(isinstance(original,bytes) and isinstance(derived,bytes) and len(original)==len(derived),
              'Same-length original/derived native bytes required')
    before,root=decode(original,model,expected_meshes);after,newroot=decode(derived,model,expected_meshes)
    c.require(root==newroot and set(before)==set(roles) and set(roles.values())<={'skin','garment'} and 'skin' in roles.values(),
              'Exact native root and source-proved role inventory required')
    attribute_intervals(before);attribute_intervals(after);expected=bytearray(original);allowed=np.zeros(len(original),bool);proofs={};changed=0
    for name,a in before.items():
        b=after[name];c.require(a['layout']==b['layout'],'Native layout changed')
        for field in ('position','normal','uv','faces','sign'):
            c.require(a[field].dtype==b[field].dtype and a[field].shape==b[field].shape
                      and a[field].tobytes()==b[field].tobytes(),'Protected native '+field+' changed')
        n=a['normal'].astype(np.float64);t=a['tangent'].astype(np.float64);length=np.sqrt(np.sum(n*n,axis=1))
        c.require((length>0).all(),'Nonzero original normal required');n=n/length[:,None]
        dots=np.einsum('ij,ij->i',n,t);ids=np.flatnonzero(np.abs(dots)>=THRESHOLD)
        c.require(roles[name]=='skin' or not len(ids),'Non-skin tangent cannot be changed')
        projected=t[ids]-n[ids]*dots[ids,None];magnitudes=np.sqrt(np.sum(projected*projected,axis=1))
        c.require(np.isfinite(magnitudes).all() and (magnitudes>1e-8).all(),'Degenerate original tangent projection')
        new=(projected/magnitudes[:,None]).astype('<f4');start=12+a['layout']['rawOffset']+a['layout']['attributeOffsets']['tangent']
        for vertex,value in zip(ids,new):
            offset=start+int(vertex)*12;expected[offset:offset+12]=value.tobytes();allowed[offset:offset+12]=True
        c.require(b['tangent'][ids].tobytes()==new.tobytes(),'Emitted tangent differs from independent original-parent equation')
        retained=np.ones(len(t),bool);retained[ids]=False
        c.require(b['tangent'][retained].tobytes()==a['tangent'][retained].tobytes(),'Noneligible tangent changed')
        tangent=tangent_proof(b);direction=compare_derivative_directions(a,b);changed+=len(ids)
        proofs[name]={'role':roles[name],'nativeLayout':b['layout'],'eligibleVertices':ids.tolist(),'eligibleCount':len(ids),
             'allPNUVFaceSignBytesExact':True,'noneligibleTangentBytesExact':True,'actualNativeTangentArrays':tangent,
             'UVGradientDirectionBeforeAfter':direction}
    c.require(changed>0,'Repeated or unnecessary tangent derivation rejected')
    c.require(bytes(expected)==derived,'Derived native contains a changed protected/header/controller/material/noneligible byte')
    c.require(np.array_equal(np.frombuffer(original,'u1')[~allowed],np.frombuffer(derived,'u1')[~allowed]),'Non-T byte changed')
    return after,root,proofs,allowed


def audit(derivation_path,output):
    derivation_path=Path(derivation_path).resolve();r=json.loads(derivation_path.read_text(encoding='utf-8'))
    c.require(r.get('schemaVersion')==1 and r.get('kind')==KIND and r.get('policy')==POLICY
              and type(r.get('derivationApplications')) is int and r['derivationApplications']==1
              and r.get('diagnosticOnly') is True and r.get('nativeCompilerExecuted') is False
              and r.get('originalCompileReceiptRewritten') is False and r.get('sourcePNUTMapsChanged') is False,
              'Explicit single postcompile derivative receipt required')
    frozen={};config_path=exact(r['configuration'],frozen);cfg=json.loads(config_path.read_text(encoding='utf-8'));ctx=load_parent(cfg)
    frozen.update(ctx['frozenInputs']);frozen[str(derivation_path)]=c.sha(derivation_path)
    c.verify_binding(r,ctx['targetPath'],ctx['target'],ctx['space'])
    c.require(r['part']==ctx['part'] and r['model']==ctx['model'] and r['statureApplications']==ctx['stage']['statureApplications'],
              'Derived part/space/conversion association differs')
    for key,expected in [('originalCompilerReceipt',file_row(ctx['compilePath'])),('originalCompiledNative',file_row(ctx['nativePath'])),
                         ('stageReceipt',file_row(ctx['stagePath'])),('compositionReceipt',file_row(ctx['compositionPath']))]:
        c.require(r[key]==expected,'Original parent pin relabeled: '+key);exact(r[key],frozen)
    c.require(r['sourceAuditConfiguration']==cfg['sourceAuditConfiguration'] and r['installedShaderSupplement']==cfg['installedShaderSupplement'],
              'Original audit/shader lineage relabeled')
    for p,h in r['frozenInputs'].items():exact({'path':p,'sha256':h},frozen)
    source=ctx['nativePath'].read_bytes();original_copy=exact(r['originalCompiledNativeCopy'],frozen)
    c.require(original_copy.read_bytes()==source,'Preserved compiler parent copy differs')
    native_path=exact(r['nativeModel'],frozen);c.require(native_path.name==ctx['model']+'.mdl' and native_path!=ctx['nativePath'],
              'Fresh modified native model must remain distinct from compiler parent')
    native,root,proofs,allowed=audit_emitted_bytes(source,native_path.read_bytes(),ctx['model'],ctx['native'],ctx['roles'])
    c.require(set(r['meshes'])==set(proofs),'Receipt mesh inventory differs')
    for name,row in proofs.items():
        c.require(r['meshes'][name]['role']==row['role'] and r['meshes'][name]['eligibleVertices']==row['eligibleVertices']
                  and r['meshes'][name]['eligibleCount']==row['eligibleCount'],'Receipt eligibility/ownership differs')
        row.update(ctx['sourceProofs'][name])
    expected_resources={native_path.name:r['nativeModel']['sha256'],**ctx['stage']['materialResourceHashes']}
    c.require(r['materialResourceHashes']==ctx['stage']['materialResourceHashes'] and flat_hashes(native_path.parent)==expected_resources,
              'Derived resource inventory/material hashes differ')
    for name,h in ctx['stage']['materialResourceHashes'].items():exact({'path':str(native_path.parent/name),'sha256':h},frozen)
    c.require(r['eligibleTangentByteCount']==int(allowed.sum()) and r['changedByteCount']==int((np.frombuffer(source,'u1')!=np.frombuffer(native_path.read_bytes(),'u1')).sum()),
              'Reported native delta count differs')
    output=Path(output).resolve();c.require(not output.exists(),'Fresh immutable derived-native audit required');(output/'helpers').mkdir(parents=True)
    helpers={}
    for name in ('audit_derived_native_tangent.py','target_native_tangent_descendant.py','audit_target_native_part.py','audit_native_limb_shading.py'):
        p=Path(__file__).with_name(name);dest=output/'helpers'/name;shutil.copyfile(p,dest);frozen[str(p)]=c.sha(p);helpers[str(p)]=file_row(dest)
    for p,h in frozen.items():exact({'path':p,'sha256':h},{})
    receipt={'schemaVersion':1,'kind':KIND_AUDIT,**c.binding(ctx['targetPath'],ctx['target'],ctx['space']),
         'part':ctx['part'],'model':ctx['model'],'statureApplications':ctx['stage']['statureApplications'],
         'stageReceipt':str(ctx['stagePath']),'stageReceiptSha256':c.sha(ctx['stagePath']),
         'nativeReceipt':str(ctx['compilePath']),'nativeReceiptSha256':c.sha(ctx['compilePath']),
         'originalCompiledNative':file_row(ctx['nativePath']),'nativeModel':file_row(native_path),'nativeModelSha256':c.sha(native_path),
         'nativeDerivationReceipt':file_row(derivation_path),'root':root,'meshes':proofs,'materials':ctx['materialProofs'],
         'materialInputBasis':ctx['effective']['materialInputBasis'],'derivedMaterialProof':ctx['effective']['derivedMaterialProof'],
         'attributeTransportVerified':True,'materialTransportVerified':True,'nativeTangentProjectionIndependentlyReplayed':True,
         'allNonTBytesExact':True,'sourcePNUTMapsUnchanged':True,'normalPixelsEdited':False,'roughnessPixelsEdited':False,
         'nativeCompilerExecuted':False,'originalCompileReceiptRewritten':False,'postcompileTangentXYZDerived':True,
         'nativeTangentVisualAccepted':False,'productionAccepted':False,'clientAccepted':False,'diagnosticOnly':True,
         'frozenInputs':frozen,'helperSnapshots':helpers,'limits':['Explicit postcompile T XYZ modification, not original compiled bytes.','Source authored native normal lengths/signs are preserved.','UV gradient directions are finite diagnostics, not normal-mapped native/client visual acceptance.']}
    path=output/'derived-native-attribute-audit.json';path.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8');return path


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--derivation',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();r=audit(a.derivation,a.output);print(json.dumps({'receipt':str(r),'sha256':c.sha(r)}))
