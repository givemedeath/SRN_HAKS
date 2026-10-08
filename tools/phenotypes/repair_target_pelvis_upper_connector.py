"""One diagnostic pelvis upper-skin connector, with source-face subdivision.

Both nested upper disks are retained. Local Z and every complete lower clipped
surface stay fixed; source maps/UVs remain archived and unchanged. New corners
record separate float32-preview and authoritative-double barycentric ancestry.
"""
import argparse,copy,json,shutil
from pathlib import Path
import numpy as np
import target_contract as contract
from conservative_face_selection import topology
from deform_target_terminal_envelope import transport
from repair_target_chest_connector import split_at_plane,face_diagnostics
from place_purposebuilt_pelvis import BASIS,accessor,embedded_maps,node_matrix,raw_corners,read_glb,write_glb

def upper_field(points,plane,full_z,centre,scales):
    p=np.asarray(points,float);c=np.asarray(centre,float);s=np.asarray(scales,float)
    contract.require(p.ndim==2 and p.shape[1]==3 and np.isfinite(p).all(),'Finite attachment-local points required')
    contract.require(np.isfinite(plane) and np.isfinite(full_z) and 0<plane<full_z,
                     'Measured positive-Z upper connector support required')
    contract.require(c.shape==(2,) and np.isfinite(c).all() and s.shape==(2,) and np.isfinite(s).all() and
                     np.all(s>0) and np.all(s<=1) and np.prod(s)>=.25,'Positive bounded XY scales and determinant margin required')
    t=np.clip((p[:,2]-plane)/(full_z-plane),0,1);h=t*t*(3-2*t);dh=6*t*(1-t)/(full_z-plane)
    scale=1-h[:,None]*(1-s);relative=p[:,:2]-c
    out=p.copy();out[:,:2]=c+relative*scale
    jac=np.tile(np.eye(3),(len(p),1,1));jac[:,0,0]=scale[:,0];jac[:,1,1]=scale[:,1]
    jac[:,:2,2]=-relative*(1-s)*dh[:,None]
    protected=p[:,2]<=plane;out[protected]=p[protected];jac[protected]=np.eye(3)
    return out,jac

def subdivide(attributes,faces,planes,native=None):
    """Conforming horizontal splits; each final child still names one source face."""
    contract.require(isinstance(planes,list) and len(planes)>=2 and all(np.isfinite(planes)) and
                     all(0<a<b for a,b in zip(planes,planes[1:])),'Ordered positive subdivision planes required')
    original_faces=np.asarray(faces,np.int64);a=attributes;f=original_faces.copy()
    parents=np.arange(len(f));weights=np.tile(np.eye(3),(len(f),1,1));native_weights=weights.copy()
    native_values=None if native is None else {k:np.asarray(v).copy() for k,v in native.items()}
    steps=[];last_plane=None
    for value in planes:
        sp=split_at_plane(a,f,value);ids=sp['parentFaceIds'];w=sp['barycentric']
        nw=w.copy()
        if native_values is not None:
            cp=native_values['positions']
            for cid,pid in enumerate(ids):
                for corner,cw in enumerate(w[cid]):
                    hit=np.flatnonzero(cw)
                    if len(hit)==2:
                        ia,ib=hit;za=cp[pid,ia,2];zb=cp[pid,ib,2]
                        t=(sp['plane']-za)/(zb-za)
                        contract.require(0<t<1,'Native edge no longer crosses frozen source plane')
                        nw[cid,corner]=0;nw[cid,corner,ia]=1-t;nw[cid,corner,ib]=t
            native_values={k:np.einsum('fci,fij->fcj',nw,v[ids]) for k,v in native_values.items()}
            cut=np.count_nonzero(nw,axis=2)==2;native_values['positions'][:,:,2][cut]=sp['plane']
        weights=np.einsum('fci,fij->fcj',w,weights[ids])
        native_weights=np.einsum('fci,fij->fcj',nw,native_weights[ids])
        steps.append({'planeLocalZMetres':sp['plane'],'sourceStepFaces':len(f),'childFaces':len(sp['faces']),
                      'crossingStepFaceIds':sp['crossingParentFaceIds'].tolist(),
                      'splitRawRows':{str(k):{'sourceRawEdge':list(v[:2]),'bWeight':v[2]}
                                      for k,v in sp['splitRowEdgeLineage'].items()}})
        parents=parents[ids];a=sp['attributes'];f=sp['faces'];last_plane=sp['plane']
    plane=float(np.float32(planes[0]));lower=a['POSITION'][f,1].max(1)<=plane
    contract.require(np.all(lower|(a['POSITION'][f,1].min(1)>=plane)),
                     'A final child crosses the lower protection plane')
    return {'attributes':a,'faces':f,'parentFaceIds':parents,'barycentric':weights,'nativeBarycentric':native_weights,
            'nativeValues':native_values,'lowerFaceMask':lower,'plane':plane,'steps':steps,
            'originalRowCount':len(attributes['POSITION'])}

