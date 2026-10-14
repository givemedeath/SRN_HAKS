"""PhenoMorpher editable scenes with recoverable NWN topology/UV lineage.

Native offsets are owned by the existing constrained attribute decoder. ASCII
uses the existing node/array parser and complete hierarchy evaluator. Unsupported
attributes remain unavailable, rather than receiving fabricated source values.
"""
import hashlib,json,re,struct
from pathlib import Path
import numpy as np
from .audit_geometry import arrays
from .retarget import NODE
from .silhouette_model import decode,frames,ascii_model
from .target_contract import PART_JOINTS

def require(value,message):
    if not value:raise ValueError(message)
def pin(path):
    p=Path(path).resolve();return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}

def native_attributes(data,model,expected_meshes):
    """Reachable rigid trees, after silhouette_model's complete static validation.

    Attribute fields follow audit_target_native_part and the existing
    prepare_target_native_material_preview.stock_neck_decode, including the
    packed UINT32 color pointer at 0x248. Packed colors are opaque source
    lineage, never interpreted as display RGBA or silently discarded.
    """
    require(len(data)>=12+0xe8,'Truncated native header')
    zero,raw_offset,raw_size=struct.unpack_from('<III',data)
    require(zero==0 and 12+raw_offset+raw_size==len(data),'Complete native sections required')
    end=12+raw_offset
    def region(off,size):
        require(off>=0 and size>=0 and 12+off+size<=end,'Native model section bounds exceeded')
        return 12+off
    def u32(at):
        require(12<=at and at+4<=end,'Native field bounds exceeded')
        return struct.unpack_from('<I',data,at)[0]
    def array(at,width):
        require(at+12<=end,'Native array header bounds exceeded')
        off,n,cap=struct.unpack_from('<III',data,at)
        require(n<=cap,'Native array capacity differs');region(off,n*width)
        return off,n
    root=u32(12+0x48);pending=[root];seen=set();names=set();records={}
    while pending:
        off=pending.pop();require(off not in seen and len(seen)<4096,'Native cycle/shared child')
        seen.add(off);at=region(off,0x70)
        blob=data[at+0x20:at+0x40];require(b'\0' in blob,'Unterminated node name')
        name=blob.split(b'\0',1)[0].decode('ascii').lower();require(name not in names,'Duplicate native node');names.add(name)
        flags=u32(at+0x6c);require(flags in (1,33,289),'Unsupported rigid native node')
        children,nchildren=array(at+0x48,4)
        pending.extend(u32(region(children+4*i,4)) for i in range(nchildren))
        if flags==1:continue
        region(off,0x264);face_off,nfaces=array(at+0x78,32)
        n,uv_count=struct.unpack_from('<HH',data,at+0x230)
        require(n>0 and nfaces>0 and uv_count<=1,'Nonempty at-most-one-UV native mesh required')
        decoded={};offsets={}
        for key,field,width,dtype in [('position',0x22c,3,'<f4'),('uv',0x234,2,'<f4'),('normal',0x244,3,'<f4'),('color',0x248,1,'<u4'),('tangent',0x258,3,'<f4'),('sign',0x260,1,'<f4')]:
            ptr=u32(at+field);offsets[key]=ptr
            if ptr==0xffffffff:
                require(key!='position','Missing source positions');continue
            require(ptr+n*width*4<=raw_size,'Native attribute raw bounds exceeded: '+key)
            value=np.frombuffer(data,dtype,n*width,end+ptr).reshape(n,width).copy()
            require(np.isfinite(value).all(),'Nonfinite native '+key);decoded[key]=value
        require(('tangent' in decoded)==('sign' in decoded),'Incomplete native tangent pair')
        if 'sign' in decoded:require(np.isin(decoded['sign'],[-1,1]).all(),'Invalid tangent sign')
        require(('uv' in decoded)==bool(uv_count),'Native UV inventory mismatch')
        f=np.ndarray((nfaces,3),dtype='<u2',buffer=data,offset=12+face_off+26,strides=(32,2)).copy()
        require(f.max()<n,'Native face index outside vertices');decoded['faces']=f
        slots=[]
        for i in range(4):
            b=data[at+0xe8+64*i:at+0xe8+64*(i+1)];require(b'\0' in b,'Unterminated texture slot');slots.append(b.split(b'\0',1)[0].decode('ascii'))
        decoded['layout']={'nodeAbsoluteOffset':at,'flags':flags,'vertices':n,'triangles':nfaces,'attributeOffsets':offsets,'faceOffset':face_off,'rawOffset':raw_offset,'rawSize':raw_size,'textureSlots':slots,'packedColorSemantics':'opaque UINT32 source values; display channel interpretation unavailable','attributeLayoutAuthority':'prepare_target_native_material_preview.stock_neck_decode + audit_target_native_part.decode'}
        records[name]=decoded
    require(model.lower() in names and set(records)==set(expected_meshes),'Complete source attribute mesh inventory differs')
    return records,None

