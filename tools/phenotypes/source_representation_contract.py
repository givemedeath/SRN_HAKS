"""Exact read-only source representations; no staging or consumer dispatch.

Current tracked pure array functions are explicitly code-bound. Historical
helpers remain inert. Encoded GLB arrays and native-double lineage stay separate.
"""
import ast
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import struct
from types import MappingProxyType

import numpy as np

import phenotype_infrastructure_adoption as adoption
import phenotype_execution_adoption as execution
import target_contract as c
import target_part_pipeline as pipeline
from repair_target_pelvis_upper_connector import subdivide, upper_field
from deform_target_terminal_envelope import transport

KIND = 'target-source-representation-contract'
OPERATION = 'verify-original-representation-v1'
PROTOCOLS = frozenset(('literal-exact-v1', 'absent-authored-tangent-direct-encoded-v1',
    'native-v-complement-f32-v1', 'sequential-plane-split-raw-field-v1',
    'original-source-barycentric-plus-native-field-delta-v1'))
B = np.array([[1.,0,0],[0,0,-1],[0,1,0]])
B.setflags(write=False)
_SEAL = object()
_FIELDS = {'schemaVersion','kind','operation','verificationApplications','targetContract',
    'targetId','rigRevision','coordinateSpace','part','joint','model','statureApplications',
    'protocol','candidate','geometryReceipt','nativeCornerArchive','adoptionProof',
    'inputReceipts','protocolInputs','sourceClosure','currentCodeSupport','ancestorContract'}


def require(value, message):
    c.require(bool(value), message)


def pin(row):
    require(isinstance(row,dict) and set(row)=={'path','sha256'} and
        isinstance(row['path'],str) and Path(row['path']).is_absolute() and
        isinstance(row['sha256'],str) and len(row['sha256'])==64 and
        all(x in '0123456789abcdef' for x in row['sha256']), 'Exact absolute representation pin required')
    return str(Path(row['path'])),row['sha256']


def equal(a,b,label):
    require(a.shape==b.shape and a.dtype==b.dtype and
        np.ascontiguousarray(a).tobytes()==np.ascontiguousarray(b).tobytes(),
        'Exact representation differs: '+label)


def unique_json_pairs(rows):
    result={}
    for key,value in rows:
        require(key not in result,'Duplicate JSON key: '+key)
        result[key]=value
    return result


def decode_json(value):
    def nonfinite(word):
        require(False,'Nonfinite JSON constant: '+word)
    def finite_float(word):
        result=float(word)
        require(np.isfinite(result),'Nonfinite JSON number: '+word)
        return result
    return json.loads(value,object_pairs_hook=unique_json_pairs,parse_constant=nonfinite,parse_float=finite_float)


def read_json(path):
    return decode_json(Path(path).read_text(encoding='utf-8-sig'))


def current_helper_paths():
    """Static local import closure, including lazy imports; never import archives."""
    bank=Path(__file__).resolve().parent
    pending=[Path(__file__).resolve()];found=set()
    while pending:
        p=pending.pop()
        if p in found:continue
        found.add(p)
        tree=ast.parse(p.read_text(encoding='utf-8-sig'))
        for node in ast.walk(tree):
            names=([x.name for x in node.names] if isinstance(node,ast.Import) else
                   [node.module] if isinstance(node,ast.ImportFrom) and node.module else [])
            for name in names:
                for base in (bank,bank.parent):
                    child=base/(name.split('.')[0]+'.py')
                    if child.is_file():pending.append(child.resolve());break
    return tuple(sorted(found))


def glb(path, detached=True):
    raw=Path(path).read_bytes()
    require(len(raw)>=20,'Truncated GLB header')
    magic,version,size=struct.unpack_from('<III',raw)
    require((magic,version,size)==(0x46546c67,2,len(raw)),'Exact GLB2 header required')
    chunks=[];offset=12
    while offset<len(raw):
        require(offset+8<=len(raw),'Truncated chunk header')
        length,kind=struct.unpack_from('<II',raw,offset);offset+=8
        require(length%4==0 and offset+length<=len(raw),'Chunk bounds differ')
        chunks.append((kind,raw[offset:offset+length]));offset+=length
    require([k for k,_ in chunks]==[0x4e4f534a,0x004e4942],'One JSON/BIN GLB required')
    d=decode_json(chunks[0][1]);binary=chunks[1][1]
    require(d.get('asset',{}).get('version')=='2.0' and len(d.get('buffers',[]))==1 and
        not d['buffers'][0].get('uri') and type(d['buffers'][0].get('byteLength')) is int and
        0<=d['buffers'][0]['byteLength']<=len(binary),'Bounded embedded buffer required')
    require(not d.get('skins') and not d.get('animations') and not d.get('extensionsRequired'),
        'Static source only; no rig/animation/required extensions')
    if detached:
        require(d.get('nodes')==[{'name':'detached_geometry','mesh':0}] and
            len(d.get('meshes',[]))==1 and d.get('scenes')==[{'nodes':[0]}] and d.get('scene',0)==0,
            'Canonical detached identity geometry required')
    return d,binary