def execute(config_path,output):
    config_path=Path(config_path).resolve();cfg=json.loads(config_path.read_text())
    allowed={'schemaVersion','kind','diagnosticOnly','parentReceipt','parentReceiptSha256','targetContract',
             'targetContractSha256','protectedInputs','notes','planeLocalZMetres','fullScaleLocalZMetres',
             'centreLocalXYMetres','endXYScale','maximumDisplacementMetres','subdivisionPlanesLocalZMetres',
             'upperSkinParentFaceIds','ownershipInspection','maximumFaces'}
    contract.require(set(cfg)<=allowed and cfg['schemaVersion']==2 and
                     cfg['kind']=='target-face-aware-pelvis-upper-connector-trial' and cfg['diagnosticOnly'] is True,
                     'Explicit pelvis upper diagnostic configuration required')
    parentpath=Path(cfg['parentReceipt']).resolve();parent=json.loads(parentpath.read_text())
    targetpath=Path(cfg['targetContract']).resolve();target=contract.load(targetpath)
    contract.verify_binding(parent,targetpath,target,'working')
    contract.require(parent['kind']=='target-part-geometry' and parent['part']=='pelvis' and parent['joint']=='pelvis_g'
                     and parent['statureApplications']==0 and parent['operation']=='detached-component-removal',
                     'One original detached-removal working pelvis parent required; repeated conversion/connector rejected')
    source=Path(parent['candidate']).resolve();archivepath=Path(parent['nativeCornerArchive']['path']).resolve()
    pins={str(parentpath):cfg['parentReceiptSha256'],str(source):parent['candidateSha256'],
          str(archivepath):parent['nativeCornerArchive']['sha256'],str(targetpath):cfg['targetContractSha256'],
          **cfg['protectedInputs'],**parent['frozenInputs'],str(config_path):contract.sha(config_path)}
    helpers=('repair_target_pelvis_upper_connector.py','repair_target_chest_connector.py','deform_target_terminal_envelope.py',
             'conservative_face_selection.py','place_purposebuilt_pelvis.py','target_contract.py')
    for name in helpers:
        p=Path(__file__).with_name(name).resolve();pins[str(p)]=contract.sha(p)
    for p,h in pins.items():contract.require(contract.sha(p)==h,'Frozen pelvis connector input changed: '+p)
    document,binary=read_glb(source)
    contract.require(len(document['nodes'])==1 and document['nodes'][0].get('mesh')==0 and
                     np.array_equal(node_matrix(document['nodes'][0]),np.eye(4)) and len(document['meshes'])==1 and
                     len(document['meshes'][0]['primitives'])==1,'One identity-node pelvis primitive required')
    primitive=document['meshes'][0]['primitives'][0]
    attrs={k:accessor(document,binary,v) for k,v in primitive['attributes'].items()}
    faces=accessor(document,binary,primitive['indices']).reshape(-1,3).astype(np.int64)
    base=np.load(archivepath,allow_pickle=False)
    names=['positions','normals','uvGltf','uvNative']+(['tangents'] if 'tangents' in base.files else [])
    names+=[n for n in ('sourcePositions','sourceNormals','sourceUVNative') if n in base.files]
    planes=cfg['subdivisionPlanesLocalZMetres'];plane=float(np.float32(cfg['planeLocalZMetres']));full=cfg['fullScaleLocalZMetres']
    contract.require(planes[0]==cfg['planeLocalZMetres'] and abs(planes[-1]-full)<1e-8 and
                     all(b-a<=.005000001 for a,b in zip(planes,planes[1:])) and
                     plane>=.015-1e-9 and 0<full-plane<=.025000001,
                     'Frozen short +15mm upper-skin band and at most 5mm source-face subdivision required')
    upperparents=np.flatnonzero(attrs['POSITION'][faces,1].max(1)>plane)
    contract.require(cfg['upperSkinParentFaceIds']==upperparents.tolist(),'Explicit reviewed upper skin source-face set mismatch')
    split=subdivide(attrs,faces,planes,{k:base[k] for k in names})
    raw=split['attributes'];fs=split['faces'];parents=split['parentFaceIds'];lower=split['lowerFaceMask']
    contract.require(len(fs)<=cfg['maximumFaces']<=60000,'Diagnostic subdivision face budget exceeded')
    original=topology(attrs['POSITION'],faces);before=topology(raw['POSITION'],fs)
    keys=('boundaryEdges','nonmanifoldEdges','inconsistentManifoldEdgeWindings','nonmanifoldVertexLinks',
          'zeroAreaFaces','components','eulerCharacteristic')
    contract.require(all(original[k]==before[k] for k in keys),'Source subdivision changed topology')
    upper_topology=topology(raw['POSITION'],fs[~lower])
    contract.require(upper_topology['components']==2 and upper_topology['eulerCharacteristic']==2 and
                     upper_topology['nonmanifoldEdges']==upper_topology['nonmanifoldVertexLinks']==0 and
                     len(upper_topology['boundaryLoops'])==2 and
                     all(x['closedDegreeTwoRing'] for x in upper_topology['boundaryLoops']),
                     'Both measured upper sheets must remain clean manifold disks')
    local=raw['POSITION'].astype(float)@BASIS.T;proposed,jac=upper_field(local,plane,full,cfg['centreLocalXYMetres'],cfg['endXYScale'])
    ref=np.zeros(len(local),bool);ref[np.unique(fs)]=True;proposed[~ref]=local[~ref];jac[~ref]=np.eye(3)
    edited=ref&np.any(proposed!=local,axis=1);maximum=float(np.linalg.norm(proposed-local,axis=1).max())
    contract.require(0<cfg['maximumDisplacementMetres']<=.06 and maximum<=cfg['maximumDisplacementMetres'],
                     'Measured upper connector displacement limit exceeded')
    changedparents=np.unique(parents[np.any(edited[fs],axis=1)])
    contract.require(np.isin(changedparents,upperparents).all(),'Protected garment/lower source face changed')
    normals=raw['NORMAL'].astype(float)@BASIS.T;tangent=raw.get('TANGENT')
    if tangent is not None:tangent=tangent.astype(float);tangent[:,:3]=tangent[:,:3]@BASIS.T
    nn,tt=transport(normals,tangent,jac,edited);changed={k:v.copy() for k,v in raw.items()}
    changed['POSITION'][edited]=(proposed[edited]@BASIS).astype('<f4');changed['NORMAL'][edited]=(nn[edited]@BASIS).astype('<f4')
    if tt is not None:
        rt=tt.copy();rt[:,:3]=rt[:,:3]@BASIS;changed['TANGENT'][edited]=rt[edited].astype('<f4')
    winding,opposed=face_diagnostics(local[fs],(changed['POSITION'].astype(float)@BASIS.T)[fs],
                                   normals[fs],(changed['NORMAL'].astype(float)@BASIS.T)[fs])
    contract.require(np.all(winding>0) and not len(opposed),'New serialized chord reversal or authored mean-normal opposition')
    for k in raw:contract.require(raw[k][fs[lower]].tobytes()==changed[k][fs[lower]].tobytes(),
                                 'Actual whole lower clipped surface changed: '+k)
    after=topology(changed['POSITION'],fs)
    contract.require(all(before[k]==after[k] for k in keys),'Connector deformation changed topology')
    result=copy.deepcopy(document);payload=bytearray(binary)
    def append(values,indices=False):
        payload.extend(b'\0'*(-len(payload)%4));start=len(payload);payload.extend(values.tobytes());payload.extend(b'\0'*(-len(payload)%4))
        result['bufferViews'].append({'buffer':0,'byteOffset':start,'byteLength':values.nbytes,'target':34963 if indices else 34962})
        info={'bufferView':len(result['bufferViews'])-1,'componentType':5125 if indices else 5126,
              'count':values.size if indices else len(values),'type':'SCALAR' if indices else 'VEC'+str(values.shape[1])}
        if not indices and values.shape[1]==3:info.update(min=values.min(0).tolist(),max=values.max(0).tolist())
        result['accessors'].append(info);return len(result['accessors'])-1
    for k,v in changed.items():result['meshes'][0]['primitives'][0]['attributes'][k]=append(v)
    result['meshes'][0]['primitives'][0]['indices']=append(fs.astype('<u4').reshape(-1),True);result['buffers'][0]['byteLength']=len(payload)
    contract.require(bytes(payload[:len(binary)])==binary and result['materials']==document['materials'] and
                     embedded_maps(result,bytes(payload))==embedded_maps(document,binary),'Original source BIN/material/image changed')
    for k,v in changed.items():
        protection=(attrs['POSITION'][:,1]<=plane)|~ref[:len(attrs['POSITION'])]
        contract.require(v[:len(attrs['POSITION'])][protection].tobytes()==attrs[k][protection].tobytes(),
                         'Protected original attribute row changed')
    nv=split['nativeValues'];p=nv['positions'];n=nv['normals'];nt=nv.get('tangents')
    np_,nj=upper_field(p.reshape(-1,3),plane,full,cfg['centreLocalXYMetres'],cfg['endXYScale'])
    ne=np.any(np_!=p.reshape(-1,3),axis=1);native_n,native_t=transport(n.reshape(-1,3),None if nt is None else nt.reshape(-1,4),nj,ne)
    arrays={**nv,'positions':np_.reshape(p.shape),'normals':native_n.reshape(n.shape),
            'sourceFaceIds':parents,'connectorParentFaceIds':parents,'connectorBarycentricPreview':split['barycentric'],
            'connectorBarycentricNative':split['nativeBarycentric'],'connectorLowerFaceMask':lower,
            'connectorParentFaces':faces,'connectorSplitFaces':fs,'connectorParentRawPositions':attrs['POSITION'],
            'connectorEditedVertexMask':edited,'connectorJacobianLocal':jac}
    if native_t is not None:arrays['tangents']=native_t.reshape(nt.shape);arrays['tangentTriangleIds']=np.arange(len(fs))
    for name in ('sourceTriangleIds','primitiveIds'):
        if name in base.files:arrays[name]=base[name][parents]
    for k in ('positions','normals','uvGltf','uvNative','tangents'):
        if k in arrays:contract.require(np.array_equal(arrays[k][lower],nv[k][lower]),'Authoritative whole lower surface changed: '+k)
    ep,en,eu,_=raw_corners(result,bytes(payload))
    contract.require(np.max(abs(ep-arrays['positions']))<1e-7 and np.max(abs(en-arrays['normals']))<2e-6 and
                     np.max(abs(eu-arrays['uvGltf']))<2e-7,'Serialized preview differs from authoritative native lineage')
    output=Path(output).resolve();contract.require(not output.exists(),'Fresh immutable pelvis upper trial required')
    output.mkdir(parents=True);candidate=output/'candidate-local.glb';write_glb(candidate,result,bytes(payload))
    # Re-open exact disk serialization before completing its receipt.
    rd,rb=read_glb(candidate);rq=rd['meshes'][0]['primitives'][0]
    for k,v in changed.items():contract.require(accessor(rd,rb,rq['attributes'][k]).tobytes()==v.tobytes(),'Reopened serialized attributes differ')
    archive=output/'native-corners.npz';np.savez_compressed(archive,**arrays)
    lineage=output/'split-lineage.json';lineage.write_text(json.dumps({'steps':split['steps'],'originalRowCount':len(attrs['POSITION']),
       'rule':'Conforming horizontal source-face subdivisions preserve each original planar surface. New UV/authored normal/tangent rows interpolate their own raw edges without seam welding. Each final child pins original face IDs and preview/native barycentric lineage; W copied only for agreeing edge endpoints.',
       'previewNativeBarycentricDifferenceExplicit':True},indent=2)+'\n')
    shutil.copy2(config_path,output/'config.json');(output/'tools').mkdir();snapshots={}
    for name in helpers:
        p=Path(__file__).with_name(name).resolve();s=output/'tools'/name;shutil.copy2(p,s);snapshots[str(p)]={'snapshot':str(s),'sha256':contract.sha(s)}
    receipt={'schemaVersion':2,'kind':'target-part-geometry','operation':'face-aware-pelvis-upper-connector-plane-subdivision',
      **contract.binding(targetpath,target,'working'),'part':'pelvis','joint':'pelvis_g','model':contract.model(target,'pelvis'),
      'source':str(source),'sourceSha256':parent['candidateSha256'],'sourceReceipt':str(parentpath),'sourceReceiptSha256':contract.sha(parentpath),
      'candidate':str(candidate),'candidateSha256':contract.sha(candidate),'nativeCornerArchive':{'path':str(archive),'sha256':contract.sha(archive)},
      'statureApplications':0,'attachmentWorld':parent['attachmentWorld'],'sourceToAttachmentLocal':np.eye(4).tolist(),
      'connectorConfiguration':cfg,'splitLineage':{'path':str(lineage),'sha256':contract.sha(lineage)},'frozenInputs':pins,
      'helperSnapshots':snapshots,'diagnosticOnly':True,'clientAccepted':False,'productionAccepted':False,
      'proof':{'protectionPlaneLocalZMetres':plane,'sourceFaces':len(faces),'childFaces':len(fs),'originalRows':len(attrs['POSITION']),
       'newSplitRows':len(local)-len(attrs['POSITION']),'changedReferencedRows':int(edited.sum()),'lowerProtectedChildFaces':int(lower.sum()),
       'changedParentSourceFaceIds':changedparents.tolist(),'actualMaximumDisplacementMetres':maximum,
       'continuousDeterminantLowerBound':float(np.prod(cfg['endXYScale'])),'minimumDiscreteFaceNormalDot':float(winding.min()),
       'newAuthoredMeanNormalOppositionChildFaceIds':opposed.tolist(),'exactLowerOriginalRows':True,'exactWholeLowerClippedSurface':True,
       'originalBinPrefixAndAllImageBytesExact':True,'UVUnchangedOrExplicitSourceBarycentricInterpolation':True,
       'noSourceFaceDeleted':True,'noInnerSheetDeletion':True,'twoUpperDiskTopology':upper_topology,
       'sourceTopology':original,'subdividedTopology':before,'deformedTopology':after},
      'limitations':['One unselected working diagnostic. Both nested upper skin sheets retained and tapered together.',
       'Subdivided face count exceeds original 50,000 generation compact budget; no production/native performance acceptance.',
       'Five source upper UV seams retain existing cold bilinear-support padding pixels; no material ownership acceptance or pixel correction.',
       'Briefs/lower clipped pelvis fixed. Separate front chest ridge, collar, shoulder ownership, pelvis garment tracks and source nonmanifold lower topology remain unresolved.',
       'Positive continuous Jacobian does not certify finite triangle intersections; independent serialized crossing audit and finite nine-view review remain required.',
       'No runtime conversion, staging, native/client validation or selection.']}
    for p,h in pins.items():contract.require(contract.sha(p)==h,'Frozen connector input changed during execution: '+p)
    path=output/'geometry.json';path.write_text(json.dumps(receipt,indent=2)+'\n');return path,receipt

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();p,r=execute(args.config,args.output);print(json.dumps({'receipt':str(p),'sha256':contract.sha(p),
        'candidateSha256':r['candidateSha256'],'faces':r['proof']['childFaces'],'maxDisplacement':r['proof']['actualMaximumDisplacementMetres']}))

