"""Explicit unchanged-corner mesh seam trial; diagnostic, never a production stage.

One declared face group is isolated in a second identity trimesh with the same
material. Source geometry/maps are read only; every duplicate retains lineage.
Installed compilemodel execution is a separate verified launcher invocation.
"""
import argparse
import json
from pathlib import Path
import re
import shutil
import tempfile

import numpy as np

import target_contract as c
from audit_geometry import arrays
from audit_native_limb_shading import validate_transport
from audit_target_native_part import decode,tangent_proof,audit_material_resources,LAYOUT_PINS
from place_purposebuilt_pelvis import raw_corners,read_glb,accessor
from stage_stock_part import write_ascii,geometry
from target_part_pipeline import pin,read_target,verify_source_receipt
from target_part_stage import material_inputs


def face_groups(count,isolated):
    c.require(isinstance(isolated,list) and isolated and all(type(x) is int for x in isolated)
              and isolated==sorted(set(isolated)) and isolated[0]>=0 and isolated[-1]<count
              and len(isolated)<count,'Explicit unique sorted proper source-face subset required')
    mask=np.ones(count,bool);mask[isolated]=False
    return [np.flatnonzero(mask),np.asarray(isolated,int)]


def write_split_ascii(path,model,p,n,uv,isolated):
    """Same P/N/UV/material on both meshes; mesh-local dedup creates explicit copies."""
    groups=face_groups(len(p),isolated);path=Path(path);c.require(not path.exists(),'Fresh diagnostic ASCII required')
    head=[f'newmodel {model}',f'setsupermodel {model} NULL','classification CHARACTER','setanimationscale 1',
          f'beginmodelgeom {model}',f'node dummy {model}','  parent NULL','endnode']
    meshes={}
    with tempfile.TemporaryDirectory() as tmp:
        for index,faces in enumerate(groups):
            mesh=model+'p'+str(index);scratch=Path(tmp)/'part.mdl';counts=write_ascii(scratch,model,p[faces],uv[faces],n[faces])
            block=re.search(r'(?ms)^node trimesh \S+\n.*?^endnode',scratch.read_text())[0]
            head.append(re.sub(r'^node trimesh \S+',f'node trimesh {mesh}',block));meshes[mesh]={'sourceFaceIds':faces.tolist(),'counts':counts,'material':model}
    head += [f'endmodelgeom {model}',f'donemodel {model}'];path.write_text('\n'.join(head)+'\n',encoding='ascii')
    inspect_split_ascii(path,model,p,n,uv,meshes)
    return meshes