def accessor(d,b,index):
    require(type(index) is int and 0<=index<len(d.get('accessors',[])),'Accessor index out of bounds')
    a=d['accessors'][index];bi=a.get('bufferView')
    require(not a.get('sparse') and not a.get('normalized') and type(a.get('count')) is int and
        a['count']>0 and type(bi) is int and 0<=bi<len(d.get('bufferViews',[])),
        'Positive literal bounded accessor required')
    v=d['bufferViews'][bi];types={5121:'u1',5123:'<u2',5125:'<u4',5126:'<f4'}
    widths={'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4}
    require(v.get('buffer',0)==0 and a.get('componentType') in types and a.get('type') in widths,
        'Unsupported accessor buffer/type')
    dt=np.dtype(types[a['componentType']]);width=widths[a['type']];row=width*dt.itemsize
    start=v.get('byteOffset',0);length=v.get('byteLength');extra=a.get('byteOffset',0);stride=v.get('byteStride',row)
    require(all(type(x) is int for x in (start,length,extra,stride)) and start>=0 and length>=0 and
        extra>=0 and (start+extra)%dt.itemsize==0 and stride>=row and stride%dt.itemsize==0 and start+length<=d['buffers'][0]['byteLength'] and
        extra+(a['count']-1)*stride+row<=length,'Accessor/BufferView bounds or stride differ')
    value=np.ndarray((a['count'],width),dtype=dt,buffer=b,offset=start+extra,
        strides=(stride,dt.itemsize)).copy()
    require(np.isfinite(value).all(),'Nonfinite source field')
    return value


def mesh(d,b):
    aa=[];ff=[];inventory=[]
    for pi,pr in enumerate(d['meshes'][0]['primitives']):
        require(pr.get('mode',4)==4 and not pr.get('targets') and not pr.get('extensions'),
            'Literal triangles without morph/extension required')
        names=pr.get('attributes',{})
        require({'POSITION','NORMAL','TEXCOORD_0'}<=set(names) and
            set(names)<={'POSITION','NORMAL','TEXCOORD_0','TANGENT'},'Explicit PN/UV and optional T only; COLOR0 unsupported')
        a={k:accessor(d,b,names[k]) for k in ('POSITION','NORMAL','TEXCOORD_0')}
        if 'TANGENT' in names:a['TANGENT']=accessor(d,b,names['TANGENT'])
        n=len(a['POSITION'])
        require(all(v.dtype==np.dtype('<f4') and len(v)==n for v in a.values()) and
            a['POSITION'].shape==(n,3) and a['NORMAL'].shape==(n,3) and a['TEXCOORD_0'].shape==(n,2) and
            (np.linalg.norm(a['NORMAL'],axis=1)>0).all(),'Typed finite float32 PN/UV rows required')
        if 'TANGENT' in a:
            require(a['TANGENT'].shape==(n,4) and (np.linalg.norm(a['TANGENT'][:,:3],axis=1)>0).all() and
                np.isin(a['TANGENT'][:,3],[-1.,1.]).all(),'Nonzero authored T and exact sign required')
        idx=accessor(d,b,pr['indices'])
        require(idx.dtype.kind=='u' and idx.shape[1]==1 and len(idx)%3==0 and idx.max()<n,
            'Unsigned triangle indices required')
        f=idx.reshape(-1,3).astype('i8');material=pr.get('material')
        require(type(material) is int and 0<=material<len(d.get('materials',[])),'Explicit material owner required')
        aa.append(a);ff.append(f)
        inventory.append({'primitive':pi,'triangles':len(f),'material':material,
            'indexDtype':str(idx.dtype),'indexSha256':hashlib.sha256(idx.tobytes()).hexdigest(),
            'attributes':{k:{'dtype':str(v.dtype),'shape':list(v.shape),
                'sha256':hashlib.sha256(v.tobytes()).hexdigest()} for k,v in a.items()}})
    require(aa,'Nonempty body mesh required')
    return aa,ff,inventory


def corners(aa,ff):
    p=np.concatenate([(a['POSITION'].astype(float)@B.T)[f] for a,f in zip(aa,ff)])
    n=np.concatenate([(a['NORMAL'].astype(float)@B.T)[f] for a,f in zip(aa,ff)])
    u=np.concatenate([a['TEXCOORD_0'][f].astype(float) for a,f in zip(aa,ff)])
    un=u.copy();un[:,:,1]=1-u[:,:,1]
    result={'positions':p,'normals':n,'uvGltf':u,'uvNative':un,
        'primitiveIds':np.concatenate([np.full(len(f),i,dtype='i8') for i,f in enumerate(ff)])}
    present=['TANGENT' in a for a in aa]
    require(all(present) or not any(present),'Mixed authored T presence unsupported')
    if all(present):
        rows=[]
        for a,f in zip(aa,ff):
            t=a['TANGENT'].astype(float).copy();t[:,:3]=t[:,:3]@B.T;rows.append(t[f])
        result['tangents']=np.concatenate(rows)
    return result


def tangent(z):
    require(not ('authoredTangents' in z and 'tangents' in z),'Ambiguous archived T aliases')
    return z.get('authoredTangents',z.get('tangents'))


def preservation(d,b,old,ob):
    require(b[:len(ob)]==ob,'Original BIN prefix differs')
    for k in ('materials','textures','images','samplers'):require(d.get(k)==old.get(k),'Original '+k+' differs')
    require(d.get('bufferViews',[])[:len(old.get('bufferViews',[]))]==old.get('bufferViews',[]) and
        d.get('accessors',[])[:len(old.get('accessors',[]))]==old.get('accessors',[]),
        'Original bounded view/accessor descriptors differ')
    require(len(old.get('meshes',[]))==1 and
        [p.get('material') for p in d['meshes'][0]['primitives']]==
        [p.get('material') for p in old['meshes'][0]['primitives']],
        'Original ordered primitive/material owner inventory differs')
    images=[]
    for image in old.get('images',[]):
        require('bufferView' in image and not image.get('uri'),'Embedded original map required')
        index=image['bufferView']
        require(type(index) is int and 0<=index<len(old.get('bufferViews',[])) and
            index<len(d.get('bufferViews',[])),'Bounded integer image bufferView required')
        v=old['bufferViews'][index];start=v.get('byteOffset',0);end=start+v['byteLength']
        current=d['bufferViews'][index]
        require(type(start) is int and type(v['byteLength']) is int and v.get('buffer',0)==0 and
            0<=start<=end<=old['buffers'][0]['byteLength'] and end<=len(ob) and
            current==v and end<=d['buffers'][0]['byteLength'] and b[start:end]==ob[start:end],
            'Actual original/current bounded map payload differs')
        images.append({'sha256':hashlib.sha256(ob[start:end]).hexdigest(),'bytes':end-start})
    return {'originalBINPrefixBytes':len(ob),'originalBINMapsMaterialsExact':True,'images':images}


def raw_bary(rows,f,parents,w):
    source=rows[f[parents]];out=np.einsum('fci,fij->fcj',w,source.astype(float))
    one=(np.count_nonzero(w,axis=2)==1)&(w.max(2)==1)
    i,j=np.where(one);out[i,j]=source[i,np.argmax(w[i,j],axis=1)]
    return out


def knee(z,base,aa,ff,old,oldf,complement=False):
    require(len(aa)==len(old)==1,'One source-face primitive required')
    parents=z['connectorParentFaceIds'];w=z['connectorBarycentricNative'];mask=z['connectorProtectedWholeFaceMask']
    require(parents.ndim==1 and parents.dtype.kind in 'iu' and len(parents)>0 and parents.min()>=0 and
        parents.max()<len(oldf[0]) and np.array_equal(np.unique(parents),np.arange(len(oldf[0]))),'Full typed parent inventory required')
    require(w.shape==(len(parents),3,3) and w.dtype==np.dtype('f8') and np.isfinite(w).all() and
        (w>=0).all() and (w<=1).all() and np.max(abs(w.sum(2)-1))<1e-12,'Original finite simplex structural bound differs')
    areas=np.linalg.det(w);coverage=np.bincount(parents,weights=areas,minlength=len(oldf[0]))
    # Unchanged structural bound from the existing source-face protocol. This
    # is not used to accept any encoded/native attribute discrepancy.
    require((areas>0).all() and np.max(abs(coverage-1))<1e-12 and mask.dtype==bool and
        mask.shape==(len(parents),),'Positive complete source-face coverage required')
    equal(ff[0],np.arange(len(parents)*3,dtype='i8').reshape(-1,3),'literal child corner order')
    nv={k:np.einsum('fci,fij->fcj',w,base[k][parents]) for k in ('positions','normals','uvGltf','uvNative','tangents')}
    for key,value in [('connectorParentPositions',nv['positions']),('connectorParentNormals',nv['normals']),
        ('uvGltf',nv['uvGltf']),('uvNative',nv['uvNative'])]:equal(z[key],value,key)
    j=z['connectorJacobianLocalCorners']
    require(j.shape==(len(parents),3,3,3) and j.dtype==np.dtype('f8') and np.isfinite(j).all() and
        (np.linalg.det(j)>0).all(),'Finite proper native Jacobians required')
    edited=np.any(z['positions']!=nv['positions'],axis=2).reshape(-1)
    n,t=transport(nv['normals'].reshape(-1,3),nv['tangents'].reshape(-1,4),j.reshape(-1,3,3),edited)
    n=n.reshape(z['normals'].shape);t=t.reshape(z['tangents'].shape)
    n[mask]=nv['normals'][mask];t[mask]=nv['tangents'][mask]
    equal(n,z['normals'],'native inv-J N arithmetic');equal(t,z['tangents'],'native sum-projection T/W arithmetic')
    for k in ('positions','normals','tangents'):equal(z[k][mask],nv[k][mask],'protected native '+k)
    before={'POSITION':nv['positions']@B,'NORMAL':nv['normals']@B,'TEXCOORD_0':nv['uvGltf']}
    after={'POSITION':z['positions']@B,'NORMAL':z['normals']@B,'TEXCOORD_0':z['uvGltf']}
    for group,t0 in ((before,nv['tangents']),(after,z['tangents'])):
        group['TANGENT']=t0.copy();group['TANGENT'][:,:,:3]=group['TANGENT'][:,:,:3]@B
    if complement:
        u=z['uvNative'].copy();u[:,:,1]=1-u[:,:,1]
        equal(u.astype('<f4'),aa[0]['TEXCOORD_0'][ff[0]],'encoded native-to-GLTF complement')
        for sem,key in (('POSITION','positions'),('NORMAL','normals')):
            equal((z[key]@B).astype('<f4'),aa[0][sem][ff[0]],'literal native nearest-f32 '+sem)
        tt=z['tangents'].copy();tt[:,:,:3]=tt[:,:,:3]@B
        equal(tt.astype('<f4'),aa[0]['TANGENT'][ff[0]],'literal native nearest-f32 T/W')
    else:
        for sem in sorted(before):
            raw=raw_bary(old[0][sem],oldf[0],parents,w);delta=after[sem]-before[sem];expected=(raw+delta).astype('<f4')
            zero=np.all(delta==0,axis=2);expected[zero]=raw.astype('<f4')[zero];expected[mask]=raw.astype('<f4')[mask]
            equal(expected,aa[0][sem][ff[0]],'literal raw source bary+native delta '+sem)
    return {'rawPNUTBytesExact':True,'nativeTransportBytesExact':True,'fullPositiveSourceCoverage':True,
        'originalStructuralBound':1e-12,'protectedWholeFaces':int(mask.sum()),
        'sampledUV':'Current decoded GLB UV; original-double UV is independent lineage.'}


def pelvis(z,base,aa,ff,old,oldf,line,cfg):
    require(len(aa)==len(old)==1,'One pelvis primitive required')
    equal(z['connectorParentFaces'],oldf[0],'pelvis original parent indices')
    raw=old[0]
    planes=cfg['subdivisionPlanesLocalZMetres']
    require(len(planes)==len(line['steps'])==6 and planes[0]==cfg['planeLocalZMetres'] and
        planes[-1]==cfg['fullScaleLocalZMetres'] and line.get('previewNativeBarycentricDifferenceExplicit') is True,
        'Six explicitly dual-representation pelvis splits required')
    names=('positions','normals','uvGltf','uvNative','tangents')
    split=subdivide(raw,oldf[0],planes,{k:base[k] for k in names})
    require(split['steps']==line['steps'] and split['originalRowCount']==line['originalRowCount'],'Exact sequential plane/edge/rounding lineage differs')
    for key,value in [('connectorSplitFaces',split['faces']),('connectorParentFaceIds',split['parentFaceIds']),
        ('connectorBarycentricPreview',split['barycentric']),('connectorBarycentricNative',split['nativeBarycentric']),
        ('connectorLowerFaceMask',split['lowerFaceMask'])]:equal(z[key],value,key)
    require(np.array_equal(np.unique(split['parentFaceIds']),np.arange(len(oldf[0]))),'Pelvis omitted original faces')
    equal(ff[0],split['faces'],'pelvis literal split indices')
    raw=split['attributes'];local=raw['POSITION'].astype(float)@B.T;plane=float(np.float32(cfg['planeLocalZMetres']))
    q,j=upper_field(local,plane,cfg['fullScaleLocalZMetres'],cfg['centreLocalXYMetres'],cfg['endXYScale'])
    referenced=np.zeros(len(local),bool);referenced[np.unique(ff[0])]=True;q[~referenced]=local[~referenced];j[~referenced]=np.eye(3)
    edited=referenced&np.any(q!=local,axis=1)
    equal(j,z['connectorJacobianLocal'],'raw pelvis J');equal(edited,z['connectorEditedVertexMask'],'pelvis edited mask')
    n0=raw['NORMAL'].astype(float)@B.T;t0=raw['TANGENT'].astype(float).copy();t0[:,:3]=t0[:,:3]@B.T
    n,t=transport(n0,t0,j,edited);expected={k:v.copy() for k,v in raw.items()}
    expected['POSITION'][edited]=(q[edited]@B).astype('<f4');expected['NORMAL'][edited]=(n[edited]@B).astype('<f4')
    tt=t.copy();tt[:,:3]=tt[:,:3]@B;expected['TANGENT'][edited]=tt[edited].astype('<f4')
    for sem,value in expected.items():equal(value,aa[0][sem],'pelvis raw rounded '+sem)
    nv=split['nativeValues'];p0=nv['positions'].reshape(-1,3)
    nq,nj=upper_field(p0,plane,cfg['fullScaleLocalZMetres'],cfg['centreLocalXYMetres'],cfg['endXYScale'])
    ne=np.any(nq!=p0,axis=1);nn,nt=transport(nv['normals'].reshape(-1,3),nv['tangents'].reshape(-1,4),nj,ne)
    for key,value in [('positions',nq.reshape(nv['positions'].shape)),('normals',nn.reshape(nv['normals'].shape)),
        ('tangents',nt.reshape(nv['tangents'].shape)),('uvGltf',nv['uvGltf']),('uvNative',nv['uvNative'])]:equal(z[key],value,'sequential native '+key)
    for sem in expected:equal(expected[sem][ff[0][split['lowerFaceMask']]],raw[sem][ff[0][split['lowerFaceMask']]],'protected pelvis '+sem)
    return {'rawPNUTBytesExact':True,'sequentialNativePNUTBytesExact':True,'sixFloat32PlaneSplitsExact':True,
        'rawJacobianEditedMaskExact':True,'fullOriginalFaceInventory':True}


def mirror_parent(parent,left,aa,ff,old,oldf,target,config):
    part=parent['part'];sourcepart=left['part']
    require(part=='legr' and sourcepart=='legl' and parent['operation']=='mirror','Opposite thigh parent required')
    source_frame=c.frame(target,c.PART_JOINTS[sourcepart],'working')
    target_frame=c.frame(target,c.PART_JOINTS[part],'working')
    for frame in (source_frame,target_frame):
        require(frame.shape==(4,4) and np.isfinite(frame).all() and
            np.array_equal(frame[3],[0.,0.,0.,1.]) and
            np.allclose(frame[:3,:3].T@frame[:3,:3],np.eye(3),rtol=0,atol=1e-10) and
            abs(np.linalg.det(frame[:3,:3])-1)<1e-10,'Original proper rigid stock-frame bound differs')
    plane=config.get('mirrorPlaneWorldX')
    require(config.get('kind')=='target-thigh-width-diagnostic' and
        type(config.get('schemaVersion')) is int and config['schemaVersion']==2 and
        config.get('widthFactor')==.78 and type(plane) in (int,float) and np.isfinite(plane) and
        abs(plane-(source_frame[0,3]+target_frame[0,3])/2)<1e-12,
        'Pinned original thigh stock-midplane configuration required')
    # Replay the original Householder arithmetic, including negative-zero translation bytes.
    normal=np.array([1.,0.,0.]);origin=np.array([plane,0.,0.])
    normal=normal/np.linalg.norm(normal)
    reflection=np.eye(4);reflection[:3,:3]-=2*np.outer(normal,normal)
    reflection[:3,3]=2*normal*np.dot(normal,origin)
    declared=np.asarray(parent['reflectionWorld'],float)
    equal(declared,reflection,'independently derived configured stock reflection')
    require(np.array_equal(reflection[3],[0.,0.,0.,1.]) and
        np.array_equal(reflection[:3,:3].T@reflection[:3,:3],np.eye(3)) and
        np.linalg.det(reflection[:3,:3])==-1,'Affine orthogonal unit stock reflection required')
    matrix=np.asarray(parent['proof']['sourceToRightLocal'],float)
    expected=np.linalg.inv(target_frame)@reflection@source_frame
    equal(matrix,expected,'actual opposite-frame parent')
    require(len(aa)==len(old)==1,'One mirror parent primitive required')
    equal(ff[0],oldf[0][:,[0,2,1]],'single mirror winding reversal')
    for sem,val in old[0].items():
        if sem=='TEXCOORD_0':out=val
        else:
            out=val.astype(float).copy();v=(out[:,:3]@B.T)@matrix[:3,:3].T
            if sem=='POSITION':v+=matrix[:3,3]
            out[:,:3]=v@B
            if sem=='TANGENT':out[:,3]*=-1
            out=out.astype('<f4')
        equal(out,aa[0][sem],'opposite-frame raw '+sem)
    return matrix



ANCESTOR_KIND = 'target-source-representation-ancestor-contract'


def ancestor_contract(row, *, bank_pin, verified, target_path, target):
    """Read-only receipt-scoped history; never extend global adoption mappings."""
    cp,ch=pin(row);require(c.sha(cp)==ch,'Ancestor contract changed');cfg=read_json(cp)
    fields={'schemaVersion','kind','operation','verificationApplications','targetContract',
            'targetId','rigRevision','coordinateSpace','adoptionProof','receipts'}
    require(set(cfg)==fields and type(cfg['schemaVersion']) is int and cfg['schemaVersion']==1 and
        cfg['kind']==ANCESTOR_KIND and cfg['operation']=='verify-receipt-scoped-ancestors-v1' and
        type(cfg['verificationApplications']) is int and cfg['verificationApplications']==1,
        'Typed singular ancestor contract required')
    require(cfg['targetContract']=={'path':str(target_path),'sha256':c.sha(target_path)} and
        cfg['targetId']==target['id'] and cfg['rigRevision']==target['rig']['revision'] and
        cfg['coordinateSpace']=='working' and cfg['adoptionProof']==bank_pin,
        'Ancestor target/rig/space/bank differs')
    require(isinstance(cfg['receipts'],list) and cfg['receipts'],'Explicit ancestor receipts required')
    inputs={cp:ch};receipts={};scopes={};physical={};evidence=[]
    global_map={}
    for rows,key in ((verified.helperResolutions,'archivedCopy'),(verified.assetResolutions,'resolvedCopy')):
        for item in rows:
            p,h=pin(adoption.plain(item['originalClaimedSource']))
            global_map[p,h]=adoption.plain(item[key])
    repo=Path(__file__).resolve().parents[2];live=repo/'tools'/'phenotypes'/'target_part_pipeline.py'
    def checked(row):
        p,h=pin(row);require(c.sha(p)==h,'Ancestor input changed: '+p)
        require(p not in inputs or inputs[p]==h,'Conflicting ancestor physical input')
        inputs[p]=h;return Path(p)
    for declaration in cfg['receipts']:
        require(isinstance(declaration,dict) and set(declaration)=={'receipt','historicalPipeline'},
            'Exact receipt-scoped declaration required')
        rp=checked(declaration['receipt']);name=str(rp)
        require(name not in receipts,'Duplicate ancestor receipt')
        rec=read_json(rp)
        require(rec.get('kind')=='target-part-geometry' and type(rec.get('schemaVersion')) is int and
            rec['schemaVersion']==2 and rec.get('operation') in
            ('fit','mirror','bone-axis-width-affine','detached-component-removal','measured-angular-profile-ankle-taper') and
            rec.get('diagnosticOnly') is True,'Narrow typed working ancestor geometry required')
        c.verify_binding(rec,target_path,target,'working');part=rec['part']
        require(part in c.BODY_PARTS and rec['joint']==c.PART_JOINTS[part] and
            rec['model']==c.model(target,part) and rec['attachmentWorld']==c.frame(target,c.PART_JOINTS[part],'working').tolist() and
            type(rec['statureApplications']) is int and rec['statureApplications']==0,
            'Ancestor ownership/frame/conversion differs')
        require(isinstance(rec['frozenInputs'],dict) and rec['frozenInputs'],'Nonempty ancestor closure required')
        originals=dict(rec['frozenInputs'])
        require(originals.get(str(target_path))==c.sha(target_path),'Ancestor closure must pin the exact target')
        for key in ('source','sourceReceipt'):
            require(originals.get(rec[key])==rec[key+'Sha256'],'Ancestor original source closure differs')
        scoped=declaration['historicalPipeline'];replacement=None
        if scoped is not None:
            require(isinstance(scoped,dict) and set(scoped)=={'originalClaimedSource','preservationManifest',
                'actualArchivedSourcePath','archivedCopy','size'},'Exact historical pipeline association required')
            op,oh=pin(scoped['originalClaimedSource'])
            require(Path(op)==live and originals.get(op)==oh,
                'Only this receipt original pipeline claim may map')
            manifest_path=checked(scoped['preservationManifest']);manifest=read_json(manifest_path)
            require(manifest.get('kind')=='pre-main-adoption-recoverable-byte-copy' and
                manifest.get('copiesIndependentlyHashVerified') is True and
                manifest.get('sourceWorktreeResetOrClean') is False and
                manifest_path.is_relative_to(repo) and isinstance(manifest.get('files'),list),
                'Verified local preservation manifest required')
            actual=scoped['actualArchivedSourcePath']
            require(isinstance(actual,str) and Path(actual).is_absolute() and Path(actual).is_relative_to(repo) and
                Path(actual).name==live.name,'Explicit same-name historical source identity required')
            rows=[item for item in manifest['files'] if item.get('source')==actual]
            require(len(rows)==1,'Unique exact historical preservation row required');saved=rows[0]
            ap,ah=pin(scoped['archivedCopy'])
            require(saved=={'source':actual,'relative':Path(actual).relative_to(repo).as_posix(),
                'copy':ap,'size':scoped['size'],'sha256':oh,'role':saved.get('role')} and
                saved['role'] in ('modifiedTracked','untracked','ignoredAssetOrEvidence') and
                type(scoped['size']) is int and scoped['size']>=0 and ah==oh and
                Path(ap).parent==manifest_path.parent/'files' and
                len(Path(ap).stem)==8 and Path(ap).stem.isdigit() and Path(ap).suffix=='.bin',
                'Historical association differs from preserved row')
            ap=checked(scoped['archivedCopy']);require(ap.stat().st_size==scoped['size'],'Historical copy size differs')
            replacement={'path':str(ap),'sha256':oh}
        resolved={}
        for p,h in originals.items():
            p,h=pin({'path':p,'sha256':h})
            if Path(p)==live and replacement is not None:
                require(replacement['sha256']==h,'Receipt-scoped pipeline digest differs')
                actual=replacement
            else:
                actual=global_map.get((p,h),{'path':p,'sha256':h})
            fp=checked(actual);resolved[p,h]={'path':str(fp),'sha256':h}
        for item in (declaration['receipt'],{'path':rec['candidate'],'sha256':rec['candidateSha256']},rec['nativeCornerArchive']):
            p,h=pin(item);fp=checked(item);originals[p]=h;resolved[p,h]={'path':str(fp),'sha256':h}
        receipts[name]=rec;scopes[name]=originals
        for key,value in resolved.items():
            require(key not in physical or physical[key]==value,'Conflicting scoped ancestor physical copy')
            physical[key]=value
        evidence.append({'receipt':declaration['receipt'],'originalClosure':originals,
            'historicalPipeline':scoped,'originalReceiptsRewritten':False,'historicalHelpersExecuted':False})
    return receipts,scopes,physical,inputs,{'contract':row,'receipts':evidence,'assetOperations':[]}


def width_transport(normals,tangents,matrix):
    """Frozen original width arithmetic, independently code-bound here."""
    length=np.linalg.norm(normals,axis=-1);nn=normals@np.linalg.inv(matrix)
    nn*=(length/np.linalg.norm(nn,axis=-1))[...,None]
    tt=tangents.copy();unit=nn/length[...,None];v=tangents[...,:3]@matrix.T
    v-=np.sum(v*unit,axis=-1)[...,None]*unit
    v*=(np.linalg.norm(tangents[...,:3],axis=-1)/np.linalg.norm(v,axis=-1))[...,None]
    tt[...,:3]=v
    return nn,tt


def width_parent(parent,prior,aa,ff,old,oldf,native,base,target,configuration,target_path):
    require(parent['part']=='legl' and parent['operation']=='bone-axis-width-affine' and
        prior['part']=='legl' and prior['operation']=='fit' and parent['proof']['widthFactor']==.78,
        'One original width78 left ancestor required')
    require(configuration.get('kind')=='target-thigh-width-diagnostic' and
        type(configuration.get('schemaVersion')) is int and configuration['schemaVersion']==2 and
        configuration.get('widthFactor')==.78 and configuration.get('targetContract')==str(target_path) and
        configuration.get('targetContractSha256')==c.sha(target_path) and
        configuration.get('parentReceipt')==parent['sourceReceipt'] and
        configuration.get('parentReceiptSha256')==parent['sourceReceiptSha256'],
        'Pinned width configuration ancestry differs')
    hip=c.frame(target,'lthigh_g','working');knee_frame=c.frame(target,'lshin_g','working')
    shaft=(np.linalg.inv(hip)@knee_frame)[:3,3];u=shaft/np.linalg.norm(shaft)
    hint=hip[:3,:3].T@np.array([1.,0,0]);axis=hint-hint.dot(u)*u
    require(np.linalg.norm(shaft)>1e-8 and np.linalg.norm(axis)>1e-8,'Measured width axes degenerate')
    axis/=np.linalg.norm(axis);matrix=np.eye(3)+(.78-1)*np.outer(axis,axis)
    for actual in (parent['proof']['matrixLocal'],configuration['matrixLocal']):
        equal(np.asarray(actual,float),matrix,'stock-derived width78 matrix')
    for actual in (parent['proof']['widthAxisLocal'],configuration['widthAxisLocal']):
        equal(np.asarray(actual,float),axis,'stock-derived width78 axis')
    require(len(aa)==len(old)==1,'One width ancestor primitive required')
    equal(ff[0],oldf[0],'width original triangle order')
    raw=old[0];p=raw['POSITION'].astype(float)@B.T;n=raw['NORMAL'].astype(float)@B.T
    t=raw['TANGENT'].astype(float).copy();t[:,:3]=t[:,:3]@B.T
    nn,tt=width_transport(n,t,matrix);tt[:,:3]=tt[:,:3]@B
    expected={'POSITION':(p@matrix.T+np.zeros(3))@B,'NORMAL':nn@B,
        'TANGENT':tt,'TEXCOORD_0':raw['TEXCOORD_0']}
    for sem,value in expected.items():equal(value.astype('<f4'),aa[0][sem],'width original raw '+sem)
    nn,tt=width_transport(base['normals'],base['tangents'],matrix)
    for key,value in [('positions',base['positions']@matrix.T+np.zeros(3)),('normals',nn),
        ('tangents',tt),('uvGltf',base['uvGltf']),('uvNative',base['uvNative'])]:
        equal(native[key],value,'width separate native '+key)
    return {'rawWidthPNUTBytesExact':True,'nativeWidthPNUTBytesExact':True,'widthFactor':.78}


def mirror_native(matrix,native,base):
    order=[0,2,1];m=matrix[:3,:3];t=base['tangents'].copy()
    t[:,:,:3]=t[:,:,:3]@m.T;t[:,:,3]*=-1
    for key,value in [('positions',base['positions']@m.T+matrix[:3,3]),('normals',base['normals']@m.T),
        ('tangents',t),('uvGltf',base['uvGltf']),('uvNative',base['uvNative'])]:
        equal(native[key],value[:,order],'opposite-frame separate native '+key)
    return {'nativeMirrorPNUTBytesExact':True,'triangleCornerOrder':[0,2,1],'tangentWFlipsExactly':True}


@dataclass(frozen=True,init=False)
class VerifiedRepresentation:
    _seal: object
    _proof: object
    _arrays: object
    _inputs: object

    @property
    def proof(self):return self._proof

    @property
    def inputs(self):return self._inputs

    def verify(self):
        require(getattr(self,'_seal',None) is _SEAL,'Unverified representation object')
        for p,h in self._inputs.items():require(c.sha(p)==h,'Representation input changed: '+p)

    def array(self,name):
        self.verify();row=self._arrays[name]
        return np.frombuffer(row['bytes'],dtype=row['dtype']).reshape(row['shape'])


def verify_source_representation(contract_pin, *, target_path, target, part, space):
    """One explicit working-space contract; no asset/file-writing entrypoint."""
    cp,ch=pin(contract_pin);require(c.sha(cp)==ch,'Representation contract changed');cfg=read_json(cp)
    require(set(cfg)==_FIELDS and type(cfg['schemaVersion']) is int and cfg['schemaVersion']==1 and cfg['kind']==KIND and
        cfg['operation']==OPERATION and type(cfg['verificationApplications']) is int and cfg['verificationApplications']==1,'Typed singular representation contract required')
    require(space=='working' and cfg['coordinateSpace']==space and cfg['part']==part and part in c.BODY_PARTS and
        cfg['joint']==c.PART_JOINTS[part] and cfg['model']==c.model(target,part) and type(cfg['statureApplications']) is int and cfg['statureApplications']==0,
        'Representation part/frame/space/conversion differs')
    tp=Path(target_path).resolve()
    require(cfg['targetContract']=={'path':str(tp),'sha256':c.sha(tp)} and target==c.load(tp) and
        cfg['targetId']==target['id'] and cfg['rigRevision']==target['rig']['revision'],'Target/rig differs')
    require(cfg['protocol'] in PROTOCOLS,'Unsupported named equation')
    repo=Path(__file__).resolve().parents[2];read_json(pin(cfg['adoptionProof'])[0]);verified=adoption.verify_proof(cfg['adoptionProof'],repo=repo)
    code={};helpers=current_helper_paths();bank=Path(__file__).resolve().parent
    supporting={str(p) for p in helpers if p.parent!=bank}
    require(isinstance(cfg['currentCodeSupport'],dict) and set(cfg['currentCodeSupport'])==supporting,
        'Exact outside-bank current supporting import inventory required')
    for p in helpers:
        expected=(verified.proof['currentHelpers'].get(str(p)) if p.parent==bank else
                  cfg['currentCodeSupport'].get(str(p)))
        pin({'path':str(p),'sha256':expected})
        require(expected==c.sha(p),'Current code missing/stale: '+str(p));code[str(p)]=expected
    require(cfg['inputReceipts']==[cfg['geometryReceipt']],'Global execution scope is exactly the current bank receipt')
    ctx=execution.prepare_execution_adoption(cfg['adoptionProof'],target_path=tp,target=target,space=space,
        consumer='target_part_pipeline.verify_source_receipt',receipt_pins=cfg['inputReceipts'])
    claims={};receipts={}
    def claim(row):
        p,h=pin(row);require(p not in claims or claims[p]==h,'Conflicting original source claim');claims[p]=h
    for row in cfg['inputReceipts']:
        name,_=pin(row);r=read_json(name)
        pipeline.verify_source_receipt(Path(r['candidate']),Path(name),tp,target,r['part'],space,execution_adoption=ctx)
        receipts[name]=r
        for p,h in r['frozenInputs'].items():claim({'path':p,'sha256':h})
        for item in (row,{'path':r['candidate'],'sha256':r['candidateSha256']},r['nativeCornerArchive']):claim(item)
    direct=cfg['protocol'] in ('literal-exact-v1','absent-authored-tangent-direct-encoded-v1')
    ancestors={};scopes={};ancestor_physical={};ancestor_inputs={};ancestor_evidence=None
    if direct:
        require(cfg['ancestorContract'] is None,'Direct representation cannot import ancestor scope')
    else:
        require(cfg['ancestorContract'] is not None,'Separate exact ancestor contract required')
        ancestors,scopes,ancestor_physical,ancestor_inputs,ancestor_evidence=ancestor_contract(
            cfg['ancestorContract'],bank_pin=cfg['adoptionProof'],verified=verified,target_path=tp,target=target)
        require(not set(ancestors)&set(receipts),'Ancestor scope cannot repeat current bank receipt')
        receipts.update(ancestors)
    allowed=set(claims.items())|{(p,h) for scope in scopes.values() for p,h in scope.items()}
    mapping={}
    for rows,key in ((verified.helperResolutions,'archivedCopy'),(verified.assetResolutions,'resolvedCopy')):
        for row in rows:mapping[pin(adoption.plain(row['originalClaimedSource']))]=adoption.plain(row[key])
    physical={}
    def path(row):
        p,h=pin(row);m=ancestor_physical.get((p,h),mapping.get((p,h)))
        require((p,h) in allowed and (m is None or m['sha256']==h),'Undeclared source or replacement digest')
        actual=Path(m['path']) if m else Path(p).resolve()
        require(c.sha(actual)==h,'Stale physical representation source');physical[str(actual)]=h;return actual
    rn,_=pin(cfg['geometryReceipt']);require(rn in receipts,'Current receipt outside requested scope');r=receipts[rn]
    require(r['part']==part and r.get('operation')!='runtime' and
        cfg['candidate']=={'path':r['candidate'],'sha256':r['candidateSha256']} and cfg['nativeCornerArchive']==r['nativeCornerArchive'],
        'Current candidate/archive/receipt differs')
    bank=read_json(verified.proof['originalBank']['path'])
    require(bank['parts'][part]['geometry']==cfg['geometryReceipt'] and bank['parts'][part]['candidate']==cfg['candidate'],
        'Current input is not the pinned unchanged bank')
    inputs=cfg['protocolInputs'];direct=cfg['protocol'] in ('literal-exact-v1','absent-authored-tangent-direct-encoded-v1')
    wanted={'parentCandidate'} if direct else {'parentCandidate','parentGeometryReceipt','parentNativeCornerArchive','sourceLineage'}
    if cfg['protocol']=='original-source-barycentric-plus-native-field-delta-v1':
        wanted.update(('widthSource','widthConfiguration'))
        if part=='legr':wanted.update(('mirrorSource','mirrorConfiguration'))
    require(isinstance(inputs,dict) and set(inputs)==wanted,'Exact named equation input inventory required')
    # These are outputs owned by the pinned current receipt, not historical frozen inputs.
    owned_outputs={}
    if not direct:
        pelvis_protocol=cfg['protocol']=='sequential-plane-split-raw-field-v1'
        field='splitLineage' if pelvis_protocol else 'lineage'
        operation=('face-aware-pelvis-upper-connector-plane-subdivision' if pelvis_protocol else
            'measured-convex-knee-endpoint-source-face-subdivision')
        owners=(('pelvis',) if pelvis_protocol else ('shinl','shinr') if
            cfg['protocol']=='native-v-complement-f32-v1' else ('legl','legr'))
        require(r.get('operation')==operation and part in owners,
            'Receipt-owned lineage operation/part differs')
        output=r.get(field);p,h=pin(output)
        require(inputs.get('sourceLineage')==output,'Receipt-owned source lineage pin differs')
        require(all(ep!=p or eh==h for ep,eh in allowed),
            'Conflicting receipt-owned lineage digest')
        allowed.add((p,h));owned_outputs[field]=dict(output)
    for k,row in inputs.items():
        values=row.values() if k in ('mirrorSource','widthSource') else [row]
        if k in ('mirrorSource','widthSource'):require(set(row)=={'candidate','geometryReceipt','nativeCornerArchive'},'Ancestor source inventory differs')
        for item in values:
            p,h=pin(item);require((p,h) in allowed,'Equation input outside exact scoped original closure')
    require(cfg['sourceClosure']==claims,'Requested current original closure differs')
    expected_ancestors=set()
    if not direct:
        expected_ancestors.add(pin(inputs['parentGeometryReceipt'])[0])
        for key in ('mirrorSource','widthSource'):
            if key in inputs:expected_ancestors.add(pin(inputs[key]['geometryReceipt'])[0])
    require(set(ancestors)==expected_ancestors,'Exact required ancestor receipt inventory differs')
    d,b=glb(path(cfg['candidate']));aa,ff,inventory=mesh(d,b);encoded=corners(aa,ff)
    def archive(row):
        with np.load(path(row),allow_pickle=False) as z:out={k:z[k].copy() for k in z.files}
        require(all(np.isfinite(v).all() for v in out.values() if v.dtype.kind in 'fiu'),'Nonfinite archive')
        count=len(out.get('positions',[]))
        require(count>0,'Nonempty native-double corner archive required')
        for name,width in (('positions',3),('normals',3),('uvGltf',2),('uvNative',2)):
            value=out.get(name)
            require(isinstance(value,np.ndarray) and value.dtype==np.dtype('f8') and
                value.shape==(count,3,width),'Exact native-double archive field required: '+name)
        require((np.linalg.norm(out['normals'],axis=2)>0).all(),'Nonzero original native normals required')
        value=tangent(out)
        if value is not None:
            require(value.dtype==np.dtype('f8') and value.shape==(count,3,4) and
                (np.linalg.norm(value[:,:,:3],axis=2)>0).all() and
                np.isin(value[:,:,3],[-1.,1.]).all(),'Exact native-double authored T/sign inventory required')
        if 'primitiveIds' in out:
            require(out['primitiveIds'].dtype==np.dtype('i8') and out['primitiveIds'].shape==(count,),
                'Exact int64 native primitive inventory required')
        return out
    z=archive(cfg['nativeCornerArchive'])
    require(inputs['parentCandidate']=={'path':r['source'],'sha256':r['sourceSha256']},'Immediate source differs')
    old,ob=glb(path(inputs['parentCandidate']),detached=not direct);preserved=preservation(d,b,old,ob)
    source_primitives=[p for m in old.get('meshes',[]) for p in m['primitives']]
    require(source_primitives and all('COLOR_0' not in p.get('attributes',{}) for p in source_primitives),
        'Original COLOR0 source is unsupported by this narrow PNUT protocol')
    if direct:
        for k in ('positions','normals','uvGltf','uvNative'):equal(z[k].astype('<f4'),encoded[k].astype('<f4'),'literal '+k)
        t=tangent(z)
        if cfg['protocol']=='absent-authored-tangent-direct-encoded-v1':
            require(part in ('chest','handl','handr') and t is None and 'tangents' not in encoded and
                all('TANGENT' not in p['attributes'] for m in old.get('meshes',[]) for p in m['primitives']),
                'Absent T must remain absent in source/candidate/archive')
        else:
            require(t is not None and 'tangents' in encoded and
                all('TANGENT' in p.get('attributes',{}) for p in source_primitives),
                'Literal protocol requires original authored T in every source/candidate/archive primitive')
            equal(t.astype('<f4'),encoded['tangents'].astype('<f4'),'literal T/sign')
        proof={'literalPNUTBytesExact':True,'authoredTangentStatus':'absent' if t is None else 'present'}
    else:
        pn,_=pin(inputs['parentGeometryReceipt']);require(pn in receipts,'Parent receipt outside scope');parent=receipts[pn]
        require(inputs['parentGeometryReceipt']=={'path':r['sourceReceipt'],'sha256':r['sourceReceiptSha256']} and
            inputs['parentCandidate']=={'path':parent['candidate'],'sha256':parent['candidateSha256']} and
            inputs['parentNativeCornerArchive']==parent['nativeCornerArchive'] and parent['part']==part,
            'Parent geometry/archive differs')
        base=archive(inputs['parentNativeCornerArchive']);old_a,old_f,_=mesh(old,ob);line=read_json(path(inputs['sourceLineage']))
        if cfg['protocol']=='sequential-plane-split-raw-field-v1':
            require(part=='pelvis' and r['operation']=='face-aware-pelvis-upper-connector-plane-subdivision' and
                inputs['sourceLineage']==r['splitLineage'],'Exact pelvis lineage required')
            proof=pelvis(z,base,aa,ff,old_a,old_f,line,r['connectorConfiguration'])
        else:
            allowed_parts=('shinl','shinr') if cfg['protocol']=='native-v-complement-f32-v1' else ('legl','legr')
            require(part in allowed_parts and r['operation']=='measured-convex-knee-endpoint-source-face-subdivision' and
                inputs['sourceLineage']==r['lineage'] and line.get('sourceGeometry')==inputs['parentGeometryReceipt'] and
                line.get('nativeSource')==inputs['parentNativeCornerArchive'] and line.get('originalSha256')==inputs['parentCandidate']['sha256'] and
                line.get('allSourceFacesRetained') is True,'Exact source-face ancestry required')
            if part in ('legl','legr'):
                wp=inputs['widthSource'];wn,_=pin(wp['geometryReceipt']);prior=receipts[wn]
                left=parent if part=='legl' else receipts[pin(inputs['mirrorSource']['geometryReceipt'])[0]]
                require(wp['candidate']=={'path':left['source'],'sha256':left['sourceSha256']} and
                    wp['geometryReceipt']=={'path':left['sourceReceipt'],'sha256':left['sourceReceiptSha256']} and
                    wp['nativeCornerArchive']==prior['nativeCornerArchive'],'Width source binding differs')
                wd,wb=glb(path(wp['candidate']));wa,wf,_=mesh(wd,wb);width_base=archive(wp['nativeCornerArchive'])
                mc=read_json(path(inputs['widthConfiguration']))
                if part=='legl':left_d,left_b,left_a,left_f,left_native=old,ob,old_a,old_f,base
                else:
                    left_d,left_b=glb(path(inputs['mirrorSource']['candidate']))
                    left_a,left_f,_=mesh(left_d,left_b);left_native=archive(inputs['mirrorSource']['nativeCornerArchive'])
                width_proof=width_parent(left,prior,left_a,left_f,wa,wf,left_native,width_base,target,mc,tp)
                preservation(left_d,left_b,wd,wb)
            if part=='legr':
                mp=inputs['mirrorSource'];mn,_=pin(mp['geometryReceipt']);require(mn in receipts,'Mirror source outside scope');left=receipts[mn]
                require(mp['candidate']=={'path':parent['source'],'sha256':parent['sourceSha256']} and
                    mp['geometryReceipt']=={'path':parent['sourceReceipt'],'sha256':parent['sourceReceiptSha256']} and
                    mp['nativeCornerArchive']==left['nativeCornerArchive'],'Mirror source binding differs')
                md,mb=glb(path(mp['candidate']));ma,mf,_=mesh(md,mb)
                require(inputs['mirrorConfiguration']==inputs['widthConfiguration'],'One pinned width/mirror configuration required')
                mc=read_json(path(inputs['mirrorConfiguration']))
                require(mc.get('targetContract')==str(tp) and mc.get('targetContractSha256')==c.sha(tp),
                    'Mirror configuration target differs')
                mirror_matrix=mirror_parent(parent,left,old_a,old_f,ma,mf,target,mc)
                mirror_proof=mirror_native(mirror_matrix,base,left_native);preservation(old,ob,md,mb)
            proof=knee(z,base,aa,ff,old_a,old_f,complement=cfg['protocol']=='native-v-complement-f32-v1')
            if part in ('legl','legr'):proof['widthAncestor']=width_proof
            if part=='legr':proof['mirrorAncestor']=mirror_proof
    if 'primitiveIds' in z:equal(z['primitiveIds'].astype('i8'),encoded['primitiveIds'],'primitive order')
    ctx.verify();physical.update(adoption.plain(verified.inputs));physical.update(ancestor_inputs);physical.update(code);physical[cp]=ch
    result=object.__new__(VerifiedRepresentation)
    arrays={k:MappingProxyType({'bytes':np.ascontiguousarray(v).tobytes(),'shape':v.shape,'dtype':v.dtype.str}) for k,v in encoded.items()}
    record={'schemaVersion':1,'kind':'verified-target-source-representation','contract':contract_pin,'protocol':cfg['protocol'],
        'targetContract':cfg['targetContract'],'targetId':cfg['targetId'],'rigRevision':cfg['rigRevision'],'part':part,'coordinateSpace':space,
        'candidate':cfg['candidate'],'originalGeometryReceipt':cfg['geometryReceipt'],'originalNativeCornerArchive':cfg['nativeCornerArchive'],
        'nativeDoubleLineageKeptSeparate':True,'sampledRepresentation':'Actual current decoded GLB fields; native UV is1-promote64(encodedV).',
        'protocolProof':proof,'preservation':preserved,'primitiveInventory':inventory,'currentCode':code,
        'reusedCurrentPureFunctions':['repair_target_pelvis_upper_connector.subdivide','repair_target_pelvis_upper_connector.upper_field','deform_target_terminal_envelope.transport'],
        'executionAdoption':adoption.plain(ctx.evidence()),'ancestorEvidence':ancestor_evidence,
        'receiptOwnedOutputs':owned_outputs,
        'historicalHelpersExecuted':False,'originalReceiptsRewritten':False,
        'assetOperations':[],'selected':False,'clientAccepted':False}
    for key,value in {'_seal':_SEAL,'_proof':adoption.immutable(record),'_arrays':MappingProxyType(arrays),'_inputs':adoption.immutable(physical)}.items():object.__setattr__(result,key,value)
    result.verify();return result