def read_attributes(path):
    p=Path(path);before=pin(p);data=p.read_bytes();skeleton,geometry=decode(p);result={}
    if data[:4]==b'\0\0\0\0':
        roots=[n for n,r in skeleton.items() if r['parent']=='null'];require(len(roots)==1,'Unique native model root required')
        records,_=native_attributes(data,roots[0],{m['name'] for m in geometry})
        for mesh in geometry:
            a=records[mesh['name']];require(np.array_equal(mesh['faces'],a['faces']) and np.array_equal(mesh['position'],a['position'].astype(float)),'Native attribute/geometry decoder disagreement')
            row={**mesh,'material':a['layout']['textureSlots'],'sourceLayout':a['layout']}
            for key in ('normal','uv','tangent','sign','color'):
                if key in a:row[key]=a[key].copy() if key=='color' else a[key].astype(float)
            if 'uv' in row:row['uvFaces']=a['faces'].astype(int)
            row['unavailableSourceAttributes']=[k for k in ('normal','uv','tangent','sign','color') if k not in row]
            result[mesh['name']]=row
    else:
        text=data.decode('utf-8-sig');parsed={m[2].lower():m[3] for m in NODE.finditer(text.split('endmodelgeom',1)[0]) if m[1].lower() in ('trimesh','danglymesh')}
        for mesh in geometry:
            body=parsed[mesh['name']];f=np.asarray(arrays(body,'faces'),int);n=np.asarray(arrays(body,'normals'),float);uv=np.asarray(arrays(body,'tverts'),float)
            require(np.array_equal(f[:,:3],mesh['faces']),'ASCII geometry/attribute face mismatch')
            row={**mesh,'material':[m[1] for m in re.finditer(r'(?mi)^\s*(?:bitmap|materialname)\s+(\S+)',body)]}
            if n.size:
                require(n.shape==mesh['position'].shape and np.isfinite(n).all(),'Malformed authored normal array');row['normal']=n
            if uv.size:
                require(uv.ndim==2 and uv.shape[1]>=2 and f.shape[1]>=7 and np.isfinite(uv).all(),'Malformed authored UV array')
                require(f[:,4:7].min()>=0 and f[:,4:7].max()<len(uv),'UV face index outside source attributes');row.update(uv=uv[:,:2],uvFaces=f[:,4:7])
            row['unavailableSourceAttributes']=[k for k in ('normal','uv','tangent','sign') if k not in row]
            result[mesh['name']]=row
    require(pin(p)==before,'Source attributes changed while reading')
    return skeleton,result,before

def attach_source_attributes(source_assembled,candidate,spec,source_name_aliases=None):
    require(len(source_assembled)==len(candidate),'Candidate mesh inventory changed')
    rig,rig_attrs,rig_pin=read_attributes(spec['rig']);rig_world=frames(rig);cache={'rig':(rig_world,rig_attrs,rig_pin)}
    for part,path in spec['parts'].items():
        sk,attrs,p=read_attributes(path);cache[part]=(frames(sk),attrs,p)
    out=[];aliases=source_name_aliases or {}
    for s,c in zip(source_assembled,candidate):
        expected_source_name=aliases.get(c['name'],c['name'])
        require((s['part'],s['name'],s.get('render',True))==(c['part'],expected_source_name,c.get('render',True)) and np.array_equal(s['faces'],c['faces']) and s['position'].shape==c['position'].shape,'Source-owned topology/order changed')
        local,attrs,p=cache[s['part']];a=attrs[s['name']]
        transform=local[s['name']] if s['part']=='rig' else rig_world[PART_JOINTS[s['part']]]@local[s['name']]
        expected=a['position']@transform[:3,:3].T+transform[:3,3]
        require(np.allclose(expected,s['position'],atol=1e-12,rtol=0),'Complete source mesh transform differs')
        require(np.array_equal(a['faces'],s['faces']),'Source attribute topology differs')
        out.append({**c,'sourceAttributes':a,'sourceAttributePin':p,'sourceCompleteTransform':transform.tolist(),'sourceAttributeNodeName':s['name']})
    return out

