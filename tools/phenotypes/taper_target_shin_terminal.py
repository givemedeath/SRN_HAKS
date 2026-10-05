"""Diagnostic shin-only terminal radial taper; never re-fit or re-scale a target.

In the declared frozen ankle/bone frame F(u,v,t)=(s(t)u,s(t)v,t).
Quintic smoothstep reaches1 at+75mm. det J=s*s>0 and unchanged t
proves injectivity. Discrete triangles and authored shading are checked separately.
"""
import argparse,copy,json,shutil
from pathlib import Path
import numpy as np
import target_contract as contract
from conservative_face_selection import topology
from place_purposebuilt_pelvis import BASIS,accessor,embedded_maps,node_matrix,raw_corners,read_glb,write_glb
from target_part_pipeline import pin,verify_source_receipt

APPROVED_FACTORS=(.75,.65,.55)
END=.075

def validate_field(factor,end,origin,basis):
    contract.require(isinstance(factor,(int,float)) and np.isfinite(factor) and factor in APPROVED_FACTORS,'Reviewed distal radial factor must be 0.75, 0.65 or 0.55')
    contract.require(end==END,'Exact +75 mm unchanged upper-calf boundary required')
    origin=np.asarray(origin,float);basis=np.asarray(basis,float)
    contract.require(origin.shape==(3,) and basis.shape==(3,3) and np.isfinite(origin).all() and np.isfinite(basis).all(),'Finite explicit ankle origin and basis required')
    contract.require(np.allclose(basis.T@basis,np.eye(3),atol=1e-12,rtol=0) and abs(np.linalg.det(basis)-1)<1e-12,'Proper orthonormal ankle/bone basis required')
    return origin,basis

def frozen_axis(target,part):
    contract.require(part=='shinl','Bounded first trial owns left shin only')
    shin=contract.frame(target,'lshin_g','working');foot=contract.frame(target,'lfoot_g','working')
    rotation=shin[:3,:3];origin=rotation.T@(foot[:3,3]-shin[:3,3]);axis=rotation.T@(shin[:3,3]-foot[:3,3]);length=np.linalg.norm(axis)
    contract.require(length>1e-8,'Distinct frozen ankle/knee required');axis/=length
    radial=np.array([1.,0,0]);radial-=axis*(radial@axis);contract.require(np.linalg.norm(radial)>1e-8,'Frozen shin X cannot define radial basis');radial/=np.linalg.norm(radial);basis=np.column_stack([radial,np.cross(axis,radial),axis])
    return origin,basis

def field(points,factor,end,origin,basis):
    origin,basis=validate_field(factor,end,origin,basis);points=np.asarray(points,float)
    contract.require(points.ndim==2 and points.shape[1]==3 and np.isfinite(points).all(),'Finite shin-local positions required')
    uvw=(points-origin)@basis;t=uvw[:,2];x=np.clip(t/end,0,1);h=x*x*x*(10+x*(-15+6*x));dh=30*x*x*(1-x)*(1-x)/end
    s=factor+(1-factor)*h;derivative=(1-factor)*dh;inside=t<end;changed=uvw.copy();changed[:,:2]*=s[:,None]
    proposed=changed@basis.T+origin;proposed[~inside]=points[~inside]
    j=np.zeros((len(points),3,3));j[:,0,0]=s;j[:,1,1]=s;j[:,2,2]=1;j[:,0,2]=derivative*uvw[:,0];j[:,1,2]=derivative*uvw[:,1]
    j=basis[None]@j@basis.T[None];j[~inside]=np.eye(3)
    contract.require(np.min(np.linalg.det(j),initial=1.)>=factor*factor-1e-12,'Positive determinant bound violated')
    return proposed,j,inside,uvw,s

