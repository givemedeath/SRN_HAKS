"""Source-bound, unaccepted35mm pelvis cuff shortening; no rig/fit/runtime changes."""
import argparse,copy,json,shutil
from pathlib import Path
import numpy as np
import target_contract as tc
from place_purposebuilt_pelvis import BASIS,accessor,embedded_maps,read_glb,write_glb
from conservative_face_selection import topology
KIND='target-part-diagnostic-pelvis-terminal-geometry'
OPERATION='same-topology-local-positive-axial-shortening'
COUNTS=(13049,722,722,29397,3567,3645)
TOPOLOGY_KEYS=('referencedSerializedVertices','exactPositionVertices','faces','boundaryEdges','nonmanifoldEdges','inconsistentManifoldEdgeWindings','zeroAreaFaces','nonmanifoldVertexLinks','components','eulerCharacteristic')

def field(p):
    p=np.asarray(p,float);tc.require(p.ndim==2 and p.shape[1]==3 and np.isfinite(p).all(),'Finite world positions required')
    z,x=p[:,2],p[:,0];tz=np.clip((z-.910)/.075,0,1);tx=np.clip((abs(x)-.020)/.040,0,1)
    s=lambda t:t*t*t*(10+t*(-15+6*t));g=lambda t:30*t*t*(t-1)**2
    w=np.where(z<=.910,1.,np.where(z>=.985,0.,1-s(tz)));chi=np.where(abs(x)<=.020,0.,np.where(abs(x)>=.060,1.,s(tx)))
    wz=np.where((z>.910)&(z<.985),-g(tz)/.075,0.);cx=np.where((abs(x)>.020)&(abs(x)<.060),g(tx)*np.sign(x)/.040,0.)
    value=w*chi;grad=np.column_stack([w*cx,np.zeros(len(p)),chi*wz]);J=np.broadcast_to(np.eye(3),(len(p),3,3)).copy();J[:,2,:]+=.035*grad
    tc.require(np.all(np.linalg.det(J)>=.125-1e-12),'Positive monotone Jacobian violated');return value,J

def move(p):
    q=np.asarray(p,float).copy();w,_=field(q);mask=w!=0;q[mask,2]+=.035*w[mask];return q

def transport(p,n,t):
    n=np.asarray(n);t=np.asarray(t);p=np.asarray(p,float);tc.require(n.shape==p.shape and t.shape==(len(p),4),'Matching authored P/N/T')
    tc.require(np.isfinite(n).all() and np.isfinite(t).all(),'Finite shading required');w,J=field(p);affected=w!=0;active=affected&np.any(J!=np.eye(3),axis=(1,2));nn,tt=n.copy(),t.copy()
    if affected.any():tc.require(np.all(np.linalg.norm(n[affected],axis=1)>1e-8) and np.all(np.linalg.norm(t[affected,:3],axis=1)>1e-8) and np.all(abs(t[affected,3])==1),'Degenerate affected authored shading rejected')
    if active.any():
        ns=n[active].astype(float);ts=t[active].astype(float);nl=np.linalg.norm(ns,axis=1);tl=np.linalg.norm(ts[:,:3],axis=1);outn=np.linalg.solve(np.swapaxes(J[active],1,2),ns[...,None])[...,0];outn*= (nl/np.linalg.norm(outn,axis=1))[:,None];unit=outn/nl[:,None]
        outt=np.einsum('nij,nj->ni',J[active],ts[:,:3]);outt-=np.sum(outt*unit,axis=1)[:,None]*unit;l=np.linalg.norm(outt,axis=1);tc.require((l>1e-8).all(),'Degenerate GS tangent rejected');outt*= (tl/l)[:,None];nn[active]=outn;tt[active,:3]=outt
    return nn,tt

