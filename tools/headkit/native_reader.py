"""Bounded reader for rigid native part trees (NwnMdlNodes.h layout).

Field definitions: https://github.com/niv/nwn-tools/blob/master/_NwnLib/NwnMdlNodes.h
Only static dummy/trimesh nodes and one UV channel are supported. Final exports
require identity local controllers by default. Donor inspection may explicitly
apply bounded rigid local transforms; animated and other layouts still reject.
"""
import struct
import numpy as np
from .common import require


def decode(data, model, *, require_tangents=True, apply_rigid_transforms=False, allow_constant_alpha=False):
    require(type(require_tangents)is bool,'Explicit native tangent requirement required')
    require(type(apply_rigid_transforms)is bool,'Explicit donor transform policy required')
    require(type(allow_constant_alpha)is bool,'Explicit constant-alpha policy required')
    require(len(data)>=12,'Truncated native header')
    zero,raw_offset,raw_size=struct.unpack_from('<III',data)
    require(zero==0 and 12+raw_offset+raw_size==len(data),'Invalid native sections')
    def block(offset,size):
        require(offset>=0 and offset+size<=raw_offset,'Native model pointer escapes section')
        return 12+offset
    def array(node,field,width):
        offset,count,capacity=struct.unpack_from('<III',data,node+field)
        require(count==capacity,'Unpacked native array')
        block(offset,count*width); return offset,count
    token=model.encode('ascii')+b'\0'; candidates=[]; start=0
    while True:
        found=data.find(token,start,12+raw_offset)
        if found<0: break
        start=found+1; node=found-32
        if node>=12 and node+0x70<=12+raw_offset and struct.unpack_from('<I',data,node+0x6c)[0]==1:
            candidates.append(node-12)
    require(len(candidates)==1,'Unique named native dummy root required')
    visited=set(); meshes=[]
    def visit(offset,parent_world):
        require(offset not in visited and len(visited)<32,'Native node cycle or excessive tree')
        visited.add(offset); node=block(offset,0x70)
        flags=struct.unpack_from('<I',data,node+0x6c)[0]
        require(flags in (1,33),'Rigid dummy/trimesh nodes required')
        name=data[node+32:node+64].split(b'\0')[0].decode('ascii')
        # EE binaries do not retain a usable parent back-pointer in this legacy
        # field. Ownership follows the bounded child tree, never that value.
        keys,count=array(node,0x54,12); values,nvalues=array(node,0x60,4)
        floats=np.frombuffer(data,'<f4',nvalues,12+values)
        controls={} if apply_rigid_transforms else None
        alpha=1.;alpha_seen=False
        for index in range(count):
            kind,rows,key_start,value_start,columns,pad=struct.unpack_from('<ihhhbb',data,12+keys+12*index)
            if kind==128 and allow_constant_alpha:
                require(flags==33 and rows==columns==1 and not alpha_seen
                        and 0<=value_start<nvalues,'Invalid static mesh alpha controller')
                alpha=float(floats[value_start]);alpha_seen=True
                require(np.isfinite(alpha) and 0<=alpha<=1,'Native alpha outside [0,1]')
                continue
            require(rows==1 and kind in (8,20,36),'Unsupported animated/native local controller')
            width={8:3,20:4,36:1}[kind]
            require(columns==width and 0<=value_start and value_start+width<=nvalues,'Invalid static controller')
            expected={8:[0,0,0],20:[0,0,0,1],36:[1]}[kind]
            value=floats[value_start:value_start+width]
            if apply_rigid_transforms:
                require(kind not in controls and np.isfinite(value).all(),'Invalid rigid native controller')
                controls[kind]=value.astype(float)
            else:require(np.allclose(value,expected,atol=1e-7),'Nonidentity native local controller rejected')
        world=None
        if apply_rigid_transforms:
            position=controls.get(8,(0.,0.,0.));q=np.asarray(controls.get(20,(0.,0.,0.,1.)))
            scale=float(controls.get(36,(1.,))[0]);length=float(np.linalg.norm(q))
            require(abs(length-1)<1e-6 and scale>0,'Unit rigid quaternion and positive scale required')
            x,y,z,w=q/length
            rotation=np.array([[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],
                               [2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],
                               [2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]])
            local=np.eye(4);local[:3,:3]=rotation*scale;local[:3,3]=position
            world=parent_world@local
        if flags==33:
            block(offset,0x264); faces,nfaces=array(node,0x78,32)
            vertices,uvcount=struct.unpack_from('<HH',data,node+0x230)
            require(vertices>0 and nfaces>0 and uvcount==1,'Packed one-UV mesh required')
            attributes={}
            for key,field,width in [('position',0x22c,3),('uv',0x234,2),('normal',0x244,3),('tangent',0x258,3),('sign',0x260,1)]:
                pointer=struct.unpack_from('<I',data,node+field)[0]
                if pointer==0xffffffff and key in ('tangent','sign')and not require_tangents:continue
                require(pointer!=0xffffffff and pointer+vertices*width*4<=raw_size,'Missing/outside native attribute: '+key)
                attributes[key]=np.frombuffer(data,'<f4',vertices*width,12+raw_offset+pointer).reshape(-1,width).copy()
                require(np.isfinite(attributes[key]).all(),'Nonfinite native attribute')
            indices=np.ndarray((nfaces,3),dtype='<u2',buffer=data,offset=12+faces+26,strides=(32,2)).copy()
            require(indices.max()<vertices,'Native index escapes vertex array')
            if require_tangents:require(np.isin(attributes['sign'],[-1,1]).all(),'Invalid tangent sign')
            textures=[data[node+0xe8+64*i:node+0xe8+64*(i+1)].split(b'\0')[0].decode('ascii') for i in range(4)]
            if apply_rigid_transforms:
                attributes['position']=attributes['position']@world[:3,:3].T+world[:3,3]
                normal_matrix=np.linalg.inv(world[:3,:3])
                for key in ('normal','tangent'):
                    if key not in attributes:continue
                    value=attributes[key]@normal_matrix
                    lengths=np.linalg.norm(value,axis=1)
                    require((lengths>1e-12).all(),'Undefined transformed native direction')
                    attributes[key]=value/lengths[:,None]
            meshes.append({'name':name,'textures':textures,'faces':indices,**attributes,
                           **({'alpha':alpha} if allow_constant_alpha else {})})
        children,nchildren=array(node,0x48,4)
        for child in struct.unpack_from('<'+'I'*nchildren,data,12+children): visit(child,world)
    visit(candidates[0],np.eye(4) if apply_rigid_transforms else None)
    require(meshes,'No native meshes'); return meshes
