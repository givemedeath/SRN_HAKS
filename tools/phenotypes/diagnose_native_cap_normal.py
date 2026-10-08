"""Measured three-corner cap-normal exception atop an immutable mesh seam trial.

The source GLB and all original BIN/accessors/maps remain archived unchanged.
A diagnostic descendant appends three duplicated cap records, one replacement
index accessor and an explicit original-face map. Native staging stays separate.
"""
import argparse
import copy
import json
from pathlib import Path
import re
import shutil

import numpy as np

import target_contract as c
from audit_native_limb_shading import validate_transport
from audit_target_native_part import decode,tangent_proof,audit_material_resources
from diagnose_native_tangent_seam import face_groups,write_split_ascii,inspect_split_ascii,save
from place_purposebuilt_pelvis import BASIS,accessor,embedded_maps,read_glb,raw_corners,write_glb
from stage_stock_part import geometry
from target_part_pipeline import pin
from target_part_stage import material_inputs


def oriented_closed_surface(p):
    points,ids=np.unique(p.reshape(-1,3),axis=0,return_inverse=True);ids=ids.reshape(-1,3)
    edges=np.stack([ids,ids[:,[1,2,0]]],axis=2).reshape(-1,2)
    _,ei,count=np.unique(np.sort(edges,axis=1),axis=0,return_inverse=True,return_counts=True)
    signed=np.bincount(ei,weights=np.where(edges[:,0]<edges[:,1],1,-1))
    proof=geometry(p);proof['incoherentDirectedEdges']=int((signed!=0).sum())
    c.require((count==2).all() and not signed.any() and proof['degenerateTriangles']==0
              and proof['coincidentTriangles']==0 and proof['signedVolume']>0,
              'Closed coherently outward-wound nondegenerate source required')
    return proof


def cap_exception(p,n,uv,t,face):
    c.require(type(face) is int and 0<=face<len(p),'Explicit valid isolated source face required')
    c.require(t.shape==(len(p),3,4) and np.isfinite(t).all() and np.isin(t[:,:,3],[-1,1]).all(),'Complete original authored tangents required')
    topology=oriented_closed_surface(p)
    dp1,dp2=p[face,1]-p[face,0],p[face,2]-p[face,0];cross=np.cross(dp1,dp2)
    normal=cross/np.linalg.norm(cross)
    projected=t[face,:,:3]-np.einsum('ci,i->c',t[face,:,:3],normal)[:,None]*normal
    lengths=np.linalg.norm(projected,axis=1);c.require(lengths.min()>1e-8,'Authored tangent projection collapsed')
    projected/=lengths[:,None];d1,d2=uv[face,1]-uv[face,0],uv[face,2]-uv[face,0];det=d1[0]*d2[1]-d1[1]*d2[0]
    c.require(abs(det)>1e-12,'Declared cap UV derivative degenerate')
    td=(dp1*d2[1]-dp2*d1[1])/det;bd=(dp2*d1[0]-dp1*d2[0])/det
    h=np.einsum('ci,i->c',np.cross(normal,projected),bd);c.require((abs(h)>1e-8).all(),'Ambiguous independently derived cap handedness')
    hand=np.sign(h);nc=np.broadcast_to(normal,(3,3)).astype('f4').astype(float)
    tc=np.c_[projected,hand].astype('f4').astype(float)
    corrected_n=n.copy();corrected_t=t.copy();corrected_n[face]=nc;corrected_t[face]=tc
    angles=np.degrees(np.arccos(np.clip(n[face]@normal/np.linalg.norm(n[face],axis=1),-1,1)))
    proof={'sourceFaceId':face,'geometricNormalDouble':normal.tolist(),'serializedNormalFloat32':nc.tolist(),
           'oldAuthoredNormals':n[face].tolist(),'normalChangeAngleDegrees':angles.tolist(),
           'oldAuthoredTangents':t[face].tolist(),'serializedProjectedTangentsFloat32':tc.tolist(),
           'rawUvDeterminant':float(det),'nativeExpectedWAfterVFlip':(-hand).tolist(),
           'projectedTangentVersusRawUvDerivativeCosines':(projected@td/np.linalg.norm(td)).tolist(),
           'derivedBitangentVersusRawUvDerivativeCosines':(np.einsum('ci,i->c',np.cross(normal,projected)*hand[:,None],bd)/np.linalg.norm(bd)).tolist(),
           'areaMm2':float(np.linalg.norm(cross)*.5e6),'maximumEdgeMm':float(max(np.linalg.norm(p[face,(i+1)%3]-p[face,i]) for i in range(3))*1000),
           'normalsChangedCorners':int(np.any(corrected_n!=n,axis=2).sum()),
           'authoredTangentsChangedCorners':int(np.any(corrected_t!=t,axis=2).sum()),
           'closedDirectedTopology':topology,'normalPolicy':'Exact declared geometric face normal, only three duplicated corners; no neighbor average',
           'tangentPolicy':'Original XYZ projected/normalized against declared geometric normal; W independently derived from exact raw UV derivatives; float32 serialization explicit'}
    return corrected_n,corrected_t,proof