def derived_normals(position,faces):
    p=np.asarray(position,float);f=np.asarray(faces,int);n=np.zeros_like(p);tri=p[f];fn=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0])
    for i in range(3):np.add.at(n,f[:,i],fn)
    size=np.linalg.norm(n,axis=1);referenced=np.zeros(len(p),bool);referenced[np.unique(f)]=True
    require(np.all(size[referenced]>1e-20),'Derived candidate normals unavailable at referenced degenerate/cancelling vertices')
    # Source topology has unused vertices. They retain exact geometry in the
    # companion archive but are not emitted through indexed GLB primitives.
    result=np.zeros_like(n);result[referenced]=n[referenced]/size[referenced,None]
    return result

def transform_normals(normals,matrix):
    transformed=np.asarray(normals,float)@np.linalg.inv(np.asarray(matrix,float)[:3,:3]);length=np.linalg.norm(transformed,axis=1)
    require(np.all(length>1e-20),'Zero transformed normal');return transformed/length[:,None]

def glb_document(meshes,world_frames,parents):
    """Rig nodes store local column-major matrices; each mesh owns one child node."""
    require(set(world_frames)==set(parents),'Complete rig hierarchy required')
    nodes=[];node_index={};roots=[];binary=bytearray();views=[];accessors=[];gmeshes=[]
    def accessor(values,component,kind,target=None):
        require(component in (5123,5125,5126),'Supported explicit GLB component type required')
        require(component!=5125 or target==34963,'UNSIGNED_INT only permitted for triangle indices')
        arr=np.asarray(values,dtype={5123:'<u2',5125:'<u4',5126:'<f4'}[component]);require(np.isfinite(arr).all(),'Nonfinite GLB attribute')
        require(len(arr)>0,'Nonempty GLB accessor required')
        while len(binary)%4:binary.append(0)
        offset=len(binary);binary.extend(arr.tobytes(order='C'));view={'buffer':0,'byteOffset':offset,'byteLength':arr.nbytes}
        if target:view['target']=target
        views.append(view);a={'bufferView':len(views)-1,'componentType':component,'count':len(arr),'type':kind}
        if kind in ('SCALAR','VEC3'):
            dims=arr.reshape(len(arr),-1);a['min']=dims.min(axis=0).tolist();a['max']=dims.max(axis=0).tolist()
        accessors.append(a);return len(accessors)-1
    for name,world in world_frames.items():
        parent=parents[name];require(parent=='null' or parent in world_frames,'Unresolved fitted rig parent')
        local=np.asarray(world,float) if parent=='null' else np.linalg.inv(np.asarray(world_frames[parent],float))@np.asarray(world,float)
        require(local.shape==(4,4) and np.isfinite(local).all(),'Invalid rig frame');node_index[name]=len(nodes);nodes.append({'name':name,'matrix':local.flatten(order='F').tolist(),'children':[],'extras':{'PhenoMorpherRole':'fitted-native-rig-frame'}})
    for name,parent in parents.items():
        if parent=='null':roots.append(node_index[name])
        else:nodes[node_index[parent]]['children'].append(node_index[name])
    for mesh in meshes:
        owner=mesh['name'] if mesh['part']=='rig' else PART_JOINTS[mesh['part']];require(owner in world_frames,'Mesh owner frame unavailable')
        world=np.asarray(world_frames[owner],float);inverse=np.linalg.inv(world);p=np.asarray(mesh['position']);local=p@inverse[:3,:3].T+inverse[:3,3];f=np.asarray(mesh['faces'],int)
        require(f.ndim==2 and f.shape[1]==3 and f.min()>=0 and f.max()<len(p),'Invalid mesh topology')
        a=mesh['sourceAttributes'];require(np.array_equal(a['faces'],f),'Attribute topology mismatch')
        uv=a.get('uv');uf=a.get('uvFaces');require((uv is None)==(uf is None),'Partial UV correspondence')
        pairs={};vi=[];ui=[];indices=[]
        for face_index,face in enumerate(f):
            row=[]
            for corner,v in enumerate(face):
                u=int(uf[face_index,corner]) if uf is not None else -1;key=(int(v),u)
                if key not in pairs:pairs[key]=len(vi);vi.append(int(v));ui.append(u)
                row.append(pairs[key])
            indices.append(row)
        vi=np.asarray(vi,int)
        require(len(vi)>0 and vi.max()<=2**24,'FLOAT32 vertex lineage index must remain exact')
        attributes={'POSITION':accessor(local[vi],5126,'VEC3',34962),
                    '_NWN_VERTEX_INDEX':accessor(vi,5126,'SCALAR',34962)}
        if mesh.get('render',True):
            normal_world=derived_normals(p,f);normal_local=transform_normals(normal_world[vi],inverse);attributes['NORMAL']=accessor(normal_local,5126,'VEC3',34962)
        if uv is not None:
            require(max(ui)<=2**24,'FLOAT32 UV lineage index must remain exact')
            attributes['TEXCOORD_0']=accessor(uv[np.asarray(ui)],5126,'VEC2',34962);attributes['_NWN_UV_INDEX']=accessor(ui,5126,'SCALAR',34962)
        if 'normal' in a:attributes['_NWN_AUTHORED_NORMAL']=accessor(a['normal'][vi],5126,'VEC3',34962)
        if 'tangent' in a:attributes['_NWN_AUTHORED_TANGENT']=accessor(a['tangent'][vi],5126,'VEC3',34962)
        if 'sign' in a:attributes['_NWN_AUTHORED_TANGENT_SIGN']=accessor(a['sign'][vi].reshape(-1),5126,'SCALAR',34962)
        if 'color' in a:
            color=np.asarray(a['color']);require(color.shape==(len(p),1) and color.dtype==np.dtype('<u4'),'Exact UINT32 source colors required')
            packed=color[vi].reshape(-1)
            halves=np.column_stack((packed&0xffff,packed>>16))
            attributes['_NWN_PACKED_COLOR_HALVES']=accessor(halves,5123,'VEC2',34962)
        primitive={'attributes':attributes,'indices':accessor(np.asarray(indices,np.uint32).reshape(-1),5125,'SCALAR',34963),'material':0 if mesh.get('render',True) else 1,'mode':4}
        extras={'NWNPart':mesh['part'],'NWNMeshNode':mesh['name'],'render':mesh.get('render',True),'sourcePin':mesh.get('sourceAttributePin'),
                'sourceVertexCount':len(p),'sourceFaceCount':len(f),'sourceOrderedFaces':f.tolist(),'sourceMaterials':a.get('material',[]),
                'UVSeamSplitsAreRepresentationOnly':True,'authoredNormalsPreservedInCustomAttribute':'_NWN_AUTHORED_NORMAL' in attributes,'authoredNormalBasis':'original source mesh-local coordinates',
                'sourceAttributeNodeName':mesh.get('sourceAttributeNodeName',mesh['name']),'gltfAttributesFloat32':True,'exactOriginalAttributes':'companion source-attributes NPZ retains original arrays without GLB float32 rounding',
                'lineageIndices':'exact integer FLOAT32 (bounded <=2^24)',
                'packedColorAttribute':'_NWN_PACKED_COLOR_HALVES: unsigned SHORT VEC2, not normalized; [low16,high16]; uint32 = low16 | (high16 << 16); no color-channel interpretation',
                'displayNormals':'derived from current candidate triangles, distinct from authored normals','texturesEmbedded':False,'productionAccepted':False}
        gmeshes.append({'name':mesh['part']+'::'+mesh['name'],'primitives':[primitive],'extras':extras})
        index=len(nodes);nodes.append({'name':mesh['part']+'::'+mesh['name'],'mesh':len(gmeshes)-1,'extras':extras});nodes[node_index[owner]]['children'].append(index)
    # glTF Y-up: NWN X/right,Z/up,-Y/forward. Right-handed determinant+1.
    conversion=np.array([[1,0,0,0],[0,0,1,0],[0,-1,0,0],[0,0,0,1]],float)
    nodes.append({'name':'PhenoMorpher NWN Z-up to glTF Y-up','matrix':conversion.flatten(order='F').tolist(),'children':roots})
    document={'asset':{'version':'2.0','generator':'PhenoMorpher v15'},'scene':0,'scenes':[{'nodes':[len(nodes)-1]}],
              'nodes':nodes,'meshes':gmeshes,'buffers':[{'byteLength':len(binary)}],'bufferViews':views,'accessors':accessors,
              'materials':[{'name':'Neutral clay','pbrMetallicRoughness':{'baseColorFactor':[.62,.65,.68,1.],'metallicFactor':0.,'roughnessFactor':.8},'doubleSided':True},
                           {'name':'Native nonrender node','pbrMetallicRoughness':{'baseColorFactor':[0,0,0,0],'metallicFactor':0.,'roughnessFactor':1.},'alphaMode':'BLEND','doubleSided':True}],
              'extras':{'editablePreviewOnly':True,'nativeAnimationsIncluded':False,'authoredUVsPreserved':True,'nativeValidated':False,'productionAccepted':False}}
    return document,bytes(binary)