def inspect_split_ascii(path,model,p,n,uv,meshes):
    c.require(len(meshes)==2, 'Exactly two declared diagnostic meshes required')
    text=Path(path).read_text(encoding='ascii');blocks=re.findall(r'(?ms)^node (\S+) (\S+)\n(.*?)^endnode\s*$',text)
    c.require(len(blocks)==len(meshes)+1 and blocks[0][:2]==('dummy',model) and
              re.search(r'(?m)^\s*parent NULL\s*$',blocks[0][2]),'Diagnostic direct ASCII hierarchy differs')
    c.require(re.search(r'(?m)^setsupermodel '+re.escape(model)+r' NULL$',text) and
              re.search(r'(?m)^setanimationscale 1$',text) and 'newanim ' not in text,'Diagnostic isolated header differs')
    rows={};allids=[]
    for kind,name,body in blocks[1:]:
        c.require(kind=='trimesh' and name in meshes and name not in rows,'Diagnostic mesh inventory differs')
        for line in ('parent '+model,'position 0 0 0','orientation 0 0 0 0','bitmap '+model,'materialname '+model,'render 1','shadow 1'):
            c.require(re.search(r'(?m)^\s*'+re.escape(line)+r'\s*$',body),'Diagnostic identity/material binding differs')
        c.require(not re.search(r'(?m)^\s*(scale|positionkey|orientationkey|scalekey)\b',body),'Diagnostic extra transform differs')
        a,b,t,f=[np.asarray(arrays(body,key)) for key in ('verts','normals','tverts','faces')]
        c.require(a.ndim==2 and a.shape[1]==3 and b.shape==a.shape and t.ndim==2 and t.shape[1]==3 and all(np.isfinite(q).all() for q in (a,b,t,f)), 'Finite complete ASCII attributes required')
        c.require(f.ndim==2 and f.shape[1]==8 and np.array_equal(f,f.astype(int)),'Diagnostic face data differs');f=f.astype(int)
        c.require(f.size and f[:,:3].min()>=0 and f[:,:3].max()<len(a) and f[:,4:7].min()>=0 and f[:,4:7].max()<len(t),'Diagnostic attribute indices differ')
        ids=np.asarray(meshes[name]['sourceFaceIds']);c.require(ids.ndim==1 and np.issubdtype(ids.dtype,np.integer) and len(ids)==len(f) and len(ids) and ids.min()>=0 and ids.max()<len(p), 'Explicit valid diagnostic face lineage required');allids.extend(ids.tolist());row={'position':a[f[:,:3]],'normal':b[f[:,:3]],'uv':t[f[:,4:7],:2]}
        c.require(all(np.array_equal(row[key],expected[ids]) for key,expected in [('position',p),('normal',n),('uv',uv)]),'Diagnostic source-corner attributes differ')
        rows[name]=row
    c.require(set(rows)==set(meshes) and sorted(allids)==list(range(len(p))),'Diagnostic complete unique source-face ownership differs')
    return rows


def save(path,value):Path(path).write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')


