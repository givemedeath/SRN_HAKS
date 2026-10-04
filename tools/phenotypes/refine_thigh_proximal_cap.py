"""Bounded attachment-crown taper, preserving a fitted thigh's muscular shaft.

Only a smooth positive elliptical contraction above the recorded blend start
is allowed. It is a measured cap operation, not a new fit/stock skin projection.
Normals use inverse differential with authored magnitudes; tangents use forward
differential and keep handedness. UV/material/map accessors remain unchanged.
"""
import argparse
import copy
import json
from pathlib import Path
import shutil

import numpy as np

from place_purposebuilt_pelvis import BASIS,accessor,bounds,embedded_maps,node_matrix,raw_corners,read_glb,require,sha,write_glb


def taper_field(points,knots,centre):
    """C1 smoothstep between explicit local-z factors; exact identity belowband."""
    points=np.asarray(points,float)
    knots=np.asarray(knots,float)
    require(knots.ndim==2 and knots.shape[1] in [3,5] and len(knots)>=2,'Knots must be ordered[z,xFactor,yFactor,optionaloffsetX,offsetY]')
    require(np.isfinite(knots).all() and np.all(np.diff(knots[:,0])>0),'Finite strict ascending knots required')
    require(np.all((knots[:,1:3]>.2)&(knots[:,1:3]<=1)),'Only positive bounded local contraction allowed')
    require(np.array_equal(knots[0,1:3],[1,1]),'Lowerband must begin with exactidentity')
    if knots.shape[1]==5:require(np.array_equal(knots[0,3:],[0,0]),'Lowerband offset must begin with exactidentity')
    centre=np.asarray(centre,float)
    require(centre.shape==(2,) and np.isfinite(centre).all(),'Finite local ellipse centreXY required')
    factors=np.ones((len(points),2));slopes=np.zeros_like(factors)
    offsets=np.zeros_like(factors);offset_slopes=np.zeros_like(factors)
    for left,right in zip(knots[:-1],knots[1:]):
        mask=(points[:,2]>=left[0])&(points[:,2]<right[0])
        t=(points[mask,2]-left[0])/(right[0]-left[0]);w=t*t*(3-2*t)
        factors[mask]=left[1:3]+w[:,None]*(right[1:3]-left[1:3])
        slopes[mask]=(6*t*(1-t)/(right[0]-left[0]))[:,None]*(right[1:3]-left[1:3])
        if knots.shape[1]==5:
            offsets[mask]=left[3:]+w[:,None]*(right[3:]-left[3:])
            offset_slopes[mask]=(6*t*(1-t)/(right[0]-left[0]))[:,None]*(right[3:]-left[3:])
    factors[points[:,2]>=knots[-1,0]]=knots[-1,1:3]
    if knots.shape[1]==5:offsets[points[:,2]>=knots[-1,0]]=knots[-1,3:]
    transformed=points.copy();offset=points[:,:2]-centre
    transformed[:,:2]=centre+offset*factors+offsets
    jac=np.tile(np.eye(3),(len(points),1,1))
    jac[:,0,0]=factors[:,0];jac[:,1,1]=factors[:,1]
    jac[:,0,2]=offset[:,0]*slopes[:,0]+offset_slopes[:,0];jac[:,1,2]=offset[:,1]*slopes[:,1]+offset_slopes[:,1]
    return transformed,jac