def descendant(doc,binary,face):
    c.require(doc.get('nodes')==[{'name':'detached_geometry','mesh':0}] and len(doc['meshes'])==1
              and len(doc['meshes'][0]['primitives'])==1,'Canonical single primitive detached parent required')
    prim=doc['meshes'][0]['primitives'][0];attr=prim['attributes'];c.require(set(attr)=={'POSITION','NORMAL','TEXCOORD_0','TANGENT'},'Explicit P/N/UV/T-only parent required')
    extra={};p,n,uv,_=raw_corners(doc,binary,extra=extra);t=np.concatenate(extra['TANGENT']['rows']);cn,ct,proof=cap_exception(p,n,uv,t,face);groups=face_groups(len(p),[face]);ids=accessor(doc,binary,prim['indices']).reshape(-1,3)
    result=copy.deepcopy(doc);output=bytearray(binary)
    def append(rows,component=5126):
        a=np.asarray(rows,dtype='<f4' if component==5126 else '<u4');width=a.shape[1] if a.ndim==2 else 1
        output.extend(b'\0'*(-len(output)%4));offset=len(output);output.extend(a.tobytes());output.extend(b'\0'*(-len(output)%4))
        result['bufferViews'].append({'buffer':0,'byteOffset':offset,'byteLength':a.nbytes});result['accessors'].append({'bufferView':len(result['bufferViews'])-1,'componentType':component,'count':len(a),'type':{1:'SCALAR',2:'VEC2',3:'VEC3',4:'VEC4'}[width]})
        return len(result['accessors'])-1
    main=copy.deepcopy(prim);main['indices']=append(ids[groups[0]].reshape(-1),5125)
    cap=copy.deepcopy(prim);cap['indices']=append(np.arange(3,dtype='u4'),5125);cap['attributes']={
        'POSITION':append(accessor(doc,binary,attr['POSITION'])[ids[face]]),
        'NORMAL':append(cn[face]@BASIS),'TEXCOORD_0':append(accessor(doc,binary,attr['TEXCOORD_0'])[ids[face]])}
    rt=ct[face].copy();rt[:,:3]=rt[:,:3]@BASIS;cap['attributes']['TANGENT']=append(rt)
    pos=accessor(result,output,cap['attributes']['POSITION']);result['accessors'][cap['attributes']['POSITION']].update(min=pos.min(0).tolist(),max=pos.max(0).tolist())
    result['meshes'][0]['primitives']=[main,cap];result['buffers'][0]['byteLength']=len(output);order=np.concatenate(groups)
    validate_descendant(doc,binary,result,bytes(output),face)
    return result,bytes(output),p,cn,uv,ct,order,proof