def cap_shading(p,faces,uv,oldn,oldt):
    """Generated cap geometry normals/UV tangents, preserving N/T magnitudes/W."""
    p=np.asarray(p,float);uv=np.asarray(uv,float);F=np.asarray(faces);q=p[F];n=np.cross(q[:,1]-q[:,0],q[:,2]-q[:,0]);tc.require((np.linalg.norm(n,axis=1)>2e-15).all(),'Generated cap degenerate triangle rejected');uniq,inv=np.unique(p,axis=0,return_inverse=True);sums=np.zeros((len(uniq),3));np.add.at(sums,inv[F].reshape(-1),np.repeat(n,3,axis=0));directions=sums[inv];directions/=np.linalg.norm(directions,axis=1)[:,None]
    du=uv[F[:,1]]-uv[F[:,0]];dv=uv[F[:,2]]-uv[F[:,0]];det=du[:,0]*dv[:,1]-du[:,1]*dv[:,0];tc.require((abs(det)>1e-14).all(),'Generated cap UV basis degenerate');tan=((q[:,1]-q[:,0])*dv[:,1,None]-(q[:,2]-q[:,0])*du[:,1,None])/det[:,None];tsums=np.zeros_like(sums);np.add.at(tsums,inv[F].reshape(-1),np.repeat(tan*np.linalg.norm(n,axis=1)[:,None],3,axis=0));td=tsums[inv];td-=np.sum(td*directions,axis=1)[:,None]*directions;length=np.linalg.norm(td,axis=1);tc.require((length>1e-8).all(),'Generated cap tangent degenerate');nl=np.linalg.norm(oldn,axis=1);tl=np.linalg.norm(oldt[:,:3],axis=1);tc.require((nl>1e-8).all() and (tl>1e-8).all() and (abs(oldt[:,3])==1).all(),'Generated ancestor N/T/W invalid');nn=directions*nl[:,None];tt=oldt.copy();tt[:,:3]=td*(tl/length)[:,None];return nn,tt

def append(doc,blob,groups):
    result=copy.deepcopy(doc);payload=bytearray(blob)
    for primids,values in groups:
        for semantic,v in values.items():
            v=np.asarray(v,dtype='<f4');tc.require(np.isfinite(v).all(),'Serialization overflow');payload.extend(b'\0'*(-len(payload)%4));start=len(payload);payload.extend(v.tobytes());result['bufferViews'].append({'buffer':0,'byteOffset':start,'byteLength':v.nbytes});a={'bufferView':len(result['bufferViews'])-1,'componentType':5126,'count':len(v),'type':'VEC'+str(v.shape[1])}
            if semantic=='POSITION':a.update(min=v.min(0).astype(float).tolist(),max=v.max(0).astype(float).tolist())
            result['accessors'].append(a)
            for i in primids:result['meshes'][0]['primitives'][i]['attributes'][semantic]=len(result['accessors'])-1
    result['buffers'][0]['byteLength']=len(payload);return result,bytes(payload)

def shared_active_rows(doc,blob,primitive):
    attrs=primitive['attributes'];key=tuple(attrs[s] for s in ['POSITION','NORMAL','TANGENT']);active=np.zeros(len(accessor(doc,blob,attrs['POSITION'])),bool)
    for item in doc['meshes'][0]['primitives']:
        if tuple(item['attributes'][s] for s in ['POSITION','NORMAL','TANGENT'])==key:active[np.unique(accessor(doc,blob,item['indices']))]=True
    return active

def validate_approval(a,c):
    tc.require(a.get('kind')=='root-approved-pelvis-local-shortening35-diagnostic' and a.get('reviewedBy')=='/root' and a.get('authorizeImplementationAndOneFreshExport') is True and a.get('configuration')==c,'Exact executed root approval required')
    exact={'part':'pelvis','coordinateSpace':'working','liftMetres':.035,'zFullMetres':.910,'zZeroMetres':.985,'centralProtectedHalfWidthMetres':.020,'lateralFullHalfWidthMetres':.060,'statureApplications':0,'capRoundMetres':0.}
    tc.require(all(c.get(k)==v for k,v in exact.items()),'Exact35mm shortening recipe only');tc.require(a.get('capRoundAuthorizedByThisReceipt') is False,'No unreviewed dome')

