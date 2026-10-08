"""Explicit postcompile native skin-tangent descendant; original compile stays immutable.

Only tangent XYZ words selected from the exact compiler parent may change. Stored
P/N/UV, handedness, cloth, controllers, headers and dependencies stay byte-exact.
The separate auditor independently replays the emitted binary before preview.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct

import numpy as np
import target_contract as c
from target_part_pipeline import pin, read_target, verify_source_receipt
from target_body_inventory import expected_body_resources, flat_hashes, skin_atlas_keys
from audit_target_native_part import (decode, ascii_meshes, audit_source_inputs,
    audit_material_resources, tangent_proof, LAYOUT_PINS)
from audit_native_limb_shading import validate_transport, float32_ulp_distance

KIND = 'target-native-tangent-orthogonalization-descendant'
CONFIG = 'target-native-tangent-orthogonalization-configuration'
THRESHOLD = 2e-5
POLICY = 'compiler-parent-skin-only-TXYZ-orthogonal-projection-v1'


def file_row(path):
    path=Path(path).resolve()
    return {'path':str(path),'sha256':c.sha(path)}


def exact(row, frozen):
    c.require(isinstance(row,dict) and set(row)=={'path','sha256'}
              and isinstance(row['path'],str) and Path(row['path']).is_absolute()
              and isinstance(row['sha256'],str) and re.fullmatch('[a-f0-9]{64}',row['sha256']),
              'Explicit absolute input path/hash required')
    path=pin(row['path'],row['sha256'])
    c.require(str(path) not in frozen or frozen[str(path)]==row['sha256'],'Conflicting input pin')
    frozen[str(path)]=row['sha256'];return path


def controls(cfg):
    required={'schemaVersion','kind','diagnosticOnly','targetContract','targetId','rigRevision',
              'part','coordinateSpace','sourceAuditConfiguration','installedShaderSupplement','policy'}
    c.require(isinstance(cfg,dict) and set(cfg)==required and type(cfg['schemaVersion']) is int
              and cfg['schemaVersion']==1 and cfg['kind']==CONFIG and cfg['diagnosticOnly'] is True
              and cfg['policy']==POLICY,'Explicit native T-only diagnostic configuration required')
    c.require(cfg['part'] in c.BODY_PARTS and cfg['coordinateSpace'] in ('working','runtime'),
              'Declared native tangent owner/space required')


def shader_inputs(row,tp,target,space,frozen):
    p=exact(row,frozen);s=json.loads(p.read_text(encoding='utf-8'))
    c.require(s.get('kind')=='actual-installed-shader-provenance-supplement-native-T-interface'
              and s.get('schemaVersion')==1 and s.get('nativeBytesWritten') is False
              and s.get('helpersEdited') is False,'Actual installed shader supplement required')
    bank=exact(s['installedShaderReceipt'],frozen);b=json.loads(bank.read_text(encoding='utf-8'))
    c.verify_binding(b,tp,target,space)
    c.require(b.get('kind')=='target-material-shader-preparation' and b.get('schemaVersion')==2
              and b.get('installedShaderSourceVerified') is True and b.get('userOverrideEmpty') is True,
              'Verified installed shader bank with empty overrides required')
    for name,h in b['frozenInputs'].items():exact({'path':name,'sha256':h},frozen)
    wrapper=exact(s['explicitLegacyMetadataWrapperProvenance'],frozen);w=json.loads(wrapper.read_text(encoding='utf-8'))
    c.require(w.get('kind')=='explicit-female-installed-shader-source-freeze-wrapper-provenance'
              and w.get('shaderReceipt')==file_row(bank),'Honest target-policy shader wrapper provenance required')
    c.require(set(s['literalSources'])==set(b['resources']) and 'inc_transform.shd' in b['resources'],
              'Complete actual installed shader source closure required')
    for name,r in s['literalSources'].items():
        source=exact(r,frozen);c.require(source.name==name and c.sha(source)==b['resources'][name]['sha256']
               and b['resources'][name]['overrideEnabledSha256']==c.sha(source),'Installed/override shader bytes differ')
    setup=exact(s['setupTSB']['source'],frozen);c.require(setup==Path(s['literalSources']['inc_transform.shd']['path']).resolve(),'SetupTSB source differs')
    lines=setup.read_text().splitlines();start=s['setupTSB']['firstLine']-1
    c.require(lines[start:start+len(s['setupTSB']['lines'])]==s['setupTSB']['lines']
              and any('normalize(vVertexTangent)' in x for x in s['setupTSB']['lines'])
              and any('cross(vSurfaceNormal, vTangent)' in x for x in s['setupTSB']['lines'])
              and not any('dot(' in x for x in s['setupTSB']['lines']),'Actual frozen tangent shader snippet differs')
    return s


def load_parent(cfg):
    """Full original compiler/source/material association; never waive old audit T failure."""
    controls(cfg);frozen={};tp=exact(cfg['targetContract'],frozen);target=c.load(tp);part=cfg['part'];space=cfg['coordinateSpace']
    c.require(target['id']==cfg['targetId'] and target['rig']['revision']==cfg['rigRevision'],
              'Native tangent target/rig differs')
    ap=exact(cfg['sourceAuditConfiguration'],frozen);ac=json.loads(ap.read_text(encoding='utf-8'))
    allowed={'schemaVersion','kind','part','coordinateSpace','targetContract','targetContractSha256','stageReceipt',
             'stageReceiptSha256','converted','compositionSha256','nativeReceiptSha256','layoutDirectory',
             'nativeUvMaximumUlps','float32UvRoundingEvidence','exactUVPolicyAttempt'}
    c.require(set(ac)<=allowed and ac.get('kind')=='target-native-part-audit' and ac.get('schemaVersion')==2
              and ac['part']==part and ac['coordinateSpace']==space,'Original native audit configuration owner differs')
    oldtp,oldtarget=read_target(ac);c.require(oldtp==tp and oldtarget==target,'Original audit target contract differs')
    ulps=ac.get('nativeUvMaximumUlps',0);c.require(type(ulps) is int and ulps in (0,1),'Existing explicit 0-or-1 ULP policy only')
    for field in ('float32UvRoundingEvidence','exactUVPolicyAttempt'):
        if field in ac:exact({k:ac[field][k] for k in ('path','sha256')},frozen)
    shader=shader_inputs(cfg['installedShaderSupplement'],tp,target,space,frozen)
    sp=exact({'path':ac['stageReceipt'],'sha256':ac['stageReceiptSha256']},frozen);stage=json.loads(sp.read_text(encoding='utf-8'))
    model=c.model(target,part)
    c.require(stage.get('schemaVersion')==2 and stage.get('kind')=='target-part-stage'
              and stage['part']==part and stage['model']==model,'Exact stage owner differs')
    c.verify_binding(stage,tp,target,space)
    c.require(stage['statureApplications']==(0 if space=='working' else 1),'Native stage conversion count differs')
    for name,h in stage['frozenInputs'].items():exact({'path':name,'sha256':h},frozen)
    src=exact({'path':stage['source'],'sha256':stage['sourceSha256']},frozen)
    sr=exact({'path':stage['sourceReceipt'],'sha256':stage['sourceReceiptSha256']},frozen)
    if not (isinstance(stage.get('derivedMaterialProof'),dict) and stage['derivedMaterialProof'].get('kind')
            in ('replayed-c1-skin-intensity-compiler-inputs','replayed-original-source-chart-detail-compiler-inputs')):
        verify_source_receipt(src,sr,tp,target,part,space)
    folder=Path(ac['converted']).resolve();cp=exact({'path':str(folder/'conversion.json'),'sha256':ac['compositionSha256']},frozen)
    composition=json.loads(cp.read_text(encoding='utf-8'))
    c.require(composition.get('schemaVersion')==2 and composition.get('kind')=='target-body-composition','Original target composition required')
    c.verify_binding(composition,tp,target,space)
    for name,h in composition['frozenInputs'].items():exact({'path':name,'sha256':h},frozen)
    matches=[r for r in composition['composition']['sourceReceipts'] if r['part']==part]
    c.require(len(matches)==1 and Path(matches[0]['path']).resolve()==sp and matches[0]['sha256']==c.sha(sp),
              'Composition does not select exact stage')
    npth=exact({'path':str(folder/'native-compile.json'),'sha256':ac['nativeReceiptSha256']},frozen)
    compiled=json.loads(npth.read_text(encoding='utf-8'))
    c.require(compiled.get('complete') is True and compiled.get('executionMode')=='compilemodel'
              and compiled.get('interactiveClientLaunched') is False,'Original completed offline compiler receipt required')
    exact({'path':compiled['client'],'sha256':compiled['clientSha256']},frozen)
    native_rows={r['name']:r for r in compiled['models']}
    c.require(len(native_rows)==len(compiled['models']) and set(native_rows)==set(composition['modelParts']),
              'Original compiler model inventory differs')
    hashes=flat_hashes(folder/'resources')
    c.require(set(hashes)==set(composition['materialResourceHashes'])|set(native_rows),'Original compiler resource closure differs')
    for name,h in composition['materialResourceHashes'].items():
        c.require(hashes[name]==h,'Original compiler material dependency changed: '+name);exact({'path':str(folder/'resources'/name),'sha256':h},frozen)
    for name,row in native_rows.items():
        c.require(row['sourceSha256']==composition['asciiModelHashes'][name] and row['binarySha256']==hashes[name]
                  and (folder/'resources'/name).stat().st_size==row['bytes'],'Compiler parent association changed or derived parent repeated')
    native_path=exact({'path':str(folder/'resources'/(model+'.mdl')),'sha256':native_rows[model+'.mdl']['binarySha256']},frozen)
    ascii_path=exact({'path':stage['asciiModel'],'sha256':stage['asciiModelSha256']},frozen)
    c.require(composition['asciiModelHashes'][model+'.mdl']==c.sha(ascii_path),'Stage ASCII/compiler source differs')
    for name,h in stage['materialResourceHashes'].items():c.require(composition['materialResourceHashes'].get(name)==h,'Stage dependency differs')
    roles={int(k):v for k,v in stage['materialRoles'].items()}
    expected=expected_body_resources(target,{part},{part} if 'garment' in roles.values() else set(),{part:skin_atlas_keys(stage.get('materialSlots'))})-{model+'.mdl'}
    c.require(set(stage['materialResourceHashes'])==expected,'Declared native material ownership differs')
    for name,h in LAYOUT_PINS.items():exact({'path':str(Path(ac['layoutDirectory']).resolve()/name),'sha256':h},frozen)
    effective=audit_source_inputs(stage,src,sr,tp,target,part,space)
    for path in effective['auditFiles']:exact(file_row(path),frozen)
    p,n,u=effective['positions'],effective['normals'],effective['uv'];pr=effective['primitives']
    role_faces=np.asarray([roles[r['material']] for r in pr for _ in range(r['triangles'])]);native_uv=u.copy();native_uv[:,:,1]=1-native_uv[:,:,1]
    ascii_rows=ascii_meshes(ascii_path.read_text(encoding='ascii'),model,roles.values());meshes,root=decode(native_path.read_bytes(),model,ascii_rows)
    proofs={};material_proofs={}
    for name,row in ascii_rows.items():
        role=row['role'];mask=role_faces==role;native=meshes[name];selected={'position':p[mask],'normal':n[mask],'uv':native_uv[mask]}
        corners={k:native[k][native['faces']] for k in selected};ae,be,ex=validate_transport(selected,row['corners'],corners,ulps)
        if role=='garment':c.require(np.array_equal(corners['uv'],selected['uv'].astype('<f4')),'Garment native UV must remain exact')
        c.require(native['layout']['textureSlots']==[row['material'],'','',row['material']] and native['layout']['shadowFlag']==1,
                  'Native material slots or shadow changed')
        uv_delta=float32_ulp_distance(corners['uv'],selected['uv'])
        proofs[name]={'role':role,'nativeLayout':native['layout'],'sourceToAsciiOrderedCornerMaximumErrors':ae,
             'sourceToNativeOrderedCornerMaximumErrors':be,'nativeCornersExactSourceFloat32':ex,
             'nativeUvFloat32Rounding':{'explicitMaximumAllowedUlps':ulps,'observedMaximumUlps':int(uv_delta.max()),'nonexactValues':int((uv_delta>0).sum())}}
        material_proofs[role],paths=audit_material_resources(folder/'resources',row['material'],role,effective['materialRows'][role],compiled)
        for path in paths:exact(file_row(path),frozen)
    return {'config':cfg,'targetPath':tp,'target':target,'part':part,'space':space,'model':model,'stagePath':sp,'stage':stage,
            'compositionPath':cp,'compilePath':npth,'compiled':compiled,'nativePath':native_path,'native':meshes,'root':root,
            'roles':{k:r['role'] for k,r in ascii_rows.items()},'sourceProofs':proofs,'materialProofs':material_proofs,
            'effective':effective,'frozenInputs':frozen,'shaderSupplement':shader}


def attribute_intervals(native):
    intervals=[]
    for name,row in native.items():
        layout=row['layout'];start=12+layout['rawOffset'];count=layout['vertices']
        for key,width in [('position',3),('normal',3),('uv',2),('tangent',3),('sign',1)]:
            a=start+layout['attributeOffsets'][key];b=a+count*width*4;intervals.append((a,b,name,key))
    ordered=sorted(intervals)
    c.require(all(a[1]<=b[0] for a,b in zip(ordered,ordered[1:])), 'Aliased native attribute arrays cannot be patched')
    return intervals


def project_skin_tangents(data,native,roles):
    c.require(set(native)==set(roles) and set(roles.values())<={'skin','garment'} and 'skin' in roles.values(),
              'Exact source-proved skin/cloth inventory required')
    attribute_intervals(native);out=bytearray(data);allowed=np.zeros(len(data),dtype=bool);rows={};total=0
    for name,row in native.items():
        n=row['normal'].astype(float);t=row['tangent'].astype(float);nl=np.linalg.norm(n,axis=1);tl=np.linalg.norm(t,axis=1)
        c.require(np.isfinite(n).all() and np.isfinite(t).all() and (nl>0).all() and np.allclose(tl,1,atol=THRESHOLD,rtol=0),
                  'Finite original normal/unit native tangent required')
        unit=n/nl[:,None];dot=np.einsum('ij,ij->i',unit,t);eligible=np.abs(dot)>=THRESHOLD
        c.require(roles[name]=='skin' or not eligible.any(),'Cloth tangent failure outside explicit skin-only operation')
        projected=t-unit*dot[:,None];length=np.linalg.norm(projected,axis=1)
        c.require(np.isfinite(length).all() and (length>1e-8).all(),'Degenerate native tangent projection')
        q=(projected/length[:,None]).astype('<f4');changed=row['tangent'].copy();changed[eligible]=q[eligible]
        start=12+row['layout']['rawOffset']+row['layout']['attributeOffsets']['tangent']
        for vertex in np.flatnonzero(eligible):
            at=start+int(vertex)*12;out[at:at+12]=changed[vertex].tobytes();allowed[at:at+12]=True
        proof=tangent_proof({**row,'tangent':changed});total+=int(eligible.sum())
        rows[name]={'role':roles[name],'eligibleVertices':np.flatnonzero(eligible).tolist(),'eligibleCount':int(eligible.sum()),
              'originalAbsUnitNormalDotTMaximum':float(abs(dot).max()),'originalNormalLengthRange':[float(nl.min()),float(nl.max())],
              'minimumProjectedLength':float(length.min()),'derivedTangentProof':proof,'tangentAbsoluteStart':start}
    c.require(total>0,'No failing original compiler skin tangent; repeated or unnecessary derivation rejected')
    source=np.frombuffer(data,'u1');actual=np.frombuffer(out,'u1')
    c.require(np.array_equal(source[~allowed],actual[~allowed]),'Non-tangent byte changed')
    return bytes(out),rows,allowed


def derive(config_path,output):
    config_path=Path(config_path).resolve();cfg=json.loads(config_path.read_text(encoding='utf-8'));ctx=load_parent(cfg)
    output=Path(output).resolve();c.require(not output.exists(),'Fresh immutable T derivative output required')
    original=ctx['nativePath'].read_bytes();derived,rows,allowed=project_skin_tangents(original,ctx['native'],ctx['roles'])
    decoded,root=decode(derived,ctx['model'],ctx['native']);c.require(root==ctx['root'],'Derived native hierarchy differs')
    for name,row in decoded.items():
        for key in ('position','normal','uv','faces','sign'):c.require(row[key].tobytes()==ctx['native'][name][key].tobytes(),'Protected native array changed: '+key)
        c.require(row['layout']==ctx['native'][name]['layout'],'Native layout changed');tangent_proof(row)
    output.mkdir();(output/'resources').mkdir();(output/'original-parent').mkdir();(output/'helpers').mkdir()
    original_copy=output/'original-parent'/ctx['nativePath'].name;shutil.copyfile(ctx['nativePath'],original_copy)
    native_path=output/'resources'/ctx['nativePath'].name;native_path.write_bytes(derived)
    c.require(native_path.read_bytes()==derived and c.sha(original_copy)==c.sha(ctx['nativePath']),'Native copy/write differs')
    material_rows={}
    for name,h in ctx['stage']['materialResourceHashes'].items():
        src=ctx['nativePath'].parent/name;dest=output/'resources'/name;shutil.copyfile(src,dest);c.require(c.sha(dest)==h,'Copied material changed');material_rows[name]=h
    frozen={**ctx['frozenInputs'],str(config_path):c.sha(config_path)};snapshots={}
    for name in ('target_native_tangent_descendant.py','audit_derived_native_tangent.py','audit_target_native_part.py','audit_native_limb_shading.py'):
        src=Path(__file__).with_name(name);dest=output/'helpers'/name;shutil.copyfile(src,dest);frozen[str(src)]=c.sha(src);snapshots[str(src)]=file_row(dest)
    for p,h in frozen.items():pin(p,h)
    receipt={'schemaVersion':1,'kind':KIND,**c.binding(ctx['targetPath'],ctx['target'],ctx['space']),'part':ctx['part'],'model':ctx['model'],
             'statureApplications':ctx['stage']['statureApplications'],'policy':POLICY,'derivationApplications':1,'configuration':file_row(config_path),
             'sourceAuditConfiguration':cfg['sourceAuditConfiguration'],'originalCompilerReceipt':file_row(ctx['compilePath']),
             'originalCompiledNative':file_row(ctx['nativePath']),'originalCompiledNativeCopy':file_row(original_copy),
             'nativeModel':file_row(native_path),'stageReceipt':file_row(ctx['stagePath']),'compositionReceipt':file_row(ctx['compositionPath']),
             'installedShaderSupplement':cfg['installedShaderSupplement'],'meshes':rows,'materialResourceHashes':material_rows,
             'eligibleTangentByteCount':int(allowed.sum()),'changedByteCount':int((np.frombuffer(original,'u1')!=np.frombuffer(derived,'u1')).sum()),
             'allNonEligibleTangentAndNonTBytesExact':True,'originalCompileReceiptRewritten':False,'nativeCompilerExecuted':False,
             'sourcePNUTMapsChanged':False,'nativeTangentXYZExplicitlyDerived':True,'fixedClothUnchanged':True,
             'diagnosticOnly':True,'selected':False,'clientAccepted':False,'productionAccepted':False,'frozenInputs':frozen,'helperSnapshots':snapshots}
    path=output/'derivation.json';path.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8');return path


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    path=derive(args.config,args.output);print(json.dumps({'receipt':str(path),'sha256':c.sha(path)}))

