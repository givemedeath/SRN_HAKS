"""Read-only native static equipment tree audit using pointer identities.

Native names are labels; child offsets identify the serialized hierarchy.
Constrained to static dummy/trimesh geometry, with no local animations.
"""
from collections import Counter
import struct
import numpy as np

GEOMETRY_LAYOUT='https://github.com/niv/nwn-tools/blob/master/_NwnLib/NwnMdlGeometry.h'
NODE_LAYOUT='https://github.com/niv/nwn-tools/blob/master/_NwnLib/NwnMdlNodes.h'


def require(value,message):
    if not value:raise ValueError(message)


def quaternion_matrix(value):
    q=np.asarray(value,float)
    require(q.shape==(4,) and np.isfinite(q).all() and np.isclose(q@q,1,atol=2e-5),'Native static quaternion must be unit')
    x,y,z,w=q/np.linalg.norm(q)
    return np.array([[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],
                     [2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],
                     [2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]])


def decode_static_equipment(data):
    require(len(data)>=12+0x88,'Truncated native model header')
    zero,raw_offset,raw_size=struct.unpack_from('<III',data)
    require(zero==0 and 12+raw_offset+raw_size==len(data),'Native sections must exactly cover file')
    model_start=12;raw_start=12+raw_offset
    def check_model(offset,size):
        require(0<=offset and 0<=size and offset+size<=raw_offset,'Native accessor exceeds model section')
        return model_start+offset
    def uint(offset):return struct.unpack_from('<I',data,check_model(offset,4))[0]
    def array(offset,width):
        pointer,count,capacity=struct.unpack_from('<III',data,check_model(offset,12))
        require(count<=capacity,'Native array count exceeds capacity')
        check_model(pointer,count*width)
        return pointer,count
    require(array(0x78,4)[1]==0,'Animated equipment is outside static native audit')
    root=uint(0x48);declared_count=uint(0x4c)
    nodes=[];seen=set();frames={};meshes=[]
    def read_raw(pointer,count,width):
        require(pointer!=0xffffffff and pointer+count*width*4<=raw_size,'Native accessor exceeds raw section')
        value=np.frombuffer(data,'<f4',count*width,raw_start+pointer).reshape(count,width).astype(float)
        require(np.isfinite(value).all(),'Nonfinite native vertex attribute')
        return value
    def walk(offset,parent,ancestors):
        require(offset not in ancestors,'Native child-pointer cycle')
        require(offset not in seen,'Repeated native child pointer')
        seen.add(offset);absolute=check_model(offset,0x70)
        name=data[absolute+0x20:absolute+0x40].split(b'\0')[0].decode('ascii')
        flags=uint(offset+0x6c)
        require(flags in (1,33),'Only native static dummy/trimesh nodes supported')
        pointer,count=array(offset+0x48,4)
        children=list(struct.unpack_from('<'+str(count)+'I',data,check_model(pointer,count*4))) if count else []
        key_pointer,key_count=array(offset+0x54,12);data_pointer,data_count=array(offset+0x60,4)
        control_data=np.frombuffer(data,'<f4',data_count,check_model(data_pointer,data_count*4)).astype(float)
        require(np.isfinite(control_data).all(),'Nonfinite native controller data')
        position=np.zeros(3);rotation=np.eye(3);scale=1.;controllers=[];types=set()
        for i in range(key_count):
            kind,rows,time_index,value_index,columns,_=struct.unpack_from('<ihhhbb',data,check_model(key_pointer+12*i,12))
            require(kind not in types,'Duplicate native static controller');types.add(kind)
            require(rows==1 and 0<=time_index<data_count and 0<=value_index and value_index+columns<=data_count,'Unsupported native static controller layout')
            value=control_data[value_index:value_index+columns]
            controllers.append({'type':kind,'rows':rows,'columns':columns,'value':value.tolist(),'time':float(control_data[time_index])})
            if kind==8:
                require(columns==3,'Native position requires three columns');position=value
            elif kind==20:
                require(columns==4,'Native orientation requires quaternion');rotation=quaternion_matrix(value)
            elif kind==36:
                require(columns==1 and value[0]>0,'Native scale requires positive scalar');scale=float(value[0])
            # Material controllers do not change the static geometry frame.
        local=np.eye(4);local[:3,:3]=scale*rotation;local[:3,3]=position
        frame=frames[parent]@local if parent is not None else local;frames[offset]=frame
        row={'offset':offset,'name':name,'flags':flags,'parentByChildTraversal':parent,
             'storedParentPointer':uint(offset+0x44),'children':children,'controllers':controllers,
             'localFrame':local.tolist(),'worldFrame':frame.tolist()};nodes.append(row)
        if flags==33:
            check_model(offset,0x264)
            count,textures=struct.unpack_from('<HH',data,check_model(offset+0x230,4))
            require(count>0 and textures<=4,'Unexpected native static mesh arrays')
            positions=read_raw(uint(offset+0x22c),count,3)
            normals=read_raw(uint(offset+0x244),count,3)
            uv=[read_raw(uint(offset+0x234+4*i),count,2) for i in range(textures)]
            face_pointer,face_count=array(offset+0x78,32)
            faces=np.ndarray((face_count,3),dtype='<u2',buffer=data,offset=check_model(face_pointer,face_count*32)+26,strides=(32,2)).astype(int)
            require(face_count>0 and faces.max()<count,'Native face index outside vertices')
            world=positions@frame[:3,:3].T+frame[:3,3]
            world_normals=normals@np.linalg.inv(frame[:3,:3])
            require((np.linalg.norm(world_normals,axis=1)>0).all(),'Native normals must be nonzero')
            world_normals/=np.linalg.norm(world_normals,axis=1)[:,None]
            bitmap=data[absolute+0xe8:absolute+0x128].split(b'\0')[0].decode('ascii')
            row.update({'vertices':count,'faces':face_count,'render':uint(offset+0xdc),'bitmap':bitmap})
            meshes.append({'offset':offset,'positions':positions,'normals':normals,'uv':uv,'faces':faces,
                           'worldPositions':world,'worldNormals':world_normals,'render':row['render']})
        for child in children:walk(child,offset,ancestors|{offset})
    walk(root,None,set())
    require(len(nodes)==declared_count,'Native traversed node count differs from declared count')
    counts=Counter(row['name'].lower() for row in nodes)
    rendered=[mesh['worldPositions'] for mesh in meshes if mesh['render']]
    points=np.vstack(rendered) if rendered else None
    bounds=None if points is None else {'minimumModelLocalNwn':points.min(0).tolist(),
         'maximumModelLocalNwn':points.max(0).tolist(),'extentMeters':np.ptp(points,axis=0).tolist(),'renderedVertices':len(points)}
    return {'modelName':data[20:84].split(b'\0')[0].decode('ascii'),'rootOffset':root,
            'declaredNodeCount':declared_count,'nodes':nodes,'meshes':meshes,'bounds':bounds,
            'duplicateNames':sorted(name for name,count in counts.items() if count>1),
            'hierarchyIdentity':'native child offsets','staticOnly':True}
