"""Bounded reader for rigid native part trees (NwnMdlNodes.h layout).

Field definitions: https://github.com/niv/nwn-tools/blob/master/_NwnLib/NwnMdlNodes.h
Only static dummy/trimesh nodes, one UV channel and identity local controllers
are supported. This reader rejects other layouts rather than guessing.
"""
import struct
import numpy as np
from head_workflow import require


def decode(data, model):
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
    def visit(offset,parent):
        require(offset not in visited and len(visited)<32,'Native node cycle or excessive tree')
        visited.add(offset); node=block(offset,0x70)
        flags=struct.unpack_from('<I',data,node+0x6c)[0]
        require(flags in (1,33),'Rigid dummy/trimesh nodes required')
        name=data[node+32:node+64].split(b'\0')[0].decode('ascii')
        # EE binaries do not retain a usable parent back-pointer in this legacy
        # field. Ownership follows the bounded child tree, never that value.
        keys,count=array(node,0x54,12); values,nvalues=array(node,0x60,4)
        floats=np.frombuffer(data,'<f4',nvalues,12+values)
        for index in range(count):
            kind,rows,key_start,value_start,columns,pad=struct.unpack_from('<ihhhbb',data,12+keys+12*index)
            require(rows==1 and kind in (8,20,36),'Unsupported animated/native local controller')
            width={8:3,20:4,36:1}[kind]
            require(columns==width and 0<=value_start and value_start+width<=nvalues,'Invalid static controller')
            expected={8:[0,0,0],20:[0,0,0,1],36:[1]}[kind]
            value=floats[value_start:value_start+width]
            require(np.allclose(value,expected,atol=1e-7),'Nonidentity native local controller rejected')
        if flags==33:
            block(offset,0x264); faces,nfaces=array(node,0x78,32)
            vertices,uvcount=struct.unpack_from('<HH',data,node+0x230)
            require(vertices>0 and nfaces>0 and uvcount==1,'Packed one-UV mesh required')
            attributes={}
            for key,field,width in [('position',0x22c,3),('uv',0x234,2),('normal',0x244,3),('tangent',0x258,3),('sign',0x260,1)]:
                pointer=struct.unpack_from('<I',data,node+field)[0]
                require(pointer!=0xffffffff and pointer+vertices*width*4<=raw_size,'Missing/outside native attribute: '+key)
                attributes[key]=np.frombuffer(data,'<f4',vertices*width,12+raw_offset+pointer).reshape(-1,width).copy()
                require(np.isfinite(attributes[key]).all(),'Nonfinite native attribute')
            indices=np.ndarray((nfaces,3),dtype='<u2',buffer=data,offset=12+faces+26,strides=(32,2)).copy()
            require(indices.max()<vertices,'Native index escapes vertex array')
            require(np.isin(attributes['sign'],[-1,1]).all(),'Invalid tangent sign')
            textures=[data[node+0xe8+64*i:node+0xe8+64*(i+1)].split(b'\0')[0].decode('ascii') for i in range(4)]
            meshes.append({'name':name,'textures':textures,'faces':indices,**attributes})
        children,nchildren=array(node,0x48,4)
        for child in struct.unpack_from('<'+'I'*nchildren,data,12+children): visit(child,offset)
    visit(candidates[0],0)
    require(meshes,'No native meshes'); return meshes