def prepare(config_path,output):
    config_path=Path(config_path).resolve();cfg=json.loads(config_path.read_text());tp,target=read_target(cfg)
    allowed={'schemaVersion','kind','diagnosticOnly','targetContract','targetContractSha256','part','stageReceipt','stageReceiptSha256','controlNativeAudit','controlNativeAuditSha256','splitFaceIds','client','clientSha256','layoutDirectory'}
    c.require(set(cfg)<=allowed and cfg.get('kind')=='target-native-tangent-seam-diagnostic' and cfg.get('diagnosticOnly') is True,'Explicit seam-only diagnostic config required')
    c.require(c.rig_mode(target)=='stock-exact','Current seam diagnostic uses authoritative stock-exact working frame')
    part=cfg['part'];sp=pin(cfg['stageReceipt'],cfg['stageReceiptSha256']);stage=json.loads(sp.read_text());c.verify_binding(stage,tp,target,'working')
    c.require(stage.get('kind')=='target-part-stage' and stage['part']==part and stage['model']==c.model(target,part) and stage['statureApplications']==0,'Working stage owner differs')
    c.require(set(stage['materialRoles'].values())=={'skin'} and not stage.get('derivedMaterialProof') and stage.get('materialInputBasis') in (None,'original-embedded-maps'),'Current seam control requires untouched single-role skin maps')
    for name,expected in stage['frozenInputs'].items():pin(name,expected)
    source=pin(stage['source'],stage['sourceSha256']);sr=pin(stage['sourceReceipt'],stage['sourceReceiptSha256']);verify_source_receipt(source,sr,tp,target,part,'working')
    controlpath=pin(cfg['controlNativeAudit'],cfg['controlNativeAuditSha256']);control=json.loads(controlpath.read_text());c.verify_binding(control,tp,target,'working')
    c.require(control.get('kind')=='target-native-part-audit' and Path(control['stageReceipt']).resolve()==sp and control['stageReceiptSha256']==c.sha(sp) and control['part']==part and control['model']==c.model(target,part) and control['attributeTransportVerified'] and control['materialTransportVerified'],'Matching verified native control required')
    client=pin(cfg['client'],cfg['clientSha256']);native_receipt=pin(control['nativeReceipt'],control['nativeReceiptSha256']);nr=json.loads(native_receipt.read_text());c.require(nr['clientSha256']==c.sha(client) and nr['complete'],'Installed compiler must match native control')
    layout=[pin(Path(cfg['layoutDirectory'])/name,h) for name,h in LAYOUT_PINS.items()]
    doc,binary=read_glb(source);extra={};p,n,uv,recs=raw_corners(doc,binary,extra=extra);c.require(len(recs)==1 and doc['nodes']==[{'name':'detached_geometry','mesh':0}],'One canonical source mesh required')
    groups=face_groups(len(p),cfg['splitFaceIds']);native_uv=uv.copy();native_uv[:,:,1]=1-native_uv[:,:,1]
    output=Path(output).resolve();c.require(not output.exists(),'Fresh immutable seam trial required');converted=output/'converted';(converted/'ascii').mkdir(parents=True);(converted/'resources').mkdir()
    model=c.model(target,part);ascii_path=converted/'ascii'/(model+'.mdl');meshes=write_split_ascii(ascii_path,model,p,n,native_uv,cfg['splitFaceIds'])
    parent_resources=sp.parent/'resources'
    c.require({path.name:c.sha(path) for path in parent_resources.iterdir()}==stage['materialResourceHashes'],'Original staged material payload changed')
    for path in parent_resources.iterdir():shutil.copyfile(path,converted/'resources'/path.name)
    prim=doc['meshes'][0]['primitives'][0];ids=accessor(doc,binary,prim['indices']).reshape(-1,3);source_t=np.concatenate(extra['TANGENT']['rows'])
    c.require(source_t.shape==(len(p),3,4) and np.isfinite(source_t).all() and np.isin(source_t[:,:,3],[-1,1]).all(), 'Complete authored tangent/sign lineage required')
    archive=output/'source-corner-lineage.npz';np.savez_compressed(archive,positions=p,authoredNormals=n,rawUv=uv,nativeUv=native_uv,authoredTangents=source_t,sourceTriangleVertexIds=ids,mainSourceFaceIds=groups[0],isolatedSourceFaceIds=groups[1])
    tuples=np.concatenate([p,n,native_uv],axis=2);sets=[{tuple(row) for row in tuples[g].reshape(-1,8)} for g in groups]
    inputs={str(path):c.sha(path) for path in [config_path,tp,sp,source,sr,controlpath,native_receipt,client,*layout,Path(__file__)]};inputs.update(stage['frozenInputs'])
    (output/'helpers').mkdir()
    for name in ['diagnose_native_tangent_seam.py','stage_stock_part.py','audit_target_native_part.py','audit_native_limb_shading.py','audit_geometry.py','target_contract.py','target_part_pipeline.py','place_purposebuilt_pelvis.py','target_part_stage.py','native_compile.py','pipeline.py']:
        origin=Path(__file__).with_name(name);inputs[str(origin.resolve())]=c.sha(origin);shutil.copyfile(origin,output/'helpers'/name)
    for name,h in inputs.items():pin(name,h)
    snapshots={str(q):c.sha(q) for q in (output/'helpers').iterdir()}
    receipt={'schemaVersion':2,'kind':'target-native-tangent-seam-preparation',**c.binding(tp,target,'working'),'part':part,'model':model,'stageReceipt':str(sp),'stageReceiptSha256':c.sha(sp),'source':str(source),'sourceSha256':c.sha(source),'sourceReceipt':str(sr),'sourceReceiptSha256':c.sha(sr),'controlNativeAudit':str(controlpath),'controlNativeAuditSha256':c.sha(controlpath),'client':str(client),'clientSha256':c.sha(client),'converted':str(converted),'asciiModel':str(ascii_path),'asciiModelSha256':c.sha(ascii_path),'materialResourceHashes':stage['materialResourceHashes'],'meshes':meshes,'splitFaceIds':cfg['splitFaceIds'],'sourceCornerLineage':{'path':str(archive),'sha256':c.sha(archive)},'duplicateExactPNUvBoundaryTuples':len(sets[0]&sets[1]),'weldedSourceGeometry':geometry(p),'helperSnapshots':snapshots,'frozenInputs':inputs,'diagnosticOnly':True,'selected':False,'geometryPixelsEdited':False,'normalsEdited':False,'uvEdited':False,'mapsEdited':False,'clientAccepted':False,'limitation':'Distinct diagnostic receipt, not a target-part-stage. Same-material direct mesh boundary isolates compiler vertex records; no rendering or hidden-defect acceptance.'}
    path=output/'seam-preparation.json';save(path,receipt);return path