def transport(normals,tangents,jacobian,edited):
    normals=np.asarray(normals,float);tangents=np.asarray(tangents,float);jacobian=np.asarray(jacobian,float);edited=np.asarray(edited,bool)
    contract.require(normals.ndim==2 and normals.shape[1]==3 and tangents.shape==(len(normals),4) and jacobian.shape==(len(normals),3,3) and edited.shape==(len(normals),),'Matching finite P/N/T/J support arrays required')
    contract.require(np.isfinite(normals).all() and np.isfinite(tangents).all() and np.isfinite(jacobian).all(),'Nonfinite authored shading rejected')
    nl=np.linalg.norm(normals,axis=1);tl=np.linalg.norm(tangents[:,:3],axis=1)
    contract.require(np.all(nl>1e-8) and np.all(tl>1e-8) and np.all(np.abs(tangents[:,3])==1),'Valid authored directions and tangent W +/-1 required')
    contract.require(np.all(np.linalg.det(jacobian)>0),'Transport requires proper positive Jacobian')
    n=np.einsum('nij,nj->ni',np.linalg.inv(jacobian).transpose(0,2,1),normals);n*= (nl/np.linalg.norm(n,axis=1))[:,None]
    t=tangents.copy();direction=np.einsum('nij,nj->ni',jacobian,t[:,:3]);un=n/nl[:,None];direction-=np.einsum('ij,ij->i',direction,un)[:,None]*un
    contract.require(np.all(np.linalg.norm(direction,axis=1)>1e-8),'Degenerate transported tangent rejected');direction*= (tl/np.linalg.norm(direction,axis=1))[:,None];t[:,:3]=direction;n[~edited]=normals[~edited];t[~edited]=tangents[~edited]
    return n,t