def validate_descendant(parent,binary,child,child_binary,face):
    extra={};p,n,uv,_=raw_corners(parent,binary,extra=extra);t=np.concatenate(extra['TANGENT']['rows']);cn,ct,proof=cap_exception(p,n,uv,t,face);groups=face_groups(len(p),[face]);order=np.concatenate(groups)
    c.require(child_binary[:len(binary)]==binary,'Original BIN prefix changed')
    c.require(child['accessors'][:len(parent['accessors'])]==parent['accessors'] and child['bufferViews'][:len(parent['bufferViews'])]==parent['bufferViews'],'Original attribute/map accessor definitions changed')
    for key in set(parent)|set(child):
        if key not in ('accessors','bufferViews','buffers','meshes'):
            c.require(child.get(key)==parent.get(key),'Original document/material binding changed: '+key)
    c.require(embedded_maps(child,child_binary)==embedded_maps(parent,binary),'Original map bytes changed')
    c.require(len(child['buffers'])==1 and {k:v for k,v in child['buffers'][0].items() if k!='byteLength'}=={k:v for k,v in parent['buffers'][0].items() if k!='byteLength'} and child['buffers'][0]['byteLength']==len(child_binary), 'Derived embedded buffer closure differs')
    c.require(len(child['meshes'])==1 and {k:v for k,v in child['meshes'][0].items() if k!='primitives'}=={k:v for k,v in parent['meshes'][0].items() if k!='primitives'}, 'Derived mesh inventory differs')
    c.require(len(child['accessors'])==len(parent['accessors'])+6 and len(child['bufferViews'])==len(parent['bufferViews'])+6, 'Exactly six explicit appended accessor/view records required')
    prim=parent['meshes'][0]['primitives'][0];cp=child['meshes'][0]['primitives'];c.require(len(cp)==2 and cp[0]['attributes']==prim['attributes'] and all(q.get('material')==prim.get('material') for q in cp),'Derived primitive ownership/material differs')
    ids=accessor(parent,binary,prim['indices']).reshape(-1,3)
    c.require(np.array_equal(accessor(child,child_binary,cp[0]['indices']).reshape(-1,3),ids[groups[0]]) and np.array_equal(accessor(child,child_binary,cp[1]['indices']).reshape(-1),[0,1,2]),'Explicit duplicate/index lineage differs')
    e={};dp,dn,du,recs=raw_corners(child,child_binary,extra=e);dt=np.concatenate(e['TANGENT']['rows'])
    c.require(len(recs)==2 and all(np.array_equal(actual,expected[order]) for actual,expected in [(dp,p),(dn,cn),(du,uv),(dt,ct)]),'Serialized cap descendant differs from declared exception')
    before,after=geometry(p),geometry(dp)
    c.require({k:v for k,v in before.items() if k!='signedVolume'}=={k:v for k,v in after.items() if k!='signedVolume'} and abs(before['signedVolume']-after['signedVolume'])<=1e-15,'Cap repair changed welded geometry/topology')
    return p,cn,uv,ct,order,proof


def validate_plan_owner(plan,parent,target):
    face=plan['sourceFaceId']
    c.require(plan['kind']=='explicit-cap-normal-repair-plan' and plan['targetId']==target['id']
              and plan['part']==parent['part'] and plan['coordinateSpace']=='working'
              and parent['splitFaceIds']==[face], 'Pinned measured plan/seam/target owner differs')
    return face