def audit(preparation_path,output):
    preparation_path=Path(preparation_path).resolve();prep=json.loads(preparation_path.read_text());c.require(prep.get('kind')=='target-native-tangent-seam-preparation','Explicit seam preparation required')
    tp=Path(prep['targetContract']);target=c.load(tp);c.verify_binding(prep,tp,target,'working')
    for name,h in prep['frozenInputs'].items():pin(name,h)
    for name,h in prep['helperSnapshots'].items():pin(name,h)
    source=pin(prep['source'],prep['sourceSha256']);sp=pin(prep['stageReceipt'],prep['stageReceiptSha256']);stage=json.loads(sp.read_text());archive=pin(**{'path':prep['sourceCornerLineage']['path'],'expected':prep['sourceCornerLineage']['sha256']});data=np.load(archive)
    doc,binary=read_glb(source);extra={};p,n,uv,recs=raw_corners(doc,binary,extra=extra);nu=uv.copy();nu[:,:,1]=1-nu[:,:,1]
    prim=doc['meshes'][0]['primitives'][0];ids=accessor(doc,binary,prim['indices']).reshape(-1,3);st=np.concatenate(extra['TANGENT']['rows']);groups=face_groups(len(p),prep['splitFaceIds'])
    c.require(all(np.array_equal(data[key],value) for key,value in [('positions',p),('authoredNormals',n),('rawUv',uv),('nativeUv',nu),('authoredTangents',st),('sourceTriangleVertexIds',ids),('mainSourceFaceIds',groups[0]),('isolatedSourceFaceIds',groups[1])]),'Frozen source corner archive differs')
    ascii_path=pin(prep['asciiModel'],prep['asciiModelSha256']);arows=inspect_split_ascii(ascii_path,prep['model'],p,n,nu,prep['meshes']);converted=Path(prep['converted']);npth=converted/'native-compile.json';compiled=json.loads(npth.read_text())
    c.require(compiled.get('complete') is True and compiled.get('executionMode')=='compilemodel' and compiled.get('interactiveClientLaunched') is False and compiled['clientSha256']==prep['clientSha256'],'Matching offline native compiler required');pin(compiled['client'],compiled['clientSha256'])
    c.require(compiled['materialResourceHashes']==prep['materialResourceHashes'] and len(compiled['models'])==1,'Exact material closure/single model required');row=compiled['models'][0];nativepath=converted/'resources'/(prep['model']+'.mdl');c.require(row['name']==nativepath.name and row['sourceSha256']==prep['asciiModelSha256'] and row['binarySha256']==c.sha(nativepath) and row['bytes']==nativepath.stat().st_size,'Native seam source/binary association differs')
    actual={q.name:c.sha(q) for q in (converted/'resources').iterdir()};c.require(set(actual)==set(prep['materialResourceHashes'])|{nativepath.name} and all(actual[k]==v for k,v in prep['materialResourceHashes'].items()),'Seam native inventory/dependencies differ')
    native,root=decode(nativepath.read_bytes(),prep['model'],set(prep['meshes']));proof={};reassembled=np.empty_like(p);materialrows,_=material_inputs(doc,binary,{int(k):v for k,v in stage['materialRoles'].items()},prep['part'],stage['aoStrength'],c.fixed_garment_parts(target));mp,mfiles=audit_material_resources(converted/'resources',prep['model'],'skin',materialrows['skin'],compiled)
    for mesh,m in prep['meshes'].items():
        fids=np.asarray(m['sourceFaceIds']);a=native[mesh];corners={key:a[key][a['faces']] for key in ('position','normal','uv')};expected={'position':p[fids],'normal':n[fids],'uv':nu[fids]};ae,be,exact=validate_transport(expected,arows[mesh],corners,0);reassembled[fids]=corners['position'];nt=a['tangent'][a['faces']];sign=a['sign'][a['faces']];st=data['authoredTangents'][fids];d1,d2=nu[fids,1]-nu[fids,0],nu[fids,2]-nu[fids,0];det=d1[:,0]*d2[:,1]-d1[:,1]*d2[:,0];c.require((abs(det)>1e-12).all(),'Nondegenerate UVs required for this tangent diagnostic');dp1,dp2=p[fids,1]-p[fids,0],p[fids,2]-p[fids,0];bf=(dp2*d1[:,0,None]-dp1*d2[:,0,None])/det[:,None];nb=np.cross(corners['normal'],nt)*sign;cos=np.einsum('tci,tci->tc',nb,bf[:,None,:])/(np.linalg.norm(nb,axis=2)*np.linalg.norm(bf,axis=1)[:,None]);bad=np.argwhere(cos<0);wrong=np.argwhere(sign[:,:,0]!=-st[:,:,3]);slots=a['layout']['textureSlots'];c.require(slots==[prep['model'],'','',prep['model']] and a['layout']['shadowFlag']==1,'Seam material bindings differ')
        proof[mesh]={'triangles':len(fids),'nativeVertices':a['layout']['vertices'],'sourceToAsciiErrors':ae,'sourceToNativeErrors':be,'cornersExactSourceFloat32':exact,'nativeTangentProof':tangent_proof(a),'negativeDerivativeCorners':[{'globalSourceFaceId':int(fids[f]),'corner':int(k),'cosine':float(cos[f,k]),'nativeVertexId':int(a['faces'][f,k])} for f,k in bad],'sourceVFlippedHandednessMismatchCorners':[{'globalSourceFaceId':int(fids[f]),'corner':int(k),'sourceW':float(st[f,k,3]),'nativeW':float(sign[f,k,0])} for f,k in wrong]}
    c.require(np.array_equal(reassembled,p.astype('f4').astype(float)),'Reassembled seam positions changed')
    c.require(geometry(reassembled)==geometry(p), 'Welded topology/geometry differs')
    output=Path(output).resolve();c.require(not output.exists(),'Fresh seam audit required');output.mkdir();shutil.copyfile(__file__,output/'executed-helper.py');inputs={str(q):c.sha(q) for q in [preparation_path,archive,source,sp,ascii_path,npth,nativepath,*mfiles,Path(__file__)]};inputs.update(prep['frozenInputs'])
    inputs.update(prep['helperSnapshots'])
    receipt={'schemaVersion':2,'kind':'target-native-tangent-seam-audit',**c.binding(tp,target,'working'),'part':prep['part'],'preparation':{'path':str(preparation_path),'sha256':c.sha(preparation_path)},'nativeModel':{'path':str(nativepath),'sha256':c.sha(nativepath)},'nativeCompileReceipt':{'path':str(npth),'sha256':c.sha(npth)},'root':root,'meshes':proof,'materialProof':mp,'completeSourceFaceInventoryExact':True,'positionsNormalsUvExact':True,'weldedTopologyUnchanged':True,'weldedSourceGeometry':geometry(p),'weldedNativeGeometry':geometry(reassembled),'mapsExact':True,'frozenInputs':inputs,'nativeCompilerExecutedByAudit':False,'diagnosticOnly':True,'selected':False,'knownAuthoredNormalDefectsRepaired':False,'clientAccepted':False,'productionAccepted':False,'limitation':'Mesh partition alone preserves geometric/UV/normal samples and maps. Residual cap normals, normal-map appearance, seam shading, animations, equipment and literal-client acceptance remain separate.'}
    save(output/'seam-audit.json',receipt);return output/'seam-audit.json'


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--phase',choices=('prepare','audit'),required=True);parser.add_argument('--input',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();result=prepare(args.input,args.output) if args.phase=='prepare' else audit(args.input,args.output);print(json.dumps({'receipt':str(result),'sha256':c.sha(result)}))