def directions(normals,jac):
    original=np.asarray(normals,float)
    lengths=np.linalg.norm(original,axis=1)
    require(np.all(lengths>.5),'Valid authored normal magnitudes required')
    # Column normal transforms by J^{-T}; row notation below is equivalent.
    rotated=np.einsum('nij,nj->ni',np.linalg.inv(jac).transpose(0,2,1),original)
    rotated*= (lengths/np.linalg.norm(rotated,axis=1))[:,None]
    identity=np.all(jac==np.eye(3),axis=(1,2));rotated[identity]=original[identity]
    return rotated


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parent-receipt',type=Path,required=True)
    parser.add_argument('--config',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    require(not args.output.exists(),'Fresh descendant required')
    parent_path=args.parent_receipt.resolve();parent=json.loads(parent_path.read_text())
    candidate=Path(parent['candidate']).resolve();archive_path=Path(parent['nativeCornerArchive']['path']).resolve()
    require(sha(candidate)==parent['candidateSha256'] and sha(archive_path)==parent['nativeCornerArchive']['sha256'],'Exact bound parent required')
    config=json.loads(args.config.read_text())
    allowed={'schemaVersion','diagnosticOnly','parentReceiptSha256','parentSourceSha256','parentArchiveSha256','knots','centreXY','protectedBelowZ','maximumMovementMetres','label','measuredProfileEvidence','landmarkNotes'}
    require(not set(config)-allowed and config.get('schemaVersion')==1 and config.get('diagnosticOnly') is True,'Explicit bounded diagnostic config required')
    for key,expected in [('parentReceiptSha256',sha(parent_path)),('parentSourceSha256',sha(candidate)),('parentArchiveSha256',sha(archive_path))]:
        require(config.get(key)==expected,'Cap parent association mismatch '+key)
    knots=np.asarray(config['knots'],float);protected=float(config['protectedBelowZ'])
    require(protected<=-.040 and knots[0,0]>=-.010,'Muscularshaft through-40mm and lowerblend protected')
    require(np.isfinite(protected) and 0<float(config['maximumMovementMetres'])<=.050,'Explicit bounded50mm maximum capmovement')
    base=np.load(archive_path,allow_pickle=False)
    p=np.asarray(base['positions'],float);n=np.asarray(base['normals'],float);uvnative=np.asarray(base['uvNative'],float)
    require(p.shape==n.shape and p.ndim==3 and p.shape[1:]==(3,3) and uvnative.shape==(len(p),3,2),'Authoritative ordered corner contract required')
    flat=p.reshape(-1,3);changed,jac=taper_field(flat,knots,config['centreXY'])
    newn=directions(n.reshape(-1,3),jac).reshape(n.shape);newp=changed.reshape(p.shape)
    pd=np.linalg.norm(newp-p,axis=2);nd=np.linalg.norm(newn-n,axis=2)
    require(float(pd.max())<=float(config['maximumMovementMetres']),'Recorded cap movement bound exceeded')
    protected_corners=p[:,:,2]<=protected
    require(np.array_equal(newp[protected_corners],p[protected_corners]) and np.array_equal(newn[protected_corners],n[protected_corners]),'Protected muscularshaft changed')
    doc,binary=read_glb(candidate);sp,sn,suv,records=raw_corners(doc,binary)
    require(np.max(abs(sp-p))<1e-6 and np.max(abs(sn-n))<1e-6,'RenderedGLB/authoritativeparent correspondence lost')
    require(np.array_equal(1-suv[:,:,1],uvnative[:,:,1]) and np.array_equal(suv[:,:,0],uvnative[:,:,0]),'Parent UV/native onceflip mismatch')
    require(len(doc['nodes'])==1 and doc['nodes'][0].get('mesh')==0 and np.array_equal(node_matrix(doc['nodes'][0]),np.eye(4)),'Canonical detached identity input required')
    newdoc=copy.deepcopy(doc);output=bytearray(binary);offset=0;tangent_archive=[];tangent_ids=[]
    def append(rows):
        rows=np.asarray(rows,dtype='<f4');output.extend(b'\0'*(-len(output)%4));start=len(output)
        output.extend(rows.tobytes());output.extend(b'\0'*(-len(output)%4))
        newdoc['bufferViews'].append({'buffer':0,'byteOffset':start,'byteLength':rows.nbytes})
        newdoc['accessors'].append({'bufferView':len(newdoc['bufferViews'])-1,'componentType':5126,'count':len(rows),'type':'VEC'+str(rows.shape[1])})
        if rows.shape[1]==3:newdoc['accessors'][-1].update(min=rows.min(0).tolist(),max=rows.max(0).tolist())
        return len(newdoc['accessors'])-1
    for primitive,newprimitive in zip(doc['meshes'][0]['primitives'],newdoc['meshes'][0]['primitives']):
        ids=accessor(doc,binary,primitive['indices']).reshape(-1,3).astype(int);count=len(ids)
        positions=newp[offset:offset+count];normals=newn[offset:offset+count]
        vertex_count=doc['accessors'][primitive['attributes']['POSITION']]['count']
        rows_p=accessor(doc,binary,primitive['attributes']['POSITION']).astype(float)@BASIS.T
        rows_n=accessor(doc,binary,primitive['attributes']['NORMAL']).astype(float)@BASIS.T
        rows_p[ids]=positions;rows_n[ids]=normals
        require(np.max(abs(rows_p[ids]-positions))<1e-12 and np.max(abs(rows_n[ids]-normals))<1e-12,'Sharedvertex authoredcorner conflict requires explicitsplit, no substitution')
        newprimitive['attributes']['POSITION']=append(rows_p@BASIS)
        newprimitive['attributes']['NORMAL']=append(rows_n@BASIS)
        if 'TANGENT' in primitive['attributes']:
            raw_t=accessor(doc,binary,primitive['attributes']['TANGENT']).astype(float)
            source_p=accessor(doc,binary,primitive['attributes']['POSITION']).astype(float)@BASIS.T
            source_p[ids]=p[offset:offset+count]
            _,vj=taper_field(source_p,knots,config['centreXY'])
            t=raw_t[:,:3]@BASIS.T
            if 'tangents' in base.files:
                tid=np.asarray(base['tangentTriangleIds'],int)
                require(np.all(np.isin(np.arange(offset,offset+count),tid)),'Missingauthoredcorner tangent lineage')
                lookup={int(key):i for i,key in enumerate(tid)}
                ct=base['tangents'][[lookup[i] for i in range(offset,offset+count)]]
                t[ids]=ct[:,:,:3]
                require(np.max(abs(t[ids]-ct[:,:,:3]))<1e-12,'Sharedvertex tangent conflict')
                require(np.array_equal(raw_t[ids,3],ct[:,:,3]),'Authored tangent handedness changed inparent')
            length=np.linalg.norm(t,axis=1)
            tt=np.einsum('nij,nj->ni',vj,t)
            nn=rows_n/np.linalg.norm(rows_n,axis=1)[:,None]
            tt-=np.sum(tt*nn,axis=1)[:,None]*nn
            require(np.all(np.linalg.norm(tt,axis=1)>1e-8),'Degenerate localtangent rejected')
            tt*= (length/np.linalg.norm(tt,axis=1))[:,None]
            identity=np.all(vj==np.eye(3),axis=(1,2));tt[identity]=t[identity]
            transformed_t=raw_t.copy();transformed_t[:,:3]=tt@BASIS
            newprimitive['attributes']['TANGENT']=append(transformed_t)
            native_t=transformed_t.copy();native_t[:,:3]=tt
            tangent_archive.append(native_t[ids]);tangent_ids.extend(range(offset,offset+count))
        offset+=count
    require(offset==len(p),'All authoritativefaces covered')
    newdoc['buffers'][0]['byteLength']=len(output)
    out=args.output.resolve();out.mkdir(parents=True)
    target=out/'refined-local.glb';write_glb(target,newdoc,bytes(output))
    actualdoc,actualbin=read_glb(target);ap,an,au,_=raw_corners(actualdoc,actualbin)
    require(np.max(abs(ap-newp))<1e-6 and np.max(abs(an-newn))<1e-6,'CapFLOAT32 render precision exceedsdeclaredbudget')
    require(np.array_equal(au,suv) and embedded_maps(actualdoc,actualbin)==embedded_maps(doc,binary),'UV/maps changed')
    require(actualdoc['materials']==doc['materials'] and actualbin[:len(binary)]==binary,'Material/source BIN prefix changed')
    # Keep durable source/corner association, not a parent's operation-specific
    # delta/mask fields with stale meanings. This operation's parent arrays and
    # deltas are explicit; earlier fan repair remains in its bound receipt.
    durable={'uvNative','uvGltf','sourcePositions','sourceNormals','sourceUVNative',
        'sourceTriangleIds','primitiveIds','sourceCornerOrder','sourceFaceIds','sourceCornerIds',
        'tangents','tangentTriangleIds'}
    arrays={key:base[key] for key in base.files if key in durable};arrays.update(positions=newp,normals=newn,
        capBasePositions=p,capBaseNormals=n,parentPositions=p,parentNormals=n,
        positionDelta=newp-p,normalDelta=newn-n,positionChangedCornerMask=pd>0,normalChangedCornerMask=nd>0)
    if tangent_archive:arrays.update(tangents=np.concatenate(tangent_archive),tangentTriangleIds=np.asarray(tangent_ids,np.int64))
    archive=out/'native-corners.npz';np.savez_compressed(archive,**arrays)
    code=Path(__file__).resolve();inputs={str(x):sha(x) for x in [parent_path,candidate,archive_path,args.config.resolve(),code,code.with_name('place_purposebuilt_pelvis.py')]}
    report={'schemaVersion':1,'diagnosticOnly':True,'operation':'bounded-thigh-proximal-crown-taper',
        'candidate':str(target),'candidateSha256':sha(target),'parentReceipt':str(parent_path),'parentReceiptSha256':sha(parent_path),
        'parentSource':str(candidate),'parentSourceSha256':sha(candidate),'configuration':config,
        'nativeCornerArchive':{'path':str(archive),'sha256':sha(archive)},'frozenInputHashes':inputs,
        'proof':{'sourceUVMapsMaterialIndicesExact':True,'topologyChanged':False,'protectedShaftPNExact':True,
            'changedPositionCorners':int(np.sum(pd>0)),'changedNormalCorners':int(np.sum(nd>0)),
            'maximumPositionDeltaMetres':float(pd.max()),'minimumJacobianDeterminant':float(np.linalg.det(jac).min()),
            'maximumNormalMagnitudeError':float(np.max(abs(np.linalg.norm(newn,axis=2)-np.linalg.norm(n,axis=2)))),
            'maximumPositionFloat32ErrorMetres':float(np.max(abs(ap-newp))),'maximumNormalFloat32Error':float(np.max(abs(an-newn))),
            'normalPolicy':'Onlylocalinverse-transpose Jacobian; normalize transformed direction to original authored magnitude; exactidentity outsideband.',
            'tangentPolicy':'Onlylocalforward Jacobian+normalorthogonalization; retain authoredlength and handedness; exactidentity outsideband.',
            'fitPolicy':'Completedproperuniformfit ancestry preserved; no refit, rig, neighbour or muscleshaftexterior edits.'},
        'archiveOperationFieldScope':'parentPositions/Normals, positionDelta/normalDelta and changedcornermasks describe THIS capoperation relative to bound immediateparent. Earlierrepair only in parentreceipt; no stale copied operationdeltas.',
        'bounds':bounds(newp),'clientAccepted':False,'requiresPoseAndIndependentTopologyReview':True}
    for path,h in inputs.items():require(sha(path)==h,'Frozeninputchanged '+path)
    (out/'refinement.json').write_text(json.dumps(report,indent=2)+'\n')
    shutil.copy2(args.config,out/'executed-config.json');shutil.copy2(code,out/'executed-refine_thigh_proximal_cap.py')
    print(json.dumps({'output':str(out),'proof':report['proof']}))


if __name__=='__main__':main()