def prepare(config_path,output):
    config_path=Path(config_path).resolve();cfg=json.loads(config_path.read_text());allowed={'schemaVersion','kind','diagnosticOnly','parentPreparation','parentPreparationSha256','parentAudit','parentAuditSha256','repairPlan','repairPlanSha256'}
    c.require(set(cfg)==allowed and cfg['schemaVersion']==2 and cfg['kind']=='target-native-cap-normal-diagnostic' and cfg['diagnosticOnly'] is True,'Explicit cap-only diagnostic configuration required')
    pp=pin(cfg['parentPreparation'],cfg['parentPreparationSha256']);parent=json.loads(pp.read_text());ap=pin(cfg['parentAudit'],cfg['parentAuditSha256']);pa=json.loads(ap.read_text());plan_path=pin(cfg['repairPlan'],cfg['repairPlanSha256']);plan=json.loads(plan_path.read_text())
    c.require(parent['kind']=='target-native-tangent-seam-preparation' and pa['kind']=='target-native-tangent-seam-audit' and pa['preparation']=={'path':str(pp),'sha256':c.sha(pp)} and pa['positionsNormalsUvExact'] and pa['mapsExact'],'Verified immutable seam parent required')
    for name,h in {**parent['frozenInputs'],**parent['helperSnapshots']}.items():pin(name,h)
    tp=pin(parent['targetContract'],parent['targetContractSha256']);target=c.load(tp);c.verify_binding(parent,tp,target,'working');c.verify_binding(pa,tp,target,'working');c.require(c.rig_mode(target)=='stock-exact','Authoritative stock-exact working basis required')
    face=validate_plan_owner(plan,parent,target)
    for name,h in plan['inputPins'].items():pin(name,h)
    source=pin(parent['source'],parent['sourceSha256']);doc,binary=read_glb(source);nd,nb,p,cn,uv,ct,order,proof=descendant(doc,binary,face)
    c.require(np.array_equal(p[face],plan['originalPositionsMetres']) and np.array_equal(proof['oldAuthoredNormals'],plan['oldAuthoredNormals']) and np.allclose(proof['geometricNormalDouble'],plan['proposedGeometricNormalDouble'],atol=1e-15,rtol=0) and np.allclose(ct[face],np.asarray(plan['proposedProjectedTangentsDouble'],dtype='f4'),atol=0,rtol=0),'Fresh exception differs from measured plan')
    output=Path(output).resolve();c.require(not output.exists(),'Fresh immutable cap diagnostic required');converted=output/'converted';(converted/'ascii').mkdir(parents=True);(converted/'resources').mkdir();candidate=output/'cap-normal-diagnostic.glb';write_glb(candidate,nd,nb)
    # Reload the serialized GLB independently before using any proposed arrays.
    vd,vb=read_glb(candidate);p,cn,uv,ct,order,proof=validate_descendant(doc,binary,vd,vb,face);nu=uv.copy();nu[:,:,1]=1-nu[:,:,1];model=parent['model'];ascii_path=converted/'ascii'/(model+'.mdl');meshes=write_split_ascii(ascii_path,model,p,cn,nu,[face]);old_ascii=pin(parent['asciiModel'],parent['asciiModelSha256'])
    def mainblock(q):return re.search(r'(?ms)^node trimesh '+re.escape(model+'p0')+r'\n.*?^endnode',q.read_text())[0]
    c.require(mainblock(ascii_path)==mainblock(old_ascii),'Protected main mesh ASCII changed')
    for name,h in parent['materialResourceHashes'].items():origin=pin(Path(parent['converted'])/'resources'/name,h);shutil.copyfile(origin,converted/'resources'/name)
    oldextra={};_,oldn,_,_=raw_corners(doc,binary,extra=oldextra);oldt=np.concatenate(oldextra['TANGENT']['rows']);archive=output/'explicit-cap-corner-lineage.npz';np.savez_compressed(archive,originalPositions=p,originalNormals=oldn,originalTangents=oldt,rawUv=uv,nativeUv=nu,correctedNormals=cn,correctedTangents=ct,serializedTriangleToOriginalFace=order,duplicatedSourceVertexIds=accessor(doc,binary,doc['meshes'][0]['primitives'][0]['indices']).reshape(-1,3)[face])
    inputs={str(q):c.sha(q) for q in [config_path,pp,ap,plan_path,source,tp,old_ascii,Path(__file__).resolve()]};inputs.update(parent['frozenInputs']);inputs.update(parent['helperSnapshots']);(output/'helpers').mkdir()
    for name in ['diagnose_native_cap_normal.py','diagnose_native_tangent_seam.py','stage_stock_part.py','audit_target_native_part.py','audit_native_limb_shading.py','audit_geometry.py','target_contract.py','target_part_pipeline.py','place_purposebuilt_pelvis.py','target_part_stage.py','native_compile.py','pipeline.py']:
        origin=Path(__file__).with_name(name);inputs[str(origin.resolve())]=c.sha(origin);shutil.copyfile(origin,output/'helpers'/name)
    snapshots={str(q):c.sha(q) for q in (output/'helpers').iterdir()};receipt={'schemaVersion':2,'kind':'target-native-cap-normal-preparation',**c.binding(tp,target,'working'),'part':parent['part'],'model':model,'parentPreparation':{'path':str(pp),'sha256':c.sha(pp)},'parentAudit':{'path':str(ap),'sha256':c.sha(ap)},'repairPlan':{'path':str(plan_path),'sha256':c.sha(plan_path)},'source':str(source),'sourceSha256':c.sha(source),'diagnosticCandidate':str(candidate),'diagnosticCandidateSha256':c.sha(candidate),'sourceReceipt':parent['sourceReceipt'],'sourceReceiptSha256':parent['sourceReceiptSha256'],'stageReceipt':parent['stageReceipt'],'stageReceiptSha256':parent['stageReceiptSha256'],'client':parent['client'],'clientSha256':parent['clientSha256'],'converted':str(converted),'asciiModel':str(ascii_path),'asciiModelSha256':c.sha(ascii_path),'materialResourceHashes':parent['materialResourceHashes'],'meshes':meshes,'sourceFaceId':face,'explicitCornerException':proof,'cornerLineage':{'path':str(archive),'sha256':c.sha(archive)},'originalBinPrefixExact':True,'originalAccessorDefinitionsExact':True,'protectedMainAsciiMeshExact':True,'positionsUvMapsEdited':False,'normalTangentsEdited':True,'frozenInputs':inputs,'helperSnapshots':snapshots,'selected':False,'diagnosticOnly':True,'clientAccepted':False,'productionAccepted':False,'limitation':'Only the measured cap corner normal/tangent exception is represented. This distinct diagnostic is not a production geometry/stage receipt; source cap shape, second known defect10913 and fresh direct views/animation/client acceptance remain separate.'}
    native_archive=output/'native-corners.npz'
    np.savez_compressed(native_archive,positions=p[order],normals=cn[order],uvGltf=uv[order],uvNative=nu[order],sourcePositions=p[order],sourceNormals=oldn[order],sourceUVNative=nu[order],authoredTangents=ct[order],sourceAuthoredTangents=oldt[order],primitiveIds=np.r_[np.zeros(len(order)-1,dtype=int),1],originalSourceFaceIds=order)
    geometry_receipt={'schemaVersion':2,'kind':'target-part-geometry','operation':'explicit-cap-normal-corner-exception',**c.binding(tp,target,'working'),'part':parent['part'],'joint':c.PART_JOINTS[parent['part']],'model':model,'sourcePart':parent['part'],'source':str(source),'sourceSha256':c.sha(source),'sourceReceipt':parent['sourceReceipt'],'sourceReceiptSha256':parent['sourceReceiptSha256'],'candidate':str(candidate),'candidateSha256':c.sha(candidate),'nativeCornerArchive':{'path':str(native_archive),'sha256':c.sha(native_archive)},'statureApplications':0,'sourceToAttachmentLocal':np.eye(4).tolist(),'attachmentWorld':c.frame(target,c.PART_JOINTS[parent['part']],'working').tolist(),'reflectionWorld':None,'repairPlan':receipt['repairPlan'],'parentSeamPreparation':receipt['parentPreparation'],'proof':{'explicitCornerException':proof,'originalBinPrefixExact':True,'originalAccessorDefinitionsExact':True,'originalPositionUvMapSamplesExact':True,'allOtherOriginalNormalTangentSamplesExact':True,'originalTriangleOrderMap':order.tolist(),'normalsEdited':True,'authoredTangentsEdited':True,'positionsEdited':False,'uvEdited':False,'mapsEdited':False},'frozenInputs':{**inputs,**snapshots,str(archive):c.sha(archive),str(native_archive):c.sha(native_archive)},'diagnosticOnly':True,'rigMode':c.rig_mode(target),'rigValidated':c.rig_ready(target),'rigPilotAccepted':False,'clientAccepted':False,'productionAccepted':False,'limitation':'Explicit measured three-corner cap normal/tangent exception; no source position/UV/map edit. Complete face order and duplicate lineage are archived. This is unselected, and does not repair physical cap fold or second normal defect10913; direct shading/animation/client acceptance remains open.'}
    geometry_path=output/'geometry.json';save(geometry_path,geometry_receipt);receipt['geometryReceipt']={'path':str(geometry_path),'sha256':c.sha(geometry_path)}
    save(output/'cap-preparation.json',receipt);return output/'cap-preparation.json'