def export_glb(meshes,world_frames,parents,path):
    p=Path(path);companion=p.with_suffix('.source-attributes.npz');require(not p.exists() and not companion.exists(),'Fresh GLB and attribute archive required')
    source_pins={r['sourceAttributePin']['path']:r['sourceAttributePin'] for r in meshes if r.get('sourceAttributePin')}
    for row in source_pins.values():require(pin(row['path'])==row,'Source attribute input changed before export')
    document,binary=glb_document(meshes,world_frames,parents)
    j=json.dumps(document,separators=(',',':')).encode();j+=b' '*((-len(j))%4);binary+=b'\0'*((-len(binary))%4)
    payload=struct.pack('<III',0x46546c67,2,12+8+len(j)+8+len(binary))+struct.pack('<II',len(j),0x4e4f534a)+j+struct.pack('<II',len(binary),0x004e4942)+binary
    p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(payload)
    archive_arrays={};inventory=[]
    for i,mesh in enumerate(meshes):
        keys={}
        for name in ('position','faces','normal','uv','uvFaces','tangent','sign','color'):
            if name in mesh['sourceAttributes']:
                key='mesh'+str(i)+'_'+name;archive_arrays[key]=np.asarray(mesh['sourceAttributes'][name]);keys[name]=key
        current_keys={}
        for name in ('position','faces'):
            key='mesh'+str(i)+'_current_'+name;archive_arrays[key]=np.asarray(mesh[name]);current_keys[name]=key
        owner=mesh['name'] if mesh['part']=='rig' else PART_JOINTS[mesh['part']]
        inventory.append({'part':mesh['part'],'node':mesh['name'],'sourceNode':mesh.get('sourceAttributeNodeName',mesh['name']),'arrays':keys,'currentGeometryArrays':current_keys,'currentGeometryBasis':'captured exact world geometry, including unused vertices','currentOwnerFrame':np.asarray(world_frames[owner]).tolist(),'sourcePin':mesh.get('sourceAttributePin'),'sourceCompleteTransform':mesh.get('sourceCompleteTransform')})
    archive_arrays['inventoryJSON']=np.frombuffer(json.dumps(inventory).encode('utf-8'),np.uint8)
    np.savez_compressed(companion,**archive_arrays)
    for row in source_pins.values():require(pin(row['path'])==row,'Source attribute input changed after export')
    return {**pin(p),'sourceAttributeArchive':pin(companion),'sourceInputs':list(source_pins.values()),'allSourceInputsUnchanged':True,'productionAccepted':False}