def execute(config_path,output):
    config_path=Path(config_path).resolve();c=json.loads(config_path.read_text());allowed={'schemaVersion','kind','diagnosticOnly','part','coordinateSpace','targetContract','targetContractSha256','rigRevision','source','sourceSha256','sourceReceipt','sourceReceiptSha256','distalRadialFactor','unchangedFromAxialMetres','axisOriginAttachmentLocal','axisBasisColumnsAttachmentLocal','protectedInputs','label','notes'}
    contract.require(set(c)<=allowed and c.get('schemaVersion')==2 and c.get('kind')=='target-shin-terminal-taper' and c.get('diagnosticOnly') is True,'Explicit bounded diagnostic shin taper configuration required')
    contract.require(c.get('part')=='shinl' and c.get('coordinateSpace')=='working','Left shin working space before runtime stature required')
    tp=pin(c['targetContract'],c['targetContractSha256']);target=contract.load(tp);contract.require(target['rig']['revision']==c['rigRevision'],'Explicit frozen rig revision differs');identity=target['identity'];contract.require(identity.get('prefix')=='pmg0' and identity.get('race')=='troll' and identity.get('gender')=='male','Troll male target ownership required')
    source=pin(c['source'],c['sourceSha256']);parent_path=pin(c['sourceReceipt'],c['sourceReceiptSha256']);parent=verify_source_receipt(source,parent_path,tp,target,'shinl','working');contract.require(parent['operation']=='fit','One untreated fitted shin parent required; cumulative taper rejected')
    factor=c['distalRadialFactor'];end=c['unchangedFromAxialMetres'];origin,basis=validate_field(factor,end,c['axisOriginAttachmentLocal'],c['axisBasisColumnsAttachmentLocal']);actual_origin,actual_basis=frozen_axis(target,'shinl');contract.require(np.array_equal(origin,actual_origin) and np.array_equal(basis,actual_basis),'Declared frozen ankle/bone frame differs')
    pins={}
    def add(path,expected):
        p=Path(path).resolve();key=str(p);contract.require(key not in pins or pins[key]==expected,'Conflicting provenance pin');contract.require(contract.sha(p)==expected,'Frozen taper input changed: '+key);pins[key]=expected
    for path,expected in parent['frozenInputs'].items():add(path,expected)
    for path,expected in c['protectedInputs'].items():add(path,expected)
    for path,expected in [(source,c['sourceSha256']),(parent_path,c['sourceReceiptSha256']),(tp,c['targetContractSha256']),(config_path,contract.sha(config_path)),(parent['nativeCornerArchive']['path'],parent['nativeCornerArchive']['sha256'])]:add(path,expected)
    helper_names=('taper_target_shin_terminal.py','target_part_pipeline.py','target_contract.py','conservative_face_selection.py','place_purposebuilt_pelvis.py','mirror_stock_limb_part.py','retarget.py')
    for name in helper_names:
        p=Path(__file__).with_name(name).resolve();add(p,contract.sha(p))
    doc,blob=read_glb(source);contract.require(doc['nodes']==[{'name':'detached_geometry','mesh':0}] and doc['scenes']==[{'nodes':[0]}] and not doc.get('skins') and not doc.get('animations'),'Exact static identity-node fitted source required');contract.require(len(doc['meshes'])==1 and len(doc['meshes'][0]['primitives'])==1,'One original shin primitive required');primitive=doc['meshes'][0]['primitives'][0];attrs=primitive['attributes'];contract.require(set(attrs) in ({'POSITION','NORMAL','TEXCOORD_0','TANGENT'},{'POSITION','NORMAL','TEXCOORD_0','TANGENT','COLOR_0'}),'Original P/N/UV/T required');contract.require(primitive.get('mode',4)==4 and not primitive.get('targets') and not primitive.get('extensions'),'Static uncompressed triangles only')
    rows={k:accessor(doc,blob,attrs[k]) for k in ['POSITION','NORMAL','TEXCOORD_0','TANGENT']};faces=accessor(doc,blob,primitive['indices']).reshape(-1,3).astype(np.int64);contract.require(all(v.dtype==np.dtype('<f4') and len(v)==len(rows['POSITION']) and np.isfinite(v).all() for v in rows.values()),'Finite original float32 rows required');contract.require(rows['POSITION'].shape[1:]==(3,) and rows['NORMAL'].shape[1:]==(3,) and rows['TEXCOORD_0'].shape[1:]==(2,) and rows['TANGENT'].shape[1:]==(4,) and len(faces)>0 and faces.min()>=0 and faces.max()<len(rows['POSITION']),'Valid exhaustive vertex/triangle attribute correspondence required');active=np.zeros(len(rows['POSITION']),bool);active[np.unique(faces)]=True
    local=rows['POSITION'].astype(float)@BASIS.T;nlocal=rows['NORMAL'].astype(float)@BASIS.T;tlocal=rows['TANGENT'].astype(float);tlocal[:,:3]=tlocal[:,:3]@BASIS.T;proposed,j,scope,coords,s=field(local,factor,end,origin,basis);edited=scope&active;proposed[~edited]=local[~edited];j[~edited]=np.eye(3);newn,newt=transport(nlocal,tlocal,j,edited)
    newrows={k:rows[k].copy() for k in ['POSITION','NORMAL','TANGENT']};newrows['POSITION'][edited]=(proposed[edited]@BASIS).astype('<f4');newrows['NORMAL'][edited]=(newn[edited]@BASIS).astype('<f4');rawt=newt.copy();rawt[:,:3]=rawt[:,:3]@BASIS;newrows['TANGENT'][edited]=rawt[edited].astype('<f4')
    changed=copy.deepcopy(doc);payload=bytearray(blob)
    for semantic,values in newrows.items():
        payload.extend(b'\0'*(-len(payload)%4));start=len(payload);payload.extend(values.tobytes());payload.extend(b'\0'*(-len(payload)%4));changed['bufferViews'].append({'buffer':0,'byteOffset':start,'byteLength':values.nbytes});item={'bufferView':len(changed['bufferViews'])-1,'componentType':5126,'count':len(values),'type':'VEC'+str(values.shape[1])}
        if semantic=='POSITION':item.update(min=values.min(0).astype(float).tolist(),max=values.max(0).astype(float).tolist())
        changed['accessors'].append(item);changed['meshes'][0]['primitives'][0]['attributes'][semantic]=len(changed['accessors'])-1
    changed['buffers'][0]['byteLength']=len(payload);before=topology(rows['POSITION'],faces);after=topology(newrows['POSITION'],faces)
    for key in ['boundaryEdges','nonmanifoldEdges','nonmanifoldVertexLinks','inconsistentManifoldEdgeWindings','zeroAreaFaces','components']:contract.require(before[key]==after[key] and (before[key]==0 or key=='components' and before[key]==1),'Serialized discrete taper changes clean source topology: '+key)
    oldtri=local[faces];newtri=(newrows['POSITION'].astype(float)@BASIS.T)[faces];oldcross=np.cross(oldtri[:,1]-oldtri[:,0],oldtri[:,2]-oldtri[:,0]);newcross=np.cross(newtri[:,1]-newtri[:,0],newtri[:,2]-newtri[:,0]);dots=np.einsum('ij,ij->i',oldcross,newcross)/(np.linalg.norm(oldcross,axis=1)*np.linalg.norm(newcross,axis=1));contract.require(np.all(dots>0),'Serialized chord-face inversion despite continuous proper field')
    with np.load(parent['nativeCornerArchive']['path'],allow_pickle=False) as a:archive={k:a[k].copy() for k in a.files}
    contract.require(archive['positions'].shape==oldtri.shape and np.array_equal(archive['sourceTriangleIds'],np.arange(len(faces))) and np.array_equal(archive['sourceCornerOrder'],np.tile([0,1,2],(len(faces),1))),'Exhaustive parent face/corner association required');contract.require(archive['normals'].shape==oldtri.shape and archive['tangents'].shape==(len(faces),3,4) and np.array_equal(archive['uvGltf'],rows['TEXCOORD_0'][faces]) and np.max(abs(archive['positions']-oldtri))<=parent['proof']['maximumPositionFloat32ErrorMetres']+1e-15 and np.max(abs(archive['normals']-nlocal[faces]))<=parent['proof']['maximumNormalFloat32Error']+1e-15,'Original serialized/authoritative parent correspondence differs from frozen measured precision');corner_mask=edited[faces].reshape(-1);ap=archive['positions'].reshape(-1,3);an=archive['normals'].reshape(-1,3);at=archive['tangents'].reshape(-1,4);cp,cj,_,_,_=field(ap,factor,end,origin,basis);cp[~corner_mask]=ap[~corner_mask];cj[~corner_mask]=np.eye(3);cn,ct=transport(an,at,cj,corner_mask);archive['positions']=cp.reshape(oldtri.shape);archive['normals']=cn.reshape(oldtri.shape);archive['tangents']=ct.reshape(len(faces),3,4)
    archive.update(taperEditedSourceVertexMask=edited,taperParentSourceFaces=faces,taperJacobianAttachmentLocal=j,taperParentRawPositions=rows['POSITION'],taperParentRawNormals=rows['NORMAL'],taperParentRawTangents=rows['TANGENT'],taperAxialCoordinates=coords[:,2],taperRadialScales=s)
    output=Path(output).resolve();contract.require(not output.exists(),'Fresh immutable taper output required');output.mkdir(parents=True);candidate=output/'candidate-local.glb';write_glb(candidate,changed,bytes(payload));corners=output/'native-corners.npz';np.savez_compressed(corners,**archive);actual,actual_blob=read_glb(candidate);actual_positions,actual_normals,uv,_=raw_corners(actual,actual_blob);contract.require(actual_blob[:len(blob)]==blob and embedded_maps(actual,actual_blob)==embedded_maps(doc,blob) and actual['materials']==doc['materials'],'Original BIN/maps/material changed');contract.require(np.array_equal(uv,archive['uvGltf']),'UV/order changed')
    for semantic,values in newrows.items():contract.require(values[~edited].tobytes()==rows[semantic][~edited].tobytes(),'Outside-support P/N/T bytes changed')
    snapshots={};(output/'tools').mkdir()
    for name in helper_names:
        p=Path(__file__).with_name(name).resolve();dest=output/'tools'/name;shutil.copy2(p,dest);snapshots[str(p)]={'snapshot':str(dest),'sha256':contract.sha(dest)}
    shutil.copy2(config_path,output/'config.json');proof={'globalDeterminantLowerBound':factor**2,'actualMinimumJacobianDeterminant':float(np.linalg.det(j).min()),'injectivity':'Unchanged axial t and positive radial s(t) uniquely preserve every axial plane; detJ=s(t)^2.','supportEndsAtAxialMetres':end,'editedActiveVertices':int(edited.sum()),'unchangedVertices':int((~edited).sum()),'affectedOriginalFaces':int(np.count_nonzero(np.any(edited[faces],axis=1))),'maximumDisplacementMetres':float(np.linalg.norm(proposed-local,axis=1).max()),'outsideSupportSerializedPositionNormalTangentBytesExact':True,'outsideSupportAuthoritativeParentCornersExact':True,'originalUVIndicesMaterialsMapBytesExact':True,'sourceBINPrefixExact':True,'normalPolicy':'Inverse transpose Jacobian, rescaled only to original authored magnitude; no regeneration.','tangentPolicy':'Jacobian tangent followed by normal-plane orthogonalization and original tangent magnitude; W unchanged for positive determinant.','maximumAuthoredNormalMagnitudeError':float(np.abs(np.linalg.norm(newn,axis=1)-np.linalg.norm(nlocal,axis=1)).max()),'maximumEditedNormalTangentDot':float(np.abs(np.einsum('ij,ij->i',newn[edited],newt[edited,:3])).max()),'minimumDiscreteFaceNormalDot':float(dots.min()),'beforeTopology':before,'afterTopology':after,'maximumSerializedPositionVsAuthoritativeCornerErrorMetres':float(abs(actual_positions-archive['positions']).max()),'maximumSerializedNormalVsAuthoritativeCornerError':float(abs(actual_normals-archive['normals']).max()),'normalFace26291Policy':'Original authored opposition is transported, not corrected or waived.'}
    receipt={'schemaVersion':2,'kind':'target-part-geometry','operation':'bounded-shin-terminal-radial-taper',**contract.binding(tp,target,'working'),'part':'shinl','joint':'lshin_g','model':contract.model(target,'shinl'),'source':str(source),'sourceSha256':parent['candidateSha256'],'sourceReceipt':str(parent_path),'sourceReceiptSha256':contract.sha(parent_path),'candidate':str(candidate),'candidateSha256':contract.sha(candidate),'nativeCornerArchive':{'path':str(corners),'sha256':contract.sha(corners)},'attachmentWorld':parent['attachmentWorld'],'sourceToAttachmentLocal':np.eye(4).tolist(),'statureApplications':0,'nonlinearField':c,'frozenInputs':pins,'helperSnapshots':snapshots,'proof':proof,'diagnosticOnly':True,'rigStructureAcceptedOnly':target['rig']['pilotAccepted'],'anatomyAccepted':False,'topologyAccepted':False,'capOwnershipAccepted':False,'connectorAccepted':False,'materialAccepted':False,'collisionAccepted':False,'soleContactAccepted':False,'clientAccepted':False,'productionAccepted':False,'selectionMade':False,'limits':['Continuous proper taper and discrete topology do not prove cap concealment/contact, ankle motion or engine behavior.','Untouched foot/rig/upper-calf/current neighbors remain protected; no stature, frame, fit, mirror or cleanup is reapplied.','Source shin cap face26291 authored/geometric opposition remains unresolved and transported.']}
    for path,h in pins.items():contract.require(contract.sha(path)==h,'Frozen taper input changed during execution: '+path)
    rp=output/'geometry.json';rp.write_text(json.dumps(receipt,indent=2)+'\n');return rp

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();rp=execute(args.config,args.output);print(json.dumps({'receipt':str(rp),'sha256':contract.sha(rp)}))