def audit(preparation_path,output):
    preparation_path=Path(preparation_path).resolve();prep=json.loads(preparation_path.read_text());c.require(prep['kind']=='target-native-cap-normal-preparation','Explicit cap diagnostic preparation required');tp=pin(prep['targetContract'],prep['targetContractSha256']);target=c.load(tp);c.verify_binding(prep,tp,target,'working')
    for name,h in {**prep['frozenInputs'],**prep['helperSnapshots']}.items():pin(name,h)
    source=pin(prep['source'],prep['sourceSha256']);candidate=pin(prep['diagnosticCandidate'],prep['diagnosticCandidateSha256']);doc,binary=read_glb(source);nd,nb=read_glb(candidate);p,cn,uv,ct,order,proof=validate_descendant(doc,binary,nd,nb,prep['sourceFaceId']);c.require(proof==prep['explicitCornerException'],'Measured normal/tangent exception changed');nu=uv.copy();nu[:,:,1]=1-nu[:,:,1]
    archive=pin(prep['cornerLineage']['path'],prep['cornerLineage']['sha256']);data=np.load(archive);extra={};_,oldn,_,_=raw_corners(doc,binary,extra=extra);oldt=np.concatenate(extra['TANGENT']['rows']);ids=accessor(doc,binary,doc['meshes'][0]['primitives'][0]['indices']).reshape(-1,3)[prep['sourceFaceId']]
    c.require(all(np.array_equal(data[k],v) for k,v in [('originalPositions',p),('originalNormals',oldn),('originalTangents',oldt),('rawUv',uv),('nativeUv',nu),('correctedNormals',cn),('correctedTangents',ct),('serializedTriangleToOriginalFace',order),('duplicatedSourceVertexIds',ids)]),'Explicit source/descendant corner archive differs')
    ascii_path=pin(prep['asciiModel'],prep['asciiModelSha256']);arows=inspect_split_ascii(ascii_path,prep['model'],p,cn,nu,prep['meshes']);converted=Path(prep['converted']);cp=converted/'native-compile.json';compiled=json.loads(cp.read_text());pin(compiled['client'],prep['clientSha256'])
    c.require(compiled['complete'] and compiled['executionMode']=='compilemodel' and compiled['interactiveClientLaunched'] is False and compiled['clientSha256']==prep['clientSha256'] and compiled['materialResourceHashes']==prep['materialResourceHashes'] and len(compiled['models'])==1,'Matching isolated native compiler/material closure required')
    nativepath=converted/'resources'/(prep['model']+'.mdl');row=compiled['models'][0];c.require(row['name']==nativepath.name and row['sourceSha256']==c.sha(ascii_path) and row['binarySha256']==c.sha(nativepath) and row['bytes']==nativepath.stat().st_size,'Explicit cap native/source association differs')
    actual={q.name:c.sha(q) for q in (converted/'resources').iterdir()};c.require(set(actual)==set(prep['materialResourceHashes'])|{nativepath.name} and all(actual[k]==v for k,v in prep['materialResourceHashes'].items()),'Native cap dependency inventory changed')
    native,root=decode(nativepath.read_bytes(),prep['model'],set(prep['meshes']));pa_path=pin(prep['parentAudit']['path'],prep['parentAudit']['sha256']);pa=json.loads(pa_path.read_text());parent_native=pin(pa['nativeModel']['path'],pa['nativeModel']['sha256']);pnative,_=decode(parent_native.read_bytes(),prep['model'],set(prep['meshes']));main=prep['model']+'p0';c.require(all(np.array_equal(native[main][k],pnative[main][k]) for k in ['position','normal','uv','tangent','sign','faces']),'Protected main native attribute/tangent/index arrays changed')
    sp=pin(prep['stageReceipt'],prep['stageReceiptSha256']);stage=json.loads(sp.read_text());materialrows,_=material_inputs(doc,binary,{int(k):v for k,v in stage['materialRoles'].items()},prep['part'],stage['aoStrength'],c.fixed_garment_parts(target));mp,mfiles=audit_material_resources(converted/'resources',prep['model'],'skin',materialrows['skin'],compiled);meshes={}
    for name,m in prep['meshes'].items():
        fids=np.asarray(m['sourceFaceIds']);a=native[name];corners={k:a[k][a['faces']] for k in ['position','normal','uv']};expected={'position':p[fids],'normal':cn[fids],'uv':nu[fids]};ae,be,ex=validate_transport(expected,arows[name],corners,0);w=a['sign'][a['faces'],0];wrong=np.argwhere(w!=-ct[fids,:,3]);tpv=tangent_proof(a);nt=a['tangent'][a['faces']];cost=np.einsum('tci,tci->tc',nt,ct[fids,:,:3])/(np.linalg.norm(nt,axis=2)*np.linalg.norm(ct[fids,:,:3],axis=2))
        c.require(a['layout']['textureSlots']==[prep['model'],'','',prep['model']] and a['layout']['shadowFlag']==1,'Exact cap native material/renderer binding differs')
        meshes[name]={'triangles':len(fids),'nativeVertices':a['layout']['vertices'],'sourceToAsciiErrors':ae,'sourceToNativeErrors':be,'cornersExactDeclaredFloat32':ex,'nativeTangentProof':tpv,'minimumNativeTangentVsProjectedAuthoredCosine':float(cost.min()),'handednessMismatchCorners':[{'sourceFaceId':int(fids[f]),'corner':int(k),'expectedNativeW':float(-ct[fids[f],k,3]),'actualNativeW':float(w[f,k])} for f,k in wrong]}
    native_verified=all(not m['handednessMismatchCorners'] and all(m['nativeTangentProof']['faceUvDirectionCosinesDiagnosticOnly'][k]['negativeCorners']==0 for k in ['tangent','bitangent']) for m in meshes.values());output=Path(output).resolve();c.require(not output.exists(),'Fresh immutable cap audit required');output.mkdir();shutil.copyfile(__file__,output/'executed-helper.py');inputs={str(q):c.sha(q) for q in [preparation_path,source,candidate,archive,ascii_path,cp,nativepath,pa_path,parent_native,sp,*mfiles,Path(__file__).resolve()]};inputs.update(prep['frozenInputs']);inputs.update(prep['helperSnapshots'])
    receipt={'schemaVersion':2,'kind':'target-native-cap-normal-audit',**c.binding(tp,target,'working'),'part':prep['part'],'preparation':{'path':str(preparation_path),'sha256':c.sha(preparation_path)},'diagnosticCandidate':{'path':str(candidate),'sha256':c.sha(candidate)},'nativeModel':{'path':str(nativepath),'sha256':c.sha(nativepath)},'nativeCompileReceipt':{'path':str(cp),'sha256':c.sha(cp)},'root':root,'meshes':meshes,'explicitCornerException':proof,'materialProof':mp,'frozenInputs':inputs,'positionsUvMapsExact':True,'allOtherOriginalNormalsTangentsExact':True,'protectedMainNativeExact':True,'originalBinAccessorMapBytesExact':True,'closedWeldedTopologyUnchanged':True,'explicitCapNativeTangentVerified':native_verified,'selected':False,'diagnosticOnly':True,'clientAccepted':False,'productionAccepted':False,'knownDefect10913Repaired':False,'limitation':'Normal/tangent transport and compiler isolation only. Face24724 physical fold persists; new cap normals differ149.7deg from neighbors. Fresh location/direct shading views, cap exposure through all motion/equipment and literal-client acceptance remain required; finite ray occlusion is not global hidden-defect acceptance.'}
    save(output/'cap-audit.json',receipt);return output/'cap-audit.json'


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--phase',choices=('prepare','audit'),required=True);parser.add_argument('--input',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();result=prepare(args.input,args.output) if args.phase=='prepare' else audit(args.input,args.output);print(json.dumps({'receipt':str(result),'sha256':c.sha(result)}))