def execute(approval_path,output):
    ap=Path(approval_path).resolve();a=json.loads(ap.read_text(encoding='utf-8-sig'));pins={};snapshots={}
    def pin(p,h=None):
        p=Path(p).resolve();s=tc.sha(p);tc.require(h is None or h==s,'Exact input changed '+str(p));pins[str(p)]=s;return p
    proposal=pin(a['proposal']['path'],a['proposal']['sha256']);c=json.loads(proposal.read_text());validate_approval(a,c);pin(ap);output=Path(output).resolve();tc.require(not output.exists(),'Fresh immutable export required')
    rp=pin(c['parentReceipt']['path'],c['parentReceipt']['sha256']);r=json.loads(rp.read_text());source=pin(c['parentCandidate']['path'],c['parentCandidate']['sha256']);tc.require(r['candidate']==str(source) and r['candidateSha256']==c['parentCandidate']['sha256'],'Parent geometry closure');tp=pin(c['targetContract'],c['targetContractSha256']);target=tc.load(tp);tc.verify_binding(r,tp,target,'working');tc.require(r['kind']=='target-part-diagnostic-uv-basis-material-geometry' and r['statureApplications']==0,'Exact reviewed material-cut parent only');H=np.asarray(r['attachmentWorld']);tc.require(np.array_equal(H,c['attachmentWorld']) and np.array_equal(H[:3,:3],np.eye(3)),'Frozen pelvis working frame required')
    for p,h in r['frozenInputs'].items():pin(p,h)
    for k in ['bodyFloat64DerivedCornerArchive','capSerializedFloat32CornerArchive']:pin(r[k]['path'],r[k]['sha256'])
    pin(c['maskEvidence']['path'],c['maskEvidence']['sha256']);pin(c['seamEvidence']['path'],c['seamEvidence']['sha256']);doc,blob=read_glb(source);prims=doc['meshes'][0]['primitives'];tc.require(len(prims)==6 and [p['material'] for p in prims]==[0,1,1,2,0,2],'Declared six-primitive roles only');groups=[];oldPs=[];newPs=[];allFs=[];offset=0;inventory=[];bodynew={};capnew={};used=set()
    with np.load(c['maskEvidence']['path'],allow_pickle=False) as maskarchive:
        for i,p in enumerate(prims):
            F=accessor(doc,blob,p['indices']).reshape(-1,3).astype(np.int64);tc.require(len(F)==COUNTS[i],'Exact parent counts');attrs=p['attributes'];key=tuple(attrs[s] for s in ['POSITION','NORMAL','TANGENT'])
            if key in used:continue
            used.add(key);group=[j for j,x in enumerate(prims) if tuple(x['attributes'][s] for s in ['POSITION','NORMAL','TANGENT'])==key];P=accessor(doc,blob,attrs['POSITION']);N=accessor(doc,blob,attrs['NORMAL']);T=accessor(doc,blob,attrs['TANGENT']);UV=accessor(doc,blob,attrs['TEXCOORD_0']);active=np.zeros(len(P),bool);active[np.unique(np.concatenate([accessor(doc,blob,prims[j]['indices']) for j in group]))]=True
            local=P.astype(float)@BASIS.T;world=local+H[:3,3];w,J=field(world);changed=active&(w!=0);n=N.astype(float)@BASIS.T;t=T.astype(float).copy();t[:,:3]=t[:,:3]@BASIS.T;proposed=move(world);nn,tt=transport(world[active],n[active],t[active]) if i not in [1,2] else cap_shading(proposed,F,UV,n,t)
            rows={'POSITION':P.copy(),'NORMAL':N.copy(),'TANGENT':T.copy()};rows['POSITION'][changed,1]=(local[changed,2]+.035*w[changed]).astype('<f4')
            if i in [1,2]:rows['NORMAL']=(nn@BASIS).astype('<f4');ct=tt.copy();ct[:,:3]=ct[:,:3]@BASIS;rows['TANGENT']=ct.astype('<f4')
            else:
                nr=n.copy();tr=t.copy();nr[active]=nn;tr[active]=tt;shade=changed&np.any(J!=np.eye(3),axis=(1,2));rows['NORMAL'][shade]=(nr[shade]@BASIS).astype('<f4');nt=tr[shade].copy();nt[:,:3]=nt[:,:3]@BASIS;rows['TANGENT'][shade]=nt.astype('<f4')
            for semantic,v in rows.items():tc.require(v[~changed].tobytes()=={'POSITION':P,'NORMAL':N,'TANGENT':T}[semantic][~changed].tobytes(),'Protected P/N/T bytes altered')
            tc.require(rows['POSITION'][:,[0,2]].tobytes()==P[:,[0,2]].tobytes(),'X/Y modified');groups.append((group,rows))
            for j in group:
                f=accessor(doc,blob,prims[j]['indices']).reshape(-1,3).astype(np.int64);jm=active.copy();jm[:]=False;jm[np.unique(f)]=True;tc.require(np.array_equal(np.flatnonzero(jm&(w!=0)),maskarchive[f'p{j}ChangedAccessorRows']),'Approved primitive mask differs');old=local[f];new=(rows['POSITION'].astype(float)@BASIS.T)[f];on=np.cross(old[:,1]-old[:,0],old[:,2]-old[:,0]);gn=np.cross(new[:,1]-new[:,0],new[:,2]-new[:,0]);tc.require((np.linalg.norm(gn,axis=1)>2e-15).all(),'New zero-area face');tc.require((np.linalg.norm(on,axis=1)>2e-15).all(),'Parent zero-area face requires diagnosis')
                if j in [1,2]:
                    tc.require(np.array_equal(old[:,:,:2],new[:,:,:2]) and np.array_equal(on[:,2],gn[:,2]) and (abs(on[:,2])>2e-15).all(),'Cap projected XY graph changed');tc.require(len(np.unique(local[:,:2],axis=0))==len(np.unique(local,axis=0)),'Original cap must be single-valued XY graph');orientation=float(np.min(np.sum(on*gn,axis=1)/(np.linalg.norm(on,axis=1)*np.linalg.norm(gn,axis=1))))
                    capnew[j]={'P':rows['POSITION'],'N':rows['NORMAL'],'T':rows['TANGENT'],'UV':UV,'F':f,'parentP':P,'parentN':N,'parentT':T}
                else:
                    _,jac=field(old.mean(1)+H[:3,3]);expected=np.linalg.solve(np.swapaxes(jac,1,2),on[...,None])[...,0];dot=np.sum(expected*gn,axis=1)/(np.linalg.norm(expected,axis=1)*np.linalg.norm(gn,axis=1));tc.require((dot>0).all(),'True body orientation reversal');orientation=float(dot.min());bodynew[j]={'P':rows['POSITION'],'N':rows['NORMAL'],'T':rows['TANGENT'],'UV':UV,'F':f}
                oldPs.append(P);newPs.append(rows['POSITION']);allFs.append(f+offset);offset+=len(P);inventory.append({'primitive':j,'material':prims[j]['material'],'faces':len(f),'changedRows':int((jm&(w!=0)).sum()),'minimumOrientationDot':orientation,'orientationPolicy':'unchanged-signed-XY-graph' if j in [1,2] else 'centroid-J-inverse-transpose-original-geometric-normal'})
    before=topology(np.concatenate(oldPs),np.concatenate(allFs));after=topology(np.concatenate(newPs),np.concatenate(allFs))
    for key in TOPOLOGY_KEYS:tc.require(before[key]==after[key],'New aggregate topology defect '+key)
    newdoc,newblob=append(doc,blob,groups);output.mkdir(parents=True);candidate=output/'candidate-local.glb';write_glb(candidate,newdoc,newblob)
    # Preserve body original source/barycentric records; derive only current P/N/T.
    with np.load(r['bodyFloat64DerivedCornerArchive']['path'],allow_pickle=False) as ar:body={k:ar[k].copy() for k in ar.files}
    bp=body['positions'].reshape(-1,3);bn=body['normals'].reshape(-1,3);bt=body['tangents'].reshape(-1,4);ww=bp+H[:3,3];newn,newt=transport(ww,bn,bt);body.update(terminalParentPositions=body['positions'].copy(),terminalParentNormals=body['normals'].copy(),terminalParentTangents=body['tangents'].copy());affected=field(ww)[0]!=0;newbp=bp.copy();newbp[affected]=move(ww)[affected]-H[:3,3];body['positions']=newbp.reshape(body['positions'].shape);body['normals']=newn.reshape(body['normals'].shape);body['tangents']=newt.reshape(body['tangents'].shape);bodypath=output/'body-float64-deformed-corners.npz';np.savez_compressed(bodypath,**body)
    with np.load(r['capSerializedFloat32CornerArchive']['path'],allow_pickle=False) as ar:caps={k:ar[k].copy() for k in ar.files}
    for semantic in ['POSITION','NORMAL','TANGENT']:caps['parentGeneratedCap'+semantic]=caps[semantic].copy();caps[semantic]=np.concatenate([capnew[j][{'POSITION':'P','NORMAL':'N','TANGENT':'T'}[semantic]][capnew[j]['F']] for j in [1,2]])
    cappath=output/'generated-cap-deformed-corners.npz';np.savez_compressed(cappath,**caps)
    helpers=[Path(__file__),Path(tc.__file__),Path(__file__).with_name('place_purposebuilt_pelvis.py'),Path(__file__).with_name('conservative_face_selection.py')];(output/'helpers').mkdir()
    for path in helpers:path=pin(path);dest=output/'helpers'/path.name;shutil.copyfile(path,dest);snapshots[str(path)]={'path':str(dest),'sha256':tc.sha(dest)}
    receipt={**tc.binding(tp,target,'working'),'schemaVersion':1,'kind':KIND,'operation':OPERATION,'part':'pelvis','joint':'pelvis_g','model':r['model'],'candidate':str(candidate),'candidateSha256':tc.sha(candidate),'candidateToAttachmentLocal':np.eye(4).tolist(),'fitSourceToAttachmentLocal':r['fitSourceToAttachmentLocal'],'attachmentWorld':r['attachmentWorld'],'statureApplications':0,'parentMaterialGeometryReceipt':{'path':str(rp),'sha256':tc.sha(rp)},'parentCandidate':{'path':str(source),'sha256':tc.sha(source)},'rootApproval':{'path':str(ap),'sha256':tc.sha(ap)},'fieldConfiguration':c,'bodyFloat64DeformedCornerArchive':{'path':str(bodypath),'sha256':tc.sha(bodypath)},'generatedCapDeformedCornerArchive':{'path':str(cappath),'sha256':tc.sha(cappath)},'capShadingPolicy':'area-weighted-generated-geometry-normal-UV-tangent-original-magnitude-W-v1','capXYFootprintAndIndicesUnchanged':True,'capRoundMetres':0.,'primitiveInventory':sorted(inventory,key=lambda x:x['primitive']),'proof':{'beforeTopology':before,'afterTopology':after,'originalBinPrefixExact':True,'protectedPNTBytesExact':True,'indicesUVMapsMaterialsRolesExact':True,'fieldContinuousMinimumDeterminant':.125,'existingCapGraphProjectedTrianglesExact':True},'frozenInputs':pins,'helperSnapshots':snapshots,'diagnosticOnly':True,'canonicalNativeLineage':False,'closedExteriorClaim':False,'geometryAccepted':False,'capOwnershipAccepted':False,'materialAccepted':False,'nativeAccepted':False,'stagingAccepted':False,'clientAccepted':False,'productionAccepted':False,'selectionMade':False,'limits':['Inherited material-cut source topology retained; no full-closed/anatomy/material/client acceptance.','Unchanged projected cap triangulation proves no introduced same-cap projected/self crossings; cap/body neighboring exterior collisions require literal and independent followup.','Generated cap shading is new generated lineage; it is never presented as original anatomy authored N/T.','Main garment/waist aboveZ.985 and centralabsX<=.020 protected; reviewed lower garment hem is changed with skin at exact seams.']};path=output/'diagnostic-terminal-geometry.json';path.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8');verify_receipt(path,tp,target);return path

def verify_receipt(receipt_path,target_path,target,space='working'):
    path=Path(receipt_path).resolve();r=json.loads(path.read_text());tc.require(r['kind']==KIND and r['operation']==OPERATION and space=='working' and r['statureApplications']==0 and r['capRoundMetres']==0 and r['canonicalNativeLineage'] is False,'Exact typed working terminal diagnostic required');tc.verify_binding(r,target_path,target,space)
    for p,h in r['frozenInputs'].items():tc.require(tc.sha(p)==h,'Frozen diagnostic input changed '+p)
    tc.require(tc.sha(r['candidate'])==r['candidateSha256'],'Child pin changed');parent=json.loads(Path(r['parentMaterialGeometryReceipt']['path']).read_text());a=json.loads(Path(r['rootApproval']['path']).read_text());validate_approval(a,r['fieldConfiguration']);old,blob=read_glb(parent['candidate']);new,nb=read_glb(r['candidate']);tc.require(nb[:len(blob)]==blob and embedded_maps(old,blob)==embedded_maps(new,nb),'Original BIN/maps changed');tc.require(old['materials']==new['materials'] and old['nodes']==new['nodes'],'Materials/transform changed');tc.require(len(old['meshes'][0]['primitives'])==len(new['meshes'][0]['primitives'])==6,'Exact six primitives required')
    for i,(p,q) in enumerate(zip(old['meshes'][0]['primitives'],new['meshes'][0]['primitives'])):
        tc.require(p['indices']==q['indices'] and p['material']==q['material'] and p['attributes']['TEXCOORD_0']==q['attributes']['TEXCOORD_0'],'Indices/UV/ownership changed');P=accessor(old,blob,p['attributes']['POSITION']);N=accessor(old,blob,p['attributes']['NORMAL']);T=accessor(old,blob,p['attributes']['TANGENT']);F=accessor(old,blob,p['indices']);active=shared_active_rows(old,blob,p);world=P.astype(float)@BASIS.T+np.asarray(r['attachmentWorld'])[:3,3];w,_=field(world);protected=~(active&(w!=0))
        for sem,v in [('POSITION',P),('NORMAL',N),('TANGENT',T)]:tc.require(accessor(new,nb,q['attributes'][sem])[protected].tobytes()==v[protected].tobytes(),'Protected P/N/T changed')
        tc.require(accessor(new,nb,q['attributes']['POSITION'])[:,[0,2]].tobytes()==P[:,[0,2]].tobytes(),'XY changed');expectedP=P.copy();changed=active&(w!=0);expectedP[changed,1]=(P[changed,1].astype(float)+.035*w[changed]).astype('<f4');tc.require(accessor(new,nb,q['attributes']['POSITION']).tobytes()==expectedP.tobytes(),'Exact approved field mapping changed')
        n=N.astype(float)@BASIS.T;t=T.astype(float).copy();t[:,:3]=t[:,:3]@BASIS.T;expectedN=N.copy();expectedT=T.copy();_,J=field(world)
        if i in [1,2]:
            nn,tt=cap_shading(move(world),F.reshape(-1,3),accessor(old,blob,p['attributes']['TEXCOORD_0']),n,t);expectedN=(nn@BASIS).astype('<f4');tt[:,:3]=tt[:,:3]@BASIS;expectedT=tt.astype('<f4')
        else:
            nn,tt=transport(world[active],n[active],t[active]);nr=n.copy();tr=t.copy();nr[active]=nn;tr[active]=tt;shade=changed&np.any(J!=np.eye(3),axis=(1,2));expectedN[shade]=(nr[shade]@BASIS).astype('<f4');tr[:,:3]=tr[:,:3]@BASIS;expectedT[shade]=tr[shade].astype('<f4')
        tc.require(accessor(new,nb,q['attributes']['NORMAL']).tobytes()==expectedN.tobytes() and accessor(new,nb,q['attributes']['TANGENT']).tobytes()==expectedT.tobytes(),'Exact approved body/generated-cap shading differs')
    for key in ['bodyFloat64DeformedCornerArchive','generatedCapDeformedCornerArchive']:tc.require(tc.sha(r[key]['path'])==r[key]['sha256'],'Deformed archive pin changed')
    return {'receipt':r,'candidate':Path(r['candidate']),'inputs':{**r['frozenInputs'],str(path):tc.sha(path),r['candidate']:r['candidateSha256']},'primitiveInventory':r['primitiveInventory']}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--approval',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();r=execute(a.approval,a.output);print(json.dumps({'receipt':str(r),'sha256':tc.sha(r)}),flush=True)
